#!/usr/bin/env python3
"""Fixed lego exec provider for the manual DNS wizard; never executes user code."""
import json
import os
from pathlib import Path
import secrets
import sys
import time
from https_manager import read_json, write_private


def run(action, name, value, jobdir, timeout=1800):
    jobdir = Path(jobdir)
    if action == 'cleanup':
        challenge = read_json(jobdir / 'challenge.json')
        challenge['cleanup'] = True
        write_private(jobdir / 'challenge.json', challenge)
        return 0
    if action != 'present':
        return 1
    nonce = secrets.token_hex(16)
    write_private(jobdir / 'challenge.json', dict(name=name, value=value, type='TXT', nonce=nonce))
    write_private(jobdir / 'state.json', dict(phase='waiting_dns',
                  message='Add this TXT record at your DNS provider, then confirm.'))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if (jobdir / 'cancelled.json').exists():
            return 1
        confirmed = read_json(jobdir / 'confirmed.json')
        if confirmed.get('nonce') == nonce:
            write_private(jobdir / 'state.json', dict(phase='validating', message='Checking DNS propagation.'))
            return 0
        time.sleep(1)
    return 1


if __name__ == '__main__':
    os.umask(0o077)
    if len(sys.argv) != 4 or not os.environ.get('U2L_HTTPS_JOB'):
        sys.exit(1)
    sys.exit(run(*sys.argv[1:], os.environ['U2L_HTTPS_JOB']))
