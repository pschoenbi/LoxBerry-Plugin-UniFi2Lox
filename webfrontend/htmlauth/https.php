<?php
require_once 'loxberry_system.php';
require_once 'loxberry_web.php';
LBWeb::lbheader('UniFi2Lox — HTTPS', 'https://github.com/pschoenbi/LoxBerry-Plugin-UniFi2Lox', '');
?>
<style>
#https{max-width:1000px;margin:auto;padding:16px;line-height:1.5}#https fieldset{border:1px solid #999;border-radius:8px;padding:16px;margin:16px 0}#https label{display:block;margin:12px 0}#https input:not([type=checkbox]),#https select{display:block;width:100%;max-width:620px;padding:8px;box-sizing:border-box}#https button,#https a.button{display:inline-block;padding:10px 16px;margin:6px 6px 6px 0;cursor:pointer}#https pre{white-space:pre-wrap;overflow-wrap:anywhere;background:rgba(127,127,127,.12);padding:12px}#https .note{color:#666}#https .warning{border-left:4px solid #d99500;padding-left:12px}#https [hidden]{display:none!important}#https #message{padding:12px;font-weight:bold}#https code{overflow-wrap:anywhere}#https .links{margin-bottom:18px}
</style>
<div id="https" data-role="none">
<a href="index.php">← Camera settings</a>
<h2>Remote camera access</h2>
<p>Use your VPN, an existing reverse proxy, or let this plugin serve HTTPS itself. Existing local camera links keep working. HTTPS is disabled until you explicitly enable it.</p>
<p class="warning">Experimental: test via mobile internet in the Loxone app before relying on remote access. Keep LoxBerry administration, port 1984 and RTSP private.</p>
<div id="message" role="status" aria-live="polite"></div>
<fieldset><legend>Connection</legend>
<label>Access method<select id="mode" data-role="none"><option value="off">Local network / VPN only</option><option value="managed">HTTPS managed by this plugin</option><option value="external">Existing reverse proxy</option></select></label>
<div id="managed">
<label>Camera hostname<input id="domain" type="text" placeholder="camera.example.com" autocomplete="off" data-role="none"></label>
<label>HTTPS port on this LoxBerry<input id="listen_port" type="number" min="1024" max="65535" data-role="none"></label>
<label>External HTTPS port<input id="public_port" type="number" min="1" max="65535" data-role="none"></label>
<p class="note">Forward the external TCP port to the HTTPS port above. No port 80 forwarding is needed for DNS validation. Create a DNS A/AAAA record pointing to your reachable internet address; dynamic DNS is separate. With Cloudflare, use DNS only for the camera hostname.</p>
<details><summary>Local snapshot server</summary><label>LoxBerry HTTP port<input id="snapshot_port" type="number" min="1" max="65535" data-role="none"></label><p>Used only on loopback to fetch snapshots. The external endpoint always requires the camera username and password.</p></details>
</div>
<div id="external"><label>External HTTPS origin<input id="external_url" type="text" placeholder="https://camera.example.com" data-role="none"></label><p>Your proxy must implement the fixed <code>/camera/SLUG/video.mjpeg</code> and <code>/camera/SLUG/snapshot.jpg</code> routes and authentication described in the documentation. Entering an address does not configure your proxy.</p></div>
</fieldset>
<fieldset id="cert"><legend>Certificate</legend>
<label>Certificate method<select id="certificate_mode" data-role="none"><option value="dns">Automatic DNS validation</option><option value="manual">Manual DNS TXT challenge (any DNS provider)</option><option value="import">Import an existing certificate</option></select></label>
<div id="acme">
<label>Email for the certificate account<input id="email" type="email" data-role="none"></label>
<label>Certificate DNS resolvers (optional)<input id="dns_resolvers" type="text" placeholder="1.1.1.1:53" autocomplete="off" data-role="none"></label>
<p class="note">Leave blank to use system DNS. If local DNS hides public TXT records, enter a reachable public resolver such as 1.1.1.1:53. Separate multiple IP:port entries with commas; use [IPv6]:port for IPv6. Applies to certificate requests and renewals only; system DNS stays unchanged.</p>
<details id="certificate-advanced"><summary>Advanced certificate testing</summary><label><input id="staging" type="checkbox" data-role="none"> Use Let's Encrypt staging for testing (certificate is NOT trusted by browsers/apps)</label><p class="note">Leave this off for normal use. Changing this setting requires requesting a certificate from the selected environment.</p></details>
<label><input id="terms" type="checkbox" data-role="none"> I accept the <a href="https://letsencrypt.org/repository/" target="_blank" rel="noopener noreferrer">Let's Encrypt terms</a> and authorize requests for this hostname.</label>
</div>
<div id="dns"><label>DNS provider<select id="provider" data-role="none"></select></label><p id="provider-help"></p><div id="credentials"></div><label><input id="clear_credentials" type="checkbox" data-role="none"> Remove all saved DNS credentials</label><p class="note">Credentials stay on this LoxBerry and are never returned to the browser. Leave fields blank to keep saved values. Enter tokens here, never in a support chat.</p></div>
<p id="manual-note" class="warning">Manual DNS validation cannot renew unattended. The plugin shows a new TXT record when validation is required. Check the expiry status and request renewal before it expires. A pending challenge times out after 30 minutes.</p>
<div id="import"><label>Certificate chain (PEM)<input type="file" id="certificate-file" accept=".pem,.crt,.cer" data-role="none"></label><label>Unencrypted private key (PEM)<input type="file" id="key-file" accept=".pem,.key" data-role="none"></label><p class="warning">Imported certificates must be renewed and imported again by you. Upload private keys only over a trusted local connection or VPN.</p></div>
</fieldset>
<p>Saving stops the external HTTPS service. After saving, obtain a certificate and click Enable / apply HTTPS. Local playback is unaffected.</p>
<button id="save" data-role="none">Save settings</button>
<button id="install" data-role="none">Install HTTPS tools</button>
<button id="issue" data-role="none">Request / renew certificate</button>
<button id="upload" data-role="none">Import certificate</button>
<button id="apply" data-role="none">Enable / apply HTTPS</button>
<button id="disable" data-role="none">Disable HTTPS</button>
<fieldset><legend>Status</legend><pre id="status"></pre><p id="expiry" class="warning" hidden></p>
<div id="challenge" hidden><p>Add the following TXT record at your DNS provider. Do not replace unrelated TXT values at the same name.</p><pre id="record"></pre><button id="confirm" data-role="none">TXT record is in place — validate</button><p id="cleanup" hidden>The request finished. You can remove this specific TXT value.</p></div>
</fieldset>
<h3>External camera links</h3><p>Use the camera username and password from the main plugin settings. These links do not contain credentials.</p><div id="links"></div>
</div>
<script src="https.js?v=1.1.2.5"></script>
<?php LBWeb::lbfooter(); ?>
