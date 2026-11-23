#!/bin/sh
# ASUS installer and interactive manager. Binaries stay pinned to this release.
# BusyBox ash and dash both support local variables.
# shellcheck disable=SC3043
set -eu
umask 077
PATH=/usr/sbin:/usr/bin:/sbin:/bin:/opt/sbin:/opt/bin
export PATH
RELEASE=v1.104.7-r1
MANAGER_SHA256=82c6cfec128b0b31266ef471c63491218244edd25c50039a35c713041c542a8e
MANIFEST_ARM64_SHA256=b79baf17f61aada5d281572c8636e0abe607d2ecfc82a1cfae98a2700ee4e665
MANIFEST_ARMV7_SHA256=13f9bcafe39ef80da9733d9bc4dcd42cbd3a32ef5d40ea34c984dafce9e264a0
REPO=LiuTangLei/openwrt-tailscale-awg
DEFAULT_MIRRORS='https://gh-proxy.org https://ghfast.top direct'
HOME_DIR=${TS_ASUS_HOME:-/jffs/addons/tailscale-awg}
RUN_DIR=${TS_ASUS_RUN:-/tmp/tailscale-awg}
M=$HOME_DIR/tailscale-asus
work=/tmp/tailscale-asus-install.$$
enabled_scripts=false
installed=false
show_menu=true
custom_mirror=''

die() { echo "ASUS Tailscale: $*" >&2; exit 1; }
cleanup() {
    rm -rf "$work"
    if [ "$enabled_scripts" = true ] && [ "$installed" = false ]; then
        nvram set jffs2_scripts=0
        nvram commit
    fi
}
sha() {
    local digest
    if type sha256sum >/dev/null 2>&1; then
        digest=$(sha256sum "$1") || return
        printf '%s\n' "${digest%% *}"
    else
        digest=$(openssl dgst -sha256 "$1") || return
        printf '%s\n' "${digest##* }"
    fi
}
field() { awk -F= -v key="$2" '$1==key {n++; value=substr($0,index($0,"=")+1)} END {if(n!=1) exit 1; print value}' "$1"; }
fetch() {
    rm -f "$2.part"
    if curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --tlsv1.2 \
        --connect-timeout 5 --max-time "$3" "$1" -o "$2.part"; then
        mv -f "$2.part" "$2"
    else
        rm -f "$2.part"
        return 1
    fi
}
prefix_for() { case "$1" in direct) prefix='' ;; *) prefix=$1/ ;; esac; }
set_mirror() {
    case "$1" in
        https://*[!a-zA-Z0-9./:_~-]*) die '--mirror requires an HTTPS prefix';;
        https://?*) custom_mirror=${1%/};;
        *) die '--mirror requires an HTTPS prefix';;
    esac
}
preflight_space() {
    local binary_bytes need_ram_kb probe_run tmp_free_kb mem_avail_kb probe_home flash_free_kb reclaim=0 old previous
    binary_bytes=$(field "$1" binary_bytes)
    case "$binary_bytes" in ''|*[!0-9]*|0*) die 'invalid binary size in manifest';; esac
    need_ram_kb=$(( binary_bytes / 1024 + 65536 ))
    probe_run=$RUN_DIR
    while [ ! -e "$probe_run" ] && [ "$probe_run" != / ]; do probe_run=$(dirname "$probe_run"); done
    tmp_free_kb=$(df -k "$probe_run" | awk 'END {print $4}')
    mem_avail_kb=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
    [ -n "$mem_avail_kb" ] || mem_avail_kb=$(awk '/^MemFree:/ {print $2}' /proc/meminfo)
    [ "$tmp_free_kb" -ge "$need_ram_kb" ] && [ "$mem_avail_kb" -ge "$need_ram_kb" ] ||
        die "insufficient RAM: need at least ${need_ram_kb} KiB free before downloading payload"
    if [ ! -d "$HOME_DIR/releases/$slot" ]; then
        probe_home=$HOME_DIR
        while [ ! -e "$probe_home" ] && [ "$probe_home" != / ]; do probe_home=$(dirname "$probe_home"); done
        flash_free_kb=$(df -k "$probe_home" | awk 'END {print $4}')
        old=$(cat "$HOME_DIR/current" 2>/dev/null || true)
        previous=$(cat "$HOME_DIR/previous" 2>/dev/null || true)
        case "$previous" in ''|*[!a-zA-Z0-9._-]*|.*) previous='';; esac
        if [ -n "$previous" ] && [ "$previous" != "$old" ] && [ -d "$HOME_DIR/releases/$previous" ]; then
            reclaim=$(du -sk "$HOME_DIR/releases/$previous" | awk '{print $1}')
        fi
        # Conservative lower bound before downloading the ~15 MiB gzip; tailscale-asus checks exact size + 4 MiB reserve.
        [ $((flash_free_kb + reclaim)) -ge 16384 ] ||
            die 'insufficient flash for active + candidate compressed payloads and 4 MiB reserve; active release is untouched'
    fi
}

while [ $# -gt 0 ]; do
    case "$1" in
        --no-menu) show_menu=false; shift;;
        --mirror) [ $# -ge 2 ] || die '--mirror requires an HTTPS prefix'; set_mirror "$2"; shift 2;;
        --help|-h)
            echo 'Usage: /bin/sh install-asus.sh [--no-menu] [--mirror PREFIX]'
            echo 'ASUS stock/Merlin installer; --no-menu skips the interactive menu.'
            echo '--mirror (or TS_ASUS_MIRROR) prefers an HTTPS proxy for checksum-pinned downloads.'
            exit 0;;
        *) die "unknown option: $1";;
    esac
done
[ -n "$custom_mirror" ] || [ -z "${TS_ASUS_MIRROR:-}" ] || set_mirror "$TS_ASUS_MIRROR"
MIRRORS=$DEFAULT_MIRRORS
[ -z "$custom_mirror" ] || MIRRORS="$custom_mirror $MIRRORS"

[ "$(awk '/^Uid:/ {print $3}' /proc/self/status)" = 0 ] || die 'run this command as root'
[ -d /jffs ] && type nvram >/dev/null 2>&1 || die 'this installer is for ASUS firmware'
case "$(uname -m)" in
    aarch64|arm64) ARCH=arm64; MANIFEST_SHA256=$MANIFEST_ARM64_SHA256;;
    armv7l|armv8l) ARCH=armv7; MANIFEST_SHA256=$MANIFEST_ARMV7_SHA256;;
    *) die 'supported CPUs: ARM64 and ARMv7';;
esac
kernel=$(uname -r); major=${kernel%%.*}; kernel=${kernel#*.}; minor=${kernel%%.*}
[ "$major" -gt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -ge 2 ]; } ||
    die 'Go requires Linux 3.2 or newer (old 2.6 ASUS kernels are unsupported)'
type curl >/dev/null 2>&1 || die 'curl is required'
curl --version | grep -qw UnixSockets || die 'curl with UnixSockets support is required'
if [ -x /rom/etc/init.d/custom-init.sh ] && [ -e /rom/etc/rc3.d/S45custom-init ]; then
    detected_platform=stock
elif nvram get rc_support | grep -qw am_addons; then
    detected_platform=merlin
elif [ -x /opt/etc/init.d/rc.unslung ]; then
    detected_platform=entware
else
    die 'no supported boot hook (checked /rom/etc/init.d/custom-init.sh + /rom/etc/rc3.d/S45custom-init, Merlin am_addons, and /opt/etc/init.d/rc.unslung); stock firmware needs an existing fwtool custom-init or Entware startup hook'
fi
if [ -f "$HOME_DIR/platform" ] && [ "$(cat "$HOME_DIR/platform")" != "$detected_platform" ]; then
    die "use the original platform when updating ($(cat "$HOME_DIR/platform") != $detected_platform)"
fi

mkdir "$work" || die 'cannot create temporary directory'
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

asset=tailscale-asus-$RELEASE-$ARCH.gz
slot=$RELEASE-$ARCH
base=https://github.com/$REPO/releases/download/$RELEASE
selected=''
already_current=false
space_checked=false
for mirror in $MIRRORS; do
    prefix_for "$mirror"
    echo "ASUS Tailscale: checking $mirror"
    if ! fetch "$prefix$base/$asset.manifest" "$work/manifest" 20 ||
       ! fetch "$prefix$base/tailscale-asus" "$work/tailscale-asus" 30; then continue; fi
    if [ "$(sha "$work/manifest")" != "$MANIFEST_SHA256" ] ||
       [ "$(sha "$work/tailscale-asus")" != "$MANAGER_SHA256" ]; then
        echo 'ASUS Tailscale: invalid or stale mirror metadata; trying another source'
        continue
    fi
    if [ -x "$M" ] && [ "$(cat "$HOME_DIR/current" 2>/dev/null || true)" = "$slot" ] &&
       cmp -s "$work/manifest" "$HOME_DIR/releases/$slot/manifest" &&
       cmp -s "$work/tailscale-asus" "$HOME_DIR/releases/$slot/manager"; then
        selected=$mirror; already_current=true; break
    fi
    if [ "$space_checked" = false ]; then
        preflight_space "$work/manifest"
        space_checked=true
    fi
    if fetch "$prefix$base/$asset" "$work/payload.gz" 300 &&
       [ "$(sha "$work/payload.gz")" = "$(field "$work/manifest" sha256)" ]; then
        selected=$mirror; break
    fi
    echo 'ASUS Tailscale: payload download or checksum failed; trying another source'
done
[ -n "$selected" ] || die 'no verified download source is available; current installation is unchanged'

if [ "$already_current" = false ] && [ "$detected_platform" = merlin ]; then
    if [ "$(nvram get jffs2_scripts)" = 0 ]; then
        echo 'ASUS Tailscale: enabling Merlin JFFS custom scripts'
        enabled_scripts=true
        nvram set jffs2_scripts=1
        nvram commit
    fi
fi

if [ "$already_current" = true ]; then
    "$M" start
    echo "ASUS Tailscale: $RELEASE is already installed; service retained"
else
    /bin/sh "$work/tailscale-asus" install --bundle "$work/payload.gz" --manifest "$work/manifest" --platform auto
fi
installed=true
echo "ASUS Tailscale: ready ($RELEASE, $selected)"
if [ "$show_menu" = true ] && ( : </dev/tty ) 2>/dev/null; then
    if [ -n "$custom_mirror" ]; then
        "$M" menu --mirror "$custom_mirror" </dev/tty >/dev/tty 2>&1
    else
        "$M" menu </dev/tty >/dev/tty 2>&1
    fi
    [ ! -x "$M" ] || echo "ASUS Tailscale: reopen menu offline anytime with: $M menu"
else
    echo "Menu:  $M menu"
    echo "Login: $M cli up --accept-dns=false --accept-routes=false"
fi
