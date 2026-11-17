# ASUS / Asuswrt-Merlin

This is a separate static build of the same AWG/QUIC fork core as OpenWrt.
It does not install an OpenWrt package, change firmware, resize JFFS, or
replace Entware's Tailscale package. Core: **v1.104.7**, QUIC
**v0.65.0-quic.4**, BBRv3/pacing retained. Peer Relay and Taildrop remain.
Only self-update/appliance management are excluded; updates use this manager.
Payload and hook checksums use `sha256sum`, or the firmware's OpenSSL SHA-256
implementation when that BusyBox applet is absent (as on ET8 Gnuton).

## Hardware and startup

| Firmware | Startup | Requirements |
| --- | --- | --- |
| Stock ET12 without USB | Existing fwtool `S45custom-init` dispatcher | ARM64, Linux 4.19, writable JFFS, TUN |
| ET8 Gnuton Merlin 388.11_1 | Merlin service/firewall scripts | ARMv7, Linux 4.1, writable JFFS, TUN |
| Other stock firmware | Same custom-init dispatcher, or an already working Entware boot setup | ARM64/ARMv7, Linux >=3.2, TUN |
| Asuswrt-Merlin | `services-start`, `services-stop`, `firewall-start` | Enable JFFS custom scripts in Administration / System |

An arbitrary stock ASUS firmware does **not** necessarily execute JFFS
scripts. Installation refuses to claim boot support when the required hook
is missing. This package does not flash/patch firmware. Old Linux 2.6 routers
and MIPS models are unsupported. A build for an architecture does not prove
TUN/firewall compatibility on every model.

Merlin hooks follow the [firmware's documented user-script interface](https://github.com/Asuswrt-Merlin/asuswrt-merlin.ng/wiki/User-scripts).
An AiMesh node may redirect its Web GUI to the main router. Enable custom
scripts on that node over SSH, as documented by Merlin, after checking the
existing contents of `/jffs/scripts`:

```sh
nvram set jffs2_scripts=1
nvram commit
```

An existing hook is moved unchanged to `.tailscale-asus.original` and invoked
as a separate process with its original interpreter. An existing `exit 0`, missing final newline, or symlink
does not prevent our hook from running. Uninstall restores the original;
if a managed hook has subsequently been edited, automatic removal refuses
to overwrite it. Existing stock/Entware hook name collisions also abort.

## ET12 storage layout

- `/jffs/addons/tailscale-awg/releases/`: current and previous **gzip payloads**,
  checksummed manifests and manager scripts. No unpacked executable on flash.
- `/jffs/addons/tailscale-awg/state/`: private, persistent node identity.
- `/tmp/tailscale-awg/`: unpacked executable, socket, PIDs, and log capped at
  256 KiB. Recreated from the local compressed payload after boot, without WAN.

An update downloads and checks the candidate in RAM, executes its version
check, then copies and verifies it on flash before atomically switching the
active pointer. The old active payload stays on flash throughout. Startup
failure restores it. There must be space for **active + candidate + 4 MiB
reserve**. An older rollback payload may be removed only after RAM validation.
Otherwise the update aborts; it never deletes the active payload to make room.
Keep additional room for other applications and growing state. No UBI/JFFS
resizing is performed. `TS_ASUS_HOME` may select persistent USB storage;
`TS_ASUS_RUN` must remain under `/tmp`.

## One-command installation

Run over SSH on either stock firmware or Merlin:

```sh
curl -fsSL https://gh-proxy.org/https://github.com/LiuTangLei/openwrt-tailscale-awg/releases/latest/download/install-asus.sh | /bin/sh
```

The release-pinned installer detects the CPU and firmware, enables Merlin's
JFFS scripts when necessary, and downloads the matching compressed payload.
It tries the upstream mirror services `gh-proxy.org`, `ghfast.top`, then GitHub
directly. Scripts and manifests are checked against pinned SHA256 values;
payload checksums remain mandatory. Invalid mirror pages and partial downloads
are rejected before changing the active installation.
Stock firmware still needs one of the startup hooks listed above; firmware
flashing and JFFS resizing are not automated. Existing hooks and node identity
are preserved. An installation failure restores a previously disabled Merlin
script setting.

On an interactive SSH terminal it then opens a Chinese management menu for
login/Headscale, AWG/QUIC configuration, restart, logs, updates, rollback and
uninstall. Run the same command again to reopen it: an identical installed
version skips the payload download and retains the running daemon. Add
`--no-menu` when invoking the downloaded installer in automation.

## Install a particular release

Download `tailscale-asus` from the **same release** as the chosen manifest.
To select a specific version explicitly (replace TAG):

```sh
TAG=v1.104.7
curl -fL "https://github.com/LiuTangLei/openwrt-tailscale-awg/releases/download/$TAG/tailscale-asus" -o /tmp/tailscale-asus
sh /tmp/tailscale-asus install --release "$TAG" --platform auto
/jffs/addons/tailscale-awg/tailscale-asus status
```

Release manifests bind the compressed payload, decompressed binary and
installer SHA256. They are fetched over verified HTTPS from a version-specific
GitHub release; SHA256 detects corruption, not compromise of the release account.
For offline installation, transfer the installer, architecture-specific gzip
and manifest, then use `install --bundle FILE.gz --manifest FILE.gz.manifest`.

If your existing tailnet uses AWG, also import its shared camouflage parameters
with `cli set --amnezia-wg JSON`. A new device starts with standard WireGuard
parameters. Keep the new device identity independent; do not copy another
device's state directory or private keys.

The daemon starts without joining a tailnet or advertising LAN/exit routes.
Login explicitly, preserving the router's normal DNS and routes:

```sh
/jffs/addons/tailscale-awg/tailscale-asus cli up --accept-dns=false --accept-routes=false
# For a custom control server add its --login-server URL.
```

The manager does not copy another device's identity or enable automatic
updates. CLI arguments including AWG/QUIC settings pass to the fork unchanged.
Tailscaled manages its own netfilter rules. Merlin's firewall hook restarts
only this instance; the stock supervisor detects loss of its previously
established `ts-input` jump and lets the daemon rebuild it. No blanket firewall
flush, third-party rule removal, WAN/LAN/DNS/NVRAM change, or global forwarding
sysctl is performed by the installer.

Use the manager to activate transport changes:

```sh
M=/jffs/addons/tailscale-awg/tailscale-asus
$M cli awg set --yes --no-restart quic
$M restart
$M cli awg status --json
```

All communicating peers must use a compatible transport. QUIC selection clears
the saved AWG camouflage parameters; retain those parameters if you plan to
return to your existing AWG network. To restore an AWG profile, stage its JSON
with `cli awg set --yes --no-restart 'JSON'`, then run the manager's `restart`.

```sh
M=/jffs/addons/tailscale-awg/tailscale-asus
$M restart
$M rollback
$M uninstall             # retains state; restores original hooks
```

Do not delete `state/` unless you intend to permanently remove this device's
identity. Firmware updates may remove a stock fwtool hook; check that startup
support remains after a firmware upgrade. Application reboot/traffic acceptance
is recorded separately from compilation and hook tests.

If an earlier `v1.104.7` ASUS preview is already installed, its manager/manifest
may differ from the final release. The installer refuses to overwrite a slot
with different contents. Download the final installer first, run the existing
manager's `uninstall` (which retains identity), then install the final release.
This briefly stops Tailscale and preserves the node's existing login state.

Tested on stock ET12 and ET8 Gnuton Merlin, including AWG/QUIC data transfer
and service recovery. IPv6 follows the firmware's existing setting. Other
models meeting the requirements above are welcome; report problems in Issues.

## Build

```sh
python3 asus/build.py --source /path/to/clean/fork \
  --release v1.104.7 --arch arm64 --output asus/out --go /path/to/go1.27.4
# Repeat with --arch armv7 for supported ARMv7 routers.
```

The builder refuses an unqualified/dirty core, embeds the exact commit,
disables CGO, verifies dependency identities and emits deterministic gzip
payloads. The ASUS workflow only builds artifacts; it does not move a stable
release or automatically publish an untested preview.
