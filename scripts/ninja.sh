#!/usr/bin/env bash
set -euo pipefail
exec "${OPENWRT_SOURCE_DIR:?}/staging_dir/host/bin/ninja" \
    -j"${NR3053_NINJA_JOBS:-2}" "$@"
