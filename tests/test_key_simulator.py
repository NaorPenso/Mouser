import importlib
import os
import sys
import types
import unittest
from unittest.mock import call, patch

from core import key_simulator


class KeySimulatorActionTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform in ("darwin", "win32"), "desktop switching actions are platform-specific")
    def test_desktop_switch_actions_exist(self):
        self.assertIn("space_left", key_simulator.ACTIONS)
        self.assertIn("space_right", key_simulator.ACTIONS)
        self.assertEqual(key_simulator.ACTIONS["space_left"]["label"], "Previous Desktop")
        self.assertEqual(key_simulator.ACTIONS["space_right"]["label"], "Next Desktop")

    @unittest.skipUnless(sys.platform in ("darwin", "win32"), "tab switching actions are platform-specific")
    def test_tab_switch_actions_exist(self):
        self.assertIn("next_tab", key_simulator.ACTIONS)
        self.assertIn("prev_tab", key_simulator.ACTIONS)
        self.assertEqual(key_simulator.ACTIONS["next_tab"]["category"], "Browser")
        self.assertEqual(key_simulator.ACTIONS["prev_tab"]["category"], "Browser")
        self.assertTrue(len(key_simulator.ACTIONS["next_tab"]["keys"]) > 0)
        self.assertTrue(len(key_simulator.ACTIONS["prev_tab"]["keys"]) > 0)


class CustomShortcutParsingTests(unittest.TestCase):
    def test_build_custom_key_name_map_adds_common_aliases(self):
        key_map = key_simulator._build_custom_key_name_map({
            "ctrl": 1,
            "alt": 2,
            "super": 3,
            "enter": 4,
            "esc": 5,
        })

        self.assertEqual(key_map["control"], 1)
        self.assertEqual(key_map["option"], 2)
        self.assertEqual(key_map["opt"], 2)
        self.assertEqual(key_map["cmd"], 3)
        self.assertEqual(key_map["command"], 3)
        self.assertEqual(key_map["meta"], 3)
        self.assertEqual(key_map["win"], 3)
        self.assertEqual(key_map["windows"], 3)
        self.assertEqual(key_map["return"], 4)
        self.assertEqual(key_map["escape"], 5)

    def test_parse_custom_combo_accepts_digit_keys(self):
        keys = key_simulator._parse_custom_combo(
            "custom:ctrl+4",
            {"ctrl": 17, "4": 52},
        )
        self.assertEqual(keys, [17, 52])

    def test_parse_custom_combo_accepts_manual_shifted_symbols(self):
        keys = key_simulator._parse_custom_combo(
            "custom:ctrl+<",
            {"ctrl": 17, "shift": 16, "comma": 188},
        )
        self.assertEqual(keys, [17, 16, 188])

    def test_parse_custom_combo_rejects_multiple_non_modifier_keys(self):
        self.assertIsNone(
            key_simulator._parse_custom_combo(
                "custom:ctrl+a+b",
                {"ctrl": 17, "a": 65, "b": 66},
            )
        )

    def test_windows_custom_shortcut_codes_include_f13_through_f24(self):
        self.assertEqual(key_simulator.WINDOWS_FUNCTION_KEY_CODES["f1"], 0x70)
        self.assertEqual(key_simulator.WINDOWS_FUNCTION_KEY_CODES["f12"], 0x7B)
        self.assertEqual(key_simulator.WINDOWS_FUNCTION_KEY_CODES["f13"], 0x7C)
        self.assertEqual(key_simulator.WINDOWS_FUNCTION_KEY_CODES["f24"], 0x87)


class LinuxDesktopShortcutTests(unittest.TestCase):
    _SCREENSHOT_ACTIONS = {
        "screenshot_region_clip": "Screenshot Region → Clipboard",
        "screenshot_region_file": "Screenshot Region → File",
        "screenshot_full_clip": "Screenshot Full Screen → Clipboard",
        "screenshot_full_file": "Screenshot Full Screen → File",
    }

    def _reload_for_linux(self, desktop: str):
        with (
            patch.object(sys, "platform", "linux"),
            patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": desktop}, clear=False),
        ):
            importlib.reload(key_simulator)
        self.addCleanup(importlib.reload, key_simulator)
        return key_simulator

    def test_gnome_uses_super_page_keys_for_workspace_switching(self):
        module = self._reload_for_linux("GNOME")

        self.assertEqual(
            module.ACTIONS["space_left"]["keys"],
            [module.KEY_LEFTMETA, module.KEY_PAGEUP],
        )
        self.assertEqual(
            module.ACTIONS["space_right"]["keys"],
            [module.KEY_LEFTMETA, module.KEY_PAGEDOWN],
        )

    def test_kde_uses_ctrl_super_arrow_for_workspace_switching(self):
        module = self._reload_for_linux("KDE")

        self.assertEqual(
            module.ACTIONS["space_left"]["keys"],
            [module.KEY_LEFTCTRL, module.KEY_LEFTMETA, module.KEY_LEFT],
        )
        self.assertEqual(
            module.ACTIONS["space_right"]["keys"],
            [module.KEY_LEFTCTRL, module.KEY_LEFTMETA, module.KEY_RIGHT],
        )

    def test_linux_custom_shortcuts_include_digit_keys_and_aliases(self):
        module = self._reload_for_linux("GNOME")

        self.assertEqual(module._KEY_NAME_TO_CODE["4"], module.KEY_4)
        self.assertIn(module.KEY_4, module._ALL_KEY_CODES)
        self.assertEqual(module._KEY_NAME_TO_CODE["control"], module.KEY_LEFTCTRL)
        self.assertEqual(module._KEY_NAME_TO_CODE["cmd"], module.KEY_LEFTMETA)
        self.assertEqual(module._KEY_NAME_TO_CODE["insert"], 110)
        self.assertIn(module._KEY_NAME_TO_CODE["semicolon"], module._ALL_KEY_CODES)
        self.assertIn(module._KEY_NAME_TO_CODE["f24"], module._ALL_KEY_CODES)

    def test_linux_screenshot_actions_are_native_requests(self):
        module = self._reload_for_linux("KDE")

        for action_id, label in self._SCREENSHOT_ACTIONS.items():
            self.assertIn(action_id, module.ACTIONS)
            self.assertEqual(module.ACTIONS[action_id]["label"], label)
            self.assertEqual(module.ACTIONS[action_id]["category"], "Screenshot")
            self.assertEqual(module.ACTIONS[action_id]["keys"], [])
            self.assertTrue(module.is_screenshot_action(action_id))

    def test_linux_screenshot_actions_dispatch_to_handler_not_keys(self):
        module = self._reload_for_linux("KDE")
        calls = []
        module.set_screenshot_action_handler(calls.append)

        with patch.object(module, "send_key_combo") as send_key_combo:
            module.execute_action("screenshot_region_file")

        self.assertEqual(calls, ["screenshot_region_file"])
        send_key_combo.assert_not_called()


class WindowsScreenshotActionTests(unittest.TestCase):
    _ACTIONS = {
        "screenshot_region_clip": "Screenshot Region → Clipboard",
        "screenshot_region_file": "Screenshot Region → File",
        "screenshot_full_clip": "Screenshot Full Screen → Clipboard",
        "screenshot_full_file": "Screenshot Full Screen → File",
    }

    def _reload_for_windows(self):
        import ctypes

        def fake_send_input(*_args):
            return 1

        fake_send_input.argtypes = []
        fake_send_input.restype = 1
        fake_windll = types.SimpleNamespace(
            user32=types.SimpleNamespace(SendInput=fake_send_input)
        )
        platform_patch = patch.object(sys, "platform", "win32")
        windll_patch = patch.object(ctypes, "windll", fake_windll, create=True)
        platform_patch.start()
        windll_patch.start()
        module = importlib.reload(key_simulator)
        self.addCleanup(importlib.reload, key_simulator)
        self.addCleanup(platform_patch.stop)
        self.addCleanup(windll_patch.stop)
        return module

    def test_windows_screenshot_actions_are_native_requests(self):
        module = self._reload_for_windows()

        for action_id, label in self._ACTIONS.items():
            self.assertIn(action_id, module.ACTIONS)
            self.assertEqual(module.ACTIONS[action_id]["label"], label)
            self.assertEqual(module.ACTIONS[action_id]["category"], "Screenshot")
            self.assertEqual(module.ACTIONS[action_id]["keys"], [])
            self.assertTrue(module.is_screenshot_action(action_id))

    def test_windows_screenshot_actions_dispatch_to_handler_not_keys(self):
        module = self._reload_for_windows()
        calls = []
        module.set_screenshot_action_handler(calls.append)

        with patch.object(module, "send_key_combo") as send_key_combo:
            module.execute_action("screenshot_full_clip")

        self.assertEqual(calls, ["screenshot_full_clip"])
        send_key_combo.assert_not_called()


class MacOSZoomActionTests(unittest.TestCase):
    _SCREENSHOT_ACTIONS = {
        "screenshot_region_clip": "Screenshot Region → Clipboard",
        "screenshot_region_file": "Screenshot Region → File",
        "screenshot_full_clip": "Screenshot Full Screen → Clipboard",
        "screenshot_full_file": "Screenshot Full Screen → File",
    }

    def _reload_for_macos(self):
        with patch.object(sys, "platform", "darwin"):
            importlib.reload(key_simulator)
        self.addCleanup(importlib.reload, key_simulator)
        return key_simulator

    def test_zoom_actions_exist(self):
        module = self._reload_for_macos()

        self.assertEqual(module.ACTIONS["zoom_in"]["label"], "Zoom In")
        self.assertEqual(module.ACTIONS["zoom_in"]["category"], "Navigation")
        self.assertEqual(module.ACTIONS["zoom_in"]["keys"], [])
        self.assertEqual(module.ACTIONS["zoom_out"]["label"], "Zoom Out")
        self.assertEqual(module.ACTIONS["zoom_out"]["category"], "Navigation")
        self.assertEqual(module.ACTIONS["zoom_out"]["keys"], [])

    def test_zoom_in_sends_three_command_equal_presses(self):
        module = self._reload_for_macos()

        with patch.object(module, "send_key_combo") as send_key_combo:
            module.execute_action("zoom_in")

        expected = [module.kVK_Command, module.kVK_ANSI_Equal]
        self.assertEqual(send_key_combo.call_count, 3)
        send_key_combo.assert_has_calls([
            call(expected, hold_ms=0),
            call(expected, hold_ms=0),
            call(expected, hold_ms=0),
        ])

    def test_zoom_out_sends_three_command_minus_presses(self):
        module = self._reload_for_macos()

        with patch.object(module, "send_key_combo") as send_key_combo:
            module.execute_action("zoom_out")

        expected = [module.kVK_Command, module.kVK_ANSI_Minus]
        self.assertEqual(send_key_combo.call_count, 3)
        send_key_combo.assert_has_calls([
            call(expected, hold_ms=0),
            call(expected, hold_ms=0),
            call(expected, hold_ms=0),
        ])

    def test_existing_alt_tab_action_still_uses_standard_key_path(self):
        module = self._reload_for_macos()

        with patch.object(module, "send_key_combo") as send_key_combo:
            module.execute_action("alt_tab")

        send_key_combo.assert_called_once_with([module.kVK_Command, module.kVK_Tab])

    def test_macos_screenshot_actions_keep_shortcut_defaults(self):
        module = self._reload_for_macos()

        for action_id, label in self._SCREENSHOT_ACTIONS.items():
            self.assertIn(action_id, module.ACTIONS)
            self.assertEqual(module.ACTIONS[action_id]["label"], label)
            self.assertEqual(module.ACTIONS[action_id]["category"], "Screenshot")
            self.assertTrue(module.ACTIONS[action_id]["keys"])
            self.assertTrue(module.is_screenshot_action(action_id))

    def test_macos_screenshot_action_without_handler_falls_back_to_shortcut(self):
        module = self._reload_for_macos()

        with patch.object(module, "send_key_combo") as send_key_combo:
            module.execute_action("screenshot_full_file")

        send_key_combo.assert_called_once_with(
            [module.kVK_Command, module.kVK_Shift, module.kVK_ANSI_3]
        )

    def test_macos_screenshot_helper_sends_existing_shortcut(self):
        module = self._reload_for_macos()

        with patch.object(module, "send_key_combo") as send_key_combo:
            handled = module.execute_screenshot_shortcut("screenshot_region_clip")

        self.assertTrue(handled)
        send_key_combo.assert_called_once_with(
            [module.kVK_Command, module.kVK_Shift, module.kVK_Control, module.kVK_ANSI_4]
        )

    def test_macos_screenshot_action_dispatches_to_registered_handler(self):
        module = self._reload_for_macos()
        calls = []
        module.set_screenshot_action_handler(calls.append)

        with patch.object(module, "send_key_combo") as send_key_combo:
            module.execute_action("screenshot_region_file")

        self.assertEqual(calls, ["screenshot_region_file"])
        send_key_combo.assert_not_called()


class CustomShortcutCaptureTests(unittest.TestCase):
    def test_custom_action_label_uses_platform_display_names(self):
        self.assertEqual(
            key_simulator.custom_action_label(
                "custom:cmd+w",
                platform_name="darwin",
            ),
            "Cmd + W",
        )
        self.assertEqual(
            key_simulator.custom_action_label(
                "custom:super+w",
                platform_name="win32",
            ),
            "Win + W",
        )
        self.assertEqual(
            key_simulator.custom_action_label(
                "custom:super+w",
                platform_name="linux",
            ),
            "Super + W",
        )

    def test_macos_swaps_qt_control_and_meta_semantics(self):
        self.assertEqual(
            key_simulator.normalize_captured_shortcut_parts(
                ["ctrl"],
                "w",
                platform_name="darwin",
            ),
            "super+w",
        )
        self.assertEqual(
            key_simulator.normalize_captured_shortcut_parts(
                ["super"],
                "w",
                platform_name="darwin",
            ),
            "ctrl+w",
        )
        self.assertEqual(
            key_simulator.normalize_captured_shortcut_parts(
                ["ctrl"],
                "ctrl",
                platform_name="darwin",
            ),
            "super",
        )
        self.assertEqual(
            key_simulator.normalize_captured_shortcut_parts(
                ["super"],
                "super",
                platform_name="darwin",
            ),
            "ctrl",
        )

    def test_non_macos_keeps_qt_control_and_meta_semantics(self):
        self.assertEqual(
            key_simulator.normalize_captured_shortcut_parts(
                ["ctrl"],
                "w",
                platform_name="linux",
            ),
            "ctrl+w",
        )
        self.assertEqual(
            key_simulator.normalize_captured_shortcut_parts(
                ["super"],
                "w",
                platform_name="linux",
            ),
            "super+w",
        )

    def test_capture_normalization_accepts_punctuation_aliases(self):
        self.assertEqual(
            key_simulator.normalize_captured_shortcut_parts(
                ["ctrl"],
                "<",
                platform_name="win32",
            ),
            "ctrl+shift+comma",
        )


class MouseButtonActionTests(unittest.TestCase):
    """Tests for the mouse-button-to-mouse-button remapping feature."""

    _MOUSE_ACTIONS = [
        "mouse_left_click",
        "mouse_right_click",
        "mouse_middle_click",
        "mouse_back_click",
        "mouse_forward_click",
    ]

    def test_mouse_button_actions_exist_in_actions_dict(self):
        for action_id in self._MOUSE_ACTIONS:
            self.assertIn(action_id, key_simulator.ACTIONS, f"{action_id} missing from ACTIONS")
            self.assertEqual(key_simulator.ACTIONS[action_id]["category"], "Mouse")
            self.assertEqual(key_simulator.ACTIONS[action_id]["keys"], [])

    def test_is_mouse_button_action_returns_true_for_mouse_actions(self):
        for action_id in self._MOUSE_ACTIONS:
            self.assertTrue(
                key_simulator.is_mouse_button_action(action_id),
                f"is_mouse_button_action({action_id!r}) should be True",
            )

    def test_is_mouse_button_action_returns_false_for_non_mouse_actions(self):
        self.assertFalse(key_simulator.is_mouse_button_action("alt_tab"))
        self.assertFalse(key_simulator.is_mouse_button_action("none"))
        self.assertFalse(key_simulator.is_mouse_button_action("custom:ctrl+c"))

    def test_mouse_button_labels_are_non_empty_strings(self):
        for action_id in self._MOUSE_ACTIONS:
            label = key_simulator.ACTIONS[action_id]["label"]
            self.assertIsInstance(label, str)
            self.assertTrue(len(label) > 0)


class WindowsZoomActionTests(unittest.TestCase):
    def _reload_for_windows(self):
        import ctypes

        def fake_send_input(*_args):
            return 1

        fake_send_input.argtypes = []
        fake_send_input.restype = 1
        fake_windll = types.SimpleNamespace(
            user32=types.SimpleNamespace(SendInput=fake_send_input)
        )
        platform_patch = patch.object(sys, "platform", "win32")
        windll_patch = patch.object(ctypes, "windll", fake_windll, create=True)
        platform_patch.start()
        windll_patch.start()
        module = importlib.reload(key_simulator)
        self.addCleanup(importlib.reload, key_simulator)
        self.addCleanup(platform_patch.stop)
        self.addCleanup(windll_patch.stop)
        return module

    def test_zoom_actions_exist(self):
        module = self._reload_for_windows()

        self.assertEqual(module.ACTIONS["zoom_in"]["label"], "Zoom In")
        self.assertEqual(module.ACTIONS["zoom_in"]["category"], "Navigation")
        self.assertEqual(
            module.ACTIONS["zoom_in"]["keys"],
            [module.VK_CONTROL, module.VK_OEM_PLUS],
        )
        self.assertEqual(module.ACTIONS["zoom_out"]["label"], "Zoom Out")
        self.assertEqual(module.ACTIONS["zoom_out"]["category"], "Navigation")
        self.assertEqual(
            module.ACTIONS["zoom_out"]["keys"],
            [module.VK_CONTROL, module.VK_OEM_MINUS],
        )

    def test_zoom_in_sends_single_ctrl_equal_press(self):
        module = self._reload_for_windows()

        with patch.object(module, "send_key_combo") as send_key_combo:
            module.execute_action("zoom_in")

        send_key_combo.assert_called_once_with([module.VK_CONTROL, module.VK_OEM_PLUS])

    def test_zoom_out_sends_single_ctrl_minus_press(self):
        module = self._reload_for_windows()

        with patch.object(module, "send_key_combo") as send_key_combo:
            module.execute_action("zoom_out")

        send_key_combo.assert_called_once_with([module.VK_CONTROL, module.VK_OEM_MINUS])


class LinuxZoomActionTests(unittest.TestCase):
    def _reload_for_linux(self, desktop: str = "GNOME"):
        with (
            patch.object(sys, "platform", "linux"),
            patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": desktop}, clear=False),
        ):
            importlib.reload(key_simulator)
        self.addCleanup(importlib.reload, key_simulator)
        return key_simulator

    def test_zoom_actions_exist(self):
        module = self._reload_for_linux()

        self.assertEqual(module.ACTIONS["zoom_in"]["label"], "Zoom In")
        self.assertEqual(module.ACTIONS["zoom_in"]["category"], "Navigation")
        self.assertEqual(
            module.ACTIONS["zoom_in"]["keys"],
            [module.KEY_LEFTCTRL, module.KEY_EQUAL],
        )
        self.assertEqual(module.ACTIONS["zoom_out"]["label"], "Zoom Out")
        self.assertEqual(module.ACTIONS["zoom_out"]["category"], "Navigation")
        self.assertEqual(
            module.ACTIONS["zoom_out"]["keys"],
            [module.KEY_LEFTCTRL, module.KEY_MINUS],
        )

    def test_zoom_key_codes_registered_for_virtual_keyboard(self):
        module = self._reload_for_linux()

        self.assertIn(module.KEY_EQUAL, module._ALL_KEY_CODES)
        self.assertIn(module.KEY_MINUS, module._ALL_KEY_CODES)

    def test_zoom_in_dispatches_single_ctrl_equal(self):
        module = self._reload_for_linux()

        with patch.object(module, "send_key_combo") as send_key_combo:
            module.execute_action("zoom_in")

        send_key_combo.assert_called_once_with([module.KEY_LEFTCTRL, module.KEY_EQUAL])

    def test_zoom_out_dispatches_single_ctrl_minus(self):
        module = self._reload_for_linux()

        with patch.object(module, "send_key_combo") as send_key_combo:
            module.execute_action("zoom_out")

        send_key_combo.assert_called_once_with([module.KEY_LEFTCTRL, module.KEY_MINUS])


if __name__ == "__main__":
    unittest.main()


class HoldShortcutTests(unittest.TestCase):
    """``hold:<combo>`` keeps a custom shortcut pressed while the mouse
    button is held, instead of tapping it on press."""

    def test_hold_prefix_is_recognised_as_a_custom_action(self):
        self.assertTrue(key_simulator.is_hold_action("hold:alt+grave"))
        self.assertFalse(key_simulator.is_hold_action("custom:alt+grave"))
        self.assertTrue(key_simulator.is_custom_action("hold:alt+grave"))
        self.assertTrue(key_simulator.is_custom_action("custom:alt+grave"))
        self.assertFalse(key_simulator.is_custom_action("copy"))

    def test_hold_label_marks_the_shortcut_as_held(self):
        tap = key_simulator.custom_action_label("custom:ctrl+a", platform_name="win32")
        hold = key_simulator.custom_action_label("hold:ctrl+a", platform_name="win32")
        self.assertEqual(tap, "Ctrl + A")
        self.assertEqual(hold, "Ctrl + A (Hold)")

    def test_parse_custom_combo_accepts_hold_prefix(self):
        key_map = {"ctrl": 1, "a": 2}
        self.assertEqual(
            key_simulator._parse_custom_combo("hold:ctrl+a", key_map), [1, 2]
        )

    def test_execute_action_taps_a_hold_shortcut(self):
        # Single-fire sources (ring slots, swipes) have no release, so a
        # hold shortcut degrades to a normal tap there.
        with patch.object(key_simulator, "send_key_combo") as send_key_combo, \
             patch.object(key_simulator, "_KEY_NAME_TO_CODE", {"ctrl": 1, "a": 2}, create=True):
            key_simulator.execute_action("hold:ctrl+a")
        if sys.platform in ("darwin", "win32", "linux"):
            send_key_combo.assert_called_once_with([1, 2])

    @unittest.skipUnless(sys.platform == "darwin", "macOS key injection")
    def test_macos_press_and_release_post_separate_key_events(self):
        posted = []
        fake_quartz = unittest.mock.MagicMock()
        fake_quartz.CGEventCreateKeyboardEvent.side_effect = (
            lambda _src, code, down: ("ev", code, down)
        )
        fake_quartz.CGEventPost.side_effect = lambda _tap, ev: posted.append(ev)
        with patch.object(key_simulator, "Quartz", fake_quartz), \
             patch.object(key_simulator, "_QUARTZ_OK", True):
            key_simulator.press_key_combo([58, 50])
            self.assertEqual(posted, [("ev", 58, True), ("ev", 50, True)])
            posted.clear()
            key_simulator.release_key_combo([58, 50])
        self.assertEqual(posted, [("ev", 50, False), ("ev", 58, False)])

    @unittest.skipUnless(sys.platform == "darwin", "macOS key injection")
    def test_macos_fn_is_posted_as_a_modifier_flag_change(self):
        # macOS has no key-down for Fn: it is a flags-changed event carrying
        # the SecondaryFn flag on press and no flags on release.
        fake_quartz = unittest.mock.MagicMock()
        fake_quartz.kCGEventFlagsChanged = 12
        fake_quartz.kCGEventFlagMaskSecondaryFn = 0x800000
        events = []

        def create(_src, code, down):
            ev = {"code": code, "down": down, "type": "key", "flags": None}
            events.append(ev)
            return ev

        fake_quartz.CGEventCreateKeyboardEvent.side_effect = create
        fake_quartz.CGEventSetType.side_effect = lambda ev, t: ev.update(type=t)
        fake_quartz.CGEventSetFlags.side_effect = lambda ev, f: ev.update(flags=f)
        with patch.object(key_simulator, "Quartz", fake_quartz), \
             patch.object(key_simulator, "_QUARTZ_OK", True), \
             patch.dict(key_simulator._MOD_FLAGS,
                        {key_simulator.kVK_Function: 0x800000}):
            key_simulator.press_key_combo([0x3F])
            key_simulator.release_key_combo([0x3F])
        self.assertEqual(events, [
            {"code": 0x3F, "down": True, "type": 12, "flags": 0x800000},
            {"code": 0x3F, "down": False, "type": 12, "flags": 0},
        ])

    @unittest.skipUnless(sys.platform == "darwin", "macOS key injection")
    def test_macos_hold_fn_action_presses_the_function_key(self):
        with patch.object(key_simulator, "press_key_combo") as press, \
             patch.object(key_simulator, "release_key_combo") as release:
            key_simulator.hold_action_press("hold:fn")
            key_simulator.hold_action_release("hold:fn")
        press.assert_called_once_with([0x3F])
        release.assert_called_once_with([0x3F])

    def test_hold_action_press_and_release_use_the_parsed_combo(self):
        with patch.object(key_simulator, "press_key_combo") as press, \
             patch.object(key_simulator, "release_key_combo") as release, \
             patch.object(key_simulator, "_KEY_NAME_TO_CODE", {"alt": 7, "grave": 9}, create=True):
            key_simulator.hold_action_press("hold:alt+grave")
            key_simulator.hold_action_release("hold:alt+grave")
        press.assert_called_once_with([7, 9])
        release.assert_called_once_with([7, 9])

    def test_hold_action_press_ignores_unparseable_combo(self):
        with patch.object(key_simulator, "press_key_combo") as press, \
             patch.object(key_simulator, "_KEY_NAME_TO_CODE", {"alt": 7}, create=True):
            key_simulator.hold_action_press("hold:alt+nosuchkey")
        press.assert_not_called()
