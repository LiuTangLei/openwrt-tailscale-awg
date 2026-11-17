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
test "$source_version" = "v${version}"
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
inspect_binary="$binary"
"$go_tool" version -m "$binary" > "$scratch/info" 2>&1 || true
if ! grep -qF 'github.com/LiuTangLei/quic-go' "$scratch/info"; then
    "$upx_tool" -t "$binary" >/dev/null
    "$upx_tool" -d -o "$scratch/unpacked" "$binary" >/dev/null
    inspect_binary="$scratch/unpacked"
    "$go_tool" version -m "$scratch/unpacked" > "$scratch/info"
fi
# -trimpath omits linker flags from Go metadata. Check the linked commit value
# in the executable itself; keep dependency versions in their Go metadata.
grep -aqF "$core" "$inspect_binary" || { echo "Embedded core commit mismatch" >&2; exit 1; }
for marker in 'go1.27.4' \
    'github.com/LiuTangLei/wireguard-go' 'v0.0.35' \
    'github.com/LiuTangLei/quic-go' 'v0.65.0-quic.4' \
    'github.com/LiuTangLei/utls' '7effde6a93dc'; do
    grep -qF "$marker" "$scratch/info" || { echo "Core identity mismatch: $marker" >&2; exit 1; }
done
{ printf 'Verified source: %s (%s)\n' "$source_version" "$core"; cat "$scratch/info"; } > "$report"
echo "Verified pinned source and transport modules: $binary"
