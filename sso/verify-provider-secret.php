<?php
// Read-only equality check; never return encrypted or decrypted credentials.
if (($argv[1] ?? '') !== '--run') {
    echo "Provider credential verification disabled\n";
    exit(0);
}
$id = $argv[2] ?? '';
if (!preg_match('/^[1-9][0-9]*$/D', $id)) {
    throw new RuntimeException('Invalid provider identity');
}
define('OC_CONSOLE', 1);
require_once '/var/www/html/lib/base.php';
$db = \OC::$server->get(\OCP\IDBConnection::class);
$query = $db->getQueryBuilder();
$query->select('client_secret')->from('user_oidc_providers')
    ->where($query->expr()->eq('id', $query->createNamedParameter((int)$id, \OCP\DB\QueryBuilder\IQueryBuilder::PARAM_INT)));
$result = $query->executeQuery();
$encrypted = $result->fetchOne();
$result->closeCursor();
if (!is_string($encrypted) || $encrypted === '') {
    throw new RuntimeException('Provider credential missing');
}
$stored = \OC::$server->get(\OCP\Security\ICrypto::class)->decrypt($encrypted);
$mounted = file_get_contents('/run/nextcloud-oidc/client-secret');
if (!is_string($mounted) || !hash_equals($stored, $mounted)) {
    throw new RuntimeException('Provider credential does not match delivered input');
}
echo "Provider credential matches delivered input\n";
