"""Fork policy guard: the software ships in English only.

The upstream project carries Simplified and Traditional Chinese string
tables, a Chinese README and a language switcher. This fork removed them;
these tests keep an upstream merge from quietly bringing them back.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Han, CJK punctuation and full-width forms. Katakana/Hiragana/Hangul are
# included so "English only" means exactly that. Built from code points so
# this file itself stays pure ASCII.
_CJK_RANGES = (
    (0x3000, 0x303F), (0x3040, 0x30FF), (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF), (0xAC00, 0xD7AF), (0xFF00, 0xFFEF),
)
CJK = re.compile(
    "[" + "".join("\\u%04x-\\u%04x" % r for r in _CJK_RANGES) + "]"
)
# Escaped forms as they appear in Python source (backslash-u followed by a
# code point inside the ranges above).
CJK_ESCAPED = re.compile(
    r"\\u(3[0-9a-f]{3}|4[e-f][0-9a-f]{2}|[5-9][0-9a-f]{3}|a[c-f][0-9a-f]{2}"
    r"|[b-c][0-9a-f]{3}|d[0-7][0-9a-f]{2}|ff[0-9a-f]{2})",
    re.IGNORECASE,
)

TEXT_SUFFIXES = {".py", ".qml", ".js", ".md", ".yml", ".yaml", ".sh", ".spec",
                 ".txt", ".json", ".plist", ".rules", ".in", ".bat", ".entitlements"}


SKIP_DIRS = {".git", ".venv", ".remember", "build", "dist", "__pycache__"}
SELF = Path(__file__).resolve()  # holds the escaped ranges it scans for


def _text_files():
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix in TEXT_SUFFIXES and path.resolve() != SELF:
            yield path


class EnglishOnlyTests(unittest.TestCase):
    def test_only_english_string_table_exists(self):
        from ui.locale_manager import (
            _ACTION_TR, _BUTTON_TR, _CATEGORY_TR, _TRANSLATIONS, AVAILABLE_LANGUAGES,
        )
        self.assertEqual(set(_TRANSLATIONS), {"en"})
        self.assertEqual([lang["code"] for lang in AVAILABLE_LANGUAGES], ["en"])
        for table in (_ACTION_TR, _BUTTON_TR, _CATEGORY_TR):
            self.assertEqual(dict(table), {})

    def test_no_cjk_text_in_any_source_or_doc(self):
        for path in _text_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            with self.subTest(file=str(path.relative_to(ROOT))):
                hit = CJK.search(text) or CJK_ESCAPED.search(text)
                if hit is not None:
                    self.fail(f"{path.relative_to(ROOT)} contains CJK text: {hit.group(0)!r}")

    def test_chinese_readme_and_language_switch_are_gone(self):
        self.assertFalse((ROOT / "README_CN.md").exists())
        scroll_page = (ROOT / "ui" / "qml" / "ScrollPage.qml").read_text(encoding="utf-8")
        self.assertNotIn("lm.setLanguage", scroll_page)
        self.assertNotIn("availableLanguages", scroll_page)
        from core.config import DEFAULT_CONFIG
        self.assertNotIn("language", DEFAULT_CONFIG["settings"])


if __name__ == "__main__":
    unittest.main()
