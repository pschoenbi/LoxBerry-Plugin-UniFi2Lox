(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const fields = ['mode','domain','listen_port','public_port','snapshot_port','certificate_mode','provider','email','staging','terms','external_url','dns_resolvers'];
  let state, busy = false, dirty = false;
  async function api(action, data) {
    const options = action === 'status' ? {} : {method:'POST', headers:{'Content-Type':'application/json','X-U2L-HTTPS':'1'}, body:JSON.stringify(data || {})};
    const response = await fetch('https-api.php?action=' + action, {...options, cache:'no-store', credentials:'same-origin'});
    const result = await response.json();
    if (!result.ok) throw new Error(result.error || 'Operation failed.');
    return result;
  }
  function show(message) { $('message').textContent = message; }
  function visibility() {
    const managed = $('mode').value === 'managed', method = $('certificate_mode').value;
    $('managed').hidden = !managed;
    $('external').hidden = $('mode').value !== 'external';
    $('cert').hidden = !managed;
    $('acme').hidden = method === 'import';
    $('dns').hidden = method !== 'dns';
    $('manual-note').hidden = method !== 'manual';
    $('import').hidden = method !== 'import';
    for (const id of ['install','apply','disable']) $(id).hidden = !managed;
    $('issue').hidden = !managed || method === 'import';
    $('upload').hidden = !managed || method !== 'import';
  }
  function providerFields() {
    const p = state.providers[$('provider').value];
    $('provider-help').textContent = p.help;
    $('credentials').replaceChildren();
    for (const field of p.fields) {
      const label = document.createElement('label'), input = document.createElement('input');
      label.textContent = field + (state.has_credentials[field] ? ' (saved)' : '');
      input.type = 'password'; input.dataset.field = field; input.autocomplete = 'new-password'; input.setAttribute('data-role','none');
      input.addEventListener('input', () => {dirty = true;});
      label.append(input); $('credentials').append(label);
    }
  }
  async function refresh(load = false) {
    state = await api('status');
    if (load) {
      $('provider').replaceChildren();
      for (const [code,p] of Object.entries(state.providers)) {
        const option = document.createElement('option'); option.value = code; option.textContent = p.name; $('provider').append(option);
      }
      for (const key of fields) {
        const el = $(key); if (el.type === 'checkbox') el.checked = state.settings[key]; else el.value = state.settings[key];
      }
      $('certificate-advanced').open = state.settings.staging;
      providerFields(); visibility(); dirty = false;
    }
    const cert = state.certificate;
    const renewal = state.renewal;
    const renewalText = renewal.enabled
      ? 'Automatic renewal: active — from 30 days before expiry; next attempt no earlier than ' + new Date(renewal.next_attempt_at * 1000).toLocaleString()
      : 'Automatic renewal: inactive — ' + renewal.reason;
    $('status').textContent = [
      'HTTPS service: ' + (state.running ? 'running' : 'stopped'),
      'Tools: ' + Object.entries(state.tools).map(([k,v]) => k + (v ? ' installed' : ' missing')).join(', '),
      cert ? (cert.error || 'Certificate expires: ' + new Date(cert.expires * 1000).toLocaleString() + (cert.staging ? ' — STAGING / NOT TRUSTED' : '')) : 'No certificate installed.',
      state.service.error || '',
      renewalText,
      renewal.last_success ? 'Last successful automatic renewal check: ' + new Date(renewal.last_success * 1000).toLocaleString() : '',
      renewal.result === 'failed' ? 'Last automatic renewal failed: ' + renewal.message + ' The existing certificate is retained; retry after 12 hours.' : '',
      state.job.phase ? 'Certificate/tools job: ' + state.job.phase + (state.job.message ? ' — ' + state.job.message : '') : ''
    ].filter(Boolean).join('\n');
    $('expiry').hidden = !cert || cert.days_remaining > 30 || !!cert.error;
    $('expiry').textContent = cert && 'Certificate expires in ' + cert.days_remaining + ' days. ' + (state.settings.certificate_mode === 'dns' ? 'Automatic renewal is attempted while managed HTTPS is enabled.' : 'Request renewal or import a replacement certificate manually.');
    const challenge = state.job.challenge;
    $('challenge').hidden = !challenge;
    if (challenge) {
      $('record').textContent = 'Type: TXT\nName: ' + challenge.name + '\nValue: ' + challenge.value;
      $('confirm').hidden = state.job.phase !== 'waiting_dns';
      $('cleanup').hidden = !challenge.cleanup;
    }
    $('links').replaceChildren();
    for (const cam of state.links) {
      const box = document.createElement('div'); box.className = 'links';
      const label = document.createElement('strong'); label.textContent = cam.name; box.append(label);
      for (const kind of ['video','snapshot']) {
        const line = document.createElement('div'), code = document.createElement('code');
        line.append(kind + ': '); code.textContent = cam[kind]; line.append(code); box.append(line);
      }
      $('links').append(box);
    }
  }
  async function act(action, data, reload = false) {
    if (busy) return;
    if (dirty && !['save','disable'].includes(action)) {show('Save your settings first.'); return;}
    busy = true;
    for (const b of document.querySelectorAll('#https button')) b.disabled = true;
    try {
      const result = await api(action, data);
      if (action === 'save') { $('clear_credentials').checked = false; dirty = false; }
      if (action === 'import') { $('certificate-file').value = ''; $('key-file').value = ''; }
      show(result.job ? 'Operation started. Status will update automatically.' : 'Done.');
      await refresh(reload);
    } catch (e) { show(e.message); }
    finally {busy = false; for (const b of document.querySelectorAll('#https button')) b.disabled = false;}
  }
  $('save').onclick = () => {
    const settings = {}, credentials = {};
    for (const key of fields) {const el = $(key); settings[key] = el.type === 'checkbox' ? el.checked : el.type === 'number' ? Number(el.value) : el.value;}
    for (const el of document.querySelectorAll('[data-field]')) credentials[el.dataset.field] = el.value;
    act('save', {settings, credentials, clear_credentials:$('clear_credentials').checked}, true);
  };
  for (const action of ['install','issue','apply','disable']) $(action).onclick = () => act(action);
  $('confirm').onclick = () => act('confirm', {id:state.job.id, nonce:state.job.challenge.nonce});
  $('upload').onclick = async () => {
    const cert = $('certificate-file').files[0], key = $('key-file').files[0];
    if (!cert || !key || cert.size > 262144 || key.size > 65536) {show('Choose a PEM certificate chain and private key within the size limits.'); return;}
    await act('import', {certificate:await cert.text(), private_key:await key.text()});
  };
  for (const key of fields) $(key).addEventListener('change', () => {dirty = true; if (key === 'provider') providerFields(); visibility();});
  for (const key of fields) $(key).addEventListener('input', () => {dirty = true;});
  $('clear_credentials').addEventListener('change', () => {dirty = true;});
  refresh(true).catch(e => show(e.message));
  setInterval(() => {if (!busy) refresh().catch(e => show(e.message));}, 5000);
})();
