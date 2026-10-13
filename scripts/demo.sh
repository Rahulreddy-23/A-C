#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if command -v uv >/dev/null 2>&1; then
  dhf_uv=$(command -v uv)
else
  dhf_uv="out/bin/uv"
fi
# No dependency downloads or paid providers during the demo.
exec "$dhf_uv" run --offline --no-sync python tools/demo.py "$@"
