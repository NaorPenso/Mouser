"""Integration test for the action, double-press and Actions Ring accordions.

Runs tests/_double_press_ui_probe.py in a subprocess: it loads the real
Settings page and Mouse page offscreen with a real Backend, clicks the
double-press controls like a user, and reports the configs the Backend
saved. A subprocess is needed because QML requires a QApplication and other
tests in this process create a QCoreApplication first.
"""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tests" / "_double_press_ui_probe.py"


def _run_probe():
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run(
        [sys.executable, str(PROBE)], cwd=ROOT, env=env,
        capture_output=True, text=True, timeout=180, check=False,
    )
    for line in result.stdout.splitlines():
        if line.startswith("PROBE_REPORT "):
            return json.loads(line[len("PROBE_REPORT "):])
    raise AssertionError(
        f"probe produced no report (exit {result.returncode}):\n"
        f"{result.stdout[-2000:]}\n{result.stderr[-4000:]}"
    )


class DoublePressUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = _run_probe()

    def test_settings_card_shows_and_switches_mode(self):
        r = self.report
        self.assertTrue(r["card_visible"])
        self.assertEqual(r["mode_after_click"], "wait")
        self.assertIn("fires at once", r["desc_instant"])
        self.assertIn("waits until the window passes", r["desc_wait"])

    def test_window_slider_saves_a_rounded_value_and_labels_it(self):
        r = self.report
        window = r["window_after_click"]
        self.assertGreater(window, 800)
        self.assertLessEqual(window, 1000)
        self.assertEqual(r["window_label"], f"{window} ms")

    def test_button_panel_is_an_accordion_that_edits_the_double_action(self):
        r = self.report
        self.assertTrue(r["section_visible_forward"])
        self.assertTrue(r["current_forward"].startswith("Paste"))
        # Collapsed until the header is clicked, then the category holding
        # the current action is already open.
        self.assertFalse(r["body_visible_collapsed"])
        self.assertTrue(r["body_visible_expanded"])
        self.assertTrue(r["current_category_open"])
        self.assertEqual(r["double_after_pick"], "copy")
        self.assertTrue(r["current_after_pick"].startswith("Copy"))
        # Picking the double action leaves the button's own action alone.
        self.assertEqual(r["single_after_pick"], "mouse_forward_click")
        self.assertFalse(r["body_visible_recollapsed"])

    def test_main_action_is_the_same_accordion(self):
        r = self.report
        self.assertTrue(r["action_current_forward"].startswith("Forward"))
        self.assertFalse(r["action_body_visible_collapsed"])
        self.assertTrue(r["action_body_visible_expanded"])
        self.assertTrue(r["action_current_category_open"])
        self.assertEqual(r["action_after_pick"], "cut")
        self.assertTrue(r["action_current_after_pick"].startswith("Cut"))
        # Picking the button's action leaves its double action alone.
        self.assertEqual(r["double_after_action_pick"], "copy")
        self.assertTrue(r["action_body_collapsed_on_new_button"])

    def test_ring_slots_are_accordions_with_one_open_at_a_time(self):
        r = self.report
        self.assertTrue(r["ring_slot1_collapsed"])
        self.assertTrue(r["ring_slot1_expanded"])
        self.assertEqual(r["ring_slots_after_pick"][1], "copy")
        self.assertTrue(r["ring_slot1_current"].startswith("Copy"))
        self.assertTrue(r["ring_slot2_expanded"])
        self.assertTrue(r["ring_slot1_closed_by_slot2"])

    def test_section_is_hidden_for_buttons_without_a_release(self):
        self.assertFalse(self.report["section_visible_hscroll"])

    def test_every_change_is_saved_and_reloads_the_engine(self):
        r = self.report
        self.assertEqual(r["qml_errors"], [])
        last = r["saved"][-1]
        self.assertEqual(last["double_press_mode"], "wait")
        self.assertEqual(last["xbutton2_double"], "copy")
        self.assertEqual(last["xbutton2"], "cut")
        self.assertEqual(last["double_press_window_ms"], r["window_after_click"])
        self.assertGreaterEqual(r["engine_reloads"], 3)


if __name__ == "__main__":
    unittest.main()
