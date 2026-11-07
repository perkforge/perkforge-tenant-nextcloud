<?php
// Read only, including when the app is disabled. Never read client_secret.
if (($argv[1] ?? '') !== '--run') {
    echo "Provider inventory verification disabled\n";
    exit(0);
}
define('OC_CONSOLE', 1);
require_once '/var/www/html/lib/base.php';
$db = \OC::$server->get(\OCP\IDBConnection::class);
if (!$db->tableExists('user_oidc_providers')) {
    echo "[]\n";
    exit(0);
}
$query = $db->getQueryBuilder();
$query->select('id', 'identifier', 'client_id', 'discovery_endpoint')
    ->from('user_oidc_providers')->setMaxResults(2);
$result = $query->executeQuery();
echo json_encode($result->fetchAllAssociative(), JSON_THROW_ON_ERROR) . "\n";
$result->closeCursor();
