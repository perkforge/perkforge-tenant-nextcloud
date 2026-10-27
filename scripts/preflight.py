#!/usr/bin/env python3
"""Read-only local-VM capacity gate; exits nonzero on missing or insufficient data."""
import json
import subprocess
import sys

MIB = 1024**2
GIB = 1024**3


def get(*args):
    return json.loads(subprocess.check_output(['kubectl', 'get', *args], timeout=30, stderr=subprocess.PIPE))


def memory(value):
    for suffix, factor in [('Ki',1024), ('Mi',MIB), ('Gi',GIB)]:
        if value.endswith(suffix):
            return int(value[:-len(suffix)]) * factor
    return int(value)


def main():
    nodes = get('nodes', '-o', 'json')['items']
    metrics = get('--raw', '/apis/metrics.k8s.io/v1beta1/nodes')['items']
    used = {x['metadata']['name']: memory(x['usage']['memory']) for x in metrics}
    problems = []
    for name, minimum in [('cks-control',512), ('cks-worker',1600)]:
        node = next(x for x in nodes if x['metadata']['name'] == name)
        conditions = {x['type']:x['status'] for x in node['status']['conditions']}
        if conditions.get('Ready') != 'True' or any(conditions.get(k) != 'False' for k in ['MemoryPressure','DiskPressure','PIDPressure']):
            problems.append(f'{name}: unhealthy or pressure conditions unknown')
        headroom = (memory(node['status']['allocatable']['memory']) - used[name]) // MIB
        print(f'{name}: {headroom} MiB memory headroom; minimum {minimum}')
        if headroom < minimum: problems.append(f'{name}: insufficient memory')
    stats = get('--raw', '/api/v1/nodes/cks-worker/proxy/stats/summary')
    available = stats['node']['fs']['availableBytes']
    print(f'Worker root filesystem: {available/GIB:.2f} GiB free; minimum 8 GiB')
    print('Operator must confirm /opt/local-path-provisioner uses this filesystem.')
    if available < 8*GIB: problems.append('worker: insufficient filesystem space')
    for problem in problems: print('BLOCKED:',problem)
    print('This gate changes nothing; passing does not activate Fleet or validate LAN access.')
    return 1 if problems else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError,ValueError,KeyError,StopIteration,subprocess.SubprocessError):
        print('BLOCKED: capacity data could not be verified',file=sys.stderr)
        sys.exit(2)
