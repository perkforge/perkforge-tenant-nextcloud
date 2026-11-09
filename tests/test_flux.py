"""Offline selection and rendered workload contracts; never contacts Kubernetes."""
import os
import json
from pathlib import Path
import subprocess
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return yaml.safe_load((ROOT / path).read_text())


class FluxContract(unittest.TestCase):
    def test_enabled_scoped_selection(self):
        built = subprocess.check_output(['kubectl', 'kustomize', str(ROOT / 'gitops/clusters/local')], text=True)
        objects = list(yaml.safe_load_all(built))
        self.assertEqual({x['kind'] for x in objects}, {'ConfigMap', 'HelmRelease'})
        releases = [x for x in objects if x['kind'] == 'HelmRelease']
        self.assertEqual(len(releases), 2)
        for obj in objects:
            self.assertEqual(obj['metadata']['namespace'], 'tenant-home-nextcloud-config')
        for obj in releases:
            spec = obj['spec']
            self.assertFalse(spec['suspend'])
            self.assertFalse(spec['install']['createNamespace'])
            for action in ['install', 'upgrade']:
                self.assertFalse(spec[action].get('disableWait', False))
            self.assertEqual(spec['serviceAccountName'], 'nextcloud-deployer')
            self.assertEqual(spec['storageNamespace'], 'tenant-home-nextcloud-release')
            self.assertEqual(spec['targetNamespace'], 'tenant-home-nextcloud')
            self.assertNotIn('kubeConfig', spec)
            for ref in spec['valuesFrom']:
                self.assertIn(ref['name'], {x['metadata']['name'] for x in objects})
        app = next(x for x in releases if x['metadata']['name'] == 'nextcloud')['spec']
        self.assertEqual(app['dependsOn'], [{'name': 'nextcloud-data'}])
        self.assertEqual(app['chart']['spec']['version'], '9.4.1')
        self.assertNotIn('cks-worker', built)
        self.assertNotIn('local-path', built)

    def test_render_pinned_chart(self):
        chart = os.environ.get('NEXTCLOUD_CHART')
        self.assertTrue(chart, 'Set NEXTCLOUD_CHART to the verified upstream 9.4.1 chart directory/archive')
        helm = os.environ.get('HELM', 'helm')
        def render(chart, defaults, cluster, extra=()):
            return list(yaml.safe_load_all(subprocess.check_output([
                helm, 'template', 'nextcloud', chart, '--namespace', 'tenant-home-nextcloud',
                '-f', str(ROOT / defaults), '-f', str(ROOT / cluster), *extra], text=True)))
        app = render(chart, 'gitops/base/app-values.yaml', 'gitops/clusters/local/app-values.yaml')
        self.assertFalse(any(x['kind'] in {'Namespace', 'Role', 'RoleBinding', 'Secret'} for x in app))
        deploy = next(x for x in app if x['kind'] == 'Deployment')
        pod = deploy['spec']['template']['spec']
        self.assertEqual(deploy['spec']['strategy']['type'], 'Recreate')
        self.assertEqual(pod['nodeSelector'], {'storage.perkforge.io/worker': 'true'})
        self.assertTrue(any(x.get('persistentVolumeClaim', {}).get('claimName') == 'nextcloud-files' for x in pod['volumes']))
        for container in pod['containers'] + pod['initContainers']:
            self.assertFalse(container['securityContext']['allowPrivilegeEscalation'])
            self.assertEqual(container['securityContext']['runAsUser'], 33)
        self.assertFalse(any(x['kind'] == 'CronJob' for x in app))
        self.assertEqual([c['name'] for c in pod['containers']], ['nextcloud', 'nextcloud-cron'])
        prepare = next(x for x in pod['initContainers'] if x['name'] == 'prepare-persistent-directories')
        self.assertEqual(prepare['volumeMounts'], [{'name': 'nextcloud-main', 'mountPath': '/bootstrap'}])
        self.assertIn('stat -c %u', prepare['command'][-1])
        disabled_app = render(chart, 'gitops/base/app-values.yaml', 'gitops/clusters/local/app-values.yaml',
            ['--set', 'cronjob.enabled=false'])
        self.assertFalse(any(x['kind'] == 'CronJob' for x in disabled_app))
        disabled_deploy = next(x for x in disabled_app if x['kind'] == 'Deployment')
        self.assertEqual([c['name'] for c in disabled_deploy['spec']['template']['spec']['containers']], ['nextcloud'])
        enabled_pod = pod
        self.assertEqual([c['name'] for c in enabled_pod['containers']], ['nextcloud', 'nextcloud-cron'])
        web, cron = enabled_pod['containers']
        self.assertEqual(cron['image'], web['image'])
        self.assertEqual(cron['volumeMounts'], [m for m in web['volumeMounts'] if m['name'] != 'nextcloud-hooks'])
        self.assertEqual(cron['securityContext']['runAsUser'], 33)
        self.assertFalse(cron['securityContext']['allowPrivilegeEscalation'])
        self.assertEqual(cron['securityContext']['capabilities']['drop'], ['ALL'])
        self.assertEqual(cron['resources']['limits']['memory'], '128Mi')
        command = cron['command'][-1]
        self.assertNotIn('/cron.sh', command)
        self.assertIn('timeout --signal=TERM --kill-after=10s 900s', command)
        self.assertIn('sleep 300', command)
        self.assertNotIn('cron.php &', command)
        for field in ['installed', 'maintenance', 'needsDbUpgrade']:
            self.assertIn(field, command)
        self.assertNotIn('nodeName', pod)
        preferred = pod['affinity']['nodeAffinity']['preferredDuringSchedulingIgnoredDuringExecution']
        self.assertEqual(preferred[0]['preference']['matchExpressions'][0]['values'], ['worker-2'])
        for c in enabled_pod['containers']:
            self.assertIn('@sha256:', c['image'])
            env = {e['name']: e for e in c['env']}
            self.assertEqual(env['PGSSLMODE']['value'], 'verify-full')
            self.assertEqual(env['PGSSLROOTCERT']['value'], '/etc/nextcloud-postgres-ca/ca.crt')
            self.assertIn({'name': 'postgres-ca', 'mountPath': '/etc/nextcloud-postgres-ca', 'readOnly': True}, c['volumeMounts'])
        self.assertTrue(any(v.get('configMap', {}).get('name') == 'nextcloud-db-ca' for v in enabled_pod['volumes']))
        tls = load('gitops/base/app-values.yaml')['nextcloud']['configs']['postgres-tls.config.php']
        self.assertIn("'pgsql_ssl'", tls)
        self.assertIn("'mode' => 'verify-full'", tls)
        self.assertEqual(prepare['image'], pod['containers'][0]['image'])
        published = json.loads((ROOT / 'sso/published-image.json').read_text())
        expected_image = published['tag'] + '@' + published['registry_digest']
        self.assertEqual({c['image'] for c in pod['containers'] + pod['initContainers']}, {expected_image})
        self.assertEqual(pod['imagePullSecrets'], [{'name': 'nextcloud-registry-existing'}])
        self.assertEqual(published['visibility'], 'private')
        self.assertFalse(published['rebuilt'])
        volumes = {v['name']: v for v in pod['volumes']}
        self.assertEqual(volumes['oidc-ca'], {'name': 'oidc-ca', 'configMap': {'name': 'nextcloud-oidc-ca'}})
        self.assertEqual(volumes['oidc-secret'], {'name': 'oidc-secret', 'secret': {
            'secretName': 'nextcloud-oidc', 'defaultMode': 288,
            'items': [{'key': 'client-secret', 'path': 'client-secret'}]}})
        for container in pod['containers']:
            mounts = {m['name']: m for m in container['volumeMounts']}
            for name, path in [('oidc-ca', '/etc/nextcloud-oidc'), ('oidc-secret', '/run/nextcloud-oidc')]:
                self.assertEqual(mounts[name], {'name': name, 'mountPath': path, 'readOnly': True})
        self.assertNotIn('oidc-secret', [m['name'] for m in prepare['volumeMounts']])
        origin = load('gitops/clusters/local/app-values.yaml')['nextcloud']['configs']['oidc-origin.config.php']
        self.assertIn('https://nextcloud.perkforge.home.arpa', origin)
        for forbidden in ['allow_local_remote_servers', 'app:enable', 'user_oidc']:
            self.assertNotIn(forbidden, (ROOT / 'gitops/base/app-values.yaml').read_text())
        ingress = next(x for x in app if x['kind'] == 'Ingress')
        self.assertEqual(ingress['spec']['tls'][0]['secretName'], 'nextcloud-tls')
        data = render(str(ROOT / 'charts/data'), 'gitops/base/data-values.yaml', 'gitops/clusters/local/data-values.yaml')
        self.assertEqual({x['kind'] for x in data}, {'Cluster'})
        for obj in data:
            self.assertEqual(obj['metadata']['annotations']['helm.sh/resource-policy'], 'keep')
        claim = next(x for x in app if x['kind'] == 'PersistentVolumeClaim')
        self.assertEqual(claim['metadata']['annotations']['helm.sh/resource-policy'], 'keep')
        self.assertEqual(claim['spec']['storageClassName'], 'longhorn-dedicated')
        self.assertEqual(claim['spec']['resources']['requests']['storage'], '128Gi')
        # Expansion must change only the existing retained PVC request, not its
        # identity, consumer Pod template, credentials, database or other objects.
        previous_app = render(chart, 'gitops/base/app-values.yaml',
                              'gitops/clusters/local/app-values.yaml',
                              ['--set', 'filesStorage.size=32Gi'])
        previous_claim = next(x for x in previous_app if x['kind'] == 'PersistentVolumeClaim')
        self.assertEqual(previous_claim['spec']['resources']['requests']['storage'], '32Gi')
        previous_claim['spec']['resources']['requests']['storage'] = '128Gi'
        self.assertEqual(app, previous_app)
        db = next(x for x in data if x['kind'] == 'Cluster')
        self.assertEqual(db['spec']['storage']['storageClass'], 'longhorn-dedicated')
        self.assertFalse(db['spec']['enableSuperuserAccess'])
        self.assertIn('@sha256:', db['spec']['imageName'])
        self.assertEqual(db['spec']['storage']['size'], '16Gi')
        self.assertEqual(db['spec']['postgresql']['pg_hba'][0], 'hostnossl all all all reject')
        self.assertIn('worker-2', str(db['spec']['affinity']['nodeAffinity']))
        missing = subprocess.run([helm, 'template', 'data', str(ROOT / 'charts/data')], capture_output=True, text=True)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn('operator-reviewed durable StorageClass', missing.stderr)
        missing_files = subprocess.run([helm, 'template', 'nextcloud', chart,
            '-f', str(ROOT / 'gitops/base/app-values.yaml')], capture_output=True, text=True)
        self.assertNotEqual(missing_files.returncode, 0)
        self.assertIn('operator-reviewed durable StorageClass', missing_files.stderr)

if __name__ == '__main__':
    unittest.main()
