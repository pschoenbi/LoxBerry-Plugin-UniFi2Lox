<?php
// Shared helpers for the unifi2lox web pages (admin UI + public snapshot endpoint)

define('U2L_FOLDER', basename(__DIR__));
define('U2L_HOME', getenv('LBHOMEDIR') ?: '/opt/loxberry');
define('U2L_BIN', U2L_HOME . '/bin/plugins/' . U2L_FOLDER);
define('U2L_CFG', U2L_HOME . '/config/plugins/' . U2L_FOLDER . '/config.json');
define('U2L_DATA', U2L_HOME . '/data/plugins/' . U2L_FOLDER);
define('U2L_LOG', U2L_HOME . '/log/plugins/' . U2L_FOLDER . '/go2rtc.log');
define('U2L_SHM', is_dir('/dev/shm') ? '/dev/shm' : sys_get_temp_dir());

function u2l_config()
{
    $c = json_decode(@file_get_contents(U2L_CFG), true);
    if (!is_array($c)) {
        $c = json_decode(@file_get_contents(dirname(U2L_CFG) . '/config.default.json'), true) ?: [];
    }
    $c += ['protect' => [], 'server' => [], 'cameras' => []];
    return $c;
}

function u2l_save_config($c)
{
    $tmp = U2L_CFG . '.tmp';
    if (file_put_contents($tmp, json_encode($c, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES)) === false) {
        return false;
    }
    @chmod($tmp, 0600);
    return rename($tmp, U2L_CFG);
}

function u2l_find_cam($c, $slug)
{
    foreach ($c['cameras'] as $cam) {
        if (($cam['slug'] ?? '') === $slug) return $cam;
    }
    return null;
}

function u2l_host($c)
{
    $h = trim($c['protect']['host'] ?? '');
    $h = preg_replace('#^https?://#', '', $h);
    return rtrim($h, '/');
}

/** HTTP GET returning [status, body, content-type] - only PHP streams, no curl needed */
function u2l_http_get($url, $headers = [], $timeout = 5, $verify = false)
{
    $ctx = stream_context_create([
        'http' => ['method' => 'GET', 'header' => implode("\r\n", $headers), 'timeout' => $timeout, 'ignore_errors' => true],
        'ssl'  => ['verify_peer' => $verify, 'verify_peer_name' => $verify, 'allow_self_signed' => !$verify],
    ]);
    $body = @file_get_contents($url, false, $ctx);
    $status = 0;
    $type = '';
    foreach ($http_response_header ?? [] as $h) {
        if (preg_match('#^HTTP/\S+\s+(\d+)#', $h, $m)) $status = (int)$m[1];
        if (stripos($h, 'Content-Type:') === 0) $type = trim(substr($h, 13));
    }
    return [$status, $body === false ? '' : $body, $type];
}

function u2l_is_jpeg($data)
{
    return strlen($data) > 100 && substr($data, 0, 2) === "\xFF\xD8";
}

/** Snapshot straight from UniFi Protect (camera JPEG, no transcoding, ~0.3 s) */
function u2l_snapshot_api($c, $cam, $hq)
{
    $host = u2l_host($c);
    $key = trim($c['protect']['apikey'] ?? '');
    if (!$host || !$key || empty($cam['id'])) return null;
    $url = "https://$host/proxy/protect/integration/v1/cameras/" . rawurlencode($cam['id']) . '/snapshot'
         . ($hq ? '?highQuality=true' : '');
    [$st, $body] = u2l_http_get($url, ["X-API-KEY: $key", 'Accept: image/jpeg'], 4, !empty($c['protect']['verify_ssl']));
    return ($st === 200 && u2l_is_jpeg($body)) ? $body : null;
}

/** Snapshot decoded from the running stream by go2rtc (works without API key) */
function u2l_snapshot_go2rtc($c, $cam)
{
    $port = (int)($c['server']['port'] ?? 1984);
    $url = "http://127.0.0.1:$port/api/frame.jpeg?src=" . rawurlencode($cam['slug']);
    if (!empty($cam['width'])) $url .= '&width=' . (int)$cam['width'];
    if (!empty($cam['rotate'])) $url .= '&rotate=' . (int)$cam['rotate'];
    [$st, $body] = u2l_http_get($url, [], 8);
    return ($st === 200 && u2l_is_jpeg($body)) ? $body : null;
}

/**
 * Returns a JPEG for the camera. Uses a short RAM cache so that several
 * Loxone apps opening at the same moment trigger only one camera request.
 */
function u2l_snapshot($c, $cam, $maxAgeMs = null)
{
    if ($maxAgeMs === null) $maxAgeMs = (int)($c['server']['snapshot_cache_ms'] ?? 1000);
    $file = U2L_SHM . '/unifi2lox_' . $cam['slug'] . '.jpg';
    // filemtime() has only 1 s resolution -> keep the exact fetch time next to the image
    $fresh = function () use ($file, $maxAgeMs) {
        $ts = (float)@file_get_contents($file . '.ts');
        return $ts > 0 && is_file($file) && (microtime(true) - $ts) * 1000 <= $maxAgeMs;
    };
    if ($maxAgeMs > 0 && $fresh()) return file_get_contents($file);

    $lock = fopen($file . '.lock', 'c');
    if ($lock) flock($lock, LOCK_EX);
    try {
        if ($maxAgeMs > 0 && $fresh()) return file_get_contents($file);  // filled while we waited
        $mode = $cam['snapshot'] ?? 'api_hq';
        $img = null;
        if ($mode === 'api_hq' || $mode === 'api') $img = u2l_snapshot_api($c, $cam, $mode === 'api_hq');
        if (!$img) $img = u2l_snapshot_go2rtc($c, $cam);
        if (!$img && $mode === 'go2rtc') $img = u2l_snapshot_api($c, $cam, true);
        if ($img) {
            file_put_contents($file . '.tmp', $img);
            rename($file . '.tmp', $file);
            file_put_contents($file . '.ts', (string)microtime(true));
            return $img;
        }
        // last resort: an older picture is better than a broken image in the Loxone app
        return is_file($file) ? file_get_contents($file) : null;
    } finally {
        if ($lock) { flock($lock, LOCK_UN); fclose($lock); }
    }
}

function u2l_local_ip()
{
    if (class_exists('LBSystem') && method_exists('LBSystem', 'get_localip')) return LBSystem::get_localip();
    $ip = $_SERVER['SERVER_ADDR'] ?? '';
    if (!$ip || $ip === '127.0.0.1' || $ip === '::1') $ip = trim(explode(' ', trim(@shell_exec('hostname -I')))[0] ?? '');
    return $ip ?: 'loxberry';
}

function u2l_service($cmd)
{
    $allowed = ['start', 'stop', 'restart', 'status'];
    if (!in_array($cmd, $allowed, true)) return [1, 'invalid'];
    $out = [];
    $rc = 0;
    exec('LBHOMEDIR=' . escapeshellarg(U2L_HOME) . ' ' . escapeshellarg(U2L_BIN . '/service.sh') . ' ' . $cmd . ' 2>&1', $out, $rc);
    return [$rc, implode("\n", $out)];
}
