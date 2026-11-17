#!/bin/sh
# ASUS installer and interactive manager. Binaries stay pinned to this release.
# BusyBox ash and dash both support local variables.
# shellcheck disable=SC3043
set -eu
umask 077
PATH=/usr/sbin:/usr/bin:/sbin:/bin:/opt/sbin:/opt/bin
export PATH
RELEASE=v1.104.7
MANAGER_SHA256=9136ddbcd0dd9a031765193be067bddf3eb2d38e78843001131ba3736cb75792
MANIFEST_ARM64_SHA256=1ec3d4745b135433b42c5766f548a1694cb3bb08badb63742689e4e3335ace48
MANIFEST_ARMV7_SHA256=f00d8856f88264cc826787f66197d85632c97b5db359c186feb5e7441a8a5eef
REPO=LiuTangLei/openwrt-tailscale-awg
MIRRORS='https://gh-proxy.org https://ghfast.top direct'
HOME_DIR=${TS_ASUS_HOME:-/jffs/addons/tailscale-awg}
RUN_DIR=${TS_ASUS_RUN:-/tmp/tailscale-awg}
M=$HOME_DIR/tailscale-asus
work=/tmp/tailscale-asus-install.$$
enabled_scripts=false
installed=false
show_menu=true

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
confirm() { printf '%s [y/N]: ' "$1"; read -r reply || return 1; case "$reply" in y|Y|yes|YES) return 0;; *) return 1;; esac; }
menu() {
    local choice server fetched
    while :; do
        printf '\n华硕 Tailscale AWG / QUIC\n1) 状态\n2) 登录 / 控制服务器\n3) 配置 AWG / QUIC\n4) 重启服务\n5) 日志\n6) 检查更新\n7) 回滚\n8) 卸载（保留身份）\n0) 退出\n请选择: '
        read -r choice || return 0
        case "$choice" in
            1) "$M" status || true; "$M" cli status || true;;
            2)
                printf '控制服务器 HTTPS 地址（留空使用官方 Tailscale）: '
                read -r server || return 0
                case "$server" in
                    '') "$M" cli up --accept-dns=false --accept-routes=false || true;;
                    https://*) "$M" cli up --login-server="$server" --accept-dns=false --accept-routes=false || true;;
                    *) echo '请输入 https:// 开头的地址';;
                esac;;
            3)
                if "$M" cli awg set --no-restart; then
                    if confirm '重启服务以应用配置？'; then "$M" restart || true; fi
                fi;;
            4) "$M" restart || true;;
            5) if [ -f "$RUN_DIR/daemon.log" ]; then tail -n 60 "$RUN_DIR/daemon.log"; else echo '暂无日志'; fi;;
            6)
                fetched=false
                for mirror in $MIRRORS; do
                    prefix_for "$mirror"
                    if fetch "${prefix}https://github.com/$REPO/releases/latest/download/install-asus.sh" "$work/update.sh" 30 &&
                       [ "$(head -n 1 "$work/update.sh")" = '#!/bin/sh' ] && /bin/sh -n "$work/update.sh"; then
                        fetched=true
                        /bin/sh "$work/update.sh" --no-menu || echo '更新未完成，请查看上方错误'
                        break
                    fi
                done
                [ "$fetched" = true ] || echo '无法下载更新，当前服务未改动';;
            7) if confirm '回滚到上一个已安装版本？'; then "$M" rollback || true; fi;;
            8) if confirm '卸载程序，保留节点身份？'; then "$M" uninstall && return 0; fi;;
            0|q|Q) return 0;;
            *) echo '请选择 0–8';;
        esac
    done
}

for option in "$@"; do
    case "$option" in
        --no-menu) show_menu=false;;
        --help|-h) echo 'ASUS stock/Merlin installer; --no-menu installs without opening the interactive menu'; exit 0;;
        *) die "unknown option: $option";;
    esac
done
[ "$(awk '/^Uid:/ {print $3}' /proc/self/status)" = 0 ] || die 'run this command as root'
[ -d /jffs ] && type nvram >/dev/null 2>&1 || die 'this installer is for ASUS firmware'
case "$(uname -m)" in
    aarch64|arm64) ARCH=arm64; MANIFEST_SHA256=$MANIFEST_ARM64_SHA256;;
    armv7l|armv8l) ARCH=armv7; MANIFEST_SHA256=$MANIFEST_ARMV7_SHA256;;
    *) die 'supported CPUs: ARM64 and ARMv7';;
esac
mkdir "$work" || die 'cannot create temporary directory'
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

asset=tailscale-asus-$RELEASE-$ARCH.gz
slot=$RELEASE-$ARCH
base=https://github.com/$REPO/releases/download/$RELEASE
selected=''
already_current=false
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
    if fetch "$prefix$base/$asset" "$work/payload.gz" 300 &&
       [ "$(sha "$work/payload.gz")" = "$(field "$work/manifest" sha256)" ]; then
        selected=$mirror; break
    fi
    echo 'ASUS Tailscale: payload download or checksum failed; trying another source'
done
[ -n "$selected" ] || die 'no verified download source is available; current installation is unchanged'

if [ "$already_current" = false ] &&
    ! { [ -x /rom/etc/init.d/custom-init.sh ] && [ -e /rom/etc/rc3.d/S45custom-init ]; } &&
    nvram get rc_support | grep -qw am_addons; then
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
    menu </dev/tty >/dev/tty 2>&1
else
    echo "Login: $M cli up --accept-dns=false --accept-routes=false"
fi
