# WallThing: supervised Chromium on Spotify Car Thing

This fork of [bishopdynamics/superbird-debian-kiosk](https://github.com/bishopdynamics/superbird-debian-kiosk) keeps the existing Debian 11 root filesystem and stock 4.9.113 kernel. A Raspberry Pi Zero 2 W provides USB networking; Chromium runs on the Car Thing.

**Version 2.0.2 is a source update awaiting physical-device validation. No new flashable image is published.** The older kernel/browser, display performance, Chromium sandbox support on that kernel, touch input, and sign-in persistence still need testing on the hardware. Keep a complete backup of the device's existing firmware; a device already running DeskThing needs a DeskThing recovery backup.

## Changes in this fork

- Unique SSH keys replace the shared upstream key; device password login is locked after pairing. No private key is distributed in this source tree.
- Both administration servers listen only on loopback, require a generated credential, and reject cross-origin writes. Mutating actions use POST. Logs and embedded password values are escaped.
- VNC and the DevTools proxy start disabled and bind to loopback when enabled. The host removes the project's old LAN port forwards without flushing unrelated firewall rules.
- Chromium runs as a separate account with its sandbox and certificate verification enabled. Xorg still runs as root for the existing framebuffer setup.
- Home Assistant is optional and connects in the background with request timeouts. A missing HA server no longer blocks browser startup.
- Browser exits trigger bounded retries; repeated failures restart the kiosk service. An offline screen retries the configured URL when connectivity returns.
- Updates require an explicitly selected commit and a clean checkout. Configuration/scripts are backed up, and the service must stay active for 30 seconds before installation is recorded as successful.

## Setup and updates

Follow [the setup and migration guide](docs/SETUP.md), including unique-key pairing **before** installing the device changes. Direct LAN administration and the old “Update to Latest” flow are no longer used.

For a new installation, the upstream v2 image is only a bootstrap. It still contains shared credentials until this fork is installed. Use a dedicated Pi, migrate over the direct USB link, and keep that bootstrap isolated from untrusted networks. Before flashing anything, complete the guide's native Windows backup procedure, check the partition sizes, and verify a second copy against its SHA-256 manifest.

The default browser URL is `https://example.org`. Set your own URL through the SSH-tunneled administration page. Enable Home Assistant explicitly only if you want its existing button actions. Application-specific dial/preset controls and an OS/browser upgrade are separate future work.

## Development checks

```bash
python3 -m venv .venv
.venv/bin/pip install -r files/data/scripts/requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q files *.py
```

Tests cover the real HTTP configuration routes, authentication, CSRF, private configuration persistence, independent startup, browser retry limits, offline recovery, credential revocation, log escaping, request timeouts, and firewall migration. They do not validate the hardware. CI runs source checks on Python 3.9 and 3.12.

## Building an image

The upstream build workflow requires an ARM64 Debian 12 build host and your own stock dump in `dumps/stock_dump`. Supply the Pi's public pairing key; the build refuses the shared upstream key:

```bash
sudo env WALLTHING_SSH_PUBLIC_KEY_FILE=/absolute/path/wallthing_ed25519.pub python3 build_images.py
```

Never distribute an image containing your own authorized key as a generic public image. Private keys stay on the host that generated them.

The upstream [case designs](Wallthing/), [pictures](pictures/), and [historical changelog](Changelog.md) are retained. The MIT license and upstream attribution remain unchanged.
