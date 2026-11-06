#!/usr/bin/env bash
set -euo pipefail
repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source="$(realpath "${1:?Usage: apply-overlay.sh OPENWRT_SOURCE}")"
test -d "$source/.git" || git -C "$source" rev-parse --git-dir >/dev/null
git -C "$source" diff --quiet
git -C "$source" diff --cached --quiet
for tree in target files; do
    while IFS= read -r -d '' path; do
        relative="${path#"$repo/overlay/"}"
        if [[ -e "$source/$relative" || -L "$source/$relative" ]]; then
            echo "Refusing to overwrite overlay destination: $relative" >&2
            exit 1
        fi
    done < <(find "$repo/overlay/$tree" -type f -print0)
done
git -C "$source" apply --check "$repo/overlay/0001-nr3053-integration.patch"
git -C "$source" apply "$repo/overlay/0001-nr3053-integration.patch"
for tree in target files; do
    mkdir -p "$source/$tree"
    cp -a "$repo/overlay/$tree/." "$source/$tree/"
done
cp "$repo/nr3053.seed.config" "$source/nr3053.seed.config"
echo "NR3053 overlay applied; Factory/bl2/fip layout unchanged."
