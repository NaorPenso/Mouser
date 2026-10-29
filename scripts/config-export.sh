#!/usr/bin/env bash
# Write the live Mouser config back into configs/<name>.json (keeps its _about).
#   scripts/config-export.sh mx4-ratmode && git diff configs/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "${MOUSER_PYTHON:-$ROOT/.venv/bin/python}" "$ROOT/scripts/config_as_code.py" export "$@"
