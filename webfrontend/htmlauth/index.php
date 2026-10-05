<?php
require_once "loxberry_system.php";
require_once "loxberry_web.php";

$L = LBSystem::readlanguage("language.ini");
function T($k) { global $L; return htmlspecialchars($L["U2L.$k"] ?? $k, ENT_QUOTES, 'UTF-8'); }
function TH($k) { global $L; return $L["U2L.$k"] ?? $k; }   // trusted HTML from our own language files
$U2L_JS = [];
foreach ($L as $k => $v) if (strpos($k, 'U2L.') === 0) $U2L_JS[substr($k, 4)] = $v;

$template_title = $L['U2L.TITLE'] ?? 'UniFi Protect';
$helplink = "https://github.com/pschoenbi/LoxBerry-Plugin-UniFi2Lox";
$helptemplate = "";

LBWeb::lbheader($template_title, $helplink, $helptemplate);
?>
<style>
.u2l{--u2l-accent:#6dac20;--u2l-line:rgba(127,127,127,.28);--u2l-soft:rgba(127,127,127,.08);--u2l-muted:rgba(127,127,127,1);
     max-width:1100px;margin:0 auto;padding:4px 2px 40px;font-size:15px;line-height:1.45}
.u2l *{box-sizing:border-box}
.u2l h2{font-size:18px;margin:28px 0 10px;font-weight:600}
.u2l .u2l-sub{color:var(--u2l-muted);font-size:13px;margin:-6px 0 12px}
.u2l .u2l-box{border:1px solid var(--u2l-line);border-radius:10px;padding:16px;margin-bottom:14px;background:var(--u2l-soft)}
.u2l .u2l-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px 16px}
.u2l label.u2l-f{display:flex;flex-direction:column;gap:4px;font-size:13px;font-weight:600}
.u2l label.u2l-f small{font-weight:400;color:var(--u2l-muted)}
.u2l input[type=text],.u2l input[type=password],.u2l input[type=number],.u2l select{
     width:100%;padding:8px 10px;border:1px solid var(--u2l-line);border-radius:6px;font:inherit;background:transparent;color:inherit}
.u2l select option{color:#000}
.u2l .u2l-chk{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:500;cursor:pointer}
.u2l .u2l-btn{display:inline-flex;align-items:center;gap:6px;padding:8px 14px;border-radius:6px;border:1px solid var(--u2l-line);
     background:transparent;color:inherit;font:inherit;font-size:14px;cursor:pointer;text-decoration:none}
.u2l .u2l-btn:hover{border-color:var(--u2l-accent)}
.u2l .u2l-btn.primary{background:var(--u2l-accent);border-color:var(--u2l-accent);color:#fff;font-weight:600}
.u2l .u2l-btn.small{padding:4px 10px;font-size:13px}
.u2l .u2l-row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.u2l .u2l-status{display:flex;flex-wrap:wrap;gap:16px;align-items:center;padding:12px 16px;border-radius:10px;border:1px solid var(--u2l-line)}
.u2l .dot{width:10px;height:10px;border-radius:50%;display:inline-block;background:#999;margin-right:6px;vertical-align:middle}
.u2l .dot.ok{background:#3fae2a}.u2l .dot.bad{background:#d9442b}.u2l .dot.idle{background:#d8a21c}
.u2l .u2l-cam{border:1px solid var(--u2l-line);border-radius:10px;margin-bottom:14px;overflow:hidden}
.u2l .u2l-cam-head{display:flex;gap:12px;align-items:center;padding:12px 16px;background:var(--u2l-soft);flex-wrap:wrap}
.u2l .u2l-cam-head .name{font-weight:600;font-size:16px;flex:1;min-width:150px}
.u2l .u2l-cam-body{padding:16px;display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:20px}
@media (max-width:820px){.u2l .u2l-cam-body{grid-template-columns:1fr}}
.u2l .u2l-prev{width:100%;aspect-ratio:16/9;background:#111;border-radius:8px;display:flex;align-items:center;justify-content:center;
     color:#aaa;font-size:13px;overflow:hidden;position:relative}
.u2l .u2l-prev img{width:100%;height:100%;object-fit:contain}
.u2l .u2l-prev .meta{position:absolute;left:6px;bottom:6px;background:rgba(0,0,0,.6);color:#fff;padding:2px 6px;border-radius:4px;font-size:11px}
.u2l .u2l-urls{margin-top:14px;display:flex;flex-direction:column;gap:8px}
.u2l .u2l-url{display:grid;grid-template-columns:110px minmax(0,1fr) auto;gap:8px;align-items:center;font-size:13px}
.u2l .u2l-url code{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;padding:6px 8px;border-radius:6px;
     border:1px dashed var(--u2l-line);overflow-x:auto;white-space:nowrap;display:block}
.u2l .u2l-tag{font-size:11px;padding:2px 8px;border-radius:20px;border:1px solid var(--u2l-line);color:var(--u2l-muted)}
.u2l details summary{cursor:pointer;font-weight:600;margin:6px 0}
.u2l pre.u2l-log{max-height:340px;overflow:auto;font-size:12px;padding:10px;border-radius:8px;background:#111;color:#ddd;white-space:pre-wrap}
.u2l .u2l-msg{position:fixed;right:16px;bottom:16px;padding:10px 16px;border-radius:8px;background:#222;color:#fff;font-size:14px;
     box-shadow:0 4px 18px rgba(0,0,0,.3);z-index:9999;display:none;max-width:420px}
.u2l .u2l-msg.err{background:#a52a1a}
.u2l .u2l-steps li{margin-bottom:6px}
.u2l .u2l-savebar{position:sticky;bottom:0;padding:12px 0;display:flex;justify-content:flex-end;gap:8px;background:inherit}
.u2l .hidden{display:none!important}
</style>

<div class="u2l" id="u2l" data-role="none">

  <div class="u2l-status" id="statusbar">
    <span><span class="dot" id="st-dot"></span><b id="st-text"><?=T('ST_LOADING')?></b></span>
    <span class="u2l-tag" id="st-ver"></span>
    <span class="u2l-tag" id="st-load"></span>
    <span style="flex:1"></span>
    <button class="u2l-btn small" data-role="none" onclick="svc('restart')"><?=T('BTN_RESTART')?></button>
    <button class="u2l-btn small" data-role="none" onclick="svc('stop')"><?=T('BTN_STOP')?></button>
  </div>

  <h2><?=T('H_PROTECT')?></h2>
  <p class="u2l-sub"><?=TH('SUB_PROTECT')?></p>
  <div class="u2l-box">
    <div class="u2l-grid">
      <label class="u2l-f"><?=T('F_HOST')?>
        <input type="text" id="p-host" placeholder="192.168.1.1" data-role="none"></label>
      <label class="u2l-f"><?=T('F_APIKEY')?> <small id="p-keyhint"></small>
        <input type="password" id="p-key" placeholder="••••••••" autocomplete="new-password" data-role="none"></label>
      <label class="u2l-f"><?=T('F_TRANSPORT')?>
        <select id="p-transport" data-role="none">
          <option value="rtspx"><?=T('OPT_RTSPX')?></option>
          <option value="rtsp"><?=T('OPT_RTSP')?></option>
        </select></label>
    </div>
    <div class="u2l-row" style="margin-top:14px">
      <label class="u2l-chk"><input type="checkbox" id="p-verify" data-role="none"> <?=T('F_VERIFY')?></label>
      <span style="flex:1"></span>
      <button class="u2l-btn" data-role="none" onclick="testApi()"><?=T('BTN_TEST')?></button>
      <button class="u2l-btn primary" data-role="none" onclick="discover()"><?=T('BTN_DISCOVER')?></button>
    </div>
    <div id="disc" class="hidden" style="margin-top:14px"></div>
  </div>

  <h2><?=T('H_CAMS')?></h2>
  <p class="u2l-sub"><?=T('SUB_CAMS')?></p>
  <div id="cams"></div>
  <button class="u2l-btn" data-role="none" onclick="addManual()"><?=T('BTN_ADD_MANUAL')?></button>

  <h2><?=T('H_LOXONE')?></h2>
  <div class="u2l-box">
    <ol class="u2l-steps">
      <li><?=TH('LOX_STEP1')?></li>
      <li><?=TH('LOX_STEP2')?></li>
      <li id="h-step3"></li>
      <li><?=TH('LOX_STEP4')?></li>
      <li><?=TH('LOX_STEP5')?></li>
    </ol>
  </div>

  <h2><?=T('H_SERVER')?></h2>
  <div class="u2l-box">
    <div class="u2l-grid">
      <label class="u2l-f"><?=T('F_PORT')?> <input type="number" id="s-port" data-role="none"></label>
      <label class="u2l-f"><?=T('F_USER')?> <input type="text" id="s-user" data-role="none"></label>
      <label class="u2l-f"><?=T('F_PASS')?> <small><?=T('F_PASS_HINT')?></small>
        <div class="u2l-row" style="flex-wrap:nowrap">
          <input type="password" id="s-pass" autocomplete="new-password" data-role="none">
          <button class="u2l-btn small" data-role="none" onclick="togglePw()" title="<?=T('F_SHOW')?>">👁</button></div></label>
      <label class="u2l-f"><?=T('F_HW')?>
        <select id="s-hw" data-role="none">
          <option value="off"><?=T('OPT_HW_OFF')?></option>
          <option value="auto"><?=T('OPT_HW_AUTO')?></option>
          <option value="vaapi"><?=T('OPT_HW_VAAPI')?></option>
          <option value="rkmpp"><?=T('OPT_HW_RKMPP')?></option>
        </select></label>
      <label class="u2l-f"><?=T('F_CACHE')?> <small><?=T('F_CACHE_HINT')?></small>
        <input type="number" id="s-cache" min="0" max="10000" step="100" data-role="none"></label>
      <label class="u2l-f"><?=T('F_LOGLEVEL')?>
        <select id="s-log" data-role="none"><option>error</option><option>warn</option><option>info</option><option>debug</option></select></label>
    </div>
    <div class="u2l-row" style="margin-top:14px;gap:22px">
      <label class="u2l-chk"><input type="checkbox" id="s-enabled" data-role="none"> <?=T('F_ENABLED')?></label>
      <label class="u2l-chk"><input type="checkbox" id="s-rtsplan" data-role="none"> <?=T('F_RTSP_LAN')?></label>
      <label class="u2l-chk"><input type="checkbox" id="s-regen" data-role="none"> <?=T('F_REGEN_KEY')?></label>
    </div>
  </div>

  <details>
    <summary><?=T('H_LOG')?></summary>
    <div class="u2l-row" style="margin:6px 0"><button class="u2l-btn small" data-role="none" onclick="loadLog()"><?=T('BTN_REFRESH')?></button></div>
    <pre class="u2l-log" id="log">–</pre>
  </details>

  <div class="u2l-savebar">
    <button class="u2l-btn primary" data-role="none" onclick="save()"><?=T('BTN_SAVE')?></button>
  </div>
  <div class="u2l-msg" id="msg"></div>
</div>

<script>
(function () {
'use strict';
const API = 'ajax.php';
const L = <?=json_encode($U2L_JS, JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_AMP)?>;
const t = (k, ...a) => (L[k] ?? k).replace(/\{(\d)\}/g, (m, i) => a[i] ?? '');
const errText = d => {
  const map = {missing_cred: 'ERR_MISSING_CRED', unauthorized: 'ERR_UNAUTHORIZED', unreachable: 'ERR_UNREACHABLE',
               invalid: 'ERR_INVALID', save: 'ERR_SAVE', no_response: 'ERR_NO_RESPONSE'};
  const base = map[d.code] ? t(map[d.code]) : '';
  return [base, d.error].filter(Boolean).join(' – ') || '?';
};
const svcText = msg => {
  const last = String(msg || '').trim().split('\n').pop().split(' ')[0];
  return L['SVC_' + last] ? t('SVC_' + last) : String(msg || '');
};
let CFG = null, IP = '', FOLDER = 'unifi2lox';
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function toast(text, err) {
  const m = $('msg'); m.textContent = text; m.className = 'u2l-msg' + (err ? ' err' : ''); m.style.display = 'block';
  clearTimeout(m._t); m._t = setTimeout(() => m.style.display = 'none', err ? 7000 : 3500);
}
async function call(action, body, method) {
  const r = await fetch(API + '?action=' + action, {method: body ? 'POST' : (method || 'GET'),
    headers: {'Content-Type': 'application/json'}, body: body ? JSON.stringify(body) : undefined, cache: 'no-store'});
  return r.json();
}

// ---------------------------------------------------------------- load / render
async function load() {
  const d = await call('get');
  CFG = d.config; IP = d.ip; FOLDER = d.folder;
  CFG.cameras.forEach(c => c._saved = true);
  const p = CFG.protect, s = CFG.server;
  $('p-host').value = p.host || ''; $('p-transport').value = p.transport || 'rtspx'; $('p-verify').checked = !!p.verify_ssl;
  $('p-keyhint').textContent = p.has_key ? t('F_KEY_SAVED') : '';
  $('s-port').value = s.port || 1984; $('s-user').value = s.username || 'loxone'; $('s-pass').value = s.password || '';
  $('s-hw').value = s.hwaccel || 'off'; $('s-cache').value = s.snapshot_cache_ms ?? 1000; $('s-log').value = s.loglevel || 'warn';
  $('s-enabled').checked = s.enabled !== false; $('s-rtsplan').checked = !!s.rtsp_lan;
  $('h-step3').innerHTML = t('LOX_STEP3', '<code>' + esc(s.username || 'loxone') + '</code>');
  $('st-ver').textContent = d.go2rtc || t('ST_GO2RTC_MISSING');
  if (!d.ffmpeg) toast(t('MSG_FFMPEG_MISSING'), true);
  renderCams();
  status();
}

function camDefaults(c) {
  return Object.assign({id:'', name:'', slug:'', enabled:true, source:'medium', manual_url:'', width:1280, fps:10,
                        quality:5, rotate:0, snapshot:'api_hq', preload:'rtsp'}, c);
}
function opt(list, val) {
  return list.map(([v, label]) => `<option value="${v}"${String(v) === String(val) ? ' selected' : ''}>${esc(label)}</option>`).join('');
}
function urls(c) {
  const s = CFG.server, port = s.port || 1984, slug = c.slug || '…';
  return {
    video: `http://${IP}:${port}/api/stream.mjpeg?src=${slug}_mjpeg`,
    image: `http://${IP}/plugins/${FOLDER}/snapshot.php?cam=${slug}`,
    imagekey: `http://${IP}/plugins/${FOLDER}/snapshot.php?cam=${slug}&key=${s.snapshot_key || ''}`,
    rtsp: `rtsp://${IP}:8554/${slug}`,
  };
}

function renderCams() {
  const box = $('cams');
  if (!CFG.cameras.length) {
    box.innerHTML = '<div class="u2l-box">' + esc(t('NO_CAMS')) + '</div>';
    return;
  }
  box.innerHTML = CFG.cameras.map((raw, i) => {
    const c = camDefaults(raw), u = urls(c), saved = !!raw._saved;
    return `<div class="u2l-cam" data-i="${i}">
      <div class="u2l-cam-head">
        <label class="u2l-chk"><input type="checkbox" data-k="enabled" ${c.enabled ? 'checked' : ''} data-role="none"></label>
        <span class="name">${esc(c.name || c.slug)}</span>
        <span class="u2l-tag" id="cs-${i}">–</span>
        <button class="u2l-btn small" data-role="none" onclick="u2l.remove(${i})">${t('BTN_REMOVE')}</button>
      </div>
      <div class="u2l-cam-body">
        <div>
          <div class="u2l-grid">
            <label class="u2l-f">${t('F_NAME')} <input type="text" data-k="name" value="${esc(c.name)}" data-role="none"></label>
            <label class="u2l-f">${t('F_SLUG')} <input type="text" data-k="slug" value="${esc(c.slug)}" placeholder="${esc(t('F_SLUG_PH'))}" data-role="none"></label>
            ${c.id ? `<label class="u2l-f">${t('F_SOURCE')} <small>${t('F_SOURCE_HINT')}</small>
              <select data-k="source" data-role="none">${opt([['high',t('OPT_SRC_HIGH')],['medium',t('OPT_SRC_MEDIUM')],['low',t('OPT_SRC_LOW')],['package',t('OPT_SRC_PACKAGE')]], c.source)}</select></label>`
            : `<label class="u2l-f" style="grid-column:1/-1">${t('F_MANUAL_URL')} <small>${t('F_MANUAL_URL_HINT')}</small>
              <input type="text" data-k="manual_url" value="${esc(c.manual_url)}" placeholder="rtsps://192.168.1.1:7441/abc123?enableSrtp" data-role="none"></label>`}
            <label class="u2l-f">${t('F_WIDTH')}
              <select data-k="width" data-role="none">${opt([[0,t('OPT_ORIGINAL')],[1920,'1920 (Full HD)'],[1280,'1280 (HD) – '+t('RECOMMENDED')],[960,'960'],[640,'640 ('+t('OPT_FAST')+')']], c.width)}</select></label>
            <label class="u2l-f">${t('F_FPS')}
              <select data-k="fps" data-role="none">${opt([[5,'5'],[8,'8'],[10,'10 – '+t('RECOMMENDED')],[12,'12'],[15,'15'],[20,'20'],[25,'25']], c.fps)}</select></label>
            <label class="u2l-f">${t('F_QUALITY')} <small>${t('F_QUALITY_HINT')}</small>
              <select data-k="quality" data-role="none">${opt([2,3,5,7,10,15].map(q => [q, q + ' – ' + t('OPT_Q' + q)]), c.quality)}</select></label>
            <label class="u2l-f">${t('F_SNAPSHOT')}
              <select data-k="snapshot" data-role="none">${opt([['api_hq',t('OPT_SNAP_API_HQ')],['api',t('OPT_SNAP_API')],['go2rtc',t('OPT_SNAP_STREAM')]], c.snapshot)}</select></label>
            <label class="u2l-f">${t('F_PRELOAD')} <small>${t('F_PRELOAD_HINT')}</small>
              <select data-k="preload" data-role="none">${opt([['none',t('OPT_PRE_NONE')],['rtsp',t('OPT_PRE_RTSP')],['mjpeg',t('OPT_PRE_MJPEG')]], c.preload)}</select></label>
            <label class="u2l-f">${t('F_ROTATE')}
              <select data-k="rotate" data-role="none">${opt([[0,'0°'],[90,'90°'],[180,'180°'],[270,'270°']], c.rotate)}</select></label>
          </div>
          <div class="u2l-urls">
            ${[[t('URL_VIDEO'), u.video], [t('URL_IMAGE'), u.image], [t('URL_IMAGE_KEY'), u.imagekey]].concat(CFG.server.rtsp_lan ? [[t('URL_RTSP'), u.rtsp]] : [])
              .map(([label, v]) => `<div class="u2l-url"><span>${label}</span><code>${esc(v)}</code>
                <button class="u2l-btn small" data-role="none" onclick="u2l.copy(this)" data-v="${esc(v)}">${t('BTN_COPY')}</button></div>`).join('')}
            ${saved ? '' : '<small style="color:#d8a21c">' + esc(t('NOT_SAVED')) + '</small>'}
          </div>
        </div>
        <div>
          <div class="u2l-prev" id="pv-${i}">${t('PREVIEW')}</div>
          <div class="u2l-row" style="margin-top:8px">
            <button class="u2l-btn small" data-role="none" onclick="u2l.snap(${i})">${t('BTN_SNAPSHOT')}</button>
            <button class="u2l-btn small" data-role="none" onclick="u2l.live(${i})">${t('BTN_LIVE')}</button>
          </div>
        </div>
      </div></div>`;
  }).join('');
  box.querySelectorAll('[data-k]').forEach(el => el.addEventListener('change', readCams));
}

function readCams() {
  document.querySelectorAll('.u2l-cam').forEach(card => {
    const c = CFG.cameras[+card.dataset.i];
    card.querySelectorAll('[data-k]').forEach(el => {
      const k = el.dataset.k;
      c[k] = el.type === 'checkbox' ? el.checked : (['width','fps','quality','rotate'].includes(k) ? +el.value : el.value);
    });
  });
}

// ---------------------------------------------------------------- actions
function protectInput() { return {host: $('p-host').value.trim(), apikey: $('p-key').value.trim()}; }

window.testApi = async function () {
  toast(t('MSG_TESTING'));
  const d = await call('test', protectInput());
  d.ok ? toast(t('MSG_CONNECTED', d.cameras, d.ms)) : toast(t('MSG_ERROR', errText(d)), true);
};

window.discover = async function () {
  toast(t('MSG_SEARCHING'));
  const d = await call('discover', protectInput());
  const box = $('disc');
  if (!d.ok) { toast(t('MSG_ERROR', errText(d)), true); return; }
  readCams();
  const known = new Set(CFG.cameras.map(c => c.id).filter(Boolean));
  box.classList.remove('hidden');
  box.innerHTML = '<b>' + esc(t('MSG_FOUND')) + '</b><div class="u2l-grid" style="margin-top:8px">' +
    d.cameras.map((c, i) => `<label class="u2l-chk"><input type="checkbox" data-d="${i}" ${known.has(c.id) ? 'disabled checked' : ''} data-role="none">
       <span>${esc(c.name)} <small class="u2l-tag">${esc(c.model)}</small>
       <span class="dot ${c.state === 'CONNECTED' ? 'ok' : 'bad'}"></span></span></label>`).join('') +
    '</div><div class="u2l-row" style="margin-top:10px"><button class="u2l-btn primary small" data-role="none" id="d-add">' + esc(t('BTN_APPLY')) + '</button></div>';
  $('d-add').onclick = () => {
    box.querySelectorAll('input[data-d]:checked:not(:disabled)').forEach(el => {
      const c = d.cameras[+el.dataset.d];
      CFG.cameras.push(camDefaults({id: c.id, name: c.name, slug: c.slug}));
      if (c.has_package) CFG.cameras.push(camDefaults({id: c.id, name: c.name + ' ' + t('PACKAGE_SUFFIX'), slug: c.slug + '_paket', source: 'package', width: 0}));
    });
    box.classList.add('hidden');
    renderCams();
    toast(t('MSG_APPLIED'));
  };
};

window.addManual = function () {
  readCams();
  CFG.cameras.push(camDefaults({name: t('CAM_DEFAULT_NAME', CFG.cameras.length + 1), snapshot: 'go2rtc'}));
  renderCams();
};

window.save = async function () {
  readCams();
  const body = {config: {
    protect: {host: $('p-host').value.trim(), apikey: $('p-key').value.trim(), transport: $('p-transport').value, verify_ssl: $('p-verify').checked},
    server: {enabled: $('s-enabled').checked, port: +$('s-port').value, username: $('s-user').value.trim(), password: $('s-pass').value,
             hwaccel: $('s-hw').value, snapshot_cache_ms: +$('s-cache').value, loglevel: $('s-log').value,
             rtsp_lan: $('s-rtsplan').checked, regen_key: $('s-regen').checked},
    cameras: CFG.cameras.map(c => { const x = Object.assign({}, c); delete x._saved; return x; })
  }};
  toast(t('MSG_SAVING'));
  const d = await call('save', body);
  if (!d.ok) { toast(t('MSG_ERROR', errText(d)), true); return; }
  toast(d.rc === 0 ? t('MSG_SAVED') + ' – ' + svcText(d.service) : t('MSG_SAVED_BUT', svcText(d.service)), d.rc !== 0);
  $('p-key').value = ''; $('s-regen').checked = false;
  await load();
};

window.svc = async function (cmd) {
  const d = await call('service', {cmd});
  toast(svcText(d.msg) || cmd, !d.ok);
  setTimeout(status, 800);
};

window.togglePw = function () { const e = $('s-pass'); e.type = e.type === 'password' ? 'text' : 'password'; };

async function status() {
  try {
    const d = await call('status');
    $('st-dot').className = 'dot ' + (d.running ? 'ok' : 'bad');
    $('st-text').textContent = d.running ? t('ST_RUNNING') : t('ST_STOPPED');
    $('st-load').textContent = d.load !== null ? t('ST_LOAD', d.load) : '';
    d.streams.forEach(s => {
      const i = CFG.cameras.findIndex(c => c.slug === s.slug);
      const el = $('cs-' + i); if (!el) return;
      const src = s.source, mj = s.mjpeg;
      let txt = t('CAM_INACTIVE');
      if (src && src.active) txt = t('CAM_CONNECTED') + (src.medias.length ? ' · ' + src.medias.filter(m => /video|h26|hevc/i.test(m)).slice(0,1).join('') : '');
      if (mj && mj.consumers) txt += ' · ' + t('CAM_VIEWERS', mj.consumers);
      el.textContent = txt;
    });
  } catch (e) { $('st-text').textContent = t('ST_UNKNOWN'); $('st-dot').className = 'dot bad'; }
}

window.loadLog = async function () { const d = await call('log'); $('log').textContent = d.log || t('LOG_EMPTY'); const l = $('log'); l.scrollTop = l.scrollHeight; };

window.u2l = {
  remove(i) { readCams(); CFG.cameras.splice(i, 1); renderCams(); toast(t('MSG_REMOVED')); },
  copy(btn) {
    const v = btn.dataset.v;
    const done = () => { btn.textContent = '✓'; setTimeout(() => btn.textContent = t('BTN_COPY'), 1200); };
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(v).then(done);
    else { const ta = document.createElement('textarea'); ta.value = v; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove(); done(); }
  },
  async snap(i) {
    const c = CFG.cameras[i], pv = $('pv-' + i);
    if (!c._saved) { toast(t('MSG_SAVE_FIRST'), true); return; }
    pv.textContent = t('MSG_LOADING');
    const t0 = performance.now();
    const r = await fetch(API + '?action=preview&cam=' + encodeURIComponent(c.slug) + '&t=' + Date.now());
    if (!r.ok) { pv.textContent = t('MSG_NO_IMAGE'); return; }
    const b = await r.blob(), url = URL.createObjectURL(b), img = new Image();
    img.onload = () => {
      pv.innerHTML = ''; pv.appendChild(img);
      const m = document.createElement('span'); m.className = 'meta';
      m.textContent = `${img.naturalWidth}×${img.naturalHeight} · ${Math.round(b.size/1024)} kB · ${r.headers.get('X-Fetch-Ms') || Math.round(performance.now()-t0)} ms`;
      pv.appendChild(m);
    };
    img.src = url;
  },
  live(i) {
    const c = CFG.cameras[i], pv = $('pv-' + i);
    if (!c._saved) { toast(t('MSG_SAVE_FIRST'), true); return; }
    const t0 = performance.now(), img = new Image();
    pv.textContent = t('MSG_STREAM_STARTING');
    img.onload = () => {
      if (img.parentNode) return;
      pv.innerHTML = ''; pv.appendChild(img);
      const m = document.createElement('span'); m.className = 'meta';
      m.textContent = t('MSG_LIVE_FIRST', Math.round(performance.now() - t0)); pv.appendChild(m);
    };
    img.onerror = () => pv.textContent = t('MSG_STREAM_FAILED');
    img.src = API + '?action=stream&cam=' + encodeURIComponent(c.slug) + '&t=' + Date.now();
  },
};

load();
setInterval(status, 10000);
})();
</script>
<?php
LBWeb::lbfooter();
?>
