import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]

class SsoPreparation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(self.directory / 'ansible'),
                        ANSIBLE_REMOTE_TEMP=str(self.directory / 'remote'))

    def run_play(self, inputs=None, check=False, success=True):
        args = ['ansible-playbook', str(ROOT / PLAY), '-e', json.dumps(inputs or {})]
        if check:
            args.append('--check')
        result = subprocess.run(args, env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def test_default_and_check_do_not_read_inputs_or_write_output(self):
        self.run_play()
        self.run_play({FLAG: True, OUTPUT: str(self.directory / 'check')}, check=True)
        self.assertFalse((self.directory / 'check').exists())

    def test_wrong_artifact_and_existing_output_refused(self):
        archive = self.directory / 'bad.tar.gz'
        archive.write_bytes(b'not the trusted archive')
        output = self.directory / 'image'
        self.run_play({'nextcloud_sso_prepare': True, 'nextcloud_sso_archive': str(archive),
                       'nextcloud_sso_output': str(output)}, success=False)
        self.assertFalse(output.exists())

    @unittest.skipUnless(os.environ.get('NEXTCLOUD_OIDC_ARCHIVE'), 'verified public artifact fixture not supplied')
    def test_trusted_context_and_repeat_refusal(self):
        output = self.directory / 'image'
        inputs = {FLAG: True, OUTPUT: str(output),
                  'nextcloud_sso_archive': os.environ['NEXTCLOUD_OIDC_ARCHIVE'],
                  'nextcloud_sso_render_values':True,'nextcloud_sso_origin':'https://files.example.test',
                  'nextcloud_sso_image':'ghcr.io/perkforge/nextcloud-sso:35.0.2-oidc8.13.0@sha256:'+'a'*64}
        self.run_play(inputs)
        import hashlib
        self.assertEqual(hashlib.sha256((output / 'user_oidc.tar.gz').read_bytes()).hexdigest(),
                         yaml.safe_load((ROOT / 'sso/artifact.yaml').read_text())['sha256'])
        candidate=yaml.safe_load((output/'candidate-app-values.yaml').read_text())
        self.assertEqual(candidate['nextcloud']['configs']['oidc-origin.config.php'].strip(),
                         '<?php\n$CONFIG = [\'overwrite.cli.url\' => "https://files.example.test"];')
        self.assertEqual(candidate['nextcloud']['extraVolumes'][-1]['secret']['secretName'],'nextcloud-oidc')
        self.assertEqual(candidate['nextcloud']['extraVolumeMounts'][-1]['mountPath'],'/run/nextcloud-oidc')
        self.assertTrue(candidate['nextcloud']['extraVolumeMounts'][-1]['readOnly'])
        if os.environ.get('NEXTCLOUD_CHART'):
            rendered=subprocess.check_output([os.environ.get('HELM','helm'),'template','nextcloud',os.environ['NEXTCLOUD_CHART'],
                       '-n','tenant-home-nextcloud','-f',str(output/'candidate-app-values.yaml'),
                       '-f',str(ROOT/'gitops/clusters/local/app-values.yaml')],text=True)
            deployment=next(x for x in yaml.safe_load_all(rendered) if x and x['kind']=='Deployment')
            pod=deployment['spec']['template']['spec']
            for container in pod['containers']+pod['initContainers']:
                self.assertEqual(container['image'],inputs['nextcloud_sso_image'])
        before = (output / 'user_oidc.tar.gz').read_bytes()
        self.run_play(inputs, success=False)
        self.assertEqual(before, (output / 'user_oidc.tar.gz').read_bytes())

    def test_no_selected_delivery(self):
        data = yaml.safe_load((ROOT / 'sso/artifact.yaml').read_text())
        self.assertEqual(data['version'], '8.13.0')
        self.assertLessEqual(data['nextcloud_min'], 35)
        self.assertGreaterEqual(data['nextcloud_max'], 35)
        self.assertEqual(len(data['sha256']), 64)
        recipe = (ROOT / 'sso/Dockerfile').read_text()
        self.assertIn(data['sha256'], recipe)
        self.assertNotIn('curl ', recipe)
        self.assertNotIn('app:enable', recipe)
        self.assertNotIn('user_oidc', (ROOT / 'gitops/base/app-values.yaml').read_text())

PLAY = 'sso/prepare.yaml'
FLAG = 'nextcloud_sso_prepare'
OUTPUT = 'nextcloud_sso_output'
