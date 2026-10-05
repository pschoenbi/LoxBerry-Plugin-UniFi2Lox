<?php
// JSON backend of the admin page (inside LoxBerry auth)
$home = getenv('LBHOMEDIR') ?: '/opt/loxberry';
require_once $home . '/bin/plugins/' . basename(__DIR__) . '/common.php';

$action = $_GET['action'] ?? '';
$in = json_decode(file_get_contents('php://input') ?: '{}', true) ?: [];

function out($data, $code = 200)
{
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function slugify($s)
{
    $s = strtr(mb_strtolower($s, 'UTF-8'), ['ä' => 'ae', 'ö' => 'oe', 'ü' => 'ue', 'ß' => 'ss', 'é' => 'e', 'è' => 'e', 'à' => 'a']);
    $s = trim(preg_replace('/[^a-z0-9]+/', '_', $s), '_');
    return $s ?: 'cam';
}

function py($cmd, $host = null, $key = null)
{
    $env = 'LBHOMEDIR=' . escapeshellarg(U2L_HOME);
    if ($host !== null && $host !== '') $env .= ' U2L_HOST=' . escapeshellarg($host);
    if ($key !== null && $key !== '') $env .= ' U2L_KEY=' . escapeshellarg($key);
    $o = [];
    exec("$env python3 " . escapeshellarg(U2L_BIN . '/unifi2lox.py') . " $cmd 2>/dev/null", $o);
    return json_decode(implode("\n", $o), true) ?: ['ok' => false, 'code' => 'no_response'];
}

function go2rtc_streams($c)
{
    $port = (int)($c['server']['port'] ?? 1984);
    [$st, $body] = u2l_http_get("http://127.0.0.1:$port/api/streams", [], 2);
    return $st === 200 ? (json_decode($body, true) ?: []) : null;
}

switch ($action) {

case 'get':
    $c = u2l_config();
    $c['protect']['has_key'] = !empty($c['protect']['apikey']);
    $c['protect']['apikey'] = '';
    $ver = trim((string)@shell_exec(escapeshellarg(U2L_BIN . '/go2rtc') . ' -version 2>&1 | head -1'));
    out(['ok' => true, 'config' => $c, 'ip' => u2l_local_ip(), 'folder' => U2L_FOLDER, 'go2rtc' => $ver,
         'ffmpeg' => trim((string)@shell_exec('command -v ffmpeg'))]);

case 'save':
    $old = u2l_config();
    $new = $in['config'] ?? null;
    if (!is_array($new)) out(['ok' => false, 'code' => 'invalid'], 400);

    $p = $new['protect'] ?? [];
    $cfg = $old;
    $cfg['protect'] = [
        'host'       => trim((string)($p['host'] ?? '')),
        'apikey'     => trim((string)($p['apikey'] ?? '')) !== '' ? trim($p['apikey']) : ($old['protect']['apikey'] ?? ''),
        'verify_ssl' => !empty($p['verify_ssl']),
        'transport'  => in_array($p['transport'] ?? '', ['rtsp', 'rtspx'], true) ? $p['transport'] : 'rtspx',
    ];
    $s = $new['server'] ?? [];
    $cfg['server'] = array_merge($old['server'], [
        'enabled'           => !empty($s['enabled']),
        'port'              => max(1024, min(65535, (int)($s['port'] ?? 1984))),
        'username'          => preg_replace('/[^A-Za-z0-9_.-]/', '', (string)($s['username'] ?? 'loxone')) ?: 'loxone',
        'password'          => (string)($s['password'] ?? '') !== '' ? (string)$s['password'] : ($old['server']['password'] ?? ''),
        'snapshot_cache_ms' => max(0, min(10000, (int)($s['snapshot_cache_ms'] ?? 1000))),
        'hwaccel'           => in_array($s['hwaccel'] ?? '', ['off', 'auto', 'vaapi', 'v4l2m2m', 'rkmpp'], true) ? $s['hwaccel'] : 'off',
        'rtsp_lan'          => !empty($s['rtsp_lan']),
        'loglevel'          => in_array($s['loglevel'] ?? '', ['debug', 'info', 'warn', 'error'], true) ? $s['loglevel'] : 'warn',
    ]);
    if (!empty($s['regen_key']) || empty($cfg['server']['snapshot_key'])) $cfg['server']['snapshot_key'] = bin2hex(random_bytes(12));

    $cams = [];
    $seen = [];
    foreach (($new['cameras'] ?? []) as $cam) {
        $name = trim((string)($cam['name'] ?? ''));
        if ($name === '' && empty($cam['id'])) continue;
        $slug = slugify($cam['slug'] ?? '' ?: $name);
        $base = $slug; $i = 2;
        while (isset($seen[$slug])) $slug = $base . '_' . $i++;
        $seen[$slug] = true;
        $cams[] = [
            'id'         => (string)($cam['id'] ?? ''),
            'name'       => $name ?: $slug,
            'slug'       => $slug,
            'enabled'    => !empty($cam['enabled']),
            'source'     => in_array($cam['source'] ?? '', ['high', 'medium', 'low', 'package'], true) ? $cam['source'] : 'medium',
            'manual_url' => trim((string)($cam['manual_url'] ?? '')),
            'width'      => max(0, min(3840, (int)($cam['width'] ?? 1280))),
            'fps'        => max(1, min(30, (int)($cam['fps'] ?? 10))),
            'quality'    => max(2, min(31, (int)($cam['quality'] ?? 5))),
            'rotate'     => in_array((int)($cam['rotate'] ?? 0), [0, 90, 180, 270], true) ? (int)$cam['rotate'] : 0,
            'snapshot'   => in_array($cam['snapshot'] ?? '', ['api_hq', 'api', 'go2rtc'], true) ? $cam['snapshot'] : 'api_hq',
            'preload'    => in_array($cam['preload'] ?? '', ['none', 'rtsp', 'mjpeg'], true) ? $cam['preload'] : 'rtsp',
        ];
    }
    $cfg['cameras'] = $cams;
    if (!u2l_save_config($cfg)) out(['ok' => false, 'code' => 'save'], 500);

    @unlink(U2L_DATA . '/stopped.flag');
    [$rc, $msg] = $cfg['server']['enabled'] ? u2l_service('restart') : u2l_service('stop');
    out(['ok' => true, 'service' => $msg, 'rc' => $rc]);

case 'test':
case 'discover':
    $c = u2l_config();
    $host = trim((string)($in['host'] ?? '')) ?: ($c['protect']['host'] ?? '');
    $key = trim((string)($in['apikey'] ?? '')) ?: ($c['protect']['apikey'] ?? '');
    out(py($action, $host, $key));

case 'status':
    $c = u2l_config();
    [$rc, $msg] = u2l_service('status');
    $streams = go2rtc_streams($c);
    $res = [];
    foreach ($c['cameras'] as $cam) {
        $info = ['slug' => $cam['slug'], 'source' => null, 'mjpeg' => null];
        foreach (['source' => $cam['slug'], 'mjpeg' => $cam['slug'] . '_mjpeg'] as $k => $name) {
            if (!isset($streams[$name])) continue;
            $st = $streams[$name];
            $medias = [];
            foreach (($st['producers'] ?? []) as $pr) {
                foreach (($pr['medias'] ?? []) as $m) $medias[] = $m;
                if (!empty($pr['receivers'])) {
                    foreach ($pr['receivers'] as $r) if (!empty($r['codec']['codec_name'])) $medias[] = $r['codec']['codec_name'];
                }
            }
            $info[$k] = [
                'active'    => count(array_filter($st['producers'] ?? [], fn($p) => !empty($p['remote_addr']) || !empty($p['receivers']) || !empty($p['id']))) > 0,
                'consumers' => count($st['consumers'] ?? []),
                'medias'    => array_values(array_unique($medias)),
            ];
        }
        $res[] = $info;
    }
    $load = sys_getloadavg();
    out(['ok' => true, 'running' => $rc === 0, 'msg' => $msg, 'streams' => $res, 'load' => $load ? round($load[0], 2) : null]);

case 'service':
    $cmd = $in['cmd'] ?? '';
    if ($cmd === 'stop') @touch(U2L_DATA . '/stopped.flag');
    if ($cmd === 'start' || $cmd === 'restart') @unlink(U2L_DATA . '/stopped.flag');
    [$rc, $msg] = u2l_service($cmd);
    out(['ok' => $rc === 0, 'msg' => $msg]);

case 'preview':
    $c = u2l_config();
    $cam = u2l_find_cam($c, (string)($_GET['cam'] ?? ''));
    $t = microtime(true);
    $img = $cam ? u2l_snapshot($c, $cam, 0) : null;
    if (!$img) { http_response_code(503); exit; }
    header('Content-Type: image/jpeg');
    header('Cache-Control: no-store');
    header('X-Fetch-Ms: ' . (int)((microtime(true) - $t) * 1000));
    echo $img;
    exit;

case 'log':
    $lines = @file(U2L_LOG) ?: [];
    out(['ok' => true, 'log' => implode('', array_slice($lines, -200))]);

case 'stream':
    // admin live preview: relay the MJPEG stream through the authenticated LoxBerry page
    $c = u2l_config();
    $cam = u2l_find_cam($c, (string)($_GET['cam'] ?? ''));
    if (!$cam) { http_response_code(404); exit; }
    $port = (int)($c['server']['port'] ?? 1984);
    $fp = @fsockopen('127.0.0.1', $port, $en, $es, 3);
    if (!$fp) { http_response_code(503); exit; }
    fwrite($fp, "GET /api/stream.mjpeg?src=" . rawurlencode($cam['slug'] . '_mjpeg') . " HTTP/1.0\r\nHost: localhost\r\n\r\n");
    $hdr = '';
    while (!feof($fp) && ($line = fgets($fp)) !== false && trim($line) !== '') $hdr .= $line;
    if (preg_match('/Content-Type:\s*(.+)/i', $hdr, $m)) header('Content-Type: ' . trim($m[1]));
    header('Cache-Control: no-store');
    header('X-Accel-Buffering: no');
    @ini_set('zlib.output_compression', '0');
    while (ob_get_level()) ob_end_flush();
    set_time_limit(120); // the preview stops itself after 2 minutes
    $end = time() + 115;
    while (!feof($fp) && !connection_aborted() && time() < $end) {
        $buf = fread($fp, 65536);
        if ($buf === false) break;
        echo $buf;
        flush();
    }
    fclose($fp);
    exit;

default:
    out(['ok' => false, 'error' => 'unknown action'], 400);
}
