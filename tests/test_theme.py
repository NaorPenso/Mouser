"""Fork design guard: the UI uses the Apple HIG palette and the system font.

ui/qml/Theme.js is the single source of color for QML; the Actions Ring
overlay mirrors its accent in QColor form. These tests pin the accent and
semantic colors to Apple's system colors and keep the old teal brand palette
from creeping back in through an upstream merge.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEME_JS = (ROOT / "ui" / "qml" / "Theme.js").read_text(encoding="utf-8")

APPLE_BLUE_LIGHT = "#007aff"
APPLE_BLUE_DARK = "#0a84ff"
UPSTREAM_TEAL = {"#00d4aa", "#00ffc8", "#0ea5a4", "#14b8a6", "#0d2e26", "#d9f4ee"}

UI_SOURCES = (
    sorted((ROOT / "ui" / "qml").glob("*.qml"))
    + [ROOT / "ui" / "qml" / "Theme.js", ROOT / "ui" / "actions_ring_overlay.py",
       ROOT / "main_qml.py"]
)


def _palette(is_dark):
    """Extract the token→color map for one appearance from Theme.js."""
    dark_block, light_block = THEME_JS.split("return {", 2)[1:]
    block = dark_block if is_dark else light_block
    return dict(re.findall(r'(\w+):\s*"(#[0-9a-fA-F]{6})"', block))


class ApplePaletteTests(unittest.TestCase):
    def test_accent_is_apple_system_blue(self):
        self.assertEqual(_palette(is_dark=False)["accent"], APPLE_BLUE_LIGHT)
        self.assertEqual(_palette(is_dark=True)["accent"], APPLE_BLUE_DARK)

    def test_semantic_colors_are_apple_system_colors(self):
        light, dark = _palette(is_dark=False), _palette(is_dark=True)
        self.assertEqual(light["danger"], "#ff3b30")
        self.assertEqual(dark["danger"], "#ff453a")
        self.assertEqual(light["success"], "#34c759")
        self.assertEqual(dark["success"], "#30d158")
        self.assertEqual(light["warning"], "#ff9500")
        self.assertEqual(dark["warning"], "#ff9f0a")

    def test_backgrounds_follow_hig_neutrals(self):
        self.assertEqual(_palette(is_dark=False)["bg"], "#f5f5f7")
        self.assertEqual(_palette(is_dark=True)["bg"], "#1c1c1e")
        self.assertEqual(_palette(is_dark=False)["textPrimary"], "#1d1d1f")

    def test_material_accent_env_matches_theme(self):
        main = (ROOT / "main_qml.py").read_text(encoding="utf-8")
        self.assertIn(f'QT_QUICK_CONTROLS_MATERIAL_ACCENT"] = "{APPLE_BLUE_LIGHT}"', main)

    def test_ring_overlay_highlight_uses_the_accent(self):
        overlay = (ROOT / "ui" / "actions_ring_overlay.py").read_text(encoding="utf-8")
        self.assertIn("_COLOR_SECTOR_HL_CENTER = QColor(10, 132, 255,", overlay)
        self.assertNotIn("QColor(0, 212, 170", overlay)

    def test_upstream_teal_palette_is_gone(self):
        for path in UI_SOURCES:
            text = path.read_text(encoding="utf-8").lower()
            for color in UPSTREAM_TEAL:
                with self.subTest(file=path.name, color=color):
                    self.assertNotIn(color, text)


class SystemFontTests(unittest.TestCase):
    def test_macos_falls_back_to_the_system_ui_font(self):
        main = (ROOT / "main_qml.py").read_text(encoding="utf-8")
        self.assertIn('self._font_family = ".AppleSystemUIFont"', main)

    def test_qml_text_uses_the_shared_font_family(self):
        # Every explicit font family in QML routes through uiState so the
        # system font applies everywhere; the only exception is the
        # monospace face used for the debug log and key codes.
        allowed = ("uiState.fontFamily", "root.monoFontFamily", '"Menlo"')
        for path in sorted((ROOT / "ui" / "qml").glob("*.qml")):
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r"family:\s*([^\n;}]+)", text):
                family = match.group(1).strip()
                with self.subTest(file=path.name, family=family):
                    self.assertTrue(any(a in family for a in allowed), family)


if __name__ == "__main__":
    unittest.main()
