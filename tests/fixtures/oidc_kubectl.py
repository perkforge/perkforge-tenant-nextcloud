#!/usr/bin/env python3
"""Synthetic kubectl/occ CLI contract. No network or real Kubernetes access."""
import json
import os
from pathlib import Path
import sys

path = Path(os.environ['NC_FIXTURE_STATE'])
s = json.loads(path.read_text())
a = sys.argv[1:]
s['calls'].append(a)

def finish(value='', write=False, code=0):
    if write:
        s['writes'].append(a)
    path.write_text(json.dumps(s))
    print(json.dumps(value) if not isinstance(value, str) else value)
    sys.exit(code)

if a[-5:] == ['namespace', 'kube-system', '-o', 'jsonpath={.metadata.uid}']:
    finish(s['cluster'])
if 'jsonpath={.metadata.uid}' in a:
    finish(s['cluster'])
if 'pod' in a and 'get' in a:
    finish(s['pod'])
if 'exec' not in a:
    finish('unknown fixture command', code=2)
cmd = a[a.index('--')+1:]
if cmd[:2] == ['sh', '-ec']:
    if 'echo installed' in cmd[2]:
        finish('installed' if s['installed'] else '')
    if 'cp -R' in cmd[2]:
        if s.get('interrupted_copy'):
            finish('interrupted stage exists', code=1)
        s['installed'] = True
        finish(write=True)
if cmd[0] == 'sha256sum':
    finish(s['secret_hash'] + '  /run/nextcloud-oidc/client-secret\n' + s['ca_hash'] + '  /etc/nextcloud-oidc/ca.crt')
if cmd[0] == 'cat':
    finish(s['ca'])
if cmd[:3] == ['php', '--', '--run']:
    source = sys.stdin.read()
    if "select('client_secret')" in source:
        finish('credential mismatch' if s.get('bad_credential') else 'credential verified',code=1 if s.get('bad_credential') else 0)
    if 'user_oidc_providers' in source:
        finish([{'id':p['id'],'identifier':p['identifier'],'client_id':p['clientId'],'discovery_endpoint':p['discoveryEndpoint']} for p in s['providers']])
    finish('discovery mismatch' if s.get('bad_discovery') else 'verified', code=1 if s.get('bad_discovery') else 0)
if cmd[:2] != ['php', '/var/www/html/occ']:
    finish('unknown fixture exec', code=2)
c = cmd[2:]
op = c[0]
if op == 'status':
    finish({'installed': True, 'maintenance': False, 'needsDbUpgrade': False, 'versionstring': '35.0.2'})
if op == 'user:info':
    if c[1] not in s['users']:
        finish('user not found', code=1)
    finish(s['users'][c[1]])
if op == 'integrity:check-app':
    finish('signature failure' if s.get('bad_integrity') else '', code=1 if s.get('bad_integrity') else 0)
if op == 'app:list':
    finish({'enabled': {'user_oidc': '8.13.0'} if s['app_enabled'] else {}, 'disabled': {} if s['app_enabled'] else {'user_oidc': '8.13.0'}})
if op == 'config:list':
    finish(s['config'])
if op == 'config:system:set':
    key = c[1]
    value = next(x.removeprefix('--value=') for x in c if x.startswith('--value='))
    s['config']['system'][key] = json.loads(value)
    finish(write=True)
if op == 'config:system:get':
    finish('true' if s['config']['system'].get(c[1]) else 'false')
if op == 'config:app:set':
    s['config']['apps'].setdefault('user_oidc', {})['allow_multiple_user_backends'] = '1'
    finish(write=True)
if op == 'app:enable':
    s['app_enabled'] = True
    finish(write=True)
if op == 'user_oidc:providers':
    finish('\n'.join(json.dumps(x) for x in s['providers']))
if op == 'user_oidc:provider':
    options = dict(x[2:].split('=',1) for x in c[2:])
    supported = {'clientid','clientsecret-file','discoveryuri','scope','mapping-uid','mapping-display-name','unique-uid','mapping-groups','group-provisioning','group-restrict-login-to-whitelist','group-whitelist-regex','check-bearer','bearer-provisioning','resolve-nested-claims'}
    if set(options) - supported:
        finish('unknown upstream option', code=2)
    if not s['providers']:
        s['providers'] = [{'id': 1, 'identifier': c[1], 'clientId': options['clientid'], 'scope': options['scope'],
                          'discoveryEndpoint': options['discoveryuri'], 'settings': {
                              'mappingUid':'sub','mappingDisplayName':options.get('mapping-display-name',''),'mappingGroups':'nextcloud_roles','uniqueUid':True,
                              'restrictLoginToGroups':True,'groupProvisioning':False,'checkBearer':False,
                              'bearerProvisioning':False,'nestedAndFallbackClaims':False,'enrichLoginIdTokenWithUserinfo':False}}]
    if 'group-whitelist-regex' in options:
        s['providers'][0]['settings']['groupWhitelistRegex'] = options['group-whitelist-regex']
    if 'mapping-display-name' in options:
        s['providers'][0]['settings']['mappingDisplayName'] = options['mapping-display-name']
    finish(write=True)
if op == 'security:certificates:export':
    finish(s.get('trust',''))
if op == 'security:certificates:import':
    s['trust'] = s['ca']
    finish(write=True)
if op in ['group:adduser','group:removeuser']:
    groups = s['users'][c[2]]['groups']
    if op == 'group:adduser':groups.append(c[1])
    else:groups.remove(c[1])
    finish(write=True)
if op in ['user:disable','user:enable']:
    s['users'][c[1]]['enabled'] = op == 'user:enable'
    finish(write=True)
if op == 'user:auth-tokens:list':
    finish(s['tokens'])
if op == 'user:auth-tokens:delete':
    if s.get('fail_token_delete'):
        finish('interrupted revocation', code=1)
    s['tokens'] = [x for x in s['tokens'] if str(x['id']) != c[2]]
    finish(write=True)
finish('unsupported fixture occ ' + op, code=2)
