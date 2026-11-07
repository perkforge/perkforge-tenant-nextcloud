"""Offline HTTPS provider redirect fixtures; no cluster or real identity provider."""
import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('callback', ROOT/'sso/verify-browser-callback.py')
callback = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(callback)


class LoginFixture:
    def __init__(self, directory):
        self.ca = Path(directory)/'login-ca.pem'
        key = Path(directory)/'login-key.pem'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                        '-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost',
                        '-keyout',str(key),'-out',str(self.ca)],check=True,capture_output=True)
        self.issuer = 'https://identity.example.test/auth/realms/perkforge'
        self.path = '/index.php/apps/user_oidc/code'
        self.status = 302
        self.requests = []
        self.extra_location = False
        fixture = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                fixture.requests.append(self.path)
                self.send_response(fixture.status)
                self.send_header('Location', fixture.location())
                if fixture.extra_location:
                    self.send_header('Location', fixture.location())
                self.send_header('Set-Cookie', 'fixture-sensitive-cookie')
                self.end_headers()
        self.server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.ca,key)
        self.server.socket = context.wrap_socket(self.server.socket,server_side=True)
        self.origin = 'https://localhost:' + str(self.server.server_port)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
    def location(self):
        return self.issuer + '/protocol/openid-connect/auth?' + urlencode({
            'redirect_uri':self.origin+self.path,'client_id':'nextcloud','response_type':'code',
            'code_challenge_method':'S256','code_challenge':'a'*43,
            'state':'fixture-sensitive-state','nonce':'fixture-sensitive-nonce'})
    def close(self):
        self.server.shutdown()
        self.server.server_close()


class BrowserCallback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.fixture = LoginFixture(cls.tmp.name)
    @classmethod
    def tearDownClass(cls):
        cls.fixture.close()
        cls.tmp.cleanup()
    def setUp(self):
        self.f = self.fixture
        self.f.path = '/index.php/apps/user_oidc/code'
        self.f.status = 302
        self.f.requests.clear()
        self.f.extra_location = False
    def verify(self, **changes):
        args = dict(origin=self.f.origin,issuer=self.f.issuer,callback_path=self.f.path,provider_id=7,ca_file=str(self.f.ca))
        callback.verify(**(args | changes))
    def test_both_routing_modes_use_real_redirect_not_cli(self):
        for path in ('/apps/user_oidc/code','/index.php/apps/user_oidc/code'):
            self.f.path = path
            self.verify()
        self.assertEqual(self.f.requests, ['/index.php/apps/user_oidc/login/7']*2)
    def test_callback_mismatch_fails(self):
        self.f.path = '/apps/user_oidc/code'
        with self.assertRaises(ValueError): self.verify(callback_path='/index.php/apps/user_oidc/code')
    def test_wrong_status_or_multiple_headers_fail_without_following(self):
        for status in (200,301,303,307,400,500):
            self.f.status = status
            with self.assertRaises(ValueError): self.verify()
        self.f.status = 302
        self.f.extra_location = True
        with self.assertRaises(ValueError): self.verify()
        self.assertEqual(len(self.f.requests),7)
    def test_invalid_tls_is_rejected(self):
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.verify(origin=self.f.origin.replace('localhost','127.0.0.1'))
        with self.assertRaises(ssl.SSLCertVerificationError): self.verify(ca_file=ssl.get_default_verify_paths().cafile)
        self.assertEqual(self.f.requests,[])
    def test_malformed_duplicate_or_foreign_redirects_fail(self):
        good = self.f.location()
        bad = [good+'&redirect_uri=foreign',good+'&client_id=nextcloud',
               good.replace('client_id=nextcloud','client_id=foreign'),
               good.replace('identity.example.test','evil.example.test'),
               good.replace('/auth?', '/token?'), good+'#fragment',
               good.replace('S256','plain'),good.replace('localhost','evil.example.test'),
               good.replace('redirect_uri=', 'redirect_uri[]='),
               good.replace('redirect_uri=', 'redirect_uri=%GG'),
               good.replace('response_type=code','response_type=token'),
               good.replace('code_challenge='+'a'*43,'code_challenge=short'),
               good+'&broken',good+'\n', good+'&%63lient_id=nextcloud']
        for location in bad:
            with self.subTest(location=location), self.assertRaises(ValueError):
                callback.verify_location(location,self.f.issuer,self.f.origin+self.f.path)
    def test_invalid_inputs_do_not_contact_server(self):
        for changes in ({'origin':self.f.origin+'/extra'}, {'provider_id':0}, {'provider_id':'1/2'},
                        {'callback_path':'/other'}, {'ca_file':None}, {'issuer':'http://identity.example.test/realms/perkforge'}):
            with self.assertRaises(ValueError): self.verify(**changes)
        self.assertEqual(self.f.requests,[])
    def test_default_disabled_and_errors_redacted(self):
        script = str(ROOT/'sso/verify-browser-callback.py')
        p = subprocess.run([sys.executable,script],capture_output=True,text=True)
        self.assertEqual(p.returncode,0)
        self.f.status = 500
        p = subprocess.run([sys.executable,script,'--run','--origin',self.f.origin,'--issuer',self.f.issuer,
                            '--callback-path',self.f.path,'--provider-id','7','--ca-file',str(self.f.ca)],capture_output=True,text=True)
        self.assertEqual(p.returncode,1)
        self.assertNotIn('fixture-sensitive',p.stdout+p.stderr)
        self.assertNotIn('https://',p.stdout+p.stderr)
