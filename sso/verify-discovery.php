<?php
// Read-only verification. Default execution performs no bootstrap or network access.
if (($argv[1] ?? '') !== '--run') {
    echo "OIDC discovery verification disabled\n";
    exit(0);
}
$issuer = $argv[2] ?? '';
if (!preg_match('~^https://[A-Za-z0-9.-]+(?::[0-9]+)?(?:/auth)?/realms/perkforge$~D', $issuer)) {
    throw new RuntimeException('Invalid exact issuer');
}
define('OC_CONSOLE', 1);
require_once '/var/www/html/lib/base.php';
$service = \OC::$server->get(\OCP\Http\Client\IClientService::class);
$client = $service->newClient();
$options = ['allow_redirects' => false, 'timeout' => 15];
$response = $client->get($issuer . '/.well-known/openid-configuration', $options);
if ($response->getStatusCode() !== 200) {
    throw new RuntimeException('Discovery status mismatch');
}
$discovery = json_decode((string)$response->getBody(), true, 64, JSON_THROW_ON_ERROR);
foreach (['issuer' => $issuer,
    'authorization_endpoint' => $issuer . '/protocol/openid-connect/auth',
    'token_endpoint' => $issuer . '/protocol/openid-connect/token',
    'jwks_uri' => $issuer . '/protocol/openid-connect/certs',
    'end_session_endpoint' => $issuer . '/protocol/openid-connect/logout'] as $key => $expected) {
    if (($discovery[$key] ?? null) !== $expected) {
        throw new RuntimeException('Discovery issuer/endpoint mismatch: ' . $key);
    }
}
if (!in_array('S256', $discovery['code_challenge_methods_supported'] ?? [], true)
    || !in_array('RS256', $discovery['id_token_signing_alg_values_supported'] ?? [], true)) {
    throw new RuntimeException('Required PKCE/signature support absent');
}
$keys = $client->get($discovery['jwks_uri'], $options);
$jwks = json_decode((string)$keys->getBody(), true, 64, JSON_THROW_ON_ERROR);
if ($keys->getStatusCode() !== 200 || empty($jwks['keys'])) {
    throw new RuntimeException('JWKS unavailable');
}
echo "Exact issuer/endpoints, S256 and trusted HTTPS discovery/JWKS verified\n";
