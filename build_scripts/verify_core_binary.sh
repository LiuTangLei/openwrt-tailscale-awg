#!/bin/bash
# Verify the built core without executing a foreign-architecture binary.
set -euo pipefail
binary="$1"
makefile="$2"
report="$3"
go_tool="$4"
upx_tool="$5"
core=$(sed -n 's/^PKG_COMMIT:=//p' "$makefile")
version=$(sed -n 's/^PKG_VERSION:=//p' "$makefile")
source_version=$(sed -n 's/^PKG_SOURCE_VERSION:=//p' "$makefile")
test -n "$core" && test -n "$version"
test "$source_version" = "v${version}-r1"
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
"$go_tool" version -m "$binary" > "$scratch/info" 2>&1 || true
if ! grep -qF 'github.com/LiuTangLei/quic-go' "$scratch/info"; then
    "$upx_tool" -t "$binary" >/dev/null
    "$upx_tool" -d -o "$scratch/unpacked" "$binary" >/dev/null
    "$go_tool" version -m "$scratch/unpacked" > "$scratch/info"
fi
for marker in "$core" 'go1.27.3' \
    'github.com/LiuTangLei/wireguard-go' 'v0.0.35' \
    'github.com/LiuTangLei/quic-go' 'v0.65.0-quic.4' \
    'github.com/LiuTangLei/utls' '7effde6a93dc'; do
    grep -qF "$marker" "$scratch/info" || { echo "Core identity mismatch: $marker" >&2; exit 1; }
done
{ printf 'Verified source: %s (%s)\n' "$source_version" "$core"; cat "$scratch/info"; } > "$report"
echo "Verified pinned source and transport modules: $binary"
