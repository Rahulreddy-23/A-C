#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="${UV_CACHE_DIR:-out/uv-cache}"
if command -v uv >/dev/null 2>&1; then
  dhf_uv=$(command -v uv)
else
  dhf_uv="out/bin/uv"
fi
# No dependency downloads. Offline by default; --live selects the configured model provider.
exec "$dhf_uv" run --offline --no-sync python tools/demo.py "$@"
