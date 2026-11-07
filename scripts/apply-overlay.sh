#!/usr/bin/env bash
set -euo pipefail
repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source="$(realpath "${1:?Usage: apply-overlay.sh OPENWRT_SOURCE}")"
test -d "$source/.git" || git -C "$source" rev-parse --git-dir >/dev/null
git -C "$source" diff --quiet
git -C "$source" diff --cached --quiet
runtime_scripts=(
    files/etc/init.d/nr3053-tune
    files/etc/uci-defaults/zz-nr3053-localization
    files/etc/uci-defaults/zz-nr3053-tune
    files/etc/uci-defaults/zzzz-nr3053-theme
    files/usr/sbin/nr3053-cpu-clock
    package/luci-theme-glass/root/etc/uci-defaults/30_luci-theme-glass
)
for tree in target files package; do
    if [[ ! -d "$repo/overlay/$tree" || -L "$repo/overlay/$tree" ]]; then
        echo "Missing or invalid overlay tree: $tree" >&2
        exit 1
    fi
    if [[ -L "$source/$tree" || ( -e "$source/$tree" && ! -d "$source/$tree" ) ]]; then
        echo "Refusing invalid overlay destination: $tree" >&2
        exit 1
    fi
    find "$repo/overlay/$tree" -mindepth 1 -print0 |
    while IFS= read -r -d '' path; do
        relative="${path#"$repo/overlay/"}"
        if [[ -d "$path" && ! -L "$path" ]]; then
            if [[ ! -L "$source/$relative" && ( ! -e "$source/$relative" || -d "$source/$relative" ) ]]; then
                continue
            fi
        elif [[ ! -e "$source/$relative" && ! -L "$source/$relative" ]]; then
            continue
        fi
        echo "Refusing to overwrite overlay destination: $relative" >&2
        exit 1
    done
done
for relative in "${runtime_scripts[@]}"; do
    path="$repo/overlay/$relative"
    if [[ ! -f "$path" || -L "$path" || ! -s "$path" ]]; then
        echo "Missing or invalid required runtime script: $relative" >&2
        exit 1
    fi
    parent="$(dirname -- "$path")"
    while [[ "$parent" != "$repo/overlay" ]]; do
        if [[ -L "$parent" ]]; then
            echo "Refusing symlink parent for runtime script: $relative" >&2
            exit 1
        fi
        parent="$(dirname -- "$parent")"
    done
done
if [[ -e "$source/nr3053.seed.config" || -L "$source/nr3053.seed.config" ]]; then
    echo "Refusing to overwrite overlay destination: nr3053.seed.config" >&2
    exit 1
fi
git -C "$source" apply --check "$repo/overlay/0001-nr3053-integration.patch"
git -C "$source" apply "$repo/overlay/0001-nr3053-integration.patch"
for tree in target files package; do
    mkdir -p "$source/$tree"
    cp -a "$repo/overlay/$tree/." "$source/$tree/"
done
for relative in "${runtime_scripts[@]}"; do
    chmod 0755 -- "$source/$relative"
done
cp "$repo/nr3053.seed.config" "$source/nr3053.seed.config"
echo "NR3053 overlay applied; Factory/bl2/fip layout unchanged."
