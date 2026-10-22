#!/usr/bin/env python3
"""Optional, unprivileged HTTPS gateway. No access to the go2rtc administration API.

Caddy serves only fixed per-camera routes. Lego manages certificates separately,
including an interactive DNS-01 hook. All mutable state lives in config/https so
LoxBerry's existing upgrade backup preserves keys, accounts and downloaded tools.
"""
import contextlib
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request

BIN = Path(__file__).resolve().parent
PROVIDERS = {
    'cloudflare': {'name': 'Cloudflare', 'fields': ['CF_DNS_API_TOKEN'],
                   'help': 'Token restricted to your zone: Zone DNS Edit and Zone Read.'},
    'digitalocean': {'name': 'DigitalOcean', 'fields': ['DO_AUTH_TOKEN'],
                     'help': 'DNS API token with permission to manage the selected zone.'},
    'desec': {'name': 'deSEC', 'fields': ['DESEC_TOKEN'],
              'help': 'DNS API token with permission to manage the selected zone.'},
    'duckdns': {'name': 'DuckDNS', 'fields': ['DUCKDNS_TOKEN'],
                'help': 'DuckDNS account token. Use your own DuckDNS hostname.'},
}
DEFAULTS = dict(mode='off', domain='', listen_port=8443, public_port=8443,
                snapshot_port=80, certificate_mode='dns', provider='cloudflare',
                email='', staging=False, terms=False, external_url='', dns_resolvers='')
CA = {'staging': 'https://acme-staging-v02.api.letsencrypt.org/directory',
      'production': 'https://acme-v02.api.letsencrypt.org/directory'}
RENEW_BEFORE = 30 * 86400
RENEW_RETRY = 12 * 3600


class Error(Exception):
    pass


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return {} if default is None else default


def private_dir(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def write_private(path, value):
    """Atomic replacement, including on failed writes. Never reuse permissive modes."""
    path = Path(path)
    private_dir(path.parent)
    data = json.dumps(value, indent=2) + '\n' if not isinstance(value, (str, bytes)) else value
    if isinstance(data, str):
        data = data.encode()
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix='.new-')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextlib.contextmanager
def lock(path, blocking=False):
    private_dir(path.parent)
    with path.open('a+') as f:
        os.chmod(path, 0o600)
        try:
            fcntl.flock(f, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError:
            raise Error('Another HTTPS operation is still running.')
        yield


def domain_name(value):
    value = str(value).strip().lower().rstrip('.')
    if len(value) > 253 or '.' not in value or not re.fullmatch(
            r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', value):
        raise Error('Enter a public DNS hostname, without scheme, port or wildcard.')
    if any(len(x) > 63 or not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?', x)
           for x in value.split('.')):
        raise Error('Invalid DNS hostname.')
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return value
    raise Error('Use a DNS hostname, not an IP address.')


def port(value, low=1):
    try:
        result = int(value)
    except (ValueError, TypeError):
        raise Error('Invalid port.')
    if not low <= result <= 65535:
        raise Error('Port must be between %s and 65535.' % low)
    return result


def validate_settings(data):
    c = dict(DEFAULTS)
    c.update({k: v for k, v in data.items() if k in DEFAULTS})
    if c['mode'] not in ('off', 'managed', 'external'):
        raise Error('Invalid HTTPS mode.')
    if c['certificate_mode'] not in ('dns', 'manual', 'import'):
        raise Error('Invalid certificate method.')
    if c['provider'] not in PROVIDERS:
        raise Error('Unsupported DNS provider.')
    raw = c['dns_resolvers']
    if not isinstance(raw, str) or len(raw) > 512:
        raise Error('Invalid DNS resolvers.')
    resolvers = []
    if raw.strip():
        for item in raw.split(','):
            item = item.strip()
            try:
                address, separator, number = item.rpartition(':')
                if not separator or not number.isascii() or not number.isdecimal():
                    raise ValueError()
                ip = ipaddress.ip_address(address[1:-1] if address.startswith('[') and address.endswith(']') else address)
                if ip.version == 6 and not (address.startswith('[') and address.endswith(']')):
                    raise ValueError()
                if '%' in address:
                    raise ValueError()
                number = port(number)
                resolvers.append(('[' + str(ip) + ']' if ip.version == 6 else str(ip)) + ':' + str(number))
            except (ValueError, Error):
                raise Error('Use DNS resolver IP:port, for example 1.1.1.1:53 or [2606:4700:4700::1111]:53.')
        if len(resolvers) > 4:
            raise Error('Use at most four DNS resolvers.')
    c['dns_resolvers'] = ','.join(resolvers)
    for key in ('staging', 'terms'):
        if not isinstance(c[key], bool):
            raise Error('Invalid boolean setting.')
    c['listen_port'] = port(c['listen_port'], 1024)
    c['public_port'] = port(c['public_port'])
    c['snapshot_port'] = port(c['snapshot_port'])
    if c['listen_port'] == c['snapshot_port']:
        raise Error('HTTPS and the local snapshot server need different ports.')
    if c['domain'] or c['mode'] == 'managed':
        c['domain'] = domain_name(c['domain'])
    c['email'] = str(c['email']).strip()
    if c['email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', c['email']):
        raise Error('Invalid email address.')
    c['external_url'] = str(c['external_url']).strip().rstrip('/')
    if c['external_url'] or c['mode'] == 'external':
        u = urllib.parse.urlsplit(c['external_url'])
        if (u.scheme != 'https' or not u.hostname or u.username or u.password or
                u.query or u.fragment or u.path or any(x.isspace() for x in c['external_url'])):
            raise Error('Use an HTTPS origin without path, credentials or query.')
        domain_name(u.hostname)
        try:
            if u.port:
                port(u.port)
        except ValueError:
            raise Error('Invalid external port.')
    return c


def certificate_info(cert, key, domain):
    """Check hostname, validity and key match before changing the live gateway."""
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(str(cert), str(key), password=lambda: '')
        info = ssl._ssl._test_decode_cert(str(cert))
        names = [v.lower() for k, v in info.get('subjectAltName', []) if k == 'DNS']
        matches = lambda name: name == domain or (name.startswith('*.') and
            domain.count('.') == name.count('.') and domain.endswith(name[1:]))
        if not any(matches(name) for name in names):
            raise Error('Certificate does not cover this hostname (DNS subjectAltName required).')
        end = ssl.cert_time_to_seconds(info['notAfter'])
        start = ssl.cert_time_to_seconds(info['notBefore'])
        if not start <= time.time() < end:
            raise Error('Certificate is not currently valid.')
        return {'expires': int(end), 'days_remaining': int((end - time.time()) / 86400),
                'subject': domain}
    except (ssl.SSLError, ValueError, OSError):
        raise Error('Certificate, private key or hostname validation failed.')


def gateway_config(settings, plugin, folder, cert, key, password_hash, admin_socket):
    srv = plugin.get('server', {})
    if not srv.get('username') or not srv.get('password'):
        raise Error('Set a camera username and password before enabling HTTPS.')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', str(srv['username'])):
        raise Error('Invalid camera username.')
    upstream_port = port(srv.get('port', 1984), 1024)
    if upstream_port == settings['listen_port']:
        raise Error('HTTPS and go2rtc need different ports.')
    routes = []
    for cam in plugin.get('cameras', []):
        if not cam.get('enabled'):
            continue
        slug = cam.get('slug', '')
        if not re.fullmatch(r'[a-z0-9_]+', slug):
            raise Error('Invalid camera slug; save the camera configuration first.')
        for kind, target, uri in (
                ('video.mjpeg', upstream_port, '/api/stream.mjpeg?src=' + slug + '_mjpeg'),
                ('snapshot.jpg', settings['snapshot_port'],
                 '/plugins/' + folder + '/snapshot.php?cam=' + slug)):
            routes.append({'match': [{'path': ['/camera/' + slug + '/' + kind],
                                      'method': ['GET', 'HEAD']}], 'handle': [
                # An explicit URI replaces user-supplied query parameters. Clients
                # cannot pass arbitrary URLs, stream names or keys to the backend.
                {'handler': 'rewrite', 'uri': uri},
                {'handler': 'reverse_proxy', 'upstreams': [{'dial': '127.0.0.1:%d' % target}],
                 'headers': {'request': {'set': {'Host': ['localhost']},
                                         'delete': ['Authorization', 'Cookie']}},
                 'transport': {'protocol': 'http', 'dial_timeout': '5s',
                               'response_header_timeout': '20s'},
                 'flush_interval': -1}], 'terminal': True})
    routes.append({'handle': [{'handler': 'static_response', 'status_code': 404}]})
    auth = {'handler': 'authentication', 'providers': {'http_basic': {
        'accounts': [{'username': srv['username'], 'password': password_hash}],
        'hash': {'algorithm': 'bcrypt'}, 'realm': 'UniFi2Lox cameras'}}}
    return {'admin': {'listen': 'unix/' + str(admin_socket), 'config': {'persist': False}},
            'apps': {'tls': {'certificates': {'load_files': [
                {'certificate': str(cert), 'key': str(key)}]}},
                     'http': {'servers': {'cameras': {
                         'listen': [':%d' % settings['listen_port']],
                         'automatic_https': {'disable': True},
                         'tls_connection_policies': [{}],
                         'protocols': ['h1', 'h2'],
                         'routes': [
                             {'match': [{'host': [settings['domain']]}],
                              'handle': [auth, {'handler': 'subroute', 'routes': routes}],
                              'terminal': True},
                             {'handle': [{'handler': 'static_response', 'status_code': 404}]}]}}}}}


class Manager:
    def __init__(self, home=None, folder=None):
        self.home = Path(home or os.environ.get('LBHOMEDIR') or BIN.parents[2])
        self.folder = folder or BIN.name
        self.base = private_dir(self.home / 'config/plugins' / self.folder / 'https')
        self.data = self.home / 'data/plugins' / self.folder
        self.settings_file = self.base / 'settings.json'
        self.tools = private_dir(self.base / 'tools')
        self.active_file = self.base / 'active.json'
        self.state = self.base / 'service.json'
        self.socket = private_dir(self.data / 'https-runtime') / 'admin.sock'
        self.gateway = self.base / 'gateway.json'

    def settings(self):
        return validate_settings(read_json(self.settings_file, DEFAULTS))

    def plugin(self):
        return read_json(self.home / 'config/plugins' / self.folder / 'config.json')

    def job(self):
        j = read_json(self.base / 'job.json')
        if j.get('id'):
            result = read_json(self.base / 'jobs' / j['id'] / 'state.json')
            j.update(result)
            challenge = read_json(self.base / 'jobs' / j['id'] / 'challenge.json')
            if challenge:
                j['challenge'] = challenge
            if (j.get('phase') not in ('ready', 'failed') and
                    not (j.get('phase') == 'queued' and time.time() - j.get('created', 0) < 15) and
                    not self.job_running()):
                j['phase'] = 'failed'
                j['message'] = 'Operation interrupted. Start a new request; old TXT records can be removed.'
        return j

    def job_running(self):
        try:
            with lock(self.base / 'operation.lock'):
                return False
        except Error:
            return True

    def process(self):
        s = read_json(self.state)
        pid = s.get('pid')
        if not isinstance(pid, int) or pid < 2:
            return None
        try:
            os.kill(pid, 0)
            # Never kill an unrelated process after PID reuse.
            exe = Path('/proc/%s/exe' % pid)
            if sys.platform.startswith('linux'):
                if exe.resolve(strict=True) != (self.tools / 'caddy').resolve(strict=True):
                    return None
                if str(self.gateway).encode() not in Path('/proc/%s/cmdline' % pid).read_bytes().split(b'\0'):
                    return None
            else:
                cmd = subprocess.check_output(['ps', '-p', str(pid), '-o', 'command='], text=True)
                if str(self.tools / 'caddy') not in cmd or str(self.gateway) not in cmd:
                    return None
            return pid
        except (OSError, subprocess.CalledProcessError):
            return None

    def status(self):
        c = self.settings()
        active = read_json(self.active_file)
        cert = None
        if active:
            try:
                cert = certificate_info(self.base / active['cert'], self.base / active['key'], c['domain'])
                cert['staging'] = active.get('staging', False)
            except Error as e:
                cert = {'error': str(e)}
        stored = read_json(self.base / 'secrets.json')
        links = []
        origin = c['external_url'] if c['mode'] == 'external' else (
            'https://' + c['domain'] + (':' + str(c['public_port']) if c['public_port'] != 443 else ''))
        if c['mode'] != 'off' and c['domain'] or c['mode'] == 'external':
            for cam in self.plugin().get('cameras', []):
                if cam.get('enabled') and re.fullmatch(r'[a-z0-9_]+', cam.get('slug', '')):
                    path = origin + '/camera/' + cam['slug'] + '/'
                    links.append({'name': cam.get('name', cam['slug']),
                                  'video': path + 'video.mjpeg', 'snapshot': path + 'snapshot.jpg'})
        return dict(ok=True, settings=c, running=bool(self.process()), certificate=cert,
                    tools={n: (self.tools / n).is_file() for n in ('caddy', 'lego')},
                    providers=PROVIDERS, has_credentials={k: bool(v) for k, v in stored.items()},
                    job=self.job(), links=links, service=read_json(self.state),
                    renewal=self.renewal_status())

    def renewal_status(self):
        c = self.settings()
        active = read_json(self.active_file)
        history = read_json(self.base / 'renewal.json')
        reason = ''
        if c['certificate_mode'] != 'dns':
            reason = 'Manual DNS and imported certificates require manual renewal.'
        elif c['mode'] != 'managed' or not read_json(self.base / 'enabled.json').get('enabled'):
            reason = 'Enable managed HTTPS to activate automatic renewal.'
        elif (self.data / 'stopped.flag').exists() or not self.plugin().get('server', {}).get('enabled', True):
            reason = 'Automatic renewal is paused while the camera service is stopped.'
        elif not active:
            reason = 'Request the first certificate and enable HTTPS.'
        elif active.get('domain') != c['domain'] or active.get('staging', False) != c['staging']:
            reason = 'Request a certificate matching the saved hostname and staging setting.'
        due = active.get('expires', 0) - RENEW_BEFORE if active else None
        return dict(enabled=not reason, reason=reason, due_at=due,
                    next_attempt_at=max(due, history.get('attempt', 0) + RENEW_RETRY) if due is not None else None,
                    last_attempt=history.get('attempt'), last_success=history.get('success'),
                    result=history.get('result'), message=history.get('message', ''))

    def save(self, payload):
        with lock(self.base / 'operation.lock'):
            c = validate_settings(payload.get('settings', {}))
            old = read_json(self.base / 'secrets.json')
            new = payload.get('credentials', {})
            if not isinstance(new, dict):
                raise Error('Invalid credentials.')
            allowed = set(PROVIDERS[c['provider']]['fields'])
            if set(new) - allowed:
                raise Error('Unknown provider credential.')
            for key, value in new.items():
                if not isinstance(value, str) or len(value) > 8192 or '\0' in value:
                    raise Error('Invalid credential.')
                if value:
                    old[key] = value
            if payload.get('clear_credentials') is True:
                old = {}
            # Saving changes always stops external access until explicit Apply.
            self.stop()
            write_private(self.base / 'secrets.json', old)
            write_private(self.settings_file, c)
            write_private(self.base / 'enabled.json', {'enabled': False})
        return self.status()

    def enqueue(self, operation, automatic=False):
        if operation not in ('install', 'issue'):
            raise Error('Invalid operation.')
        with lock(self.base / 'operation.lock'):
            if self.job().get('phase') == 'queued' and time.time() - self.job().get('created', 0) < 15:
                raise Error('An operation is already queued.')
            c = self.settings()
            if automatic and (operation != 'issue' or not self.renewal_status()['enabled']):
                raise Error('Automatic renewal is no longer enabled.')
            if operation == 'issue':
                if c['mode'] != 'managed' or c['certificate_mode'] == 'import':
                    raise Error('Select managed HTTPS and a DNS certificate method first.')
                if not c['email'] or not c['terms']:
                    raise Error('Enter an email and accept the ACME terms first.')
                if not (self.tools / 'lego').is_file():
                    raise Error('Install the HTTPS tools first.')
                if c['certificate_mode'] == 'dns':
                    stored = read_json(self.base / 'secrets.json')
                    if not all(stored.get(x) for x in PROVIDERS[c['provider']]['fields']):
                        raise Error('Enter the DNS provider credentials first.')
            ident = secrets.token_hex(12)
            private_dir(self.base / 'jobs' / ident)
            j = dict(id=ident, operation=operation, created=time.time(), phase='queued', automatic=automatic)
            write_private(self.base / 'job.json', j)
            write_private(self.base / 'jobs' / ident / 'state.json', j)
            env = dict(os.environ, LBHOMEDIR=str(self.home))
            subprocess.Popen([sys.executable, str(BIN / 'https_manager.py'), 'worker', ident],
                             env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True)
        return {'ok': True, 'job': j}

    def confirm(self, ident, nonce):
        j = self.job()
        if ident != j.get('id') or j.get('phase') != 'waiting_dns' or not self.job_running():
            raise Error('This challenge is no longer active. Request a new certificate.')
        challenge = j.get('challenge', {})
        if not secrets.compare_digest(str(challenge.get('nonce', '')), str(nonce)) or not nonce:
            raise Error('Challenge changed. Refresh the page.')
        write_private(self.base / 'jobs' / ident / 'confirmed.json', {'nonce': nonce})
        return {'ok': True}

    def install_tools(self):
        if not sys.platform.startswith('linux'):
            raise Error('Automatic installation is supported on Linux only.')
        arch = {'x86_64': 'amd64', 'aarch64': 'arm64', 'armv7l': 'armv7',
                'armv6l': 'armv6', 'i386': '386', 'i686': '386'}.get(platform.machine())
        manifest = read_json(BIN / 'https-tools.json')
        # Check all assets before changing either installed tool.
        if not arch or any(arch not in item['assets'] for item in manifest.values()):
            raise Error('No verified HTTPS tools are available for this architecture.')
        if self.process():
            raise Error('Disable HTTPS before installing tools.')
        with tempfile.TemporaryDirectory(dir=str(self.base)) as tmp:
            for name, item in manifest.items():
                asset = item['assets'][arch]
                archive = Path(tmp) / (name + '.tar.gz')
                h = hashlib.sha256()
                size = 0
                with urllib.request.urlopen(asset['url'], timeout=60) as response, archive.open('wb') as out:
                    while True:
                        buf = response.read(1024 * 1024)
                        if not buf:
                            break
                        size += len(buf)
                        if size > 250 * 1024 * 1024:
                            raise Error('HTTPS tool download exceeded size limit.')
                        h.update(buf)
                        out.write(buf)
                if h.hexdigest() != asset['sha256']:
                    raise Error('HTTPS tool checksum mismatch; installation aborted.')
                with tarfile.open(archive) as tar:
                    member = tar.getmember(name)
                    if not member.isfile() or member.size > 500 * 1024 * 1024:
                        raise Error('Invalid HTTPS tool archive.')
                    target = Path(tmp) / name
                    with tar.extractfile(member) as source, target.open('wb') as dest:
                        shutil.copyfileobj(source, dest)
                    target.chmod(0o700)
                subprocess.run([str(target), 'version' if name == 'caddy' else '--version'],
                               check=True, capture_output=True, timeout=15)
            for name in manifest:
                os.replace(Path(tmp) / name, self.tools / name)

    def worker(self, ident):
        if not re.fullmatch('[a-f0-9]{24}', ident):
            return
        jobdir = self.base / 'jobs' / ident
        job = {}
        def update(phase, message=''):
            write_private(jobdir / 'state.json', {'phase': phase, 'message': message})
            if job.get('automatic') and phase in ('ready', 'failed'):
                with lock(self.base / 'renewal.lock', blocking=True):
                    history = read_json(self.base / 'renewal.json')
                    history.update(result=phase, message=message)
                    if phase == 'ready':
                        history['success'] = time.time()
                    write_private(self.base / 'renewal.json', history)
        try:
            with lock(self.base / 'operation.lock', blocking=True):
                job = read_json(self.base / 'job.json')
                if job.get('id') != ident:
                    return
                update('running')
                if (jobdir / 'cancelled.json').exists():
                    raise Error('Operation cancelled.')
                if job['operation'] == 'install':
                    self.install_tools()
                else:
                    self.issue(jobdir)
                update('ready', 'Operation completed.')
        except Exception as exc:
            # External command output may include provider credentials. Never put it
            # into the web response or the ordinary plugin log.
            update('failed', str(exc) if isinstance(exc, Error) else
                   'Operation failed. Check DNS permissions, propagation and network access, then retry.')

    def issue(self, jobdir):
        c = self.settings()
        stage = 'staging' if c['staging'] else 'production'
        account = private_dir(self.base / 'acme' / stage)
        env = {k: v for k, v in os.environ.items()
               if k in ('PATH', 'LANG', 'LC_ALL', 'SSL_CERT_FILE', 'SSL_CERT_DIR')}
        env.update(HOME=str(self.base), U2L_HTTPS_JOB=str(jobdir))
        provider = c['provider'] if c['certificate_mode'] == 'dns' else 'exec'
        if provider == 'exec':
            env.update(EXEC_PATH=str(BIN / 'https_dns_hook.py'),
                       EXEC_PROPAGATION_TIMEOUT='600', EXEC_SEQUENCE_INTERVAL='0')
        else:
            credentials = read_json(self.base / 'secrets.json')
            secret_dir = private_dir(jobdir / 'credentials')
            for field in PROVIDERS[provider]['fields']:
                if not credentials.get(field):
                    raise Error('Missing DNS provider credentials.')
                path = secret_dir / field
                write_private(path, credentials[field])
                env[field + '_FILE'] = str(path)
        args = [str(self.tools / 'lego'), 'run', '--path', str(account), '--server', CA[stage],
                '--email', c['email'], '--accept-tos', '--domains', c['domain'],
                '--dns', provider, '--renew-days', '30']
        if c['dns_resolvers']:
            args.extend(['--dns.resolvers', c['dns_resolvers']])
        try:
            # Bounded interactive job; no credentials or client log in global logs.
            with tempfile.TemporaryFile() as output:
                proc = subprocess.Popen(args, env=env, stdin=subprocess.DEVNULL,
                                        stdout=output, stderr=output, start_new_session=True)
                try:
                    deadline = time.monotonic() + 2400
                    while proc.poll() is None:
                        if (jobdir / 'cancelled.json').exists() or time.monotonic() > deadline:
                            raise subprocess.TimeoutExpired(args, 2400)
                        time.sleep(.25)
                    rc = proc.returncode
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait()
                    raise Error('Certificate request cancelled or timed out. Request a new challenge.')
                if rc:
                    output.seek(0, os.SEEK_END)
                    output.seek(max(0, output.tell() - 32768))
                    if b'recursive nameservers:' in output.read():
                        raise Error('DNS propagation check failed at a recursive resolver. Check the Certificate DNS resolvers setting; try 1.1.1.1:53 if local DNS does not return public TXT records.')
                    raise Error('Certificate request failed. Check DNS credentials/records and propagation; then retry.')
            cert = account / 'certificates' / (c['domain'] + '.crt')
            key = account / 'certificates' / (c['domain'] + '.key')
            self.store_certificate(cert.read_bytes(), key.read_bytes(), staging=c['staging'])
        finally:
            shutil.rmtree(jobdir / 'credentials', ignore_errors=True)
            challenge = read_json(jobdir / 'challenge.json')
            if challenge:
                challenge['cleanup'] = True
                write_private(jobdir / 'challenge.json', challenge)

    def store_certificate(self, cert_bytes, key_bytes, staging=False):
        c = self.settings()
        if len(cert_bytes) > 262144 or len(key_bytes) > 65536:
            raise Error('Certificate files are too large.')
        # Immutable generations: Caddy cannot see half of a replaced pair.
        generation = private_dir(self.base / 'certificates' / secrets.token_hex(8))
        try:
            write_private(generation / 'fullchain.pem', cert_bytes)
            write_private(generation / 'key.pem', key_bytes)
            info = certificate_info(generation / 'fullchain.pem', generation / 'key.pem', c['domain'])
            new = {'cert': str((generation / 'fullchain.pem').relative_to(self.base)),
                   'key': str((generation / 'key.pem').relative_to(self.base)),
                   'domain': c['domain'], 'staging': staging, 'expires': info['expires']}
            old = read_json(self.active_file)
            write_private(self.active_file, new)
            if self.process():
                try:
                    self.apply(require_enabled=True)
                except Exception:
                    write_private(self.active_file, old)
                    raise
        except Exception:
            # A successful old gateway continues serving its original certificate.
            raise
        return info

    def import_cert(self, payload):
        with lock(self.base / 'operation.lock'):
            if self.settings()['certificate_mode'] != 'import':
                raise Error('Select the existing certificate method first.')
            self.store_certificate(str(payload.get('certificate', '')).encode(),
                                   str(payload.get('private_key', '')).encode())
        return self.status()

    def cancel(self):
        j = read_json(self.base / 'job.json')
        if j.get('id'):
            write_private(self.base / 'jobs' / j['id'] / 'cancelled.json', {'cancelled': True})

    def stop(self):
        with lock(self.base / 'service.lock', blocking=True):
            pid = self.process()
            if pid:
                os.kill(pid, signal.SIGTERM)
                for _ in range(30):
                    if not self.process():
                        break
                    time.sleep(.1)
                if self.process() == pid:
                    os.kill(pid, signal.SIGKILL)
                if getattr(self, '_child', None) is not None:
                    self._child.wait(timeout=5)
            self.socket.unlink(missing_ok=True)
            write_private(self.state, {'running': False})

    def apply(self, require_enabled=False):
        with lock(self.base / 'service.lock', blocking=True):
            if require_enabled and not read_json(self.base / 'enabled.json').get('enabled'):
                return
            c = self.settings()
            if c['mode'] != 'managed':
                raise Error('Select managed HTTPS first.')
            plugin = self.plugin()
            if (self.data / 'stopped.flag').exists() or not plugin.get('server', {}).get('enabled', True):
                raise Error('Start the camera service first.')
            active = read_json(self.active_file)
            if not active:
                raise Error('Request or import a valid certificate first.')
            cert, key = self.base / active['cert'], self.base / active['key']
            certificate_info(cert, key, c['domain'])
            tool = self.tools / 'caddy'
            if not tool.is_file():
                raise Error('Install the HTTPS tools first.')
            # stdin avoids exposing the password in ps output. Hash is cached to
            # keep minute watchdog calls cheap; only Caddy's hash is persisted.
            password = str(plugin.get('server', {}).get('password', ''))
            if not password or len(password.encode()) > 72:
                raise Error('HTTPS requires a camera password between 1 and 72 UTF-8 bytes.')
            previous = read_json(self.base / 'password-hash.json')
            fingerprint = hashlib.sha256((str(plugin.get('server', {}).get('username', '')) + '\0' + password).encode()).hexdigest()
            if previous.get('fingerprint') != fingerprint:
                hashed = subprocess.run([str(tool), 'hash-password'], input=password + '\n',
                                        text=True, capture_output=True, check=True, timeout=30).stdout.strip()
                previous = dict(fingerprint=fingerprint, hash=hashed)
                write_private(self.base / 'password-hash.json', previous)
            config = gateway_config(c, plugin, self.folder, cert, key, previous['hash'], self.socket)
            digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
            state = read_json(self.state)
            pid = self.process()
            if pid and state.get('digest') == digest:
                return
            candidate = self.base / 'candidate.json'
            write_private(candidate, config)
            env = dict(os.environ, HOME=str(self.base), XDG_DATA_HOME=str(self.base / 'caddy-data'),
                       XDG_CONFIG_HOME=str(self.base / 'caddy-config'))
            validated = subprocess.run([str(tool), 'validate', '--config', str(candidate)],
                                       env=env, capture_output=True, timeout=30)
            if validated.returncode:
                raise Error('HTTPS configuration validation failed; existing gateway kept running.')
            if pid:
                result = subprocess.run([str(tool), 'reload', '--config', str(candidate),
                                         '--address', 'unix/' + str(self.socket)],
                                        env=env, capture_output=True, timeout=30)
                if result.returncode:
                    raise Error('HTTPS reload failed; existing gateway kept running.')
                os.replace(candidate, self.gateway)
            else:
                # Probe without SO_REUSEPORT: never share an existing service's port.
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                        probe.bind(('0.0.0.0', c['listen_port']))
                except OSError:
                    raise Error('The selected HTTPS port is already in use.')
                os.replace(candidate, self.gateway)
                # Dedicated log is private and never returned by the web endpoint.
                log = self.base / 'gateway.log'
                if log.exists() and log.stat().st_size > 2 * 1024 * 1024:
                    write_private(log, b'')
                with log.open('ab') as out:
                    os.chmod(log, 0o600)
                    proc = subprocess.Popen([str(tool), 'run', '--config', str(self.gateway)], env=env,
                                            stdin=subprocess.DEVNULL, stdout=out, stderr=out,
                                            start_new_session=True, close_fds=True)
                self._child = proc
                pid = proc.pid
                time.sleep(.8)
                if proc.poll() is not None:
                    raise Error('HTTPS could not start. Check that the selected port is free.')
            write_private(self.state, {'pid': pid, 'digest': digest})
            write_private(self.base / 'enabled.json', {'enabled': True})

    def watchdog(self):
        c = self.settings()
        enabled = read_json(self.base / 'enabled.json').get('enabled')
        if c['mode'] != 'managed' or not enabled or (self.data / 'stopped.flag').exists() or not self.plugin().get('server', {}).get('enabled', True):
            if self.process():
                self.stop()
            return
        try:
            self.apply(require_enabled=True)
        except Exception:
            # Never continue exposing cameras after a failed credential/route
            # change. A valid certificate generation remains available on disk.
            self.stop()
            write_private(self.state, {'error': 'HTTPS could not be applied. Check settings, certificate and port.'})
        # Serialize overlapping watchdogs; a busy issuance must not consume the
        # retry window. Persist attempts across restarts, and never force issuance.
        try:
            with lock(self.base / 'renewal.lock'):
                renewal = self.renewal_status()
                if (not renewal['enabled'] or time.time() < renewal['next_attempt_at'] or
                        self.job_running() or self.job().get('phase') == 'queued'):
                    return
                previous = read_json(self.base / 'renewal.json')
                write_private(self.base / 'renewal.json', dict(previous, attempt=time.time(), result='queued', message=''))
                try:
                    self.enqueue('issue', automatic=True)
                except Exception:
                    write_private(self.base / 'renewal.json', previous)
                    raise
        except Error:
            # Another watchdog or interactive operation may own a lock. Retry on
            # the next minute tick without disrupting the existing gateway.
            return


def main():
    os.umask(0o077)
    manager = Manager()
    command = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if command == 'worker':
        manager.worker(sys.argv[2])
        return
    try:
        payload = json.load(sys.stdin) if command in ('save', 'confirm', 'import') else {}
        if command == 'status':
            result = manager.status()
        elif command == 'save':
            result = manager.save(payload)
        elif command in ('install', 'issue'):
            result = manager.enqueue(command)
        elif command == 'confirm':
            result = manager.confirm(payload.get('id'), payload.get('nonce'))
        elif command == 'import':
            result = manager.import_cert(payload)
        elif command == 'upgrade-check':
            if manager.job_running() or manager.job().get('phase') == 'queued':
                raise Error('Cancel the HTTPS operation and wait for completion before upgrading.')
            result = {'ok': True}
        elif command in ('apply', 'stop', 'disable', 'watchdog', 'cancel'):
            if command == 'apply':
                with lock(manager.base / 'operation.lock'):
                    manager.apply()
            elif command == 'disable':
                manager.cancel()
                write_private(manager.base / 'enabled.json', {'enabled': False})
                manager.stop()
            else:
                getattr(manager, command)()
            result = {'ok': True}
        else:
            raise Error('Unknown operation.')
        print(json.dumps(result))
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': str(exc) if isinstance(exc, Error) else
                          'HTTPS operation failed. Check configuration and permissions.'}))
        sys.exit(1)


if __name__ == '__main__':
    main()
