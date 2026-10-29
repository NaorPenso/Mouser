#!/usr/bin/env bash
# Re-resolve the dependency lock to the newest versions that satisfy
# requirements.txt, audit it for known vulnerabilities, and show the diff.
# Commit the updated requirements.lock when the audit is clean. Raise a
# floor in requirements.txt when an advisory needs a newer major version.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

uv pip compile --universal --generate-hashes --upgrade -q \
  requirements.txt -o requirements.lock
sed -i '' -e '1s|.*|# Hash-pinned dependency set for every platform. Do not edit by hand.|' \
  -e '2s|.*|# Regenerate with: scripts/audit-deps.sh|' requirements.lock

echo "== changes"
git --no-pager diff --stat -- requirements.lock
git --no-pager diff -- requirements.lock | grep -E '^[-+][a-z0-9_.-]+==' || echo "(no version changes)"

echo "== audit"
uvx pip-audit --require-hashes -r requirements.lock --no-deps
