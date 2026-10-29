# Mouser (personal fork) — agent rules

This repository is a personal fork of `TomBadash/Mouser`, a local Logitech
mouse remapper. The fork exists to run a hardened, source-built copy on the
owner's own machines. The rules below are binding for any agent or
contributor working here. They are enforced where possible by
`tests/test_no_network.py`; never weaken, skip, or delete those tests.

## Remotes and branches

- `upstream` = `https://github.com/TomBadash/Mouser.git` (read-only reference).
- `origin` = `https://github.com/NaorPenso/Mouser.git` (this fork).
- `master` mirrors `upstream/master` exactly. Never commit to it; it is only
  fast-forwarded by `scripts/sync-upstream.sh`.
- `fork` is the default branch and carries every customization. Feature work
  happens on `feat/*` or `fix/*` branches off `fork` and merges back into
  `fork`. Upstream merges land through `sync/upstream-YYYYMMDD` branches.

## Hard rules

1. **No network, ever.** The application makes no inbound or outbound
   connections: no update checks, no telemetry, no release lookups, no
   opening of URLs in a browser, no HTTP clients, no sockets. The only
   exception is the single-instance guard in `main_qml.py`, which uses a
   `QLocalServer` local socket for same-user IPC. Any upstream change that
   adds network code is stripped during sync, not merged.
2. **No auto-update, no release pipeline.** `core/updater.py`,
   `core/update_installer.py`, the manifest tools and
   `.github/workflows/release.yml` were removed and must not return. The
   fork publishes no binaries.
3. **Always build from source.** The app on this machine is produced by
   `scripts/install-macos.sh` (which runs `build_macos_app.sh`). Never
   download or install a prebuilt Mouser binary, and never suggest doing so.
4. **Pinned, audited dependencies.** `requirements.txt` holds tested floors;
   `requirements.lock` is the hash-pinned, cross-platform set that every
   install uses (`--require-hashes`). Update dependencies only through
   `scripts/audit-deps.sh`, which re-resolves, runs `pip-audit`, and shows
   the diff. Bump promptly when an advisory affects a pinned package. Never
   add a dependency that performs network I/O.
5. **Least privilege.** Do not request new OS permissions, do not add
   `shell=True` subprocess calls, do not add keyboard hooks outside the
   existing shortcut recorder, and do not log typed text or key names.
6. **Upstream sync lifecycle.** Pull upstream with `scripts/sync-upstream.sh`
   on a cadence you choose (monthly is reasonable). Resolve conflicts in
   favor of these rules, then `scripts/verify.sh` must pass before the sync
   branch merges into `fork`. After merging, rebuild and reinstall with
   `scripts/install-macos.sh`. Record notable upstream changes in the merge
   commit body.

## Working conventions

- Every feature or fix ships with an integration-level test in `tests/`.
  The suite runs with `QT_QPA_PLATFORM=offscreen .venv/bin/python -m
  unittest discover -s tests`.
- Upstream CI runs on Linux only, so macOS-specific tests are only ever
  executed here. Run the full suite on the Mac after every upstream sync;
  a test that fails only on macOS is still a failure.
- Modify files in place. No `*V2`, `*Enhanced`, or parallel implementations.
- Commit after every change cycle, on a branch, with a conventional-commit
  subject (`feat(scope): ...`, `fix(scope): ...`, `chore(sync): ...`).
- Keep `DEVELOPMENT.md` accurate when build or lifecycle steps change.
