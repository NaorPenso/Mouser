#!/usr/bin/env python3
"""Configuration as code for the Mouser fork.

The files in configs/ are the source of truth for a machine's Mouser
setup. They are plain config.json documents plus an optional top-level
"_about" block (ignored by the app, preserved on save) that names the
device and explains what each mapping is for.

    config_as_code.py apply  <name>   install configs/<name>.json as the live
                                      config (validated through the app's own
                                      migration) and restart Mouser if running
    config_as_code.py export <name>   write the live config back to
                                      configs/<name>.json, keeping its _about
    config_as_code.py check  [name]   validate that the file(s) load unchanged
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import config as core_config  # noqa: E402

CONFIGS_DIR = ROOT / "configs"
VOLATILE_SETTINGS = ("update_check_state", "check_for_updates", "language")


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def config_path(name: str) -> Path:
    path = CONFIGS_DIR / f"{name}.json"
    if not path.exists():
        sys.exit(f"no such config: {path}")
    return path


def normalise(cfg: dict) -> dict:
    """Run a document through the app's own load pipeline."""
    cfg = json.loads(json.dumps(cfg))
    cfg = core_config._migrate(cfg)
    cfg = core_config._merge_defaults(cfg, core_config.DEFAULT_CONFIG)
    cfg = core_config._validate_types(cfg, core_config.DEFAULT_CONFIG)
    return cfg


def check(path: Path) -> list[str]:
    """Return problems with a config file (empty list means it is canonical)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    problems = []
    if not isinstance(raw.get("_about"), dict) or not raw["_about"].get("name"):
        problems.append("missing _about.name")
    loaded = normalise(raw)
    if loaded != raw:
        problems.append("file is not canonical: the app would rewrite it on load "
                        "(run config_as_code.py export to refresh it)")
    return problems


def apply(name: str, restart: bool = True) -> None:
    path = config_path(name)
    problems = check(path)
    if problems:
        sys.exit(f"{path.name}: " + "; ".join(problems))
    cfg = normalise(json.loads(path.read_text(encoding="utf-8")))
    core_config.save_config(cfg)
    print(f"applied {_rel(path)} -> {core_config.CONFIG_FILE}")
    if restart and sys.platform == "darwin":
        _restart_mouser()


def export(name: str) -> None:
    path = CONFIGS_DIR / f"{name}.json"
    live = core_config.load_config()
    for key in VOLATILE_SETTINGS:
        live.get("settings", {}).pop(key, None)
    about = {}
    if path.exists():
        about = json.loads(path.read_text(encoding="utf-8")).get("_about", {})
    live.pop("_about", None)
    document = {"_about": about} if about else {}
    document.update(live)
    CONFIGS_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"exported {core_config.CONFIG_FILE} -> {_rel(path)}")


def _restart_mouser() -> None:
    running = subprocess.run(["pgrep", "-x", "Mouser"], capture_output=True).returncode == 0
    if not running:
        return
    subprocess.run(["pkill", "-x", "Mouser"], check=False)
    for _ in range(40):
        if subprocess.run(["pgrep", "-x", "Mouser"], capture_output=True).returncode != 0:
            break
        time.sleep(0.25)
    app = Path("/Applications/Mouser.app")
    if app.exists():
        subprocess.run(["open", str(app)], check=False)
        print("restarted Mouser")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p_apply = sub.add_parser("apply"); p_apply.add_argument("name")
    p_apply.add_argument("--no-restart", action="store_true")
    p_export = sub.add_parser("export"); p_export.add_argument("name")
    p_check = sub.add_parser("check"); p_check.add_argument("name", nargs="?")
    args = parser.parse_args(argv)

    if args.command == "apply":
        apply(args.name, restart=not args.no_restart)
    elif args.command == "export":
        export(args.name)
    else:
        paths = [config_path(args.name)] if args.name else sorted(CONFIGS_DIR.glob("*.json"))
        bad = 0
        for path in paths:
            problems = check(path)
            print(f"{_rel(path)}: {'ok' if not problems else '; '.join(problems)}")
            bad += bool(problems)
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
