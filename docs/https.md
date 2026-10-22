# Optional managed HTTPS (experimental)

This feature provides a separate camera-only HTTPS listener on LoxBerry. It does
not require Nginx Proxy Manager or change an existing proxy, web server, firewall,
VPN, router, or DNS A/AAAA record. It is disabled by default. Local camera URLs
continue to work. A separate hostname, for example `camera.example.com`, is
recommended. The first administration page is in English.

## Access methods

- **Local/VPN:** no additional listener or dependency downloads.
- **Managed HTTPS:** Caddy serves only fixed, authenticated camera routes. Lego
  obtains certificates independently, so no custom Caddy DNS modules are needed.
- **Existing reverse proxy:** records an external HTTPS origin and displays the
  same fixed camera URLs. This is a configuration aid; it does not configure or
  inspect another proxy. The administrator must implement the routes below.

Caddy and lego are downloaded only when the administrator selects **Install HTTPS
tools**. Versions and platform archive SHA-256 hashes are pinned in
`bin/https-tools.json`. There is no `latest` fallback, shell installer, system-wide
installation or privileged listener. Linux amd64, arm64, ARMv6 and ARMv7 are
included where both official binaries exist. Unsupported architectures retain
local/VPN operation. No new root privileges or sudo rules are installed.

## Certificates

1. **Automatic DNS-01:** initial provider adapters are Cloudflare, DigitalOcean,
   deSEC and DuckDNS. Fields are explicit allowlists, not arbitrary environment
   variables or shell commands. Add further providers to `PROVIDERS`, with tests
   and their official lego documentation. The client supports many more providers,
   but only these configured adapters are exposed by this release.
2. **Manual DNS-01:** works with providers that allow the required TXT record.
   A background job shows the exact name and value, waits for confirmation, and
   then lets lego check propagation and obtain the certificate. It expires after
   30 minutes waiting for input. A failed/interrupted job can be started again;
   stale confirmation tokens cannot confirm a new challenge. The displayed TXT
   value can be removed when the operation finishes. Never replace unrelated TXT
   records at the same name. There is no unattended renewal in manual mode.
3. **Import:** upload a PEM fullchain and an unencrypted PEM private key. Hostname,
   validity period and key matching are checked before activation. The operator
   is responsible for importing replacements and using a publicly trusted chain.
   Imports are not a public-CA trust verification service.

Cloudflare requires a scoped API token with **Zone / DNS / Edit** and
**Zone / Zone / Read** on the relevant zone. Do not use a Global API Key. Keep the
camera hostname in **DNS only** mode. The token edits challenge TXT records; the
plugin does not configure Cloudflare proxying, DDNS or firewall rules.

The UI defaults to Let's Encrypt **production** for normal use. Staging is available
under **Advanced certificate testing** for testing account/challenge handling without
issuing a trusted certificate. Saved staging selections are preserved on upgrade and
the advanced section opens when staging is selected. After a staging test succeeds,
save with staging unchecked, request a production certificate and explicitly enable HTTPS.
Staging and production account/certificate directories are separate. Never disable
certificate verification in Loxone to work around a staging certificate.

Automatic renewal is checked while managed HTTPS is enabled, within 30 days of
expiry, at most once per 12 hours. Lego also applies its ACME renewal checks.
Manual/imported certificates display an expiry warning in the plugin; there is no
email/push notification. Certificate lifetime is read from the certificate rather
than assuming a fixed validity period. Failed issuance does not replace the
active certificate. Successful replacements are validated and loaded without
stopping existing streams. Expired certificates are not served by the watchdog.

## Network and routes

Default internal and external HTTPS port: **8443**. The listener must use an
unprivileged port (1024 or higher). A router can map external 443 or 8443 to it.
DNS validation does not require exposing port 80 or using the existing proxy on
443. If another service owns external TCP 443, choose a different external port
and include it in the public URL. A public reachable address is still required
for port forwarding; DNS validation does not solve CGNAT or blocked inbound traffic.

Only configured, enabled cameras have routes:

| Public HTTPS path | Fixed loopback backend |
| --- | --- |
| `/camera/SLUG/video.mjpeg` | `http://127.0.0.1:GO2RTC_PORT/api/stream.mjpeg?src=SLUG_mjpeg` |
| `/camera/SLUG/snapshot.jpg` | `http://127.0.0.1:LOXBERRY_HTTP_PORT/plugins/PLUGIN_FOLDER/snapshot.php?cam=SLUG` |

Requests must use the configured hostname and the camera username/password from
the main plugin settings. Authentication is enforced **before** the loopback
proxy, since both current backends allow loopback requests without authentication.
Only GET/HEAD are allowed. The complete incoming query is replaced by the fixed
backend query. No arbitrary source URLs, stream selectors or administrative API
routes are forwarded. Cookies and Authorization are removed after authentication.
Caddy's admin API uses a private Unix socket, not an additional TCP port. Caddy's
HTTP/3 listener and automatic port-80 redirects are disabled.

An existing reverse proxy must enforce these same restrictions and fixed rewrites,
including authentication before proxying. Do not proxy the whole go2rtc API or the
LoxBerry administration interface to the internet. Direct forwarding of go2rtc's
1984 or RTSP's 8554 is not part of this feature.

## Installation and operation

Back up all plugin directories before installing. Open **HTTPS / Remote access**
from the camera page. Save settings, install tools, obtain/import a certificate,
and use **Enable / apply HTTPS**. Saving connection settings stops external HTTPS
until explicitly applied again. Ordinary camera-service stop/restart also controls
the gateway; the minute watchdog reconciles camera/password changes. **Disable
HTTPS** persists across restarts and also cancels pending certificate validation.
Local playback is unaffected by failures in the optional HTTPS service.

All HTTPS settings, account keys, certificates, DNS credentials, tool binaries and
private state live in `config/plugins/PLUGIN_FOLDER/https` (directory mode 0700,
files 0600, binaries 0700), included by the plugin's existing configuration backup.
Do not publish these backups. Credentials are passed to lego using secret files,
never command-line arguments, and never returned by the administration endpoint.
A failed client command produces a generic UI error rather than publishing its
potentially sensitive output. The HTTPS administration API requires same-origin
JSON POSTs with a custom header for mutations and never enables CORS.

Cancel/finish any certificate job before upgrading. The pre-upgrade check rejects
an upgrade while a job owns the operation lock. A manual job interrupted by a
reboot must be restarted. Disable HTTPS before uninstalling. To roll back just
external access, use **Disable HTTPS**; no router/NPM changes are made by the
plugin. To roll back the package, stop it and restore the saved plugin directories,
omitting stale process IDs, before restarting the old version.

## Validation and remaining release gates

Run the unit and optional real-Caddy integration tests:

```sh
python3 -m unittest discover -s tests -v
U2L_TEST_CADDY=/absolute/path/to/caddy python3 -m unittest discover -s tests -v
```

Integration tests use a generated temporary certificate and loopback camera stub.
They verify TLS, rejected unauthenticated requests, fixed queries, inaccessible
admin/disabled-camera routes, stripped credentials, graceful certificate reload,
failed certificate import preservation and occupied-port handling. Other tests
cover credentials, settings, operation locks, manual confirmation and renewal
scheduling. These tests do not demonstrate live DNS-provider API compatibility.

Confirmed on the SOYO LoxBerry test installation: Cloudflare staging and production
issuance, authenticated HTTPS snapshot/video, unauthenticated HTTP 401 responses,
remote playback in the Loxone app, and recovery after a complete LoxBerry reboot.
The combined local test package passed 32 automated tests, including the existing
VAAPI tests. This HTTPS branch is separate from the VAAPI branch.

Before marking a PR ready for production:

- Test manual DNS issuance, cancellation, reboot interruption and renewal.
- Test each additional provider with an appropriately scoped test account.
- Broaden mobile playback/reconnect testing to other supported Loxone app versions.
- Exercise renewal and LoxBerry upgrade/rollback with real installation hooks.
- Review dependency footprint and platform compatibility with the maintainer;
  complete UI translations if required by the project.

References: [lego DNS providers](https://go-acme.github.io/lego/dns/),
[lego exec provider](https://go-acme.github.io/lego/dns/exec/),
[Cloudflare token requirements](https://go-acme.github.io/lego/dns/cloudflare/),
[Caddy JSON configuration](https://caddyserver.com/docs/json/).

### Certificate DNS resolvers

The optional Certificate DNS resolvers field accepts comma-separated IP:port values,
for example `1.1.1.1:53` or `[2606:4700:4700::1111]:53`. Blank preserves system DNS.
This applies to automated and manual DNS certificate requests and renewals, not the
host resolver configuration. Use a reachable resolver returning public DNS records;
outbound DNS access is required. Propagation verification remains enabled.

During the SOYO test, the local resolver did not return the challenge
TXT record. Retrying against 1.1.1.1 completed Cloudflare staging issuance successfully.
The user subsequently confirmed production HTTPS, snapshot/video access, rejection without credentials, remote Loxone playback and HTTPS after a full reboot. A real CA renewal remains unverified.

### Automatic renewal status and recovery

Automatic renewal is enabled whenever managed HTTPS is enabled with automatic DNS
validation and an active certificate matching the hostname and staging selection.
No extra cron job is needed: the plugin's existing minute watchdog schedules it.
The status page shows whether renewal is active, the earliest next attempt, the
last successful automatic check and any failed attempt. The configured DNS resolver
and saved provider credentials are reused. Manual TXT and imported certificates
still require intervention. The camera service must remain enabled.

The scheduler starts at 30 days before expiry and retries at most every 12 hours.
Attempt timestamps survive reboot. Overlapping watchdogs cannot enqueue duplicate
renewals, and a busy job does not consume the retry window. Successful issuance
validates the certificate/key before reloading the running gateway. Failed issuance
keeps the old certificate; an expired certificate is not served. No forced
production renewal is performed during installation.

Local tests exercise failure/retry, restart persistence, both DNS validation modes'
resolver arguments, and automatic worker success/failure against a real local HTTPS
gateway with simulated certificate issuance. These do not replace a real ACME
renewal test.
