#!/usr/bin/env bash
# Build Mouser from this checkout and install it to /Applications.
# Runs the full verification gate first; a red gate never gets installed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
DEST="${MOUSER_INSTALL_DIR:-/Applications}/Mouser.app"

if [[ "${SKIP_VERIFY:-0}" != "1" ]]; then
  scripts/verify.sh
fi

./build_macos_app.sh

if pgrep -xq Mouser; then
  echo "== quitting running Mouser"
  osascript -e 'tell application "Mouser" to quit' >/dev/null 2>&1 || pkill -x Mouser || true
  for _ in $(seq 1 20); do pgrep -xq Mouser || break; sleep 0.25; done
fi

echo "== installing to $DEST"
rm -rf "$DEST"
cp -R dist/Mouser.app "$DEST"
codesign --verify --deep --strict "$DEST"
open "$DEST"
echo "installed and launched: $DEST"
