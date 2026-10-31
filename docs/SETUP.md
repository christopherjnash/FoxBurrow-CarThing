# Setup and migration

This is a source migration for the upstream v2.x Debian installation. No fork firmware image or physical hardware test is supplied. Keep a full backup of the device's current firmware and the recovery tools available (an existing DeskThing installation is not stock firmware). Use a dedicated Pi Zero 2 W running Raspberry Pi OS Lite 64-bit **Bullseye**, with user `superbird`, your own password, Wi-Fi configured, and SSH enabled. Current images with a different codename are rejected by the existing hardware installer.

The Pi remains the USB/network host; the Car Thing runs the browser. Do not replace a working installation with this fork without reserving time to verify the display and recover if the old kernel cannot support the browser sandbox.

## 1. Select the code and install the host

Review a commit in this fork and copy its full 40-character SHA from GitHub. Replace the placeholder below. This variable is a commit identifier, not a credential.

On the Pi, with the Car Thing disconnected:

```bash
WALLTHING_COMMIT=PASTE_FULL_40_CHARACTER_COMMIT_SHA
sudo apt update
sudo apt install -y git
sudo git clone https://github.com/christopherjnash/superbird-debian-kiosk.git /repo
sudo git -C /repo checkout --detach "$WALLTHING_COMMIT"
cd /repo
sudo python3 install_reviewed.py --device host --commit "$WALLTHING_COMMIT"
sudo reboot
```

If `/repo` already exists, do not clone over it. First inspect `sudo git -C /repo status --short` and preserve any changes. With a clean checkout, set its origin to this fork, fetch it, and check out the selected commit:

```bash
sudo git -C /repo remote set-url origin https://github.com/christopherjnash/superbird-debian-kiosk.git
sudo git -C /repo fetch origin
sudo git -C /repo checkout --detach "$WALLTHING_COMMIT"
```

Then run the reviewed installer as above. It removes only the upstream project's exact port-forward rules, preserves unrelated rules, and keeps outbound USB networking. It does not format the Car Thing's settings partition.



### Bullseye image customization and archived packages

For the Windows/Pi setup exercised here, Raspberry Pi Imager 2.x did not
customize the downloaded Bullseye image. Official Raspberry Pi Imager **1.9.6**
for Windows worked. Obtain it from the
[official Imager releases](https://github.com/raspberrypi/rpi-imager/releases/tag/v1.9.6).
Choose OS Lite Bullseye 64-bit, configure your hostname, user superbird, your own
password, Wi-Fi, and SSH. Verify on the Pi:

~~~bash
cat /etc/os-release
uname -m
~~~

Require Debian 11/Bullseye and aarch64. The hostname in the exercised setup was
foxdesk, reached from Windows PowerShell with ssh superbird@foxdesk.local.
Choose your own hostname if desired.

If installing Git fails with obsolete Bullseye security-package URLs returning
404s, preserve /etc/apt/sources.list and replace only its Debian entries with
the archive entries below. Leave the separate Raspberry Pi repository unchanged.
Do not apply this workaround to a different Debian release.

On the **Pi**:

~~~bash
sudo cp -n /etc/apt/sources.list /etc/apt/sources.list.before-wallthing
sudo tee /etc/apt/sources.list >/dev/null <<'EOF'
deb [check-valid-until=no] https://archive.debian.org/debian bullseye main contrib non-free
deb [check-valid-until=no] https://archive.debian.org/debian-security bullseye-security main contrib non-free
EOF
sudo apt update
sudo apt install -y git
~~~

The archive workaround disables repository expiry checking only for these
entries; it does not disable signature or HTTPS validation and does not make
Bullseye current.

After the host installer reboot, check on the **Pi**:

~~~bash
systemctl is-active kiosk-updater
~~~

The exercised host installation at commit
7ecdbff14d65e8cf1d94da52bf7c5b5037d86ca2 returned active. That confirms the host
service, not the display, touch input, browser, or recovery behavior.

## 1a. Back up the current firmware from native Windows

Complete this before any flash or restore operation. A device already running
DeskThing must be backed up as DeskThing; do not label that dump as stock Spotify
firmware. The backup captures the device's current partitions and settings.

The native Windows route below was exercised on 2026-10-31 with Python 3.13,
Git for Windows, WinUSB, and ThingLabsOSS superbird-tool v0.3.0. All 16 partition
files completed, their sizes were checked, and SHA-256 hashes were generated for
those files plus env.txt. One system_a read retried successfully. Recovery from
that backup and WallThing flashing/migration have **not** yet been tested.

The working full dump took 377 seconds at about 11 MB/s. This is an observation,
not a performance guarantee. Replacing the data cable improved reliability.
A successful small read alone did not establish full-backup stability.

### Connection and power

For normal Pi operation, use a good 5V supply rated at least 2.5A (the setup used
a 5V/3A charger), connected to PWR IN. The other micro-USB port, USB, accepts an
OTG host adapter and a USB-A-to-C **data** cable to the Car Thing. Cable and
adapter losses can still affect power even with a sufficient charger rating.

For the Windows backup, disconnect the Car Thing from the Pi and connect it
directly to a PC USB port using a known-good data cable. Hold preset buttons
1 and 4 while connecting, then release. A black screen is expected in ROM USB
mode; Windows should enumerate 1b8e:c003, GX-CHIP.

If previously using WSL/usbipd, first stop its auto-attach command with Ctrl+C.
In **Administrator PowerShell**, run the following using the Car Thing's actual
BUSID from the list (do not copy another device's ID):

~~~powershell
usbipd list
usbipd detach --busid YOUR_CAR_THING_BUSID
usbipd unbind --busid YOUR_CAR_THING_BUSID
~~~

An already-detached message is harmless. Then unplug and reconnect holding 1+4.
Do not attach it to WSL while using the native Windows tools.

### Install the backup tool on Windows

In **Windows PowerShell**, choose a working folder on a drive with at least
5 GB free, then run:

~~~powershell
py --version
git --version
git clone https://github.com/ThingLabsOSS/superbird-tool.git superbird-tool-windows
Set-Location .\superbird-tool-windows
git checkout --detach da05fb49f7ebb2d0aebff128d3e197fd087d1709
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install pyusb libusb-package git+https://github.com/superna9999/pyamlboot
git rev-parse HEAD
.\.venv\Scripts\python.exe -m pip freeze
~~~

Use a new folder; do not overwrite an existing checkout or backup. The pinned
commit is the reviewed v0.3.0 reference. Record the actual tool commit and package
versions with your recovery notes. The pyamlboot dependency is fetched from its
upstream branch, so its resolved version should also be retained.

This fork supplies the fast partition-reading protocol. The older
bishopdynamics v0.1.0 Python path read at about 145–148 KB/s on the Pi and would
have taken hours. The fast Linux-only Amlogic binary under WSL transferred small
partitions but stalled during the full backup in this setup; it is not the
validated route here. WSL support for USB detection is not proof of a reliable
full dump.

The ThingLabsOSS project marks itself superseded for general flashing, but
retains vendor-layout dump/restore functions. We use its verified backup path
here; this does not establish that its restore path has been tested with this
fork.

Create this small launcher **in Windows PowerShell, in the tool directory**.
It explicitly loads the packaged DLL, avoiding PyUSB's "No backend available"
error without copying DLLs into Windows system folders:

~~~powershell
@'
import runpy
import sys
from pathlib import Path
import libusb_package
import usb.backend.libusb1

root = Path(__file__).resolve().parent
backend = usb.backend.libusb1.get_backend(
    find_library=libusb_package.find_library
)
if backend is None:
    raise SystemExit("Could not load the libusb backend")
sys.argv = [str(root / "superbird_tool.py"), *sys.argv[1:]]
runpy.run_path(str(root / "superbird_tool.py"), run_name="__main__")
'@ | Set-Content -Encoding ascii .\run_superbird.py
~~~

### Install the Windows driver and check both USB modes

Download [Zadig from its official site](https://zadig.akeo.ie/). In Zadig:

1. Select Options → List All Devices.
2. Select GX-CHIP and verify USB ID **1B8E C003**.
3. Choose **WinUSB** as the target driver, then Install/Replace Driver.

Only change the Car Thing's driver. This changes Windows driver binding, not
the Car Thing's firmware.

In **Windows PowerShell**, in the tool directory:

~~~powershell
.\.venv\Scripts\python.exe .\run_superbird.py --find_device
.\.venv\Scripts\python.exe .\run_superbird.py --burn_mode
.\.venv\Scripts\python.exe .\run_superbird.py --find_device
~~~

The first detection should report USB Mode (buttons 1 & 4 held at boot).
The later detection must report **USB Burn Mode (ready for commands)**.
Entering burn mode uploads a temporary bootloader into RAM; it does not flash
replacement firmware. The device reconnects during that transition. If access
fails, inspect its current Windows driver and USB identity rather than assuming
the mode change failed. A network/ADB interface is not the required burn-mode
endpoint.

"No backend available" means the DLL did not load. "Found a potential device
that is not ready" hides an underlying exception and is not proof that the
Car Thing is broken. Use the launcher above; if necessary, inspect access with:

~~~powershell
@'
import libusb_package
import usb.core
import usb.backend.libusb1
backend = usb.backend.libusb1.get_backend(find_library=libusb_package.find_library)
print("Backend:", backend)
if backend is None:
    raise SystemExit("No USB backend")
device = usb.core.find(idVendor=0x1b8e, idProduct=0xc003, backend=backend)
print("Found:", device is not None)
if device is not None:
    print("Product:", device.product)
'@ | .\.venv\Scripts\python.exe -
~~~

### Test a read, then make a fresh full backup

Leave the Car Thing connected in USB Burn Mode. In **Windows PowerShell**:

~~~powershell
$testFile = "boot-b-test-$(Get-Date -Format yyyyMMdd-HHmmss).dump"
.\.venv\Scripts\python.exe .\run_superbird.py --dump_partition boot_b $testFile
~~~

The test should finish with a 16 MB file. Then:

~~~powershell
$backup = Join-Path (Get-Location).Path "carthing-full-backup-$(Get-Date -Format yyyyMMdd-HHmmss)"
if (Test-Path -LiteralPath $backup) { throw "Backup destination already exists" }
.\.venv\Scripts\python.exe .\run_superbird.py --dump_device $backup
if ($LASTEXITCODE -ne 0) { throw "Backup failed; retain partial files and inspect output" }
~~~

**Never reuse an existing backup directory:** the upstream dump command deletes
its destination before creating it. Keep Windows awake and the cable connected.
Do not run other USB commands concurrently. Require **device dump complete**,
not just a final progress line.

Fast reads retry individual partitions from zero, overwriting that partition's
partial file, while preserving earlier completed partitions. If retries exhaust
or a command hangs, the backup is incomplete. Stop the process before unplugging;
power-cycle into USB Mode and re-enter burn mode before another attempt. Test
another data cable/direct PC port. Increasing a timeout does not fix a pipe
error. Do not disable security settings or flash firmware to diagnose reads.

### Verify completeness and generate SHA-256 hashes

Still in **Windows PowerShell**, create the verifier:

~~~powershell
@'
import hashlib
import json
import sys
from pathlib import Path

folder = Path(sys.argv[1])
expected = {
    "bootloader.dump": 0x200000, "env.dump": 0x800000,
    "fip_a.dump": 0x400000, "fip_b.dump": 0x400000,
    "logo.dump": 0x800000,
    "dtbo_a.dump": 0x400000, "dtbo_b.dump": 0x400000,
    "vbmeta_a.dump": 0x100000, "vbmeta_b.dump": 0x100000,
    "boot_a.dump": 0x1000000, "boot_b.dump": 0x1000000,
    "misc.dump": 0x800000,
    "system_a.ext2": 0x2040B000, "system_b.ext2": 0x2040B000,
    "data.ext4": (0x889EA000, 0x859EA000),
    "settings.ext4": 0x10000000,
}
for name, size in expected.items():
    allowed = size if isinstance(size, tuple) else (size,)
    path = folder / name
    if not path.is_file() or path.stat().st_size not in allowed:
        raise SystemExit(f"FAILED: missing or incorrect size: {name}")
env_text = folder / "env.txt"
if not env_text.is_file() or env_text.stat().st_size == 0:
    raise SystemExit("FAILED: missing or empty env.txt")

hashes = {}
for name in sorted([*expected, "env.txt"]):
    digest = hashlib.sha256()
    with (folder / name).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    hashes[name] = digest.hexdigest()

manifest = folder / "SHA256.json"
if "--check" in sys.argv[2:]:
    recorded = json.loads(manifest.read_text(encoding="utf-8"))
    if recorded != hashes:
        raise SystemExit("FAILED: checksums do not match the saved manifest")
    print("PASS: all 17 file hashes match the saved manifest.")
else:
    if manifest.exists():
        raise SystemExit("Manifest exists; use --check instead of replacing it")
    manifest.write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    print("SHA-256 checksums saved for all 17 files.")
print("PASS: all 16 partition sizes match; env.txt is present.")
print("Backup:", folder.resolve())
'@ | Set-Content -Encoding ascii .\verify_backup.py

.\.venv\Scripts\python.exe .\verify_backup.py "$backup"
~~~

For a later PowerShell session, set $backup to the actual full backup-directory
path first. If a manifest already exists, use --check. A size check and hashes
establish file completeness and a baseline for later comparisons; they do not
prove a successful restore or independently prove every byte read from eMMC.

### Preserve an independent copy before flashing

A native Windows dump is already independent of the Pi's SD card. Copy the
**entire backup directory**, including env.txt and SHA256.json, to a separate NAS
share or external drive. Use your actual destination in place of the example:

~~~powershell
$copyRoot = Read-Host "Existing NAS share or external-drive folder for the second copy"
if (-not (Test-Path -LiteralPath $copyRoot -PathType Container)) { throw "Destination does not exist" }
$copy = Join-Path $copyRoot (Split-Path -Leaf $backup)
if (Test-Path -LiteralPath $copy) { throw "Choose a new destination; do not overwrite a backup" }
Copy-Item -LiteralPath $backup -Destination $copy -Recurse -ErrorAction Stop
.\.venv\Scripts\python.exe .\verify_backup.py "$copy" --check
if ($LASTEXITCODE -ne 0) { throw "Second-copy verification failed; do not flash" }
~~~

Keep the original manifest; do not regenerate it on the copy. A directory inside
a sync folder does not establish that upload has completed or that a remote
copy has been verified. Retain the backup privately: it can contain DeskThing
settings, account data, and credentials. Do not commit dumps or env.txt to GitHub.

## 1b. Bootstrap WallThing only after the backup is secured

If the Car Thing already runs upstream WallThing v2.x, proceed to pairing below.
A DeskThing installation is not the same prerequisite. After a complete backup
and a verified independent copy, the intended route is the **upstream v2.0
landscape bootstrap image**, followed by this fork's source migration at the
same reviewed commit used on the Pi.

Obtain the image from the
[upstream v2.0 release](https://github.com/bishopdynamics/superbird-debian-kiosk/releases/tag/v2.0).
Verify the exact selected asset against a published checksum if available; do
not invent a checksum or treat a locally generated hash as publisher validation.
Confirm the extracted image's layout and restore instructions before flashing.
No new flashable image is supplied by this fork.

The Windows work above validates backup only. Bootstrap flashing and restoration
have not yet been exercised in this setup. Do not infer a tested restore path
from a successful dump or apply unrelated firmware/mainline fastboot instructions.
The upstream bootstrap has shared credentials until migration; keep it isolated
and pair/migrate over the direct Pi USB connection.

Hardware acceleration is outside this procedure. Keep certificate validation,
unique credentials, restricted administration, and the Chromium sandbox enabled.
If the old kernel cannot support the sandbox, diagnose that failure rather than
adding --no-sandbox.

## 2. Pair the Car Thing before locking its credentials

After rebooting the Pi, attach the Car Thing running the existing upstream image to the Pi's USB data/OTG port. The Pi's power supply goes to its separate power port. On the Pi:

```bash
cd /repo
sudo python3 pair_device.py
```

This creates a unique Ed25519 key on the Pi, checks that the device route uses `usb0`, and installs the public key using `ssh-copy-id`. Confirm the host key of your directly connected device and enter its existing password when SSH prompts. The upstream bootstrap password is `superbird`; this fork subsequently locks password authentication and revokes the known shared key.

The pairing command must finish with **Unique key verified**. Keep the Pi's `~/.ssh/wallthing_ed25519` private. Back it up securely if it is your only administrative key. An additional personal public key may be installed before migration for recovery.

## 3. Install the same commit on the device

On the Pi:

```bash
ssh -i ~/.ssh/wallthing_ed25519 -o IdentitiesOnly=yes superbird@192.168.7.2
```

Now inside the Car Thing's shell, inspect `/repo` for local changes and preserve them. Set the same selected SHA again in this shell:

```bash
WALLTHING_COMMIT=PASTE_THE_SAME_FULL_COMMIT_SHA
sudo git -C /repo status --short
sudo git -C /repo remote set-url origin https://github.com/christopherjnash/superbird-debian-kiosk.git
sudo git -C /repo fetch origin
sudo git -C /repo checkout --detach "$WALLTHING_COMMIT"
cd /repo
sudo python3 install_reviewed.py --device superbird --commit "$WALLTHING_COMMIT"
```

The installer refuses to proceed without a non-legacy authorized key or an already mounted settings partition. It preserves the current browser profile and changes its owner to the browser account. The USB gadget service is not restarted during installation, preserving the SSH connection. Disabled HA is the default for migrated configurations without an explicit `ha_enabled` setting.

Before closing this session, open a second SSH connection from the Pi with the unique key and verify that it succeeds. Then reboot the Car Thing and verify it again.

## 4. Open administration through SSH

There are separate generated passwords on the Pi and Car Thing. The username for both web pages is `admin`. Read each password in that machine's SSH shell:

```bash
sudo cat /etc/kiosk/admin-token
```

The token appears after the corresponding service first starts. Keep it private.

In a Pi terminal, forward the Car Thing's loopback administration port to the Pi's loopback address. Leave this command running:

```bash
ssh -N -o ExitOnForwardFailure=yes -i ~/.ssh/wallthing_ed25519 -o IdentitiesOnly=yes -L 127.0.0.1:8080:127.0.0.1:80 superbird@192.168.7.2
```

In a separate terminal on your computer, replace `PI_HOSTNAME` with your Pi's hostname or address and leave this running:

```bash
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8080:127.0.0.1:8080 -L 127.0.0.1:9090:127.0.0.1:9090 superbird@PI_HOSTNAME
```

Open `http://127.0.0.1:8080` for the Car Thing settings and `http://127.0.0.1:9090` for Pi maintenance. Each page uses its own token. Set **Browser URL** to the application you want displayed. Use a valid HTTPS certificate; certificate errors are no longer bypassed. For CLI writes through the tunnel, HTTP Basic authentication and the `X-WallThing-Action: 1` header are required.

## Optional remote screen and debugging

VNC, websockify, and the DevTools proxy are disabled by default. To use remote screen input temporarily, set a private VNC password in the settings page, then run on the Car Thing:

```bash
sudo systemctl start vnc websockify
```

The credential installed during migration is random; set your own in the UI before connecting. Add `-L 127.0.0.1:5901:127.0.0.1:5901` to **both** SSH tunnel commands above and reconnect them. Reload the settings page to use its embedded screen. A native VNC client instead needs port 5900 forwarded through both hops. Afterward:

```bash
sudo systemctl stop vnc websockify
```

DevTools similarly requires `sudo systemctl start haproxy` on the device and port 9223 forwarded through both SSH hops. Stop the proxy afterward. Do not expose any of these ports on the LAN/router. Local administrator access remains privileged, and this fork does not replace the old operating system's security boundary.

## Check the hardware before relying on it

1. Confirm the browser runs as `wallthing-browser` and loads the chosen page without sandbox/certificate exceptions.
2. Verify touch, orientation, scaling, sign-in, and application actions.
3. Stop the browser process once and confirm the display recovers. Repeated rapid crashes should stop retrying after the configured limits; inspect `journalctl -u kiosk` rather than adding `--no-sandbox`.
4. Make the configured server unavailable and confirm the reconnecting screen appears, then the application returns when connectivity is restored.
5. Reboot the Pi and Car Thing. Check USB networking, URL/profile persistence, and SSH-key access. Turn off the setup computer; the display should keep working.
6. If using HA, test startup while HA is unavailable. Display startup must still succeed.

Inspect service state with `systemctl status kiosk` on the Car Thing or `systemctl status kiosk-updater` on the Pi. A 30-second active-service check is not proof of a working screen.

## Updates and recovery

Fetch and review a new commit, then repeat the appropriate exact-commit installation command. The old web update action and floating-branch upgrade scripts are disabled. No automatic fetch, reset, or branch change happens inside `install_reviewed.py`.

Backups are stored on each device in `/var/backups/wallthing/<timestamp>/`, including configuration and installed scripts (plus host firewall rules where present). The previously recorded commit is included when available. On failure, inspect the journal and retain the backup. Restore needed configuration/scripts while the affected service is stopped, or check out a previous **fork** commit and run its installer. Do not blindly restore the upstream shared key, passwords, or LAN forwards. Keep the pre-migration full-device dump as a separate recovery option, labeled with the firmware it actually contains.
