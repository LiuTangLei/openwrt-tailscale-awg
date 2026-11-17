#!/bin/sh
# One-command ASUS installer. The release asset pins its matching manager.
set -eu
umask 077
PATH=/usr/sbin:/usr/bin:/sbin:/bin:/opt/sbin:/opt/bin
export PATH
RELEASE=v1.104.7
REPO=LiuTangLei/openwrt-tailscale-awg
work=/tmp/tailscale-asus-install.$$
enabled_scripts=false
installed=false

die() { echo "ASUS Tailscale: $*" >&2; exit 1; }
cleanup() {
    rm -rf "$work"
    if [ "$enabled_scripts" = true ] && [ "$installed" = false ]; then
        nvram set jffs2_scripts=0
        nvram commit
    fi
}

[ "$(awk '/^Uid:/ {print $3}' /proc/self/status)" = 0 ] || die "run this command as root"
[ -d /jffs ] && type nvram >/dev/null 2>&1 || die "this installer is for ASUS firmware"
case "$(uname -m)" in aarch64|arm64|armv7l|armv8l) ;; *) die "supported CPUs: ARM64 and ARMv7";; esac
mkdir "$work" || die "cannot create temporary directory"
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
    --connect-timeout 15 --max-time 300 --retry 2 \
    "https://github.com/$REPO/releases/download/$RELEASE/tailscale-asus" \
    -o "$work/tailscale-asus"

# Stock custom-init takes precedence, matching the manager's autodetection.
if ! { [ -x /rom/etc/init.d/custom-init.sh ] && [ -e /rom/etc/rc3.d/S45custom-init ]; } &&
    nvram get rc_support | grep -qw am_addons; then
    if [ "$(nvram get jffs2_scripts)" = 0 ]; then
        echo "ASUS Tailscale: enabling Merlin JFFS custom scripts"
        enabled_scripts=true
        nvram set jffs2_scripts=1
        nvram commit
    fi
fi

sh "$work/tailscale-asus" install --release "$RELEASE" --platform auto
installed=true
echo "ASUS Tailscale: installed $RELEASE; login with:"
echo "  ${TS_ASUS_HOME:-/jffs/addons/tailscale-awg}/tailscale-asus cli up --accept-dns=false --accept-routes=false"
