#!/usr/bin/env bash
# Full verification gate for the fork: hashed install, compile, tests,
# QML lint, dependency audit. Must pass before anything merges into `fork`
# and before every local install.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${MOUSER_PYTHON:-$ROOT/.venv/bin/python}"

if [[ ! -x "$PY" ]]; then
  echo "No interpreter at $PY. Create it with: uv venv --python 3.13 .venv" >&2
  exit 1
fi

echo "== install pinned dependencies (hash-verified)"
if command -v uv >/dev/null 2>&1; then
  uv pip install --quiet --python "$PY" --require-hashes -r requirements.lock
else
  "$PY" -m pip install --quiet --require-hashes -r requirements.lock
fi

echo "== compile"
"$PY" -m py_compile main_qml.py build_support.py core/*.py ui/*.py

echo "== tests"
QT_QPA_PLATFORM=offscreen "$PY" -m unittest discover -s tests -p "test_*.py"

echo "== qml lint"
"$PY" - <<'PY'
import subprocess
from pathlib import Path
import PySide6
qmllint = Path(PySide6.__file__).resolve().parent / "qmllint"
files = sorted(str(p) for p in Path("ui/qml").glob("*.qml"))
subprocess.run([str(qmllint), *files], check=True)
print("qmllint: ok")
PY

echo "== dependency audit"
uvx pip-audit --require-hashes -r requirements.lock --no-deps

echo "verify: all gates passed"
