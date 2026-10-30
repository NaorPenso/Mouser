import copy
from pathlib import Path
import sys
import tempfile
import unittest
import unittest.mock
from types import SimpleNamespace
from unittest.mock import patch

from core.config import DEFAULT_CONFIG

try:
    from PySide6.QtCore import QCoreApplication, Qt, QUrl
    from ui.backend import Backend
except ModuleNotFoundError:
    Backend = None
    QCoreApplication = None
    Qt = None
    QUrl = None


def _ensure_qapp():
    app = QCoreApplication.instance()
    if app is None:
        return QCoreApplication(sys.argv)
    return app


class _FakeEngine:
    def __init__(
        self,
        device_connected=False,
        connected_device=None,
        hid_features_ready=False,
        smart_shift_supported=False,
    ):
        self.device_connected = device_connected
        self.connected_device = connected_device
        self.hid_features_ready = hid_features_ready
        self.smart_shift_supported = smart_shift_supported
        self.profile_callback = None
        self.dpi_callback = None
        self.connection_callback = None
        self.battery_callback = None
        self.debug_callback = None
        self.gesture_callback = None
        self.status_callback = None
        self.debug_enabled = None
        self.start_count = 0
        self.stop_count = 0
        self.start_error = None

    def set_profile_change_callback(self, cb):
        self.profile_callback = cb

    def set_dpi_read_callback(self, cb):
        self.dpi_callback = cb

    def set_connection_change_callback(self, cb):
        self.connection_callback = cb

    def set_battery_callback(self, cb):
        self.battery_callback = cb

    def set_debug_callback(self, cb):
        self.debug_callback = cb

    def set_gesture_event_callback(self, cb):
        self.gesture_callback = cb

    def set_status_callback(self, cb):
        self.status_callback = cb

    def set_debug_enabled(self, enabled):
        self.debug_enabled = enabled

    def start(self):
        self.start_count += 1
        if self.start_error:
            raise self.start_error

    def stop(self):
        self.stop_count += 1


@unittest.skipIf(Backend is None, "PySide6 not installed in test environment")
class BackendDeviceLayoutTests(unittest.TestCase):
    def _make_backend(self, engine=None, root_dir=None, cfg=None):
        loaded_config = copy.deepcopy(cfg or DEFAULT_CONFIG)
        with (
            patch("ui.backend.load_config", return_value=loaded_config),
            patch("ui.backend.save_config"),
            patch("ui.backend.supports_login_startup", return_value=False),
        ):
            return Backend(engine=engine, root_dir=root_dir)

    @staticmethod
    def _fake_create_profile(cfg, name, label=None, copy_from="default", apps=None):
        updated = copy.deepcopy(cfg)
        updated.setdefault("profiles", {})[name] = {
            "label": label or name,
            "apps": list(apps or []),
            "mappings": {},
        }
        return updated

    def test_defaults_to_generic_layout_without_connected_device(self):
        backend = self._make_backend()

        self.assertEqual(backend.effectiveDeviceLayoutKey, "generic_mouse")
        self.assertFalse(backend.hasInteractiveDeviceLayout)

    def test_device_image_source_uses_encoded_file_url(self):
        backend = self._make_backend(root_dir="/tmp/Mouser Build")

        expected = QUrl.fromLocalFile(
            "/tmp/Mouser Build/images/icons/mouse-simple.svg"
        ).toString()

        self.assertEqual(backend.deviceImageSource, expected)

    def test_mx_anywhere_2s_hotspots_expose_horizontal_scroll(self):
        device = SimpleNamespace(
            key="mx_anywhere_2s",
            display_name="MX Anywhere 2S",
            dpi_min=200,
            dpi_max=4000,
            ui_layout="mx_anywhere_2s",
            supported_buttons=("middle", "hscroll_left", "hscroll_right"),
        )
        backend = self._make_backend(
            engine=_FakeEngine(device_connected=True, connected_device=device)
        )

        hscroll_hotspots = [
            hotspot
            for hotspot in backend.deviceHotspots
            if hotspot.get("isHScroll")
        ]

        self.assertEqual(len(hscroll_hotspots), 1)
        self.assertEqual(hscroll_hotspots[0]["buttonKey"], "hscroll_left")
        self.assertEqual(hscroll_hotspots[0]["summaryType"], "hscroll")
        self.assertTrue(hscroll_hotspots[0]["isHScroll"])

    def test_disconnected_override_request_does_not_persist(self):
        backend = self._make_backend()
        backend._connected_device_key = "mx_master_3"
        backend.setDeviceLayoutOverride("mx_master")

        overrides = backend._cfg.get("settings", {}).get("device_layout_overrides", {})
        self.assertEqual(overrides, {})

    def test_connected_device_can_override_exact_layout_with_family_layout(self):
        device = SimpleNamespace(
            key="mx_master_4",
            display_name="MX Master 4",
            dpi_min=200,
            dpi_max=8000,
            ui_layout="mx_master_4",
            supported_buttons=("middle", "xbutton1", "xbutton2"),
        )

        with (
            patch("ui.backend.load_config", return_value=copy.deepcopy(DEFAULT_CONFIG)),
            patch("ui.backend.save_config"),
            patch("ui.backend.supports_login_startup", return_value=False),
        ):
            backend = Backend(engine=_FakeEngine(device_connected=True, connected_device=device))
            backend.setDeviceLayoutOverride("mx_master")

        overrides = backend._cfg.get("settings", {}).get("device_layout_overrides", {})
        self.assertEqual(overrides, {"mx_master_4": "mx_master"})
        self.assertEqual(backend.effectiveDeviceLayoutKey, "mx_master")

    def test_connected_device_supported_buttons_filter_mapping_list(self):
        device = SimpleNamespace(
            key="mx_master_3s",
            display_name="MX Master 3S",
            dpi_min=200,
            dpi_max=8000,
            ui_layout="mx_master_3s",
            supported_buttons=("middle", "xbutton1"),
        )

        with (
            patch("ui.backend.load_config", return_value=copy.deepcopy(DEFAULT_CONFIG)),
            patch("ui.backend.save_config"),
            patch("ui.backend.supports_login_startup", return_value=False),
        ):
            backend = Backend(engine=_FakeEngine(device_connected=True, connected_device=device))

        button_keys = [button["key"] for button in backend.buttons]
        self.assertIn("middle", button_keys)
        self.assertIn("xbutton1", button_keys)
        self.assertNotIn("gesture", button_keys)
        self.assertNotIn("mode_shift", button_keys)

    def test_disconnect_clears_stale_linux_device_identity_and_layout(self):
        device = SimpleNamespace(
            key="mx_master_3",
            display_name="MX Master 3S",
            dpi_min=200,
            dpi_max=8000,
            ui_layout="mx_master_3",
        )

        def fake_layout(key):
            return {"key": key, "interactive": key != "generic_mouse"}

        with (
            patch("ui.backend.load_config", return_value=copy.deepcopy(DEFAULT_CONFIG)),
            patch("ui.backend.save_config"),
            patch("ui.backend.supports_login_startup", return_value=False),
            patch("ui.backend.get_device_layout", side_effect=fake_layout),
        ):
            backend = Backend(engine=_FakeEngine(device_connected=True, connected_device=device))
            self.assertTrue(backend.mouseConnected)
            self.assertEqual(backend.connectedDeviceKey, "mx_master_3")
            self.assertEqual(backend.effectiveDeviceLayoutKey, "mx_master_3")
            backend._battery_level = 42

            backend._handleConnectionChange(False)

        self.assertFalse(backend.mouseConnected)
        self.assertEqual(backend.connectedDeviceKey, "")
        self.assertEqual(backend.effectiveDeviceLayoutKey, "generic_mouse")
        self.assertEqual(backend.batteryLevel, -1)

    def test_refresh_updates_hid_features_without_reemitting_connection_edge(self):
        device = SimpleNamespace(
            key="mx_master_3",
            display_name="MX Master 3S",
            dpi_min=200,
            dpi_max=8000,
            ui_layout="mx_master_3",
        )

        def fake_layout(key):
            return {"key": key, "interactive": key != "generic_mouse"}

        engine = _FakeEngine(
            device_connected=True,
            connected_device=None,
            hid_features_ready=False,
            smart_shift_supported=False,
        )

        with (
            patch("ui.backend.load_config", return_value=copy.deepcopy(DEFAULT_CONFIG)),
            patch("ui.backend.save_config"),
            patch("ui.backend.supports_login_startup", return_value=False),
            patch("ui.backend.get_device_layout", side_effect=fake_layout),
        ):
            backend = Backend(engine=engine)
            mouse_notifications = []
            hid_notifications = []
            backend.mouseConnectedChanged.connect(lambda: mouse_notifications.append(True))
            backend.hidFeaturesReadyChanged.connect(lambda: hid_notifications.append(True))

            engine.connected_device = device
            engine.hid_features_ready = True
            engine.smart_shift_supported = True
            backend._handleConnectionChange(True)

        self.assertTrue(backend.mouseConnected)
        self.assertTrue(backend.hidFeaturesReady)
        self.assertTrue(backend.smartShiftSupported)
        self.assertEqual(backend.connectedDeviceKey, "mx_master_3")
        self.assertEqual(mouse_notifications, [])
        self.assertEqual(hid_notifications, [True])

    def test_retry_refresh_promotes_late_hid_features_ready(self):
        device = SimpleNamespace(
            key="mx_master_3",
            display_name="MX Master 3S",
            dpi_min=200,
            dpi_max=8000,
            ui_layout="mx_master",
        )
        engine = _FakeEngine(
            device_connected=True,
            connected_device=None,
            hid_features_ready=False,
            smart_shift_supported=False,
        )
        backend = self._make_backend(engine=engine)
        backend._mouse_connected = True
        hid_notifications = []
        backend.hidFeaturesReadyChanged.connect(lambda: hid_notifications.append(True))

        engine.connected_device = device
        engine.hid_features_ready = True
        engine.smart_shift_supported = True
        backend._refresh_connected_device_info()

        self.assertTrue(backend.hidFeaturesReady)
        self.assertTrue(backend.smartShiftSupported)
        self.assertEqual(backend.connectedDeviceKey, "mx_master_3")
        self.assertEqual(hid_notifications, [True])

    def test_init_wires_engine_status_callback_into_backend(self):
        engine = _FakeEngine()

        backend = self._make_backend(engine=engine)

        self.assertIsNotNone(engine.status_callback)
        self.assertIs(engine.status_callback.__self__, backend)
        self.assertIs(engine.status_callback.__func__, Backend._onEngineStatusMessage)

    def test_screenshot_directory_defaults_to_system_behavior(self):
        backend = self._make_backend()

        self.assertEqual(backend.screenshotDirectory, "")
        self.assertEqual(backend.screenshotDirectoryLabel, "")
        self.assertFalse(backend.hasCustomScreenshotDirectory)

    def test_next_screenshot_file_path_uses_custom_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = copy.deepcopy(DEFAULT_CONFIG)
            cfg["settings"]["screenshot_directory"] = tmp
            with (
                patch("ui.backend.load_config", return_value=cfg),
                patch("ui.backend.save_config"),
                patch("ui.backend.supports_login_startup", return_value=False),
            ):
                backend = Backend(engine=None)

            path = backend.next_screenshot_file_path()

        self.assertEqual(path.parent, Path(tmp))
        self.assertTrue(path.name.startswith("Screenshot "))
        self.assertEqual(path.suffix, ".png")

    def test_next_screenshot_file_paths_reserves_multiple_custom_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = copy.deepcopy(DEFAULT_CONFIG)
            cfg["settings"]["screenshot_directory"] = tmp
            with (
                patch("ui.backend.load_config", return_value=cfg),
                patch("ui.backend.save_config"),
                patch("ui.backend.supports_login_startup", return_value=False),
            ):
                backend = Backend(engine=None)

            paths = backend.next_screenshot_file_paths(2)

        self.assertEqual([path.parent for path in paths], [Path(tmp), Path(tmp)])
        self.assertEqual(len({path.name for path in paths}), 2)

    def test_choose_screenshot_directory_persists_valid_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = copy.deepcopy(DEFAULT_CONFIG)
            with (
                patch("ui.backend.load_config", return_value=cfg),
                patch("ui.backend.save_config") as save_mock,
                patch("ui.backend.supports_login_startup", return_value=False),
                patch(
                    "PySide6.QtWidgets.QFileDialog.getExistingDirectory",
                    return_value=tmp,
                ),
            ):
                backend = Backend(engine=None)
                statuses = []
                backend.statusMessage.connect(statuses.append)
                backend.chooseScreenshotDirectory()

        self.assertEqual(backend.screenshotDirectory, str(Path(tmp)))
        self.assertTrue(backend.hasCustomScreenshotDirectory)
        save_mock.assert_called_once()
        self.assertEqual(statuses, ["Saved"])

    def test_choose_screenshot_directory_ignores_invalid_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "not-a-folder"
            file_path.write_text("x", encoding="utf-8")
            cfg = copy.deepcopy(DEFAULT_CONFIG)
            with (
                patch("ui.backend.load_config", return_value=cfg),
                patch("ui.backend.save_config") as save_mock,
                patch("ui.backend.supports_login_startup", return_value=False),
                patch(
                    "PySide6.QtWidgets.QFileDialog.getExistingDirectory",
                    return_value=str(file_path),
                ),
            ):
                backend = Backend(engine=None)
                statuses = []
                backend.statusMessage.connect(statuses.append)
                backend.chooseScreenshotDirectory()

        self.assertEqual(backend.screenshotDirectory, "")
        save_mock.assert_not_called()
        self.assertEqual(statuses, ["Choose a valid screenshot folder"])

    def test_reset_screenshot_directory_clears_custom_folder(self):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["settings"]["screenshot_directory"] = "/tmp/screens"
        with (
            patch("ui.backend.load_config", return_value=cfg),
            patch("ui.backend.save_config") as save_mock,
            patch("ui.backend.supports_login_startup", return_value=False),
        ):
            backend = Backend(engine=None)
            statuses = []
            backend.statusMessage.connect(statuses.append)
            backend.resetScreenshotDirectory()

        self.assertEqual(backend.screenshotDirectory, "")
        self.assertFalse(backend.hasCustomScreenshotDirectory)
        save_mock.assert_called_once()
        self.assertEqual(statuses, ["Saved"])

    def test_replay_failure_status_becomes_backend_status_message(self):
        app = _ensure_qapp()
        engine = _FakeEngine()

        with (
            patch("ui.backend.load_config", return_value=copy.deepcopy(DEFAULT_CONFIG)),
            patch("ui.backend.save_config"),
            patch("ui.backend.supports_login_startup", return_value=False),
        ):
            backend = Backend(engine=engine)
            status_messages = []
            backend.statusMessage.connect(status_messages.append)

            engine.status_callback("Failed to replay HID++ settings after reconnect")
            app.processEvents()

        self.assertEqual(
            status_messages,
            ["Failed to replay HID++ settings after reconnect"],
        )

    def test_non_dict_smart_shift_payload_does_not_emit_change_signal(self):
        backend = self._make_backend()
        notifications = []
        backend.smartShiftChanged.connect(lambda: notifications.append(True))

        backend._pending_smart_shift_state = "freespin"
        backend._handleSmartShiftRead()

        self.assertEqual(notifications, [])

    def test_non_dict_smart_shift_payload_does_not_mutate_config(self):
        backend = self._make_backend()
        original = copy.deepcopy(backend._cfg["settings"])

        backend._pending_smart_shift_state = "freespin"
        backend._handleSmartShiftRead()

        self.assertEqual(backend._cfg["settings"], original)

    def test_linux_reports_gesture_direction_support(self):
        backend = self._make_backend()

        with patch("ui.backend.sys.platform", "linux"):
            self.assertTrue(backend.supportsGestureDirections)

    def test_known_apps_include_paths_and_refresh_signal(self):
        backend = self._make_backend()
        fake_catalog = [
            {
                "id": "code.desktop",
                "label": "Visual Studio Code",
                "path": "/usr/bin/code",
                "aliases": ["code.desktop", "Visual Studio Code"],
                "legacy_icon": "",
            }
        ]
        notifications = []
        backend.knownAppsChanged.connect(lambda: notifications.append(True))

        with (
            patch("ui.backend.app_catalog.get_app_catalog", return_value=fake_catalog),
            patch("ui.backend.get_icon_for_exe", return_value=""),
        ):
            apps = backend.knownApps
            backend.refreshKnownAppsSilently()

        self.assertEqual(apps[0]["path"], "/usr/bin/code")
        self.assertEqual(len(notifications), 1)

    def test_shortcut_capture_keeps_ctrl_and_super_distinct_on_macos(self):
        backend = self._make_backend()

        with patch("ui.backend.sys.platform", "darwin"):
            self.assertEqual(
                backend.shortcutComboFromQtEvent(
                    Qt.Key_W,
                    Qt.ControlModifier,
                    "w",
                ),
                "super+w",
            )
            self.assertEqual(
                backend.shortcutComboFromQtEvent(
                    Qt.Key_W,
                    Qt.MetaModifier,
                    "w",
                ),
                "ctrl+w",
            )

    def test_shortcut_capture_preserves_default_qt_modifier_names_off_macos(self):
        backend = self._make_backend()

        with patch("ui.backend.sys.platform", "linux"):
            self.assertEqual(
                backend.shortcutComboFromQtEvent(
                    Qt.Key_W,
                    Qt.ControlModifier,
                    "w",
                ),
                "ctrl+w",
            )
            self.assertEqual(
                backend.shortcutComboFromQtEvent(
                    Qt.Key_W,
                    Qt.MetaModifier,
                    "w",
                ),
                "super+w",
            )

    def test_shortcut_capture_accepts_qt_enum_objects(self):
        backend = self._make_backend()

        with patch("ui.backend.sys.platform", "darwin"):
            self.assertEqual(
                backend.shortcutComboFromQtEvent(
                    Qt.Key_W,
                    Qt.ControlModifier,
                    "w",
                ),
                "super+w",
            )

    def test_shortcut_capture_keeps_enter_and_escape_capturable(self):
        backend = self._make_backend()

        self.assertEqual(
            backend.shortcutComboFromQtEvent(
                Qt.Key_Return,
                Qt.NoModifier,
                "",
            ),
            "enter",
        )
        self.assertEqual(
            backend.shortcutComboFromQtEvent(
                Qt.Key_Enter,
                Qt.NoModifier,
                "",
            ),
            "enter",
        )
        self.assertEqual(
            backend.shortcutComboFromQtEvent(
                Qt.Key_Escape,
                Qt.NoModifier,
                "",
            ),
            "esc",
        )

    def test_shortcut_capture_accepts_extended_function_keys(self):
        backend = self._make_backend()

        with patch("ui.backend.sys.platform", "win32"):
            self.assertEqual(
                backend.shortcutComboFromQtEvent(
                    Qt.Key_F13,
                    Qt.NoModifier,
                    "",
                ),
                "f13",
            )
            self.assertEqual(
                backend.shortcutComboFromQtEvent(
                    Qt.Key_F24,
                    Qt.ControlModifier,
                    "",
                ),
                "ctrl+f24",
            )

    def test_shortcut_capture_accepts_shifted_symbol_text(self):
        backend = self._make_backend()

        with patch("ui.backend.sys.platform", "win32"):
            self.assertEqual(
                backend.shortcutComboFromQtEvent(
                    Qt.Key_Comma,
                    Qt.ControlModifier | Qt.ShiftModifier,
                    "<",
                ),
                "ctrl+shift+comma",
            )

    def test_capture_event_folds_in_a_swallowed_super_key(self):
        backend = self._make_backend()

        with patch("ui.backend.sys.platform", "win32"):
            # Guard idle: nothing to fold in.
            self.assertEqual(
                backend.shortcutComboFromCaptureEvent(Qt.Key_A, Qt.NoModifier, "a"),
                "a",
            )

            backend._super_key_guard = SimpleNamespace(super_held=True)
            self.assertEqual(
                backend.shortcutComboFromCaptureEvent(Qt.Key_A, Qt.NoModifier, "a"),
                "super+a",
            )
            self.assertEqual(
                backend.shortcutComboFromCaptureEvent(
                    Qt.Key_A, Qt.ShiftModifier, "A"
                ),
                "shift+super+a",
            )

    def test_capture_event_reports_held_modifiers_without_a_main_key(self):
        backend = self._make_backend()
        backend._super_key_guard = SimpleNamespace(super_held=True)

        with patch("ui.backend.sys.platform", "win32"):
            self.assertEqual(
                backend.shortcutComboFromCaptureEvent(0, Qt.ControlModifier, ""),
                "ctrl+super",
            )

    def test_capture_event_matches_qt_event_combo_when_guard_is_idle(self):
        backend = self._make_backend()

        with patch("ui.backend.sys.platform", "linux"):
            self.assertEqual(
                backend.shortcutComboFromCaptureEvent(
                    Qt.Key_W, Qt.MetaModifier, "w"
                ),
                backend.shortcutComboFromQtEvent(Qt.Key_W, Qt.MetaModifier, "w"),
            )

    def test_begin_and_end_shortcut_capture_drive_the_guard(self):
        backend = self._make_backend()
        events = []

        class _FakeGuard:
            super_held = False

            def start(self, on_super_changed=None):
                events.append("start")
                return True

            def stop(self):
                events.append("stop")

        with patch("ui.backend.create_super_key_guard", return_value=_FakeGuard()):
            self.assertTrue(backend.beginShortcutCapture())
            backend._handleSuperKeyHeld(True)
            self.assertTrue(backend.superKeyHeld)
            backend.endShortcutCapture()

        self.assertEqual(events, ["start", "stop"])
        self.assertFalse(backend.superKeyHeld)

    def test_end_shortcut_capture_is_safe_before_any_capture(self):
        backend = self._make_backend()

        backend.endShortcutCapture()  # must not raise

        self.assertFalse(backend.superKeyHeld)

    def test_shortcut_capture_survives_a_guard_that_cannot_start(self):
        backend = self._make_backend()

        class _BrokenGuard:
            super_held = False

            def start(self, on_super_changed=None):
                raise OSError("hook refused")

            def stop(self):
                raise OSError("hook refused")

        with patch("ui.backend.create_super_key_guard", return_value=_BrokenGuard()):
            self.assertFalse(backend.beginShortcutCapture())
            backend.endShortcutCapture()

        self.assertFalse(backend.superKeyHeld)

    def test_super_key_held_notifies_only_on_change(self):
        backend = self._make_backend()
        notifications = []
        backend.superKeyHeldChanged.connect(lambda: notifications.append(True))

        backend._handleSuperKeyHeld(True)
        backend._handleSuperKeyHeld(True)
        backend._handleSuperKeyHeld(False)

        self.assertEqual(len(notifications), 2)

    def test_reserved_custom_shortcut_warning_slot(self):
        backend = self._make_backend()

        self.assertTrue(backend.isReservedCustomShortcut("Win+Shift+S"))
        self.assertFalse(backend.isReservedCustomShortcut("Ctrl+Shift+P"))

    def test_custom_shortcut_validation_error_info_explains_parse_failure(self):
        backend = self._make_backend()

        self.assertEqual(backend.customShortcutValidationErrorInfo("Ctrl+Shift+P"), {})
        self.assertEqual(
            backend.customShortcutValidationErrorInfo("Ctrl+A+B"),
            {"code": "multiple_main_keys", "detail": ""},
        )
        self.assertEqual(
            backend.customShortcutValidationErrorInfo("Ctrl++"),
            {"code": "empty_segment", "detail": ""},
        )
        self.assertEqual(
            backend.customShortcutValidationErrorInfo("Ctrl+Hyperdrive"),
            {"code": "unknown_key", "detail": "Hyperdrive"},
        )

    def test_add_profile_stores_catalog_id_for_linux_app(self):
        backend = self._make_backend()
        fake_catalog = [
            {
                "id": "firefox.desktop",
                "label": "Firefox",
                "path": "/usr/bin/firefox",
                "aliases": ["firefox.desktop", "/usr/bin/firefox", "firefox"],
                "legacy_icon": "",
            }
        ]
        fake_entry = {
            "id": "firefox.desktop",
            "label": "Firefox",
            "path": "/usr/bin/firefox",
            "aliases": ["firefox.desktop", "/usr/bin/firefox", "firefox"],
            "legacy_icon": "",
        }

        with (
            patch("ui.backend.app_catalog.get_app_catalog", return_value=fake_catalog),
            patch("ui.backend.app_catalog.resolve_app_spec", return_value=fake_entry),
            patch("ui.backend.create_profile", side_effect=self._fake_create_profile),
        ):
            backend.addProfile("firefox.desktop")

        self.assertEqual(
            backend._cfg["profiles"]["firefox"]["apps"],
            ["firefox.desktop"],
        )

    def test_add_profile_rejects_linux_duplicate_when_existing_profile_uses_legacy_path(self):
        backend = self._make_backend()
        backend._cfg["profiles"]["firefox"] = {
            "label": "Firefox",
            "apps": ["/usr/bin/firefox"],
            "mappings": {},
        }
        fake_catalog = [
            {
                "id": "firefox.desktop",
                "label": "Firefox",
                "path": "/usr/bin/firefox",
                "aliases": ["firefox.desktop", "/usr/bin/firefox", "firefox"],
                "legacy_icon": "",
            }
        ]
        status_messages = []
        backend.statusMessage.connect(status_messages.append)

        def resolve_app(spec):
            if spec in ("firefox.desktop", "/usr/bin/firefox"):
                return {
                    "id": "firefox.desktop",
                    "label": "Firefox",
                    "path": "/usr/bin/firefox",
                    "aliases": ["firefox.desktop", "/usr/bin/firefox", "firefox"],
                    "legacy_icon": "",
                }
            return None

        with (
            patch("ui.backend.app_catalog.get_app_catalog", return_value=fake_catalog),
            patch("ui.backend.app_catalog.resolve_app_spec", side_effect=resolve_app),
            patch("ui.backend.create_profile") as create_profile,
        ):
            backend.addProfile("firefox.desktop")

        create_profile.assert_not_called()
        self.assertIn("Profile already exists", status_messages)


@unittest.skipIf(Backend is None, "PySide6 not installed in test environment")
class BackendLoginStartupTests(unittest.TestCase):
    def test_init_calls_sync_from_config_when_supported(self):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["settings"]["start_at_login"] = True
        with (
            patch("ui.backend.load_config", return_value=cfg),
            patch("ui.backend.save_config"),
            patch("ui.backend.supports_login_startup", return_value=True),
            patch("ui.backend.sync_login_startup_from_config") as sync_mock,
        ):
            Backend(engine=None)
        sync_mock.assert_called_once_with(True)

    def test_init_clears_start_at_login_when_sync_fails(self):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["settings"]["start_at_login"] = True
        with (
            patch("ui.backend.load_config", return_value=cfg),
            patch("ui.backend.save_config") as save_mock,
            patch("ui.backend.supports_login_startup", return_value=True),
            patch(
                "ui.backend.sync_login_startup_from_config",
                side_effect=RuntimeError("bootstrap failed"),
            ),
        ):
            backend = Backend(engine=None)

        self.assertFalse(backend.startAtLogin)
        save_mock.assert_called_once()

    def test_init_sync_failure_keeps_disabled_config_disabled(self):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["settings"]["start_at_login"] = False
        with (
            patch("ui.backend.load_config", return_value=cfg),
            patch("ui.backend.save_config") as save_mock,
            patch("ui.backend.supports_login_startup", return_value=True),
            patch(
                "ui.backend.sync_login_startup_from_config",
                side_effect=RuntimeError("bootout failed"),
            ),
        ):
            backend = Backend(engine=None)

        self.assertFalse(backend.startAtLogin)
        save_mock.assert_not_called()

    def test_init_clears_start_at_login_when_unsupported(self):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["settings"]["start_at_login"] = True
        with (
            patch("ui.backend.load_config", return_value=cfg),
            patch("ui.backend.save_config"),
            patch("ui.backend.supports_login_startup", return_value=False),
            patch("ui.backend.sync_login_startup_from_config") as sync_mock,
        ):
            backend = Backend(engine=None)
        sync_mock.assert_not_called()
        self.assertFalse(backend.startAtLogin)

    def test_set_start_at_login_calls_apply(self):
        with (
            patch("ui.backend.load_config", return_value=copy.deepcopy(DEFAULT_CONFIG)),
            patch("ui.backend.save_config"),
            patch("ui.backend.supports_login_startup", return_value=True),
            patch("ui.backend.sync_login_startup_from_config"),
            patch("ui.backend.apply_login_startup") as apply_mock,
        ):
            backend = Backend(engine=None)
            backend.setStartAtLogin(True)

        apply_mock.assert_called_once_with(True)
        self.assertTrue(backend.startAtLogin)

    def test_set_start_at_login_keeps_config_when_os_apply_fails(self):
        status_messages = []
        with (
            patch("ui.backend.load_config", return_value=copy.deepcopy(DEFAULT_CONFIG)),
            patch("ui.backend.save_config") as save_mock,
            patch("ui.backend.supports_login_startup", return_value=True),
            patch("ui.backend.sync_login_startup_from_config"),
            patch("ui.backend.apply_login_startup", side_effect=RuntimeError("denied")),
        ):
            backend = Backend(engine=None)
            backend.statusMessage.connect(status_messages.append)
            backend.setStartAtLogin(True)

        save_mock.assert_not_called()
        self.assertFalse(backend.startAtLogin)
        self.assertEqual(status_messages, ["Failed to update login item: denied"])

    def test_set_start_at_login_rolls_back_os_when_config_save_fails(self):
        status_messages = []
        with (
            patch("ui.backend.load_config", return_value=copy.deepcopy(DEFAULT_CONFIG)),
            patch("ui.backend.save_config", side_effect=RuntimeError("disk full")),
            patch("ui.backend.supports_login_startup", return_value=True),
            patch("ui.backend.sync_login_startup_from_config"),
            patch("ui.backend.apply_login_startup") as apply_mock,
        ):
            backend = Backend(engine=None)
            backend.statusMessage.connect(status_messages.append)
            backend.setStartAtLogin(True)

        self.assertEqual([c.args for c in apply_mock.call_args_list], [(True,), (False,)])
        self.assertFalse(backend.startAtLogin)
        self.assertEqual(status_messages, ["Failed to save login item setting: disk full"])

    def test_set_start_at_login_reports_inconsistent_state_when_rollback_fails(self):
        status_messages = []
        with (
            patch("ui.backend.load_config", return_value=copy.deepcopy(DEFAULT_CONFIG)),
            patch("ui.backend.save_config", side_effect=RuntimeError("disk full")),
            patch("ui.backend.supports_login_startup", return_value=True),
            patch("ui.backend.sync_login_startup_from_config"),
            patch(
                "ui.backend.apply_login_startup",
                side_effect=[None, RuntimeError("rollback failed")],
            ) as apply_mock,
        ):
            backend = Backend(engine=None)
            backend.statusMessage.connect(status_messages.append)
            backend.setStartAtLogin(True)

        self.assertEqual([c.args for c in apply_mock.call_args_list], [(True,), (False,)])
        self.assertFalse(backend.startAtLogin)
        self.assertEqual(
            status_messages,
            ["Start-at-login state is inconsistent; please restart Mouser to recover."],
        )

    def test_set_start_minimized_does_not_call_apply_login_startup(self):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["settings"]["start_at_login"] = True
        with (
            patch("ui.backend.load_config", return_value=cfg),
            patch("ui.backend.save_config"),
            patch("ui.backend.supports_login_startup", return_value=True),
            patch("ui.backend.sync_login_startup_from_config"),
            patch("ui.backend.apply_login_startup") as apply_mock,
        ):
            backend = Backend(engine=None)
            apply_mock.reset_mock()
            backend.setStartMinimized(False)

        apply_mock.assert_not_called()
        self.assertFalse(backend.startMinimized)


@unittest.skipIf(Backend is None, "PySide6 not installed in test environment")
class BackendHandleDpiReadTests(unittest.TestCase):
    """Device-reported DPI must persist to ``config.json`` so a hardware
    DPI change taken on the mouse survives the next Mouser restart, and
    must clamp into the connected device's range to defend against
    bogus reports."""

    def setUp(self) -> None:
        self._save_mock = unittest.mock.MagicMock()
        self._patches = (
            patch("ui.backend.save_config", self._save_mock),
            patch("ui.backend.supports_login_startup", return_value=False),
        )
        for p in self._patches:
            p.start()
        self.addCleanup(self._stop_patches)

    def _stop_patches(self) -> None:
        for p in self._patches:
            p.stop()

    def _build(self, *, cfg=None, engine=None):
        loaded = copy.deepcopy(cfg or DEFAULT_CONFIG)
        with patch("ui.backend.load_config", return_value=loaded):
            backend = Backend(engine=engine)
        self._save_mock.reset_mock()
        return backend

    def test_persists_new_device_dpi_to_disk(self):
        backend = self._build()
        backend._handleDpiRead(2400)
        self.assertEqual(backend._cfg["settings"]["dpi"], 2400)
        self._save_mock.assert_called_once_with(backend._cfg)

    def test_clamps_overrange_dpi_to_device_max(self):
        device = SimpleNamespace(dpi_min=200, dpi_max=4000)
        engine = _FakeEngine(device_connected=True, connected_device=device)
        backend = self._build(engine=engine)
        backend._handleDpiRead(99999)
        self.assertEqual(backend._cfg["settings"]["dpi"], 4000)
        self._save_mock.assert_called_once_with(backend._cfg)

    def test_clamps_underrange_dpi_to_device_min(self):
        device = SimpleNamespace(dpi_min=400, dpi_max=8000)
        engine = _FakeEngine(device_connected=True, connected_device=device)
        backend = self._build(engine=engine)
        backend._handleDpiRead(50)
        self.assertEqual(backend._cfg["settings"]["dpi"], 400)
        self._save_mock.assert_called_once_with(backend._cfg)

    def test_no_change_skips_save(self):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["settings"]["dpi"] = 1500
        backend = self._build(cfg=cfg)
        backend._handleDpiRead(1500)
        self._save_mock.assert_not_called()

    def test_syncs_engine_cached_config(self):
        engine = _FakeEngine(device_connected=True)
        backend = self._build(engine=engine)
        backend._handleDpiRead(1800)
        self.assertEqual(engine.cfg["settings"]["dpi"], 1800)

    def test_emits_dpi_from_device_with_clamped_value(self):
        _ensure_qapp()
        device = SimpleNamespace(dpi_min=200, dpi_max=4000)
        engine = _FakeEngine(device_connected=True, connected_device=device)
        backend = self._build(engine=engine)
        seen = []
        backend.dpiFromDevice.connect(seen.append)
        backend._handleDpiRead(9999)
        QCoreApplication.processEvents()
        self.assertEqual(seen, [4000])


@unittest.skipIf(Backend is None, "PySide6 not installed in test environment")
class BackendListPropertyMemoizationTests(unittest.TestCase):
    """The five ``@Property(list, ...)`` getters on ``Backend`` (``buttons``,
    ``profiles``, ``knownApps``, ``actionCategories``, ``allActions``) are
    read by every QML binding that depends on them, including those evaluated
    inside delegate rebuilds. Without memoization the lists -- and their
    per-entry catalog / icon lookups -- were rebuilt on every paint."""

    def _build(self, cfg=None):
        loaded = copy.deepcopy(cfg or DEFAULT_CONFIG)
        with (
            patch("ui.backend.load_config", return_value=loaded),
            patch("ui.backend.save_config"),
            patch("ui.backend.supports_login_startup", return_value=False),
        ):
            return Backend(engine=None)

    def test_buttons_returns_same_object_across_reads(self):
        backend = self._build()
        first = backend.buttons
        second = backend.buttons
        self.assertIs(first, second)

    def test_mappings_changed_invalidates_buttons_cache(self):
        backend = self._build()
        before = backend.buttons
        backend.mappingsChanged.emit()
        after = backend.buttons
        self.assertIsNot(before, after)
        self.assertEqual(before, after)

    def test_device_layout_changed_invalidates_buttons_and_actions(self):
        backend = self._build()
        buttons_before = backend.buttons
        cats_before = backend.actionCategories
        actions_before = backend.allActions
        backend.deviceLayoutChanged.emit()
        self.assertIsNot(backend.buttons, buttons_before)
        self.assertIsNot(backend.actionCategories, cats_before)
        self.assertIsNot(backend.allActions, actions_before)

    def test_active_profile_changed_invalidates_profiles_cache(self):
        backend = self._build()
        before = backend.profiles
        backend.activeProfileChanged.emit()
        self.assertIsNot(backend.profiles, before)

    def test_known_apps_changed_invalidates_known_apps_cache(self):
        backend = self._build()
        before = backend.knownApps
        backend.knownAppsChanged.emit()
        self.assertIsNot(backend.knownApps, before)

    def test_profiles_cache_not_invalidated_by_unrelated_signals(self):
        backend = self._build()
        first = backend.profiles
        backend.knownAppsChanged.emit()
        backend.mappingsChanged.emit()
        self.assertIs(backend.profiles, first)

    def test_known_apps_cache_not_invalidated_by_unrelated_signals(self):
        backend = self._build()
        first = backend.knownApps
        backend.profilesChanged.emit()
        backend.mappingsChanged.emit()
        backend.deviceLayoutChanged.emit()
        self.assertIs(backend.knownApps, first)


class BackendHoldShortcutTests(unittest.TestCase):
    def _make_backend(self):
        _ensure_qapp()
        with (
            patch("ui.backend.load_config", return_value=copy.deepcopy(DEFAULT_CONFIG)),
            patch("ui.backend.save_config"),
            patch("ui.backend.supports_login_startup", return_value=False),
        ):
            return Backend(engine=_FakeEngine())

    def test_is_hold_action_slot(self):
        backend = self._make_backend()
        self.assertTrue(backend.isHoldAction("hold:alt+grave"))
        self.assertFalse(backend.isHoldAction("custom:alt+grave"))
        self.assertFalse(backend.isHoldAction("copy"))

    def test_button_supports_hold_action_slot(self):
        backend = self._make_backend()
        self.assertTrue(backend.buttonSupportsHoldAction("actions_ring"))
        self.assertTrue(backend.buttonSupportsHoldAction("xbutton1"))
        self.assertFalse(backend.buttonSupportsHoldAction("hscroll_left"))
        self.assertFalse(backend.buttonSupportsHoldAction(""))

    def test_hold_action_label_marks_it_as_held(self):
        backend = self._make_backend()
        self.assertTrue(backend.actionLabelFor("hold:ctrl+a").endswith("(Hold)"))


    def test_fn_alone_is_accepted_by_the_shortcut_dialog_on_macos(self):
        backend = self._make_backend()
        with patch.object(sys, "platform", "darwin"):
            self.assertEqual(backend.canonicalizeCustomShortcut("fn"), "fn")
            self.assertEqual(backend.customShortcutValidationErrorInfo("fn"), {})
            self.assertEqual(backend.displayShortcutKeyName("fn"), "Fn")
        with patch.object(sys, "platform", "win32"):
            self.assertEqual(backend.canonicalizeCustomShortcut("fn"), "")
        self.assertTrue(backend.actionLabelFor("hold:fn").startswith("Fn"))

    def test_shortcut_dialog_lists_fn_as_a_typed_key(self):
        from ui.locale_manager import _TRANSLATIONS
        self.assertIn("fn/globe", _TRANSLATIONS["en"]["key_capture.valid_keys"])


class BackendDoublePressTests(unittest.TestCase):
    def _make_backend(self, mappings=None):
        _ensure_qapp()
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["profiles"]["default"]["mappings"].update(mappings or {})
        engine = _FakeEngine()
        engine.reload_mappings = unittest.mock.Mock()
        with (
            patch("ui.backend.load_config", return_value=cfg),
            patch("ui.backend.supports_login_startup", return_value=False),
        ):
            backend = Backend(engine=engine)
        return backend, engine

    def test_mode_is_saved_coerced_and_reloads_the_engine(self):
        backend, engine = self._make_backend()
        self.assertEqual(backend.doublePressMode, "instant")
        with patch("ui.backend.save_config") as save:
            backend.setDoublePressMode("wait")
            backend.setDoublePressMode("sometimes")
        self.assertEqual(backend.doublePressMode, "instant")
        self.assertEqual(save.call_count, 2)
        self.assertEqual(engine.reload_mappings.call_count, 2)

    def test_window_is_clamped_and_unchanged_values_are_not_saved(self):
        backend, _ = self._make_backend()
        with patch("ui.backend.save_config") as save:
            backend.setDoublePressWindowMs(5000)
            self.assertEqual(backend.doublePressWindowMs, backend.doublePressWindowMaxMs)
            backend.setDoublePressWindowMs(5000)
            backend.setDoublePressWindowMs(1)
        self.assertEqual(backend.doublePressWindowMs, backend.doublePressWindowMinMs)
        self.assertEqual(save.call_count, 2)

    def test_per_button_double_action_lookup(self):
        backend, _ = self._make_backend({"xbutton2_double": "hold:fn"})
        self.assertEqual(backend.doublePressActionFor("default", "xbutton2"), "hold:fn")
        self.assertEqual(backend.doublePressActionFor("default", "xbutton1"), "none")
        self.assertEqual(backend.doublePressActionFor("missing", "xbutton2"), "none")
        self.assertTrue(backend.buttonSupportsDoublePress("actions_ring"))
        self.assertFalse(backend.buttonSupportsDoublePress("hscroll_left"))
        self.assertFalse(backend.buttonSupportsDoublePress(""))

    def test_the_second_press_can_hold_a_shortcut(self):
        backend, _ = self._make_backend()
        self.assertTrue(backend.buttonSupportsHoldAction("actions_ring_double"))
        self.assertTrue(backend.buttonSupportsHoldAction("xbutton2_double"))
        self.assertFalse(backend.buttonSupportsHoldAction("hscroll_left_double"))

if __name__ == "__main__":
    unittest.main()
