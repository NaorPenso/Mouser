#!/usr/bin/env bash
# Bring upstream changes into the fork without losing the fork's rules.
#
#   1. fast-forward local + origin `master` to upstream/master (mirror only)
#   2. create sync/upstream-YYYYMMDD from `fork` and merge upstream/master
#   3. run scripts/verify.sh (which includes the no-network policy tests)
#
# On conflicts: resolve in favor of CLAUDE.md, run scripts/verify.sh, then
# finish with the merge command printed at the end.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
FORK_BRANCH="${FORK_BRANCH:-fork}"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is not clean; commit or stash first." >&2
  exit 1
fi

git fetch --prune upstream
git fetch --prune origin

echo "== mirror upstream/master -> master"
git checkout -q master
git merge --ff-only upstream/master
git push -q origin master

SYNC="sync/upstream-$(date +%Y%m%d)"
echo "== merge upstream/master into $SYNC (from $FORK_BRANCH)"
git checkout -q "$FORK_BRANCH"
git checkout -q -B "$SYNC"
UPSTREAM_SHA="$(git rev-parse --short upstream/master)"
if ! git merge --no-ff upstream/master \
     -m "chore(sync): merge upstream/master @ $UPSTREAM_SHA"; then
  cat >&2 <<MSG

Merge conflicts. Resolve them keeping the rules in CLAUDE.md (no network
code, no updater, no release workflow), then:
    git commit
    scripts/verify.sh
    git checkout $FORK_BRANCH && git merge --ff-only $SYNC && git push origin $FORK_BRANCH
MSG
  exit 1
fi

scripts/verify.sh

cat <<MSG

Sync branch $SYNC is green. To land it:
    git checkout $FORK_BRANCH && git merge --ff-only $SYNC && git push origin $FORK_BRANCH
Then rebuild and reinstall:
    scripts/install-macos.sh
MSG
