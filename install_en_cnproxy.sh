#!/bin/sh
# English installer using the current signed feed through a GitHub mirror.
set -eu

RAW_ROOT="https://raw.githubusercontent.com/LiuTangLei/openwrt-tailscale-awg"
MIRRORS="https://ghfast.top https://gh-proxy.org direct"
CUSTOM_PROXY=false
TMP_INSTALL=false
for arg in "$@"; do
    case "$arg" in
        --help)
            echo "Tailscale-AWG OpenWrt installer (English, GitHub mirrors)"
            echo "Usage: $0 [--tempinstall] [--custom-proxy]"
            exit 0
            ;;
        --custom-proxy) CUSTOM_PROXY=true ;;
        --tempinstall) TMP_INSTALL=true ;;
        *) echo "Unknown argument: $arg" >&2; exit 1 ;;
    esac
done
if [ "$CUSTOM_PROXY" = true ]; then
    printf 'GitHub mirror URL (https://example.com): '
    read -r mirror
    case "$mirror" in https://*) ;; *) echo "Expected an https:// mirror URL" >&2; exit 1 ;; esac
    MIRRORS="${mirror%/}"
fi

work_dir=$(mktemp -d /tmp/tailscale-installer.XXXXXX)
trap 'rm -rf "$work_dir"' EXIT HUP INT TERM
for mirror in $MIRRORS; do
    case "$mirror" in direct) prefix="" ;; *) prefix="$mirror/" ;; esac
    url="${prefix}${RAW_ROOT}/main/install_en.sh"
    if wget -qO "$work_dir/install.sh" -T 15 "$url" &&
       [ "$(head -n 1 "$work_dir/install.sh")" = '#!/bin/sh' ]; then
        export TAILSCALE_FEED_URL="${prefix}${RAW_ROOT}/refs/heads/feed"
        if [ "$TMP_INSTALL" = true ]; then
            sh "$work_dir/install.sh" --tempinstall
        else
            sh "$work_dir/install.sh"
        fi
        exit $?
    fi
done
echo "Unable to download the English installer from the configured mirrors" >&2
exit 1
