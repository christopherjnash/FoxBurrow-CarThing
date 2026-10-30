"""Host/device provisioning. No shared private keys and no global firewall flush."""
import os
import pwd
import secrets
import shutil
import subprocess
from pathlib import Path
from install_config import LEGACY_SSH_PUBLIC_KEY, USER_NAME


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def ensure_pairing_key(user=USER_NAME):
    account = pwd.getpwnam(user)
    folder = Path(account.pw_dir) / '.ssh'
    folder.mkdir(mode=0o700, exist_ok=True)
    os.chown(folder, account.pw_uid, account.pw_gid)
    key = folder / 'wallthing_ed25519'
    if not key.exists():
        run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'wallthing-host', '-f', str(key)])
    for file in (key, key.with_suffix('.pub')):
        os.chown(file, account.pw_uid, account.pw_gid)
        file.chmod(0o600)
    # Remove ONLY the known upstream credential, never an unrelated user key.
    legacy_pub = folder / 'id_rsa.pub'
    if legacy_pub.exists() and legacy_pub.read_text().split()[:2] == LEGACY_SSH_PUBLIC_KEY.split()[:2]:
        legacy_pub.unlink()
        (folder / 'id_rsa').unlink(missing_ok=True)
    return key


def configure_network(prefix, execute=run, check=subprocess.run, rules_path='/etc/iptables/rules.v4'):
    device = f'{prefix}.2'
    subnet = f'{prefix}.0/24'
    def rule(table, chain, args):
        base = ['iptables', '-t', table]
        result = check(base + ['-C', chain] + args, capture_output=True)
        if result.returncode:
            execute(base + ['-A', chain] + args)
    # Remove only the exact forwards installed by the upstream project.
    for src, dst in {2022:22,5900:5900,5901:5901,9223:9223,80:80}.items():
        for table, chain, args in [
            ('nat','PREROUTING',['-p','tcp','-i','wlan0','--dport',str(src),'-j','DNAT','--to-destination',f'{device}:{dst}']),
            ('filter','FORWARD',['-p','tcp','-d',device,'--dport',str(dst),'-m','state','--state','NEW,ESTABLISHED,RELATED','-j','ACCEPT'])]:
            base=['iptables','-t',table]
            while check(base+['-C',chain]+args,capture_output=True).returncode == 0:
                execute(base+['-D',chain]+args)
    rule('nat','POSTROUTING',['-s',subnet,'-o','wlan0','-j','MASQUERADE'])
    rule('filter','FORWARD',['-i','usb0','-s',subnet,'-o','wlan0','-j','ACCEPT'])
    rule('filter','FORWARD',['-o','usb0','-d',device,'-m','conntrack','--ctstate','ESTABLISHED,RELATED','-j','ACCEPT'])
    rule('filter','FORWARD',['-o','usb0','-d',device,'-j','REJECT'])
    with open(rules_path,'w') as dest:
        execute(['iptables-save'],stdout=dest)


def paired_keys(path):
    path = Path(path)
    lines = path.read_text().splitlines() if path.exists() else []
    legacy_blob = LEGACY_SSH_PUBLIC_KEY.split()[1]
    safe = [line for line in lines if legacy_blob not in line and line.strip() and not line.lstrip().startswith('#')]
    if not safe:
        raise RuntimeError('Pair a unique host SSH key before installing. Refusing to lock out the device.')
    return safe


def revoke_legacy_key(path):
    path = Path(path)
    safe = paired_keys(path)
    path.write_text('\n'.join(safe) + '\n')
    path.chmod(0o600)


def secure_device(bypass=False):
    revoke_legacy_key(f'/home/{USER_NAME}/.ssh/authorized_keys')
    run(['passwd','-l',USER_NAME])
    try:
        pwd.getpwnam('wallthing-browser')
    except KeyError:
        run(['useradd','--system','--user-group','--create-home','--shell','/usr/sbin/nologin','wallthing-browser'])
    profile = Path('/config/chromium_profile')
    profile.mkdir(parents=True,exist_ok=True)
    run(['chown','-R','wallthing-browser:wallthing-browser',str(profile)])
    private = Path('/etc/kiosk')
    private.mkdir(mode=0o700,exist_ok=True)
    private.chmod(0o700)
    # A fresh random VNC credential replaces the shipped one, but VNC stays disabled.
    vnc = Path('/etc/vnc/vnc_passwd')
    vnc.parent.mkdir(exist_ok=True)
    data = run(['vncpasswd','-f'], input=(secrets.token_urlsafe(6)+'\n').encode(),capture_output=True).stdout
    vnc.write_bytes(data)
    vnc.chmod(0o600)
    for service in ('vnc','websockify','haproxy'):
        if not bypass:
            subprocess.run(['systemctl','stop',service],check=False)
        # Remove old enable links even when building inside a chroot.
        subprocess.run(['systemctl','disable',service],check=False)
    if not bypass:
        run(['systemctl','daemon-reload'])
