#!/usr/bin/env bash
# Install configs/<name>.json as the live Mouser config and restart the app.
#   scripts/config-apply.sh mx4-ratmode
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "${MOUSER_PYTHON:-$ROOT/.venv/bin/python}" "$ROOT/scripts/config_as_code.py" apply "$@"
