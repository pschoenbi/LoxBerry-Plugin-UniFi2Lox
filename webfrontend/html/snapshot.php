<?php
// Public JPEG endpoint for the Loxone "Bild-URL" of a custom intercom.
//   /plugins/unifi2lox/snapshot.php?cam=<slug>              + HTTP Basic Auth (Loxone user/password fields)
//   /plugins/unifi2lox/snapshot.php?cam=<slug>&key=<key>    without auth fields
$home = getenv('LBHOMEDIR') ?: '/opt/loxberry';
require_once $home . '/bin/plugins/' . basename(__DIR__) . '/common.php';

function deny($code, $msg)
{
    http_response_code($code);
    if ($code === 401) header('WWW-Authenticate: Basic realm="UniFi Kamera"');
    header('Content-Type: text/plain; charset=utf-8');
    echo $msg;
    exit;
}

$c = u2l_config();
$srv = $c['server'];

// ---- authentication ---------------------------------------------------------
$user = $_SERVER['PHP_AUTH_USER'] ?? null;
$pass = $_SERVER['PHP_AUTH_PW'] ?? null;
if ($user === null) {
    $hdr = $_SERVER['HTTP_AUTHORIZATION'] ?? ($_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? '');
    if (stripos($hdr, 'basic ') === 0) {
        [$user, $pass] = array_pad(explode(':', (string)base64_decode(substr($hdr, 6)), 2), 2, '');
    }
}
$okKey = !empty($srv['snapshot_key']) && hash_equals((string)$srv['snapshot_key'], (string)($_GET['key'] ?? ''));
$okAuth = !empty($srv['password']) && $user !== null
    && hash_equals((string)($srv['username'] ?? ''), (string)$user)
    && hash_equals((string)$srv['password'], (string)$pass);
$local = in_array($_SERVER['REMOTE_ADDR'] ?? '', ['127.0.0.1', '::1'], true);
if (!$okKey && !$okAuth && !$local) deny(401, 'Unauthorized');

// ---- camera -------------------------------------------------------------------
$slug = preg_replace('/[^a-z0-9_]/', '', strtolower($_GET['cam'] ?? ''));
$cam = u2l_find_cam($c, $slug);
if (!$cam || empty($cam['enabled'])) deny(404, 'Unknown camera');

$img = u2l_snapshot($c, $cam);
if (!$img) deny(503, 'Camera not reachable');

header('Content-Type: image/jpeg');
header('Content-Length: ' . strlen($img));
header('Cache-Control: no-store, max-age=0');
echo $img;
