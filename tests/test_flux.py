"""Offline selection and rendered workload contracts; never contacts Kubernetes."""
import os
from pathlib import Path
import subprocess
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return yaml.safe_load((ROOT / path).read_text())


class FluxContract(unittest.TestCase):
    def test_suspended_scoped_selection(self):
        built = subprocess.check_output(['kubectl', 'kustomize', str(ROOT / 'gitops/clusters/local')], text=True)
        objects = list(yaml.safe_load_all(built))
        self.assertEqual({x['kind'] for x in objects}, {'ConfigMap', 'HelmRelease'})
        releases = [x for x in objects if x['kind'] == 'HelmRelease']
        self.assertEqual(len(releases), 2)
        for obj in objects:
            self.assertEqual(obj['metadata']['namespace'], 'tenant-home-nextcloud-config')
        for obj in releases:
            spec = obj['spec']
            self.assertTrue(spec['suspend'])
            self.assertFalse(spec['install']['createNamespace'])
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
        def render(chart, defaults, cluster):
            return list(yaml.safe_load_all(subprocess.check_output([
                helm, 'template', 'nextcloud', chart, '--namespace', 'tenant-home-nextcloud',
                '-f', str(ROOT / defaults), '-f', str(ROOT / cluster)], text=True)))
        app = render(chart, 'gitops/base/app-values.yaml', 'gitops/clusters/local/app-values.yaml')
        self.assertFalse(any(x['kind'] in {'Namespace', 'Role', 'RoleBinding', 'Secret', 'PersistentVolumeClaim'} for x in app))
        deploy = next(x for x in app if x['kind'] == 'Deployment')
        pod = deploy['spec']['template']['spec']
        self.assertEqual(deploy['spec']['strategy']['type'], 'Recreate')
        self.assertEqual(pod['nodeSelector'], {'storage.perkforge.io/worker': 'true'})
        self.assertTrue(any(x.get('persistentVolumeClaim', {}).get('claimName') == 'nextcloud-files' for x in pod['volumes']))
        for container in pod['containers'] + pod['initContainers']:
            self.assertFalse(container['securityContext']['allowPrivilegeEscalation'])
            self.assertEqual(container['securityContext']['runAsUser'], 33)
        cron = next(x for x in app if x['kind'] == 'CronJob')
        self.assertEqual(cron['spec']['concurrencyPolicy'], 'Forbid')
        self.assertEqual(cron['spec']['jobTemplate']['spec']['template']['spec']['nodeSelector'], pod['nodeSelector'])
        ingress = next(x for x in app if x['kind'] == 'Ingress')
        self.assertEqual(ingress['spec']['tls'][0]['secretName'], 'nextcloud-tls')
        data = render(str(ROOT / 'charts/data'), 'gitops/base/data-values.yaml', 'gitops/clusters/local/data-values.yaml')
        self.assertEqual({x['kind'] for x in data}, {'Cluster', 'PersistentVolumeClaim'})
        for obj in data:
            self.assertEqual(obj['metadata']['annotations']['helm.sh/resource-policy'], 'keep')
        claim = next(x for x in data if x['kind'] == 'PersistentVolumeClaim')
        self.assertEqual(claim['spec']['storageClassName'], 'longhorn')
        self.assertEqual(claim['spec']['resources']['requests']['storage'], '32Gi')
        db = next(x for x in data if x['kind'] == 'Cluster')
        self.assertEqual(db['spec']['storage']['storageClass'], 'longhorn')
        self.assertFalse(db['spec']['enableSuperuserAccess'])
        missing = subprocess.run([helm, 'template', 'data', str(ROOT / 'charts/data')], capture_output=True, text=True)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn('operator-reviewed durable StorageClass', missing.stderr)

if __name__ == '__main__':
    unittest.main()
