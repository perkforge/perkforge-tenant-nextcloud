"""Execute the real recovery assertions offline, without kubectl or user changes."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


class RecoveryGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        tasks = yaml.safe_load((ROOT/'sso/reconcile.yaml').read_text())[0]['tasks'][1]['block']
        index = next(i for i,t in enumerate(tasks) if t.get('register') == 'nc_recovery')
        self.before_guard = tasks[index+1]
        self.after_guard = yaml.safe_load((ROOT/'sso/native-subject.yaml').read_text())[-1]
        self.record = {'user_id':'recovery','backend':'Database','enabled':True,'groups':['admin','other'],
                       'display_name':'Recovery','last_seen':'2026-01-01','storage':{'used':100}}

    def run_guards(self, before=None, after=None, success=True):
        play = [{'hosts':'localhost','gather_facts':False,'connection':'local',
                 'vars':{'nextcloud_recovery_user':'recovery',
                         'nc_recovery':{'stdout':json.dumps(self.record if before is None else before)},
                         'nc_recovery_after':{'stdout':json.dumps(self.record if after is None else after)}},
                 'tasks':[self.before_guard,self.after_guard]}]
        source = self.path/'guard.yaml'
        source.write_text(yaml.safe_dump(play))
        env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(self.path/'local'), ANSIBLE_REMOTE_TEMP=str(self.path/'remote'))
        result = subprocess.run(['ansible-playbook',str(source)],env=env,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)

    def test_stable_security_state_passes(self):
        self.run_guards()

    def test_metadata_and_group_order_changes_do_not_fail(self):
        after = copy.deepcopy(self.record)
        after.update(display_name='Updated recovery label',last_seen='2026-11-07',storage={'used':101},groups=['other','admin'])
        self.run_guards(after=after)

    def test_security_changes_are_rejected_before_and_after(self):
        for patch in ({'user_id':'someone-else'}, {'backend':'user_oidc'}, {'enabled':False}, {'groups':['other']}):
            for stage in ('before','after'):
                with self.subTest(patch=patch,stage=stage):
                    self.run_guards(**{stage:self.record | patch},success=False)

    def test_missing_security_fields_are_rejected_before_and_after(self):
        for field in ('user_id','backend','enabled','groups'):
            record = self.record.copy()
            del record[field]
            for stage in ('before','after'):
                with self.subTest(field=field,stage=stage):
                    self.run_guards(**{stage:record},success=False)
