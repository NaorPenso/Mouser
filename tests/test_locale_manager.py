import unittest

from ui.locale_manager import _TRANSLATIONS


class LocaleManagerTranslationTests(unittest.TestCase):
    def test_key_capture_error_messages_exist_in_all_locales(self):
        required = {
            "key_capture.error.unsupported_key",
            "key_capture.error.unknown_key",
            "key_capture.error.duplicate_key",
            "key_capture.error.multiple_main_keys",
            "key_capture.error.missing_main_key",
            "key_capture.error.empty_segment",
            "key_capture.error.unsupported",
        }

        for locale, strings in _TRANSLATIONS.items():
            with self.subTest(locale=locale):
                self.assertTrue(required.issubset(strings))
                for key in required:
                    self.assertTrue(strings[key].strip())

    def test_key_capture_recorder_strings_exist_in_all_locales(self):
        required = {
            "key_capture.placeholder_recording",
            "key_capture.record_hint",
            "key_capture.type_hint",
            "key_capture.mode_type",
            "key_capture.mode_record",
        }

        for locale, strings in _TRANSLATIONS.items():
            with self.subTest(locale=locale):
                self.assertTrue(required.issubset(strings))
                for key in required:
                    self.assertTrue(strings[key].strip())

    def test_key_capture_help_text_covers_the_supported_function_keys(self):
        for locale, strings in _TRANSLATIONS.items():
            with self.subTest(locale=locale):
                self.assertIn("f24", strings["key_capture.valid_keys"])


class AccessibilityLocaleTests(unittest.TestCase):
    """The QML accessibility labels added in this batch reference these
    keys. Missing them in a non-English locale silently regresses to a
    KeyError-as-empty-string in the QML lookup ``s[...]``, which leaves
    screen readers reading nothing for an interactive control.
    """

    REQUIRED_KEYS = frozenset({
        "dialog.close",
        "scroll.ignore_trackpad",
        "scroll.ignore_trackpad_desc",
        "scroll.smart_shift",
    })
    ENGLISH_VALUES = frozenset({
        "Close",
        "Ignore trackpad",
        "Only respond to mouse events, not trackpad or Magic Mouse",
    })

    def test_required_accessibility_keys_present_in_all_locales(self):
        for locale, strings in _TRANSLATIONS.items():
            with self.subTest(locale=locale):
                missing = self.REQUIRED_KEYS - strings.keys()
                self.assertFalse(missing, f"{locale} missing keys: {missing}")
                for key in self.REQUIRED_KEYS:
                    self.assertTrue(
                        strings[key].strip(),
                        f"{locale}.{key} is blank",
                    )

    def test_chinese_locales_do_not_passthrough_english(self):
        """Trackpad strings used to ship English text in the zh_CN and
        zh_TW maps. Pin that they are now actually localized."""
        for locale in ("zh_CN", "zh_TW"):
            with self.subTest(locale=locale):
                for key in (
                    "scroll.ignore_trackpad",
                    "scroll.ignore_trackpad_desc",
                ):
                    self.assertNotIn(
                        _TRANSLATIONS[locale][key],
                        self.ENGLISH_VALUES,
                        f"{locale}.{key} still ships English",
                    )
                self.assertNotEqual(
                    _TRANSLATIONS[locale]["scroll.smart_shift"],
                    "SmartShift",
                    f"{locale}.scroll.smart_shift still ships English",
                )


if __name__ == "__main__":
    unittest.main()


class HoldShortcutStringsTests(unittest.TestCase):
    def test_hold_toggle_strings_exist_in_all_locales(self):
        required = {"key_capture.hold_label", "key_capture.hold_hint"}
        for locale, strings in _TRANSLATIONS.items():
            with self.subTest(locale=locale):
                self.assertTrue(required.issubset(strings))
