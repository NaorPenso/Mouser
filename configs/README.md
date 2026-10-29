# Configurations as code

Each file here is a complete Mouser `config.json` plus a top-level `_about`
block that names the device and explains every mapping. The app ignores
`_about` and preserves it, so a file round-trips through the UI unchanged.

| File | Device | Highlights |
|---|---|---|
| `mx4-ratmode.json` | Logitech MX Master 4 | Sense Panel held = Wispr Flow push-to-talk (`hold:alt+grave`); Back = Paste, Forward = Copy; thumb wheel = previous / next tab. |

Commands (run from the repo root):

```bash
scripts/config-apply.sh mx4-ratmode    # install it as the live config, restart Mouser
scripts/config-export.sh mx4-ratmode   # pull UI changes back into the file
.venv/bin/python scripts/config_as_code.py check   # validate every file
```

`tests/test_config_as_code.py` validates every file through the app's own
migration pipeline, so a config that the app would rewrite on load fails CI.
After changing settings in the UI, export and commit; the file in git is the
source of truth.
