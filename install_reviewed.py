#!/usr/bin/env python3
"""Install an explicitly selected, already-fetched commit with recoverable backups."""
import argparse
import datetime
import re
import shutil
import subprocess
from pathlib import Path


def validate_commit(value):
    if not re.fullmatch(r'[0-9a-f]{40}', value):
        raise ValueError('Supply a full 40-character commit SHA, not a branch name.')
    return value


def install(device, commit, repo=Path('/repo')):
    validate_commit(commit)
    repo = repo.resolve()
    if subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True).strip():
        raise RuntimeError('Working tree has local changes. Save them before updating.')
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip() != commit:
        raise RuntimeError('Check out the reviewed commit first. Installer does not fetch or switch code.')
    previous = Path('/var/lib/wallthing/installed-commit')
    backup = Path('/var/backups/wallthing') / datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup.mkdir(parents=True,mode=0o700)
    for source in ['/etc/kiosk','/scripts' if device == 'superbird' else '/kiosk-updater','/etc/iptables/rules.v4']:
        source = Path(source)
        if source.is_dir():
            shutil.copytree(source,backup/source.name)
        elif source.exists():
            shutil.copy2(source,backup/source.name)
    if previous.exists():
        shutil.copy2(previous,backup/'previous-commit')
    command = ['python3', 'install_host.py'] if device == 'host' else ['python3','install_superbird.py','--no-reboot']
    subprocess.run(command,cwd=repo,check=True)
    service = 'kiosk-updater' if device == 'host' else 'kiosk'
    subprocess.run(['systemctl','reset-failed',service],check=True)
    subprocess.run(['systemctl','restart',service],check=True)
    # Avoid declaring a restart loop healthy merely because systemd has started the process.
    import time
    for _ in range(6):
        time.sleep(5)
        subprocess.run(['systemctl','is-active','--quiet',service],check=True)
        restarts = subprocess.check_output(['systemctl','show','-p','NRestarts','--value',service],text=True).strip()
        if restarts != '0':
            raise RuntimeError(f'{service} restarted unexpectedly. Inspect journalctl and backup {backup}.')
    previous.parent.mkdir(parents=True,exist_ok=True)
    previous.write_text(commit+'\n')
    print(f'Installed {commit}; service stayed active for 30 seconds. Backup: {backup}')
    print('Verify the physical display and touch input before treating the hardware as validated.')


if __name__ == '__main__':
    import os
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device',choices=['host','superbird'],required=True)
    parser.add_argument('--commit',required=True,type=validate_commit)
    args=parser.parse_args()
    if os.geteuid()!=0:
        parser.error('Run with sudo on the target device.')
    install(args.device,args.commit)
