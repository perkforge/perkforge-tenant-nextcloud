#!/usr/bin/env python3
"""Probe the unauthenticated provider login, never follow its authorization redirect."""
import argparse
import http.client
import re
import ssl
import sys
from urllib.parse import parse_qsl, urlsplit


class VerificationError(ValueError):
    pass


def verify_location(location, issuer, callback):
    # Do not use parse_qs's last-value behavior for security-sensitive parameters.
    if not isinstance(location, str) or any(ord(c) < 33 or ord(c) > 126 for c in location):
        raise VerificationError('Malformed authorization redirect')
    parts = urlsplit(location)
    if parts.fragment or location.split('?', 1)[0] != issuer + '/protocol/openid-connect/auth':
        raise VerificationError('Authorization endpoint differs from reviewed issuer')
    if re.search(r'%(?![0-9A-Fa-f]{2})', parts.query):
        raise VerificationError('Malformed authorization parameters')
    pairs = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True, errors='strict', max_num_fields=32)
    params = dict(pairs)
    if len(params) != len(pairs):
        raise VerificationError('Duplicate authorization parameter')
    for key, expected in {'redirect_uri': callback, 'client_id': 'nextcloud',
                          'response_type': 'code', 'code_challenge_method': 'S256'}.items():
        if params.get(key) != expected:
            raise VerificationError('Authorization callback/client/PKCE mismatch')
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}', params.get('code_challenge', '')):
        raise VerificationError('Invalid S256 challenge')


def verify(origin, issuer, callback_path, provider_id, ca_file):
    if not re.fullmatch(r'https://[A-Za-z0-9.-]+(?::[0-9]+)?', origin):
        raise VerificationError('Invalid exact Nextcloud origin')
    if not re.fullmatch(r'https://[A-Za-z0-9.-]+(?::[0-9]+)?(?:/auth)?/realms/perkforge', issuer):
        raise VerificationError('Invalid exact issuer')
    if callback_path not in ('/apps/user_oidc/code', '/index.php/apps/user_oidc/code'):
        raise VerificationError('Invalid exact callback path')
    if not re.fullmatch(r'[1-9][0-9]*', str(provider_id)):
        raise VerificationError('Invalid verified provider ID')
    if not isinstance(ca_file, str) or not ca_file.startswith('/'):
        raise VerificationError('Explicit absolute public CA file required')
    source = urlsplit(origin)
    # No environment proxies, netrc, cookies, authorization headers, redirect handler,
    # or TLS bypass. The explicit front controller also works without pretty routes.
    context = ssl.create_default_context(cafile=ca_file)
    connection = http.client.HTTPSConnection(source.hostname, source.port, context=context, timeout=15)
    try:
        connection.request('GET', '/index.php/apps/user_oidc/login/' + str(provider_id))
        response = connection.getresponse()
        locations = response.headers.get_all('Location', [])
        if response.status != 302 or len(locations) != 1:
            raise VerificationError('Provider login must return one authorization redirect')
        verify_location(locations[0], issuer, origin + callback_path)
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    for name in ('origin', 'issuer', 'callback-path', 'provider-id', 'ca-file'):
        parser.add_argument('--' + name)
    args = parser.parse_args()
    if not args.run:
        print('Browser callback verification disabled')
        return 0
    try:
        verify(args.origin, args.issuer, args.callback_path, args.provider_id, args.ca_file)
    except Exception:
        # Never expose Location, cookies, state, nonce, challenge or HTTP exception URLs.
        print('Browser callback verification failed; check trusted HTTPS, provider and exact callback inputs', file=sys.stderr)
        return 1
    print('Browser-facing exact callback, issuer, client and S256 verified')
    return 0


if __name__ == '__main__':
    sys.exit(main())
