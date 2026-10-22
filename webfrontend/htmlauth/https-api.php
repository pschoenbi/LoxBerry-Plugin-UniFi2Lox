<?php
// Served only from LoxBerry's authenticated administration directory.
$home = getenv('LBHOMEDIR') ?: dirname(realpath(__DIR__), 4);
$bin = $home . '/bin/plugins/' . basename(__DIR__);
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
function reply($data, $status = 200) {
    http_response_code($status);
    echo json_encode($data, JSON_UNESCAPED_SLASHES);
    exit;
}
$action = $_GET['action'] ?? 'status';
$allowed = ['status', 'save', 'install', 'issue', 'confirm', 'import', 'apply', 'disable'];
if (!in_array($action, $allowed, true)) reply(['ok'=>false, 'error'=>'Unknown action.'], 400);
if ($action !== 'status') {
    // Custom header + JSON require a CORS preflight cross-origin. This endpoint
    // never permits CORS. Also reject a mismatched Origin where provided.
    $origin = $_SERVER['HTTP_ORIGIN'] ?? '';
    $originHost = $origin ? parse_url($origin, PHP_URL_HOST) : '';
    $originPort = $origin ? parse_url($origin, PHP_URL_PORT) : null;
    $expected = strtolower($_SERVER['HTTP_HOST'] ?? '');
    $received = strtolower((string)$originHost . ($originPort ? ':' . $originPort : ''));
    if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST'
        || ($_SERVER['HTTP_X_U2L_HTTPS'] ?? '') !== '1'
        || stripos($_SERVER['CONTENT_TYPE'] ?? '', 'application/json') !== 0
        || ($origin && $received !== $expected)) {
        reply(['ok'=>false, 'error'=>'Request rejected. Open this page through LoxBerry.'], 403);
    }
}
$input = file_get_contents('php://input', false, null, 0, 400001);
if (strlen($input) > 400000) reply(['ok'=>false, 'error'=>'Request too large.'], 413);
if ($input && !is_array(json_decode($input, true))) reply(['ok'=>false, 'error'=>'Invalid JSON.'], 400);
putenv('LBHOMEDIR=' . $home);
$process = proc_open(['python3', $bin . '/https_manager.py', $action],
    [0=>['pipe','r'], 1=>['pipe','w'], 2=>['file','/dev/null','a']], $pipes);
if (!is_resource($process)) reply(['ok'=>false, 'error'=>'Could not start HTTPS manager.'], 500);
fwrite($pipes[0], $input ?: '{}');
fclose($pipes[0]);
$output = stream_get_contents($pipes[1]);
fclose($pipes[1]);
proc_close($process);
$data = json_decode($output, true);
reply(is_array($data) ? $data : ['ok'=>false, 'error'=>'HTTPS manager did not respond.']);
