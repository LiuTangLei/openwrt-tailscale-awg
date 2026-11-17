# ASUS / Asuswrt-Merlin (preview)

This is a separate static build of the same AWG/QUIC fork core as OpenWrt.
It does not install an OpenWrt package, change firmware, resize JFFS, or
replace Entware's Tailscale package. Core: **v1.104.7**, QUIC
**v0.65.0-quic.4**, BBRv3/pacing retained. Peer Relay and Taildrop remain.
Only self-update/appliance management are excluded; updates use this manager.

## Hardware and startup

| Firmware | Startup | Requirements |
| --- | --- | --- |
| Stock ET12 without USB | Existing fwtool `S45custom-init` dispatcher | ARM64, Linux 4.19, writable JFFS, TUN |
| Other stock firmware | Same custom-init dispatcher, or an already working Entware boot setup | ARM64/ARMv7, Linux >=3.2, TUN |
| Asuswrt-Merlin | `services-start`, `services-stop`, `firewall-start` | Enable JFFS custom scripts in Administration / System |

An arbitrary stock ASUS firmware does **not** necessarily execute JFFS
scripts. Installation refuses to claim boot support when the required hook
is missing. This package does not flash/patch firmware. Old Linux 2.6 routers
and MIPS models are unsupported. A build for an architecture does not prove
TUN/firewall compatibility on every model.

Merlin hooks follow the [firmware's documented user-script interface](https://github.com/Asuswrt-Merlin/asuswrt-merlin.ng/wiki/User-scripts).
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

## Install a particular preview

Download `tailscale-asus` from the **same release** as the chosen manifest.
Do not pipe a moving branch directly into a root shell. Example (replace TAG):

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
