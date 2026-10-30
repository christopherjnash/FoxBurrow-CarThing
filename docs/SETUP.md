# Setup and migration

This is a source migration for the upstream v2.x Debian installation. No fork firmware image or physical hardware test is supplied. Keep the full stock backup and recovery tools available. Use a dedicated Pi Zero 2 W running Raspberry Pi OS Lite 64-bit **Bullseye**, with user `superbird`, your own password, Wi-Fi configured, and SSH enabled. Current images with a different codename are rejected by the existing hardware installer.

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

Backups are stored on each device in `/var/backups/wallthing/<timestamp>/`, including configuration and installed scripts (plus host firewall rules where present). The previously recorded commit is included when available. On failure, inspect the journal and retain the backup. Restore needed configuration/scripts while the affected service is stopped, or check out a previous **fork** commit and run its installer. Do not blindly restore the upstream shared key, passwords, or LAN forwards. Keep the stock dump as a separate full-device recovery option.
