#!/usr/bin/env python3
"""Pair a unique host key over the direct USB link before installing this fork."""
import os
import subprocess
from pathlib import Path
from hardening_install import ensure_pairing_key
from install_config import USER_NAME, USBNET_PREFIX


def main():
    if os.geteuid()!=0:
        raise SystemExit('Run with sudo on the Pi host, after install_host.py.')
    key=ensure_pairing_key(USER_NAME)
    target=f'{USER_NAME}@{USBNET_PREFIX}.2'
    # Do not pair with a routed/LAN host that happens to use the same address.
    route=subprocess.check_output(['ip','route','get',f'{USBNET_PREFIX}.2'],text=True)
    if 'dev usb0' not in route:
        raise SystemExit('Expected the Car Thing on the direct usb0 link. Check the USB connection.')
    prefix=['runuser','-u',USER_NAME,'--']
    print('Verify/accept the USB-connected device host key; enter its existing password when SSH prompts.')
    subprocess.run(prefix+['ssh-copy-id','-i',str(key)+'.pub',target],check=True)
    subprocess.run(prefix+['ssh','-o','BatchMode=yes','-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes','-i',str(key),target,'true'],check=True)
    print('Unique key verified. Installing the fork on the device will revoke the known shared key and lock password login.')


if __name__=='__main__':
    main()
