"""Configuration-as-code guards for the files in configs/.

Every file must load through the app's own migration pipeline unchanged,
carry an _about block that documents it, and the MX4 RatMode file must keep
the mappings this fork was built around.
"""

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import config as core_config

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = sorted((ROOT / "configs").glob("*.json"))
MX4 = ROOT / "configs" / "mx4-ratmode.json"


def _load_tool():
    spec = importlib.util.spec_from_file_location(
        "config_as_code", ROOT / "scripts" / "config_as_code.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ConfigFilesTests(unittest.TestCase):
    def test_at_least_the_mx4_config_is_committed(self):
        self.assertIn(MX4, CONFIGS)

    def test_every_config_is_canonical_and_documented(self):
        tool = _load_tool()
        for path in CONFIGS:
            with self.subTest(file=path.name):
                self.assertEqual(tool.check(path), [])

    def test_mx4_ratmode_is_called_out_and_wired_to_wispr_flow(self):
        doc = json.loads(MX4.read_text(encoding="utf-8"))
        about = doc["_about"]
        self.assertIn("MX Master 4", about["name"])
        self.assertIn("RatMode", about["name"])
        self.assertEqual(about["author"], "Naor Penso")
        self.assertIn("Wispr Flow", about["notes"]["actions_ring_double"])
        self.assertIn("push-to-talk", about["notes"]["actions_ring_double"])
        mappings = doc["profiles"]["default"]["mappings"]
        self.assertEqual(mappings["actions_ring"], "activate_actions_ring")
        self.assertEqual(mappings["actions_ring_double"], "hold:fn")
        self.assertIn(doc["settings"]["double_press_mode"], ("instant", "wait"))
        self.assertIsInstance(doc["settings"]["double_press_window_ms"], int)
        self.assertEqual(mappings["xbutton1"], "paste")
        self.assertEqual(mappings["xbutton2"], "copy")
        self.assertIn("MX4", doc["profiles"]["default"]["label"])

    def test_no_volatile_or_removed_settings_are_committed(self):
        for path in CONFIGS:
            settings = json.loads(path.read_text(encoding="utf-8"))["settings"]
            with self.subTest(file=path.name):
                for key in ("update_check_state", "check_for_updates", "language"):
                    self.assertNotIn(key, settings)


class ApplyExportRoundTripTests(unittest.TestCase):
    def test_apply_then_export_round_trips_through_the_live_config(self):
        tool = _load_tool()
        with tempfile.TemporaryDirectory() as tmp:
            live = os.path.join(tmp, "config.json")
            with (
                patch.object(core_config, "CONFIG_DIR", tmp),
                patch.object(core_config, "CONFIG_FILE", live),
                patch.object(tool, "CONFIGS_DIR", Path(tmp) / "configs"),
            ):
                (Path(tmp) / "configs").mkdir()
                (Path(tmp) / "configs" / "mx4-ratmode.json").write_text(
                    MX4.read_text(encoding="utf-8"), encoding="utf-8"
                )
                tool.apply("mx4-ratmode", restart=False)
                self.assertTrue(os.path.exists(live))
                installed = core_config.load_config()
                self.assertEqual(
                    installed["profiles"]["default"]["mappings"]["actions_ring_double"],
                    "hold:fn",
                )
                # The _about block survives the app's own load path.
                self.assertIn("_about", installed)

                tool.export("mx4-ratmode")
                exported = json.loads(
                    (Path(tmp) / "configs" / "mx4-ratmode.json").read_text(encoding="utf-8")
                )
        original = json.loads(MX4.read_text(encoding="utf-8"))
        self.assertEqual(exported, original)


if __name__ == "__main__":
    unittest.main()
