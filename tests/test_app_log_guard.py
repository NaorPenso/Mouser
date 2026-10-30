"""Tests must never write into the user's real Mouser log.

main_qml redirects stdout into the app log on import. Every test module (and
helper) that imports it must import tests/_app_log_guard.py first.
"""

import logging
import re
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent


class AppLogGuardTests(unittest.TestCase):
    def test_every_main_qml_importer_loads_the_guard_first(self):
        for path in sorted(TESTS.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            match = re.search(r"^\s*import main_qml\b", text, re.MULTILINE)
            if match is None:
                continue
            guard = text.find("import _app_log_guard")
            with self.subTest(file=path.name):
                self.assertNotEqual(guard, -1, "imports main_qml without the guard")
                self.assertLess(guard, match.start(), "guard must come first")

    def test_setup_logging_is_a_no_op_under_the_guard(self):
        import _app_log_guard  # noqa: F401
        from core.log_setup import setup_logging
        self.assertEqual(setup_logging(), "")
        self.assertFalse(any(
            isinstance(h, logging.FileHandler)
            for h in logging.getLogger().handlers
        ))


if __name__ == "__main__":
    unittest.main()
