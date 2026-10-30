"""
Locale Manager — provides the UI string table for the QML UI.
This fork ships English only; the lookup layer stays so QML reads every
string through one place.
Exposed to QML as the context property `lm`.
"""

from PySide6.QtCore import QObject, Property, Signal, Slot

_TRANSLATIONS = {
    "en": {
        # Navigation sidebar
        "nav.mouse_profiles": "Mouse & Profiles",
        "nav.point_scroll": "General",
        "nav.haptic_feedback": "Haptic Feedback",
        "nav.actions_ring": "Actions Ring",
        "nav.about": "About",

        # Haptic Feedback page
        "haptic.title": "Haptic Feedback",
        "haptic.subtitle": "Configure the haptic motor in your MX Master 4",
        "haptic.level": "Feedback Intensity",
        "haptic.level_desc": "Choose how strongly the haptic motor responds. Higher levels use more battery.",
        "haptic.level_subtle": "Subtle",
        "haptic.level_low": "Low",
        "haptic.level_medium": "Medium",
        "haptic.level_high": "High",
        "haptic.test_title": "Test Haptic",
        "haptic.test_desc": "Play a brief haptic pulse to preview the current intensity.",
        "haptic.test": "Test",
        "haptic.actions_title": "Haptic for Actions",
        "haptic.actions_desc": "Pick which actions fire haptic feedback. Click an action to move it between Enabled and Available.",
        "haptic.actions_enabled": "Enabled",
        "haptic.actions_available": "Available",
        "haptic.actions_empty": "No actions selected. Pick from Available.",
        "haptic.buttons_title": "Haptic per Button",
        "haptic.buttons_desc": "Choose which buttons fire haptic feedback, in addition to the action picker above.",
        "haptic.buttons_enabled": "Enabled",
        "haptic.buttons_available": "Available",
        "haptic.buttons_empty": "No buttons selected. Pick from Available.",
        "haptic.dedup_title": "Prevent Duplicate Haptics",
        "haptic.dedup_desc": "When two haptic events fire close together, play only one pulse. Disable to allow both.",
        "haptic.experimental_note": "Haptic feedback support is experimental. Some settings may not take effect until the protocol is fully documented.",

        # Actions Ring page
        "ring.title": "Actions Ring",
        "ring.subtitle": "Configure hold delay and sector actions for the radial menu",
        "ring.hold_delay": "Hold Delay",
        "ring.hold_delay_desc": "How long to hold the thumb button before the ring appears",
        "ring.slots_title": "Ring Actions",
        "ring.slots_desc": "Choose the actions available in each sector of the radial menu",
        "ring.slot_prefix": "Slot ",

        # Mouse page — profile list
        "mouse.profiles": "Profiles",
        "mouse.all_applications": "All applications",
        "mouse.add_app_profile": "Add App Profile",
        "mouse.search_installed_apps": "Search installed apps or browse for one manually",
        "mouse.delete_profile": "Delete Profile",

        # Mouse page — connection / status
        "mouse.connected": "Connected",
        "mouse.not_connected": "Not Connected",
        "mouse.waiting_for_connection": "Waiting for connection",
        "mouse.connect_mouse": "Connect your Logitech mouse",
        "mouse.connect_mouse_desc": "Mouser will detect the active device, unlock button mapping, and enable the correct layout mode as soon as the mouse is available.",
        "mouse.layout_appears_auto": "Layout mode appears automatically",
        "mouse.per_device_settings": "Per-device settings stay separate",

        # Mouse page — header subtitles
        "mouse.turn_on_mouse": "Turn on your Logitech mouse to start customizing buttons",
        "mouse.click_dot": "Click a dot to configure its action",
        "mouse.choose_layout": "Choose a layout mode below while we build a dedicated overlay",

        # Mouse page — layout mode
        "mouse.layout_mode": "Layout mode",
        "mouse.experimental_override_prefix": "Experimental override active: ",
        "mouse.experimental_override_suffix": ". Switch back to Auto-detect if the hotspot map does not line up.",
        "mouse.interactive_layout_coming": "Interactive layout coming later",
        "mouse.auto_detect": "Auto-detect",

        # Mouse page — action / mapping helpers
        "mouse.do_nothing": "Do Nothing",
        "mouse.horizontal_scroll": "Horizontal Scroll",
        "mouse.tap": "Tap: ",
        "mouse.swipes_configured": "Swipes configured",
        "mouse.installed_app": "Installed app",
        "mouse.applications": "Applications",
        "mouse.system_applications": "System Applications",
        "mouse.macos_coreservices": "macOS CoreServices",

        # Mouse page — action picker
        "mouse.choose_action_suffix": " \u2014 Choose Action",
        "mouse.configure_scroll_actions": "Configure separate actions for scroll left and right",
        "mouse.configure_gesture": "Configure tap behavior plus swipe actions for the gesture button",
        "mouse.select_button_action": "Select what happens when you use this button",
        "mouse.scroll_left": "SCROLL LEFT",
        "mouse.scroll_right": "SCROLL RIGHT",
        "mouse.tap_action": "TAP ACTION",
        "mouse.action": "Action",
        "mouse.double_press": "Double press",
        "mouse.double_press_hint": "Click, then click again to run this action. Hold the second press to keep a held shortcut such as Fn down until you let go. Mode and timing are in Settings:",
        "mouse.double_press_off": "Off",
        "mouse.double_press_mode_instant": "Instant",
        "mouse.double_press_mode_wait": "Wait",
        "scroll.double_press": "Double Press",
        "scroll.double_press_desc": "How Mouser tells a single press from a double press, for every button that has a double-press action.",
        "scroll.double_press_instant": "Instant",
        "scroll.double_press_wait": "Wait",
        "scroll.double_press_instant_desc": "The single action fires at once. A second press inside the window cancels it (an open Actions Ring closes) and runs the double action. No delay, but the single action has already run.",
        "scroll.double_press_wait_desc": "The single action waits until the window passes, so nothing fires twice. Every single click lands later by the window. Holding the first press past the window runs the single action straight away.",
        "scroll.double_press_window": "Window",
        "mouse.swipe_actions": "SWIPE ACTIONS",
        "mouse.swipe_left": "Swipe left",
        "mouse.swipe_right": "Swipe right",
        "mouse.swipe_up": "Swipe up",
        "mouse.swipe_down": "Swipe down",
        "mouse.threshold": "Threshold",
        "mouse.haptic_feedback": "Haptic",

        # Mouse page — debug panel
        "mouse.debug_events": "Debug Events",
        "mouse.debug_events_desc": "Collects detected buttons, gestures, and mapped actions",
        "mouse.clear": "Clear",
        "mouse.clear_rec": "Clear Rec",
        "mouse.on": "On",
        "mouse.off": "Off",
        "mouse.rec": "Rec",
        "mouse.record": "Record",
        "mouse.live_gesture_monitor": "Live Gesture Monitor",
        "mouse.held": "Held",
        "mouse.idle": "Idle",
        "mouse.move_seen": "Move Seen",
        "mouse.no_move": "No Move",
        "mouse.debug_placeholder": "Turn on debug mode, then press buttons or use the gesture button.",
        "mouse.gesture_placeholder": "Turn on Record and perform a few gesture attempts.",

        # Mouse page — add app dialog
        "mouse.add_app_dialog.title": "Add App Profile",
        "mouse.add_app_dialog.desc": "Choose an app. Mouser will switch to this profile when that app is focused.",
        "mouse.search_placeholder": "Search apps by name",
        "mouse.browse": "Browse",
        "mouse.search_results": "Search Results",
        "mouse.suggested_apps": "Suggested Apps",
        "mouse.no_matched": "No apps matched that search.",
        "mouse.no_suggested": "No suggested apps available.",
        "mouse.try_different": "Try a different name, or use Browse to choose the app directly.",
        "mouse.use_search": "Use the search box above, or browse to choose an app directly.",
        "mouse.create_profile": "Create Profile",
        "mouse.cancel": "Cancel",

        # Mouse page — delete dialog
        "mouse.delete_dialog.title": "Delete profile?",
        "mouse.delete_dialog.confirm_prefix": "Delete the profile for ",
        "mouse.delete_dialog.confirm_suffix": "?",
        "mouse.delete_dialog.desc": "This removes its custom button mappings. The default profile will remain.",

        # Scroll / Settings page
        "scroll.title": "General Settings",
        "scroll.subtitle": "Adjust app preferences, pointer speed, screenshots, and scroll behaviour",
        "scroll.pointer_speed": "Pointer Speed (DPI)",
        "scroll.pointer_speed_desc": "Adjust the tracking speed of the sensor. Higher = faster pointer.",
        "scroll.pointer_speed_desc_range_prefix": "Adjust the tracking speed of the sensor. This device supports ",
        "scroll.pointer_speed_desc_range_to": " to ",
        "scroll.pointer_speed_desc_range_suffix": " DPI.",
        "scroll.presets": "Presets:",
        "scroll.wheel_mode": "Scroll Wheel Mode",
        "scroll.wheel_mode_desc": "Switch between tactile ratchet scrolling and smooth free-spin.",
        "scroll.ratchet": "Ratchet",
        "scroll.freespin": "Free Spin",
        "scroll.smart_shift": "SmartShift",
        "scroll.smart_shift_desc": "Automatically switches the scroll wheel from line-by-line scrolling to hyper-fast scrolling when you scroll faster.",
        "scroll.sensitivity_value": "SENSITIVITY VALUE",
        "scroll.scroll_mode_section": "SCROLL MODE",
        "scroll.scroll_force": "Scroll Force",
        "scroll.scroll_force_desc": "Adjust the ratchet firmness of the scroll wheel. Lower = smooth and subtle, higher = firm and precise.",
        "scroll.scroll_force_value": "FORCE",
        "scroll.appearance": "Appearance",
        "scroll.appearance_desc": "Choose whether Mouser follows the system, stays light, or stays dark.",
        "scroll.system": "System",
        "scroll.light": "Light",
        "scroll.dark": "Dark",
        "scroll.startup": "Startup",
        "scroll.startup_desc": "Start Mouser at login on supported desktop platforms, and choose whether the settings window opens on launch or Mouser stays in the system tray.",
        "scroll.start_at_login": "Start at login",
        "scroll.start_minimized": "Start minimized",
        "scroll.screenshots": "Screenshots",
        "scroll.screenshots_desc": "Choose where Mouser saves screenshot file actions. Clipboard actions are unaffected.",
        "scroll.screenshots_save_to": "Save to",
        "scroll.screenshots_choose": "Choose...",
        "scroll.screenshots_default": "Use Default",
        "scroll.screenshots_system_default": "System default location",
        "scroll.scroll_speed": "Scroll Speed",
        "scroll.scroll_speed_desc": "Adjust how fast the page scrolls per wheel click. 1.0\u00d7 is the system default.",
        "scroll.scroll_speed_presets": "Presets:",
        "scroll.smooth_scroll": "Smooth Scrolling",
        "scroll.smooth_scroll_desc": "Add inertia so the page coasts to a stop after each wheel tick for a smoother feel.",
        "scroll.scroll_direction": "Scroll Direction",
        "scroll.scroll_direction_desc": "Invert the scroll direction (natural scrolling)",
        "scroll.invert_vertical": "Invert vertical scroll",
        "scroll.invert_horizontal": "Invert horizontal scroll",
        "scroll.ignore_trackpad": "Ignore trackpad",
        "scroll.ignore_trackpad_desc": "Only respond to mouse events, not trackpad or Magic Mouse",
        "scroll.dpi_note": "DPI changes require HID++ communication with the device and will take effect after a short delay.",

        # Key-capture dialog
        "key_capture.title": "Custom Shortcut",
        "key_capture.placeholder": "e.g. super+shift+f5",
        "key_capture.placeholder_recording": "Press your shortcut\u2026",
        "key_capture.record_hint": "Press the keys you want. Modifier keys such as Win are captured here instead of reaching the system.",
        "key_capture.type_hint": "Type the shortcut with + between keys, e.g. super+shift+f5.",
        "key_capture.mode_type": "Type instead",
        "key_capture.mode_record": "Record keys",
        "key_capture.valid_keys": "Valid keys: ctrl/control, shift, alt/option/opt, super (aliases: cmd, command, meta, win, windows), fn/globe (macOS, works alone; type it, it cannot be recorded),\n0\u20139, a\u2013z, f1\u2013f24, space, tab, enter, esc, left, right, up, down, delete, ...",
        "key_capture.reserved_warning": "The operating system may intercept this shortcut. It can still be saved, but behavior may vary by system.",
        "key_capture.error.unsupported_key": "Choose a different key. %1 isn't available in Mouser.",
        "key_capture.error.unknown_key": "We don't recognize: %1.",
        "key_capture.error.duplicate_key": "Remove the duplicate key.",
        "key_capture.error.multiple_main_keys": "Use one key with optional Ctrl, Shift, Alt, or Super.",
        "key_capture.error.missing_main_key": "Add a key, such as A, F5, or Page Down.",
        "key_capture.error.empty_segment": "Use + only between keys. Type plus for the + key.",
        "key_capture.error.unsupported": "Shortcut is not supported.",
        "key_capture.cancel": "Cancel",
        "key_capture.confirm": "Confirm",
        "key_capture.hold_label": "Hold while the button is pressed",
        "key_capture.hold_hint": "Keeps the keys down until you release the mouse button, for push-to-talk style shortcuts.",

        # System tray (used from Python)
        "tray.open_settings": "Open Settings",
        "tray.disable_remapping": "Disable Remapping",
        "tray.enable_remapping": "Enable Remapping",
        "tray.enable_debug": "Enable Debug Mode",
        "tray.disable_debug": "Disable Debug Mode",
        "tray.quit": "Quit Mouser",
        "tray.tray_message": "Mouser is running in the system tray. Click the icon to open settings.",

        # Accessibility dialog (macOS)
        "accessibility.title": "Accessibility Permission Required",
        "accessibility.text": (
            "Mouser needs Accessibility permission to intercept "
            "mouse button events.\n\n"
            "macOS should have opened the System Settings prompt.\n"
            "Please grant permission, then restart Mouser."
        ),
        "accessibility.info": "System Settings -> Privacy & Security -> Accessibility",

        # Common dialog chrome
        "dialog.close": "Close",

        # About dialog
        "about.title": "About Mouser",
        "about.subtitle": "Runtime and build details for support and debugging.",
        "about.version": "Version",
        "about.build_mode": "Build mode",
        "about.commit": "Commit",
        "about.launch_path": "Launch path",
        "about.close": "Close",
        "about.ratmode_title": "What RatMode changes",
        "about.ratmode_1": "No network: the release check, auto-updater and every HTTP or socket path are removed. The app never connects anywhere.",
        "about.ratmode_2": "Hold shortcuts: a custom shortcut can stay pressed for as long as the button is held (long press) instead of a momentary tap. The MX Master 4 Sense Panel uses this for Wispr Flow push-to-talk.",
        "about.ratmode_3": "English only: the Chinese locales, README and language switcher are gone.",
        "about.ratmode_4": "Apple look: Human Interface Guidelines colors (macOS selection blue, HIG neutrals) and the system font.",
        "about.ratmode_5": "Built from source only, with hash-pinned and audited dependencies; no release binaries.",
        "about.ratmode_7": "Double press on every button: a second action for click-then-click (or click-then-hold, e.g. Sense Panel click opens the Actions Ring, click and hold holds Fn), in instant or wait mode with a configurable window.",
        "about.ratmode_6": "Configuration as code: the recommended MX Master 4 setup ships in configs/mx4-ratmode.json.",

        # Language names
    },

    # ── Simplified Chinese ────────────────────────────────────────

    # ── Traditional Chinese ───────────────────────────────────────
}

AVAILABLE_LANGUAGES = [
    {"code": "en", "name": "English"},
]

# ── Button name translations ──────────────────────────────────────────────────
# Key = English name from config.py BUTTON_NAMES / PROFILE_BUTTON_NAMES
_BUTTON_TR: dict[str, dict[str, str]] = {
}

# ── Action category translations ──────────────────────────────────────────────
_CATEGORY_TR: dict[str, dict[str, str]] = {
}

# ── Action label translations ─────────────────────────────────────────────────
# Key = exact English label returned by key_simulator.py / backend.
# Key combos in parentheses are preserved verbatim in the translated string.
_ACTION_TR: dict[str, dict[str, str]] = {
}


class LocaleManager(QObject):
    """Manages the active UI language and exposes translations to QML."""

    languageChanged = Signal()

    def __init__(self, language: str = "en", parent=None):
        super().__init__(parent)
        lang = language if language in _TRANSLATIONS else "en"
        self._language = lang
        self._strings: dict = dict(_TRANSLATIONS[lang])

    # ── language property ─────────────────────────────────────────
    @Property(str, notify=languageChanged)
    def language(self) -> str:
        return self._language

    @Slot(str)
    def setLanguage(self, lang: str) -> None:
        if lang == self._language:
            return
        if lang not in _TRANSLATIONS:
            return
        self._language = lang
        self._strings = dict(_TRANSLATIONS[lang])
        self.languageChanged.emit()

    # ── strings map (QVariantMap) ─────────────────────────────────
    @Property("QVariantMap", notify=languageChanged)
    def strings(self) -> dict:
        """Return the full translation dictionary for the active language."""
        return self._strings

    # ── helper slot usable from Python ───────────────────────────
    @Slot(str, result=str)
    def tr(self, key: str) -> str:
        return self._strings.get(key, key)

    # ── button / action / category translation slots for QML ─────
    @Slot(str, result=str)
    def trButton(self, english_name: str) -> str:
        """Translate a button name for the active language."""
        return _BUTTON_TR.get(self._language, {}).get(english_name, english_name)

    @Slot(str, result=str)
    def trAction(self, english_label: str) -> str:
        """Translate an action label for the active language."""
        return _ACTION_TR.get(self._language, {}).get(english_label, english_label)

    @Slot(str, result=str)
    def trCategory(self, english_cat: str) -> str:
        """Translate an action category for the active language."""
        return _CATEGORY_TR.get(self._language, {}).get(english_cat, english_cat)

    # ── available languages list ──────────────────────────────────
    @Property(list, constant=True)
    def availableLanguages(self) -> list:
        return AVAILABLE_LANGUAGES
