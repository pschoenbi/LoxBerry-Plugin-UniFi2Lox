import json
import fcntl
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import uuid

PACKAGE = Path(__file__).resolve().parents[1]


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.token = 'u2l-test-' + uuid.uuid4().hex
        self.backup = Path('/tmp') / (self.token + '_upgrade')
        self.addCleanup(lambda: shutil.rmtree(self.backup, ignore_errors=True))
        self.bin = self.root / 'bin/plugins/unifi2lox'
        self.cfg = self.root / 'config/plugins/unifi2lox'
        self.data = self.root / 'data/plugins/unifi2lox'
        self.mock = self.root / 'mock'
        for p in (self.bin, self.cfg, self.data, self.mock):
            p.mkdir(parents=True)
        self.config = {'protect': {'host': 'example.invalid', 'apikey': 'keep-this-key'},
                       'server': {'hwaccel': 'off', 'password': 'keep-this-password',
                                  'snapshot_key': 'keep-this-snapshot-key'},
                       'cameras': [{'slug': 'camera_1', 'enabled': True, 'width': 0}]}
        self.config_bytes = json.dumps(self.config, indent=3).encode()
        (self.cfg / 'config.json').write_bytes(self.config_bytes)
        (self.cfg / 'local-setting.txt').write_text('keep me too')
        private = self.cfg / 'https'
        private.mkdir(mode=0o700)
        (private/'secrets.json').write_text('{"CF_DNS_API_TOKEN":"keep-test-token"}')
        (private/'secrets.json').chmod(0o600)
        (self.data / 'streams_cache.json').write_text('{"cache":"keep"}')
        self.engine = b'#!/bin/sh\necho "go2rtc version 1.9.14 (b5948cf) linux/amd64"\n'
        (self.bin / 'go2rtc').write_bytes(self.engine)
        (self.bin / 'go2rtc').chmod(0o755)
        service = '''#!/bin/sh
echo "$1" >> "$U2L_TEST_LOG"
if [ "$1" = stop ]; then
    test -f "$U2L_TEST_ROOT/data/plugins/unifi2lox/stopped.flag" || exit 3
fi
if [ "$1" = start ] && [ "${U2L_FAIL_START:-0}" = 1 ]; then exit 1; fi
exit 0
'''
        (self.bin / 'service.sh').write_text(service)
        (self.bin / 'service.sh').chmod(0o755)
        (self.bin / 'unifi2lox.py').write_text('# test fixture')
        for name in ('https_manager.py','https_dns_hook.py'):
            (self.bin / name).write_text('# test fixture')
        for name, content in {'dpkg': '#!/bin/sh\necho amd64\n',
                              'curl': '#!/bin/sh\necho CALLED >> "$U2L_TEST_NETWORK"\nexit 1\n',
                              'ffmpeg': '#!/bin/sh\nexit 0\n'}.items():
            (self.mock / name).write_text(content)
            (self.mock / name).chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.mock) + ':' + os.environ['PATH'],
                        U2L_TEST_LOG=str(self.root / 'service.log'),
                        U2L_TEST_NETWORK=str(self.root / 'network.log'),
                        U2L_TEST_ROOT=str(self.root))

    def run_hook(self, name, ok=True):
        r = subprocess.run(['bash', str(PACKAGE / name), self.token,
                            'unifi2lox', 'unifi2lox', '1.1.2.2', str(self.root)],
                           capture_output=True, text=True, env=self.env)
        if ok:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        else:
            self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def replace_folders(self):
        # Exercise the worst case: installer has replaced the config and binary.
        shutil.rmtree(self.cfg)
        self.cfg.mkdir()
        shutil.copy2(PACKAGE / 'config/config.default.json', self.cfg)
        (self.bin / 'go2rtc').unlink()

    def test_running_upgrade_preserves_all_settings_and_engine(self):
        self.run_hook('preupgrade.sh')
        self.replace_folders()
        self.run_hook('postinstall.sh')
        self.run_hook('postupgrade.sh')
        self.assertEqual((self.cfg / 'config.json').read_bytes(), self.config_bytes)
        self.assertEqual((self.cfg / 'local-setting.txt').read_text(), 'keep me too')
        self.assertEqual(json.loads((self.cfg/'https/secrets.json').read_text())['CF_DNS_API_TOKEN'],'keep-test-token')
        self.assertEqual((self.cfg/'https/secrets.json').stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.bin / 'go2rtc').read_bytes(), self.engine)
        self.assertFalse((self.root / 'network.log').exists())
        self.assertFalse((self.data / 'stopped.flag').exists())
        self.assertFalse(self.backup.exists())
        self.assertEqual((self.root / 'service.log').read_text(), 'stop\nstart\n')

    def test_stopped_plugin_stays_stopped(self):
        (self.data / 'stopped.flag').touch()
        self.run_hook('preupgrade.sh')
        self.replace_folders()
        self.run_hook('postinstall.sh')
        self.run_hook('postupgrade.sh')
        self.assertTrue((self.data / 'stopped.flag').exists())
        self.assertEqual((self.root / 'service.log').read_text(), 'stop\n')

    def test_bad_config_aborts_before_stopping(self):
        (self.cfg / 'config.json').write_text('not JSON')
        self.run_hook('preupgrade.sh', ok=False)
        self.assertFalse((self.root / 'service.log').exists())
        self.assertFalse((self.data / 'stopped.flag').exists())

    def test_start_failure_retains_backup_and_blocks_watchdog(self):
        self.run_hook('preupgrade.sh')
        self.replace_folders()
        self.run_hook('postinstall.sh')
        self.env['U2L_FAIL_START'] = '1'
        self.run_hook('postupgrade.sh', ok=False)
        self.assertTrue((self.data / 'stopped.flag').exists())
        self.assertEqual((self.cfg / 'config.json').read_bytes(), self.config_bytes)
        self.assertTrue((self.backup / 'config/config.json').is_file())

    def test_active_https_job_prevents_upgrade_before_stopping(self):
        with (self.cfg/'https/operation.lock').open('a+') as locked:
            fcntl.flock(locked, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.run_hook('preupgrade.sh', ok=False)
        self.assertFalse((self.root/'service.log').exists())
        self.assertFalse(self.backup.exists())

    def test_unavailable_engine_fails_without_latest_fallback(self):
        (self.bin / 'go2rtc').unlink()
        self.run_hook('postinstall.sh', ok=False)
        self.assertEqual((self.root / 'network.log').read_text(), 'CALLED\n')
        self.assertEqual((self.cfg / 'config.json').read_bytes(), self.config_bytes)


if __name__ == '__main__':
    unittest.main()
