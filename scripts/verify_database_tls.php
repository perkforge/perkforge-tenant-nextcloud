<?php
// Owner-run read-only acceptance after separately approved web deployment.
// Read credentials only from the existing container environment; never print errors.
function need(bool $ok, string $message): void {
    if (!$ok) { throw new RuntimeException($message); }
}
try {
$host = getenv('POSTGRES_HOST');
$db = getenv('POSTGRES_DB');
$user = getenv('POSTGRES_USER');
$password = getenv('POSTGRES_PASSWORD');
$ca = '/etc/nextcloud-postgres-ca/ca.crt';
need($host === 'nextcloud-db-rw.tenant-home-nextcloud.svc.cluster.local', 'unexpected database endpoint');
need($db === 'nextcloud' && $user === 'nextcloud' && (bool)$password && is_readable($ca), 'missing expected credentials or public CA');
function connectDb(string $host, string $mode, string $ca, string $addr = ''): PDO {
    global $db, $user, $password;
    $dsn = "pgsql:host=$host;dbname=$db;sslmode=$mode;sslrootcert=$ca;connect_timeout=5";
    if ($addr !== '') { $dsn .= ";hostaddr=$addr"; }
    return new PDO($dsn, $user, $password, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
}
try {
    $pdo = connectDb($host, 'verify-full', $ca);
    $row = $pdo->query('SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()')->fetch(PDO::FETCH_ASSOC);
    need(in_array($row['ssl'] ?? null, [true, 't', '1', 1], true), 'session is not TLS');
    $pdo = null;
} catch (Throwable $e) { need(false, 'verified TLS connection failed; inspect privately'); }
$wrongCa = tempnam(sys_get_temp_dir(), 'nextcloud-public-ca-');
need($wrongCa !== false, 'cannot create temporary public CA');
chmod($wrongCa, 0600);
try {
    $key = openssl_pkey_new(['private_key_bits' => 2048]);
    $csr = openssl_csr_new(['commonName' => 'untrusted.invalid'], $key);
    $cert = openssl_csr_sign($csr, null, $key, 1);
    need($cert !== false && openssl_x509_export($cert, $public), 'cannot generate unrelated public CA');
    file_put_contents($wrongCa, $public);
    $addr = gethostbyname($host);
    need(filter_var($addr, FILTER_VALIDATE_IP) !== false, 'cannot resolve database address');
    foreach ([['wrong CA', $host, 'verify-full', $wrongCa, '', '/certificate|ssl error|root cert/i'],
              ['wrong hostname', 'wrong-name.invalid', 'verify-full', $ca, $addr, '/certificate|does not match/i'],
              ['plaintext', $host, 'disable', $ca, '', '/pg_hba|rejects connection/i']] as $case) {
        [$name, $h, $mode, $root, $ip, $expected] = $case;
        $denied = false;
        try { connectDb($h, $mode, $root, $ip); }
        catch (PDOException $e) { $denied = preg_match($expected, $e->getMessage()) === 1; }
        need($denied, "$name was not denied for the expected reason");
        echo "PASS: $name denied\n";
    }
    echo "PASS: verified TLS session and all three negative controls; no database writes\n";
} finally { unlink($wrongCa); }
} catch (Throwable $e) {
    // Deliberately suppress driver diagnostics, DSNs and credential-bearing traces.
    fwrite(STDERR, "FAIL: database TLS acceptance did not pass; inspect privately\n");
    exit(1);
}
