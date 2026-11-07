"""Actual Ansible against a synthetic kubectl/occ contract; never a live cluster."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SUB = '11111111-1111-1111-1111-111111111111'
UID = hashlib.sha256(('1_0_' + SUB).encode()).hexdigest()
IMAGE = 'ghcr.io/perkforge/nextcloud-sso:35.0.2-oidc8.13.0@sha256:' + 'a'*64

class NativeLifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        (self.d/'kubectl').symlink_to(ROOT/'tests/fixtures/oidc_kubectl.py')
        self.state = self.d/'state.json'
        self.s = {'cluster':'cluster-id','installed':False,'app_enabled':False,'providers':[],
                  'config':{'system':{},'apps':{}},'writes':[],'calls':[], 'ca':'public-fixture-ca',
                  'ca_hash':'b'*64,'secret_hash':'c'*64,'tokens':[{'id':3},{'id':4}],
                  'users':{'recovery':{'user_id':'recovery','backend':'Database','enabled':True,'groups':['admin']},
                           UID:{'user_id':UID,'backend':'user_oidc','enabled':True,'groups':['admin']}},
                  'pod':{'metadata':{'uid':'pod-id','labels':{'app.kubernetes.io/name':'nextcloud','app.kubernetes.io/instance':'nextcloud'}},
                         'spec':{'automountServiceAccountToken':False,'containers':[{'name':'nextcloud','image':IMAGE,'securityContext':{'runAsUser':33}}]}}}
        self.save()
        self.env = dict(os.environ, PATH=str(self.d)+':'+os.environ['PATH'], NC_FIXTURE_STATE=str(self.state),
                        ANSIBLE_LOCAL_TEMP=str(self.d/'local'), ANSIBLE_REMOTE_TEMP=str(self.d/'remote'))
        self.v = {'nextcloud_native_run':True,'nextcloud_recovery_verified':True,
                  'nextcloud_kubeconfig':'/fixture/kubeconfig','nextcloud_context':'fixture',
                  'nextcloud_cluster_uid':'cluster-id','nextcloud_pod':'nextcloud-fixture','nextcloud_pod_uid':'pod-id',
                  'nextcloud_image':IMAGE,'nextcloud_sso_issuer':'https://identity.example.test/auth/realms/perkforge',
                  'nextcloud_sso_origin':'https://files.example.test','nextcloud_recovery_user':'recovery','nextcloud_ca_sha256':'b'*64,'nextcloud_secret_sha256':'c'*64,
                  'nextcloud_private_http_approval':'oidc-private-issuer-egress-v1', 'nextcloud_subject':SUB}
        from test_sso_browser_callback import LoginFixture
        self.login = LoginFixture(self.d)
        self.addCleanup(self.login.close)
        self.v.update(nextcloud_sso_origin=self.login.origin, nextcloud_ca_file=str(self.login.ca))
    def save(self):self.state.write_text(json.dumps(self.s))
    def run_play(self, op='inspect', extra=None, check=False, success=True):
        v={**self.v,'nextcloud_native_operation':op,'nextcloud_native_approval':'nextcloud-native-'+op+'-v1',**(extra or {})}
        p=subprocess.run(['ansible-playbook',str(ROOT/'sso/reconcile.yaml'),'-e',json.dumps(v)]+(['--check'] if check else []),
                         env=self.env,capture_output=True,text=True,timeout=90)
        self.s=json.loads(self.state.read_text())
        self.assertEqual(p.returncode==0,success,p.stdout+p.stderr)
        return p
    def prepared(self):
        self.run_play('prepare'); self.run_play('apply')
        self.v['nextcloud_provider_id']=1
    def test_default_check_and_missing_approval_never_contact(self):
        self.run_play(extra={'nextcloud_native_run':False})
        self.run_play(check=True)
        self.run_play(extra={'nextcloud_native_approval':'UNAPPROVED'},success=False)
        self.assertEqual(self.s['calls'],[])
    def test_prepare_apply_repeat_activate_rollback_preserve_recovery(self):
        recovery=copy.deepcopy(self.s['users']['recovery'])
        self.prepared()
        self.assertIn('changed=0',self.run_play('prepare').stdout)
        self.assertIn('changed=0',self.run_play('apply').stdout)
        self.run_play('activate',extra={'nextcloud_client_ready':True,'nextcloud_provisioning_approval':'own-client-role-jit-v1'})
        self.assertEqual(self.s['providers'][0]['settings']['groupWhitelistRegex'],'/^(household|owner)$/')
        self.run_play('rollback',extra={'nextcloud_sessions_revoked':True})
        self.assertEqual(self.s['providers'][0]['settings']['groupWhitelistRegex'],'/^(?!)$/')
        self.assertEqual(self.s['users']['recovery'],recovery)
    def test_wrong_target_provider_and_discovery_refuse(self):
        self.run_play('prepare',extra={'nextcloud_cluster_uid':'wrong'},success=False)
        self.assertEqual(self.s['writes'],[])
        self.prepared(); before=len(self.s['writes'])
        self.run_play('activate',extra={'nextcloud_provider_id':2},success=False)
        self.assertEqual(len(self.s['writes']),before)
        self.s['bad_credential']=True;self.save()
        self.run_play('inspect',success=False)
        self.assertEqual(len(self.s['writes']),before)
        self.s['bad_credential']=False
        self.s['bad_discovery']=True;self.save()
        self.run_play('activate',extra={'nextcloud_client_ready':True,'nextcloud_provisioning_approval':'own-client-role-jit-v1'},success=False)
        self.assertEqual(len(self.s['writes']),before)
    def test_browser_callback_mismatch_blocks_activation(self):
        self.prepared()
        self.login.path = '/apps/user_oidc/code'
        before = len(self.s['writes'])
        self.run_play('activate', extra={'nextcloud_client_ready':True,
                      'nextcloud_provisioning_approval':'own-client-role-jit-v1'}, success=False)
        self.assertEqual(len(self.s['writes']), before)
        self.assertEqual(self.s['providers'][0]['settings']['groupWhitelistRegex'], '/^(?!)$/')
        self.run_play('activate', extra={'nextcloud_client_ready':True,
                      'nextcloud_provisioning_approval':'own-client-role-jit-v1',
                      'nextcloud_sso_callback_path':'/apps/user_oidc/code'})

    def test_interrupted_copy_and_foreign_config_refuse(self):
        self.s['interrupted_copy']=True;self.save()
        self.run_play('prepare',success=False)
        self.assertFalse(self.s['installed'])
        self.s['interrupted_copy']=False;self.s['config']['system']['user_oidc']={'soft_auto_provision':True};self.save()
        self.run_play('prepare',success=False)
        self.assertFalse(self.s['app_enabled'])
    def test_removal_disables_before_revocation_and_resumes(self):
        self.prepared(); recovery=copy.deepcopy(self.s['users']['recovery'])
        self.s['fail_token_delete']=True;self.save()
        self.run_play('remove-subject',success=False)
        self.assertFalse(self.s['users'][UID]['enabled'])
        self.assertNotIn('admin',self.s['users'][UID]['groups'])
        self.s['fail_token_delete']=False;self.save()
        self.run_play('remove-subject')
        self.assertEqual(self.s['tokens'],[])
        self.assertIn('changed=0',self.run_play('remove-subject').stdout)
        self.assertEqual(self.s['users']['recovery'],recovery)
        self.s['users'][UID]['backend']='Database';self.save();before=len(self.s['writes'])
        self.run_play('remove-subject',success=False)
        self.assertEqual(len(self.s['writes']),before)

    def test_native_admin_requires_exact_owned_client_and_direct_owner_role(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import ssl
        import threading
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                        '-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost',
                        '-keyout',str(self.d/'key'),'-out',str(self.d/'ca')],check=True,capture_output=True)
        values={'clientId':'nextcloud','role':'household'}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                data=({'id':'nc-id','clientId':values['clientId'],'attributes':{'perkforge-managed':'true','perkforge-purpose':'nextcloud-sso-review-v1'},'fullScopeAllowed':False}
                      if '/users/' not in self.path else
                      [{'name':values['role'],'clientRole':True,'composite':False,'containerId':'nc-id'}])
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(data).encode())
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(self.d/'ca',self.d/'key')
        server.socket=context.wrap_socket(server.socket,server_side=True)
        threading.Thread(target=server.serve_forever,daemon=True).start();self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        (self.d/'token').write_text('fixture-owner-token');(self.d/'token').chmod(0o600)
        self.v.update(nextcloud_sso_issuer='https://localhost:'+str(server.server_port)+'/auth/realms/perkforge',
                      nextcloud_client_uuid='nc-id',nextcloud_ca_file=str(self.d/'ca'),nextcloud_keycloak_token_file=str(self.d/'token'))
        self.login.issuer = self.v['nextcloud_sso_issuer']
        with (self.d/'ca').open('ab') as bundle:
            bundle.write(self.login.ca.read_bytes())
        self.prepared();self.s['users'][UID]['groups']=[];self.save();before=len(self.s['writes'])
        self.run_play('grant-admin',success=False);self.assertEqual(len(self.s['writes']),before)
        values['role']='owner';values['clientId']='foreign'
        self.run_play('grant-admin',success=False);self.assertEqual(len(self.s['writes']),before)
        values['clientId']='nextcloud';self.run_play('grant-admin');self.assertIn('admin',self.s['users'][UID]['groups'])
        self.assertIn('changed=0',self.run_play('grant-admin').stdout)
        self.run_play('remove-subject')
        values['role']='household';self.run_play('resume-subject')
        self.assertTrue(self.s['users'][UID]['enabled'])
        self.assertNotIn('admin',self.s['users'][UID]['groups'])
        self.run_play('grant-admin',success=False)

    def test_name_mapping_upgrade_is_explicit_and_preserves_identity(self):
        self.prepared()
        self.s['providers'][0]['settings']['mappingDisplayName']='';self.save()
        before=copy.deepcopy(self.s['providers'][0]);users=copy.deepcopy(self.s['users']);n=len(self.s['writes'])
        self.run_play('inspect',success=False)
        self.assertEqual(len(self.s['writes']),n)
        self.run_play('display-name',check=True)
        self.assertEqual(self.s['providers'][0],before)
        self.run_play('display-name')
        expected=copy.deepcopy(before);expected['settings']['mappingDisplayName']='name'
        self.assertEqual(self.s['providers'][0],expected)
        self.assertEqual(self.s['users'],users)
        self.assertEqual(len(self.s['writes']),n+1)
        self.assertIn('changed=0',self.run_play('display-name').stdout)
        self.run_play('inspect')
        self.s['providers'][0]['settings']['mappingDisplayName']='email';self.save();n=len(self.s['writes'])
        self.run_play('display-name',success=False)
        self.assertEqual(len(self.s['writes']),n)
