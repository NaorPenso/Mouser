import copy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.config import DEFAULT_CONFIG
from core.mouse_hook import MouseEvent
from core.mouse_hook_types import HidRuntimeState


class _FakeMouseHook:
    def __init__(self):
        self.invert_vscroll = False
        self.invert_hscroll = False
        self.debug_mode = False
        self.connected_device = None
        self.device_connected = False
        self._hid_gesture = None
        self.start_called = False
        self.stop_called = False
        self.wheel_native_invert_active = False
        # Back-compat alias mirrored on the real BaseMouseHook for callers
        # from the divert+inject build of the test fixtures.
        self.wheel_divert_active = False

    def set_debug_callback(self, cb):
        self._debug_callback = cb

    def set_gesture_callback(self, cb):
        self._gesture_callback = cb

    def set_status_callback(self, cb):
        self._status_callback = cb

    def set_connection_change_callback(self, cb):
        self._connection_change_callback = cb

    def set_battery_notify_callback(self, cb):
        self._battery_notify_callback = cb

    def configure_gestures(self, **kwargs):
        self._gesture_config = kwargs

    def configure_wheel_multipliers(self, vertical, horizontal):
        # Retained for shape compatibility; real BaseMouseHook accepts but
        # no-ops the call in native-invert mode.
        return None

    def block(self, event_type):
        pass

    def register(self, event_type, callback):
        pass

    def reset_bindings(self):
        pass

    def start(self):
        self.start_called = True

    def stop(self):
        self.stop_called = True


class _FakeAppDetector:
    def __init__(self, callback):
        self.callback = callback
        self.start_called = False
        self.stop_called = False

    def start(self):
        self.start_called = True

    def stop(self):
        self.stop_called = True


class _ImmediateThread:
    def __init__(self, target=None, args=(), kwargs=None, **_):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        if self._target:
            self._target(*self._args, **self._kwargs)


class _RecordedThread:
    def __init__(self, target=None, args=(), kwargs=None, name=None, **_):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}
        self.name = name
        self.start_called = False
        self.join = Mock()

    def start(self):
        self.start_called = True

    def run_target(self):
        if self._target:
            return self._target(*self._args, **self._kwargs)
        return None


class EngineHorizontalScrollTests(unittest.TestCase):
    def _make_engine(self, hscroll_threshold=1):
        from core.engine import Engine

        cfg = copy.deepcopy(DEFAULT_CONFIG)
        if hscroll_threshold is not None:
            cfg["settings"]["hscroll_threshold"] = hscroll_threshold

        with (
            patch("core.engine.MouseHook", _FakeMouseHook),
            patch("core.engine.AppDetector", _FakeAppDetector),
            patch("core.engine.load_config", return_value=cfg),
        ):
            return Engine()

    def test_hscroll_desktop_action_uses_cooldown(self):
        engine = self._make_engine()
        handler = engine._make_hscroll_handler("space_left")

        with patch("core.engine.execute_action") as execute_action_mock:
            handler(SimpleNamespace(
                event_type=MouseEvent.HSCROLL_LEFT,
                raw_data=1,
                timestamp=1.00,
            ))
            handler(SimpleNamespace(
                event_type=MouseEvent.HSCROLL_LEFT,
                raw_data=1,
                timestamp=1.05,
            ))
            handler(SimpleNamespace(
                event_type=MouseEvent.HSCROLL_LEFT,
                raw_data=1,
                timestamp=1.45,
            ))

        self.assertEqual(execute_action_mock.call_count, 2)

    def test_hscroll_accumulates_fractional_mac_deltas(self):
        engine = self._make_engine()
        handler = engine._make_hscroll_handler("space_right")

        with patch("core.engine.execute_action") as execute_action_mock:
            handler(SimpleNamespace(
                event_type=MouseEvent.HSCROLL_RIGHT,
                raw_data=0.35,
                timestamp=2.00,
            ))
            handler(SimpleNamespace(
                event_type=MouseEvent.HSCROLL_RIGHT,
                raw_data=0.40,
                timestamp=2.02,
            ))
            handler(SimpleNamespace(
                event_type=MouseEvent.HSCROLL_RIGHT,
                raw_data=0.30,
                timestamp=2.04,
            ))

        self.assertEqual(execute_action_mock.call_count, 1)

    def test_default_hscroll_threshold_handles_m720_fractional_delta(self):
        engine = self._make_engine(hscroll_threshold=None)
        handler = engine._make_hscroll_handler("space_right")

        with patch("core.engine.execute_action") as execute_action_mock:
            handler(SimpleNamespace(
                event_type=MouseEvent.HSCROLL_RIGHT,
                raw_data=0.100006103515625,
                timestamp=3.00,
            ))

        self.assertEqual(execute_action_mock.call_count, 1)

    def test_connection_callback_receives_current_state_immediately(self):
        engine = self._make_engine()
        engine.hook.device_connected = True

        seen = []
        engine.set_connection_change_callback(seen.append)

        self.assertEqual(seen, [True])

    def test_connection_callback_prefers_device_connected_flag_over_stale_identity(self):
        engine = self._make_engine()
        engine.hook.device_connected = False
        engine.hook.connected_device = SimpleNamespace(name="MX Master 3S")

        seen = []
        engine.set_connection_change_callback(seen.append)

        self.assertEqual(seen, [False])

    def test_hid_features_ready_requires_hid_identity(self):
        engine = self._make_engine()

        self.assertFalse(engine.hid_features_ready)

        engine.hook._hid_gesture = SimpleNamespace(connected_device=None)
        self.assertFalse(engine.hid_features_ready)

        engine.hook._hid_gesture = SimpleNamespace(
            connected_device=SimpleNamespace(name="MX Master 3S")
        )
        self.assertTrue(engine.hid_features_ready)

    def test_engine_projection_prefers_hid_runtime_state(self):
        engine = self._make_engine()
        device = SimpleNamespace(name="MX Master 3S")
        engine.hook.device_connected = False
        engine.hook.connected_device = SimpleNamespace(name="stale fallback")
        engine.hook._hid_gesture = None
        engine.hook.hid_runtime_state = HidRuntimeState(
            input_ready=True,
            hid_ready=True,
            connected_device=device,
        )

        seen = []
        engine.set_connection_change_callback(seen.append)

        self.assertTrue(engine.device_connected)
        self.assertIs(engine.connected_device, device)
        self.assertTrue(engine.hid_features_ready)
        self.assertEqual(seen, [True])

    def test_duplicate_connected_refresh_does_not_restart_battery_poller(self):
        engine = self._make_engine()
        seen = []
        engine.set_connection_change_callback(seen.append)
        engine.hook._hid_gesture = SimpleNamespace(connected_device=None)
        thread_instances = []

        def fake_thread(*args, **kwargs):
            thread = _RecordedThread(*args, **kwargs)
            thread_instances.append(thread)
            return thread

        with patch("core.engine.threading.Thread", side_effect=fake_thread):
            engine._on_connection_change(True)
            battery_threads = [
                thread for thread in thread_instances if thread.name == "BatteryPoll"
            ]
            self.assertEqual(len(battery_threads), 1)
            first_thread = battery_threads[0]

            engine.hook._hid_gesture = SimpleNamespace(
                connected_device=SimpleNamespace(name="MX Master 3S")
            )
            engine._on_connection_change(True)

        self.assertEqual(seen, [False, True, True])
        battery_threads = [
            thread for thread in thread_instances if thread.name == "BatteryPoll"
        ]
        self.assertEqual(len(battery_threads), 1)
        first_thread.join.assert_not_called()
        self.assertIs(engine._battery_poll_thread, first_thread)

    def test_start_applies_saved_dpi_without_reading_device_dpi(self):
        engine = self._make_engine()
        engine.hook._hid_gesture = SimpleNamespace(
            connected_device=SimpleNamespace(name="MX Master 3S"),
            set_dpi=Mock(return_value=True),
            read_dpi=Mock(),
            smart_shift_supported=False,
        )
        seen = []
        engine.set_dpi_read_callback(seen.append)

        with (
            patch("core.engine.threading.Thread", _ImmediateThread),
            patch("time.sleep", return_value=None),
        ):
            engine.start()

        expected = engine.cfg["settings"]["dpi"]
        engine.hook._hid_gesture.set_dpi.assert_called_once_with(expected)
        engine.hook._hid_gesture.read_dpi.assert_not_called()
        self.assertEqual(seen, [expected])
        self.assertTrue(engine.hook.start_called)
        self.assertTrue(engine._app_detector.start_called)


class EngineDesktopCycleTests(unittest.TestCase):
    def _make_engine(self):
        from core.engine import Engine

        cfg = copy.deepcopy(DEFAULT_CONFIG)
        with (
            patch("core.engine.MouseHook", _FakeMouseHook),
            patch("core.engine.AppDetector", _FakeAppDetector),
            patch("core.engine.load_config", return_value=cfg),
        ):
            return Engine()

    def test_cycle_desktops_refreshes_display_after_cursor_moves(self):
        engine = self._make_engine()
        desktop_info = Mock(side_effect=[(1, 1), (2, 1)])

        with (
            patch("core.engine.sys.platform", "darwin"),
            patch.object(engine, "_get_macos_desktop_info", desktop_info),
            patch("core.engine.execute_action") as execute_action_mock,
        ):
            engine._cycle_desktops()  # Secondary display: one desktop, skip.
            engine._cycle_desktops()  # Main display: refresh and switch.

        self.assertEqual(desktop_info.call_count, 2)
        execute_action_mock.assert_called_once_with("space_right")


class EngineReplayPhaseOneTests(unittest.TestCase):
    def _make_engine(self):
        from core.engine import Engine

        cfg = copy.deepcopy(DEFAULT_CONFIG)

        with (
            patch("core.engine.MouseHook", _FakeMouseHook),
            patch("core.engine.AppDetector", _FakeAppDetector),
            patch("core.engine.load_config", return_value=cfg),
        ):
            return Engine()

    @staticmethod
    def _thread_factory(instances):
        def factory(*args, **kwargs):
            thread = _RecordedThread(*args, **kwargs)
            instances.append(thread)
            return thread

        return factory

    @staticmethod
    def _non_battery_threads(instances):
        return [thread for thread in instances if thread.name != "BatteryPoll"]

    def _make_hid(self, *, connected_device=None, dpi_result=True, smart_shift_result=True):
        return SimpleNamespace(
            connected_device=connected_device,
            read_battery=Mock(return_value=None),
            set_dpi=Mock(return_value=dpi_result),
            set_smart_shift=Mock(return_value=smart_shift_result),
            smart_shift_supported=True,
        )

    def test_hid_ready_transition_requests_replay_worker(self):
        engine = self._make_engine()
        engine.hook._hid_gesture = self._make_hid(connected_device=None)
        threads = []

        with patch("core.engine.threading.Thread", side_effect=self._thread_factory(threads)):
            engine._on_connection_change(True)
            self.assertEqual(len(threads), 1)
            self.assertEqual(self._non_battery_threads(threads), [])
            engine.hook._hid_gesture.set_dpi.assert_not_called()
            engine.hook._hid_gesture.set_smart_shift.assert_not_called()

            engine.hook._hid_gesture.connected_device = SimpleNamespace(name="MX Master 3S")
            engine._on_connection_change(True)

        expected_dpi = engine.cfg["settings"]["dpi"]
        expected_ss_mode = engine.cfg["settings"]["smart_shift_mode"]
        expected_ss_enabled = engine.cfg["settings"]["smart_shift_enabled"]
        expected_ss_threshold = engine.cfg["settings"]["smart_shift_threshold"]
        expected_ss_scroll_force = engine.cfg["settings"]["scroll_force"]
        replay_threads = self._non_battery_threads(threads)
        self.assertEqual(len(replay_threads), 1)
        replay_threads[0].run_target()
        engine.hook._hid_gesture.set_dpi.assert_called_once_with(expected_dpi)
        self.assertEqual(engine.hook._hid_gesture.set_smart_shift.call_count, 2)
        engine.hook._hid_gesture.set_smart_shift.assert_called_with(
            expected_ss_mode, expected_ss_enabled, expected_ss_threshold, expected_ss_scroll_force
        )

    def test_live_reconnect_replay_restores_saved_values_through_worker(self):
        engine = self._make_engine()
        engine.hook._hid_gesture = self._make_hid(connected_device=None)
        threads = []
        seen_dpi = []
        seen_smart_shift = []
        engine.set_dpi_read_callback(seen_dpi.append)
        engine.set_smart_shift_read_callback(seen_smart_shift.append)

        with patch("core.engine.threading.Thread", side_effect=self._thread_factory(threads)):
            engine._on_connection_change(True)
            engine.hook._hid_gesture.connected_device = SimpleNamespace(name="MX Master 3S")
            engine._on_connection_change(True)

        replay_threads = self._non_battery_threads(threads)
        self.assertEqual(len(replay_threads), 1)
        replay_threads[0].run_target()

        self.assertEqual(seen_dpi, [engine.cfg["settings"]["dpi"]])
        self.assertGreaterEqual(len(seen_smart_shift), 2)
        self.assertEqual(
            seen_smart_shift[-1],
            {
                "mode": engine.cfg["settings"]["smart_shift_mode"],
                "enabled": engine.cfg["settings"]["smart_shift_enabled"],
                "threshold": engine.cfg["settings"]["smart_shift_threshold"],
                "scroll_force": engine.cfg["settings"]["scroll_force"],
            },
        )

    def test_evdev_only_connected_true_does_not_request_replay_worker(self):
        engine = self._make_engine()
        engine.hook.connected_device = SimpleNamespace(name="MX Master 3S", source="evdev")
        engine.hook._hid_gesture = self._make_hid(connected_device=None)
        threads = []

        with patch("core.engine.threading.Thread", side_effect=self._thread_factory(threads)):
            engine._on_connection_change(True)
            engine._on_connection_change(True)

        self.assertEqual(len(threads), 1)
        self.assertEqual(self._non_battery_threads(threads), [])
        engine.hook._hid_gesture.set_dpi.assert_not_called()
        engine.hook._hid_gesture.set_smart_shift.assert_not_called()

    def test_duplicate_same_value_refresh_does_not_create_duplicate_replay_workers(self):
        engine = self._make_engine()
        engine.hook._hid_gesture = self._make_hid(connected_device=None)
        threads = []

        with patch("core.engine.threading.Thread", side_effect=self._thread_factory(threads)):
            engine._on_connection_change(True)

            engine.hook._hid_gesture.connected_device = SimpleNamespace(name="MX Master 3S")
            engine._on_connection_change(True)
            first_replay_threads = list(self._non_battery_threads(threads))

            engine._on_connection_change(True)

        self.assertEqual(len(first_replay_threads), 1)
        self.assertEqual(self._non_battery_threads(threads), first_replay_threads)

    def test_hid_disconnect_while_evdev_connected_allows_next_hid_replay(self):
        engine = self._make_engine()
        engine.hook.connected_device = SimpleNamespace(name="MX Master 3S", source="evdev")
        engine.hook._hid_gesture = self._make_hid(
            connected_device=SimpleNamespace(name="MX Master 3S")
        )
        threads = []

        with patch("core.engine.threading.Thread", side_effect=self._thread_factory(threads)):
            engine._on_connection_change(True)
            self.assertEqual(len(self._non_battery_threads(threads)), 1)
            self._non_battery_threads(threads)[0].run_target()

            engine.hook._hid_gesture.connected_device = None
            engine._on_connection_change(True)
            self.assertEqual(len(self._non_battery_threads(threads)), 1)

            engine.hook._hid_gesture.connected_device = SimpleNamespace(name="MX Master 3S")
            engine._on_connection_change(True)

        self.assertEqual(len(self._non_battery_threads(threads)), 2)

    def test_hid_disconnect_updates_last_hid_ready_without_connection_edge(self):
        engine = self._make_engine()
        engine.hook.connected_device = SimpleNamespace(name="MX Master 3S", source="evdev")
        engine.hook._hid_gesture = self._make_hid(
            connected_device=SimpleNamespace(name="MX Master 3S")
        )

        with patch("core.engine.threading.Thread", side_effect=self._thread_factory([])):
            engine._on_connection_change(True)
        self.assertTrue(engine._last_hid_features_ready)

        engine.hook._hid_gesture.connected_device = None
        engine._on_connection_change(True)

        self.assertFalse(engine._last_hid_features_ready)

    def test_startup_fallback_does_not_queue_replay_after_hid_ready_replay_requested(self):
        engine = self._make_engine()
        engine.hook._hid_gesture = self._make_hid(connected_device=None)
        threads = []

        with (
            patch("core.engine.threading.Thread", side_effect=self._thread_factory(threads)),
            patch("core.engine.time.sleep", return_value=None),
        ):
            engine.start()
            startup_threads = list(self._non_battery_threads(threads))
            self.assertEqual(len(startup_threads), 1)

            engine._on_connection_change(True)
            engine.hook._hid_gesture.connected_device = SimpleNamespace(name="MX Master 3S")
            engine._on_connection_change(True)

        non_battery_before_fallback = list(self._non_battery_threads(threads))
        self.assertEqual(len(non_battery_before_fallback), 2)
        replay_threads = [
            thread for thread in non_battery_before_fallback
            if thread not in startup_threads
        ]
        self.assertEqual(len(replay_threads), 1)
        replay_threads[0].run_target()

        self.assertEqual(engine.hook._hid_gesture.set_dpi.call_count, 1)
        self.assertEqual(engine.hook._hid_gesture.set_smart_shift.call_count, 2)

        startup_threads[0].run_target()

        expected_dpi = engine.cfg["settings"]["dpi"]
        expected_ss_mode = engine.cfg["settings"]["smart_shift_mode"]
        expected_ss_enabled = engine.cfg["settings"]["smart_shift_enabled"]
        expected_ss_threshold = engine.cfg["settings"]["smart_shift_threshold"]
        expected_ss_scroll_force = engine.cfg["settings"]["scroll_force"]
        engine.hook._hid_gesture.set_dpi.assert_called_once_with(expected_dpi)
        self.assertEqual(engine.hook._hid_gesture.set_smart_shift.call_count, 2)
        engine.hook._hid_gesture.set_smart_shift.assert_called_with(
            expected_ss_mode, expected_ss_enabled, expected_ss_threshold, expected_ss_scroll_force
        )

    def test_replay_failure_emits_engine_status_callback(self):
        engine = self._make_engine()
        status_messages = []
        engine.set_status_callback(status_messages.append)
        engine.hook._hid_gesture = self._make_hid(
            connected_device=None,
            dpi_result=False,
            smart_shift_result=True,
        )
        threads = []

        with patch("core.engine.threading.Thread", side_effect=self._thread_factory(threads)):
            engine._on_connection_change(True)
            engine.hook._hid_gesture.connected_device = SimpleNamespace(name="MX Master 3S")
            engine._on_connection_change(True)

        replay_threads = self._non_battery_threads(threads)
        self.assertEqual(len(replay_threads), 1)
        replay_threads[0].run_target()

        self.assertTrue(status_messages)
        self.assertTrue(
            any(
                "could not be restored" in message.lower()
                for message in status_messages
            ),
            status_messages,
        )

    def test_battery_poll_skips_smart_shift_reads_while_replay_is_inflight(self):
        engine = self._make_engine()
        engine.set_frontend_visible(True)
        stop_event = Mock()
        stop_event.is_set.return_value = False
        stop_event.wait.return_value = True
        engine._replay_inflight = True
        engine.hook._hid_gesture = SimpleNamespace(
            connected_device=SimpleNamespace(name="MX Master 3S"),
            smart_shift_supported=True,
            read_battery=Mock(return_value=None),
            read_smart_shift=Mock(return_value={"mode": "ratchet", "enabled": False, "threshold": 25}),
        )

        # Pin an active user: on macOS the real idle time gates background
        # reads, so an idle machine skipped the battery read and failed here.
        with patch("core.engine._system_idle_seconds", return_value=0.0):
            engine._battery_poll_loop(stop_event)

        engine.hook._hid_gesture.read_battery.assert_called_once_with()
        engine.hook._hid_gesture.read_smart_shift.assert_not_called()

    def test_battery_poll_skips_background_hid_reads_while_frontend_hidden(self):
        engine = self._make_engine()
        stop_event = Mock()
        stop_event.is_set.return_value = False
        stop_event.wait.return_value = True
        engine.hook._hid_gesture = SimpleNamespace(
            connected_device=SimpleNamespace(name="MX Master 3S"),
            smart_shift_supported=True,
            read_battery=Mock(return_value=None),
            read_smart_shift=Mock(return_value={
                "mode": "ratchet",
                "enabled": False,
                "threshold": 25,
            }),
        )

        engine._battery_poll_loop(stop_event)

        engine.hook._hid_gesture.read_battery.assert_not_called()
        engine.hook._hid_gesture.read_smart_shift.assert_not_called()

    def test_battery_poll_skips_background_hid_reads_while_system_idle(self):
        engine = self._make_engine()
        engine.set_frontend_visible(True)
        stop_event = Mock()
        stop_event.is_set.return_value = False
        stop_event.wait.return_value = True
        engine.hook._hid_gesture = SimpleNamespace(
            connected_device=SimpleNamespace(name="MX Master 3S"),
            smart_shift_supported=True,
            read_battery=Mock(return_value=None),
            read_smart_shift=Mock(return_value={
                "mode": "ratchet",
                "enabled": False,
                "threshold": 25,
            }),
        )

        with patch("core.engine._system_idle_seconds", return_value=120.0):
            engine._battery_poll_loop(stop_event)

        engine.hook._hid_gesture.read_battery.assert_not_called()
        engine.hook._hid_gesture.read_smart_shift.assert_not_called()

    def test_battery_poll_does_not_repeat_without_user_activity_after_poll(self):
        engine = self._make_engine()
        engine.set_frontend_visible(True)
        stop_event = Mock()
        stop_event.is_set.return_value = False
        stop_event.wait.side_effect = [False, False, True]
        engine.hook._hid_gesture = SimpleNamespace(
            connected_device=SimpleNamespace(name="MX Master 3S"),
            smart_shift_supported=True,
            read_battery=Mock(return_value=None),
            read_smart_shift=Mock(return_value=None),
        )

        with (
            patch("core.engine.time.time", side_effect=[
                0.0, 0.0, 0.0, 5.0, 300.0, 300.0,
            ]),
            patch("core.engine._system_idle_seconds", side_effect=[
                0.0, 0.0, 300.0,
            ]),
        ):
            engine._battery_poll_loop(stop_event)

        engine.hook._hid_gesture.read_battery.assert_called_once_with()
        engine.hook._hid_gesture.read_smart_shift.assert_called_once_with()


class WheelInvertConnectThreadingTests(unittest.TestCase):
    """The native wheel-invert write blocks until the HID listener thread
    services the queued request from its own main loop. Because the connect
    callback runs ON that listener thread, doing the write inline deadlocks
    until the request times out. It must be deferred to a worker instead.
    """

    def _make_engine(self):
        from core.engine import Engine

        cfg = copy.deepcopy(DEFAULT_CONFIG)
        with (
            patch("core.engine.MouseHook", _FakeMouseHook),
            patch("core.engine.AppDetector", _FakeAppDetector),
            patch("core.engine.load_config", return_value=cfg),
        ):
            return Engine()

    def test_setup_hooks_defers_wheel_invert_when_requested(self):
        engine = self._make_engine()
        with patch.object(engine, "_apply_wheel_invert_setting") as apply_mock:
            engine._setup_hooks(defer_wheel_invert=True)
            apply_mock.assert_not_called()
            engine._setup_hooks()
            apply_mock.assert_called_once_with()

    def test_connect_defers_wheel_invert_off_listener_thread(self):
        engine = self._make_engine()
        engine.cfg["settings"]["invert_vscroll"] = True
        device = SimpleNamespace(
            name="MX Master 4",
            has_hires_wheel=True,
            has_thumbwheel=False,
            gesture_via_sense_panel=False,
            supported_buttons=None,
        )
        engine.hook.connected_device = device
        engine.hook.device_connected = True
        engine.hook._hid_gesture = SimpleNamespace(
            connected_device=device,
            request_wheel_native_invert=Mock(return_value=True),
            set_wheel_divert_active_flags=Mock(),
            read_battery=Mock(return_value=None),
            _hires_wheel_idx=0,
            _thumbwheel_idx=None,
        )
        request = engine.hook._hid_gesture.request_wheel_native_invert

        threads = []

        def factory(*args, **kwargs):
            thread = _RecordedThread(*args, **kwargs)
            threads.append(thread)
            return thread

        with patch("core.engine.threading.Thread", side_effect=factory):
            engine._on_connection_change(True)
            # The blocking write must NOT run on the listener (callback) thread.
            request.assert_not_called()

            worker = next(t for t in threads if t.name == "WheelInvertApply")
            self.assertEqual(worker._target, engine._apply_wheel_invert_setting)

            # Once deferred to the worker, the write is applied with the
            # configured invert state.
            worker.run_target()
            request.assert_called_once_with(True, False)



class _ManualTimer:
    """threading.Timer stand-in whose expiry the test triggers by hand."""

    live = []

    def __init__(self, interval, callback):
        self.interval = interval
        self.callback = callback
        self.cancelled = False
        self.daemon = False

    def start(self):
        _ManualTimer.live.append(self)

    def cancel(self):
        self.cancelled = True

    @classmethod
    def expire_all(cls):
        pending, cls.live = cls.live, []
        for timer in pending:
            if not timer.cancelled:
                timer.callback()


class DoublePressEngineTests(unittest.TestCase):
    """End to end through the engine: a "<btn>_double" mapping splits single
    and double presses for OS buttons and HID-diverted controls alike."""

    def _make_engine(self, mappings, mode="instant", window_ms=300):
        from core.engine import Engine

        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["profiles"]["default"]["mappings"].update(mappings)
        cfg["settings"]["double_press_mode"] = mode
        cfg["settings"]["double_press_window_ms"] = window_ms
        hook = _RecordingMouseHook()
        _ManualTimer.live = []
        self._timer_patch = patch("core.double_press.threading.Timer", _ManualTimer)
        self._timer_patch.start()
        self.addCleanup(self._timer_patch.stop)
        with (
            patch("core.engine.MouseHook", lambda: hook),
            patch("core.engine.AppDetector", _FakeAppDetector),
            patch("core.engine.load_config", return_value=cfg),
        ):
            engine = Engine()
        return engine, hook

    def test_ring_click_then_click_and_hold_holds_fn_in_instant_mode(self):
        engine, hook = self._make_engine({
            "actions_ring": "activate_actions_ring",
            "actions_ring_double": "hold:fn",
        })
        self.assertIn("sense_click", hook.blocked)
        with (
            patch("core.actions_ring.threading.Timer", _ManualTimer),
            patch("core.engine.hold_action_press") as press,
            patch("core.engine.hold_action_release") as release,
            patch("core.engine.threading.Timer"),
        ):
            # Single click: the ring opens right away, in toggle mode.
            hook.fire("sense_button_down")
            hook.fire("sense_button_up")
            self.assertEqual(engine._ring.state, engine._ring.SHOWING_TOGGLE)
            # Second press inside the window: ring closes, Fn goes down.
            hook.fire("sense_button_down")
            self.assertEqual(engine._ring.state, engine._ring.IDLE)
            press.assert_called_once_with("hold:fn")
            release.assert_not_called()
            hook.fire("sense_button_up")
            release.assert_called_once_with("hold:fn")

    def test_ring_single_click_in_wait_mode_opens_only_after_the_window(self):
        engine, hook = self._make_engine({
            "actions_ring": "activate_actions_ring",
            "actions_ring_double": "hold:fn",
        }, mode="wait", window_ms=400)
        with (
            patch("core.actions_ring.threading.Timer", _ManualTimer),
            patch("core.engine.hold_action_press") as press,
        ):
            hook.fire("sense_button_down")
            hook.fire("sense_button_up")
            self.assertEqual(engine._ring.state, engine._ring.IDLE)
            self.assertEqual(_ManualTimer.live[-1].interval, 0.4)
            _ManualTimer.expire_all()
            self.assertEqual(engine._ring.state, engine._ring.SHOWING_TOGGLE)
        press.assert_not_called()

    def test_ring_double_press_in_wait_mode_never_flashes_the_ring(self):
        engine, hook = self._make_engine({
            "actions_ring": "activate_actions_ring",
            "actions_ring_double": "hold:fn",
        }, mode="wait")
        shown = []
        engine.set_ring_show_callback(lambda *args: shown.append(args))
        with (
            patch("core.actions_ring.threading.Timer", _ManualTimer),
            patch("core.engine.hold_action_press") as press,
            patch("core.engine.hold_action_release") as release,
            patch("core.engine.threading.Timer"),
        ):
            hook.fire("sense_button_down")
            hook.fire("sense_button_up")
            hook.fire("sense_button_down")
            hook.fire("sense_button_up")
            _ManualTimer.expire_all()
        self.assertEqual(shown, [])
        press.assert_called_once_with("hold:fn")
        release.assert_called_once_with("hold:fn")

    def test_forward_button_single_and_double_actions_in_wait_mode(self):
        engine, hook = self._make_engine({
            "xbutton2": "copy",
            "xbutton2_double": "paste",
        }, mode="wait")
        with patch("core.engine.execute_action") as execute:
            hook.fire("xbutton2_down")
            hook.fire("xbutton2_up")
            execute.assert_not_called()
            _ManualTimer.expire_all()
            execute.assert_called_once_with("copy")
            execute.reset_mock()
            hook.fire("xbutton2_down")
            hook.fire("xbutton2_up")
            hook.fire("xbutton2_down")
            hook.fire("xbutton2_up")
            _ManualTimer.expire_all()
        execute.assert_called_once_with("paste")

    def test_unmapped_back_button_keeps_its_native_click_on_a_single_press(self):
        engine, hook = self._make_engine({
            "xbutton1": "none",
            "xbutton1_double": "copy",
        })
        self.assertIn("xbutton1_down", hook.blocked)
        with (
            patch("core.engine.inject_mouse_down") as down,
            patch("core.engine.inject_mouse_up") as up,
            patch("core.engine.execute_action") as execute,
            patch("core.engine.threading.Timer"),
        ):
            hook.fire("xbutton1_down")
            hook.fire("xbutton1_up")
        down.assert_called_once_with("mouse_back_click")
        up.assert_called_once_with("mouse_back_click")
        execute.assert_not_called()

    def test_double_only_mode_shift_is_still_diverted(self):
        engine, hook = self._make_engine({
            "mode_shift": "none",
            "mode_shift_double": "copy",
        })
        self.assertTrue(hook.divert_mode_shift)
        with patch("core.engine.execute_action") as execute:
            hook.fire("mode_shift_down")
            hook.fire("mode_shift_up")
            hook.fire("mode_shift_down")
        execute.assert_called_once_with("copy")

    def test_buttons_without_a_double_action_are_wired_as_before(self):
        engine, hook = self._make_engine({"xbutton2": "copy"})
        self.assertEqual(engine._double_press_detectors, [])
        with patch("core.engine.execute_action") as execute:
            hook.fire("xbutton2_down")
        execute.assert_called_once_with("copy")

    def _mx4(self, engine, hook):
        """Re-wire as the connection callback does once an MX Master 4 (whose
        rawXY control is the Sense Panel) is known."""
        hook.connected_device = SimpleNamespace(
            gesture_via_sense_panel=True, supported_buttons=None)
        hook.reset_bindings()
        engine._setup_hooks(defer_wheel_invert=True)

    def test_idle_sense_panel_keeps_rawxy_only_for_motion_actions(self):
        for single, free in (("activate_actions_ring", False),
                             ("gesture_swipe", False),
                             ("hold:alt+grave", True),
                             ("copy", True)):
            with self.subTest(single=single):
                engine, hook = self._make_engine({"actions_ring": single})
                self._mx4(engine, hook)
                self.assertEqual(hook.pointer_free_calls[-1], free)

    def test_pointer_is_freed_before_the_held_fn_press_and_pinned_after(self):
        # The firmware fixes the cursor pin when a press starts, so the
        # Sense Panel goes button-only at the first release, before the
        # second press that holds Fn, and back to rawXY once it is over.
        engine, hook = self._make_engine({
            "actions_ring": "activate_actions_ring",
            "actions_ring_double": "hold:fn",
        }, mode="wait")
        self._mx4(engine, hook)
        hook.pointer_free_calls.clear()
        with (
            patch("core.actions_ring.threading.Timer", _ManualTimer),
            patch("core.engine.hold_action_press") as press,
            patch("core.engine.hold_action_release") as release,
            patch("core.engine.threading.Timer"),
        ):
            hook.fire("sense_button_down")
            self.assertEqual(hook.pointer_free_calls, [])
            hook.fire("sense_button_up")
            self.assertEqual(hook.pointer_free_calls, [True])
            hook.fire("sense_button_down")
            press.assert_called_once_with("hold:fn")
            self.assertEqual(hook.pointer_free_calls, [True])
            hook.fire("sense_button_up")
            release.assert_called_once_with("hold:fn")
        self.assertEqual(hook.pointer_free_calls, [True, False])

    def test_a_single_click_pins_the_cursor_again_before_the_ring_opens(self):
        engine, hook = self._make_engine({
            "actions_ring": "activate_actions_ring",
            "actions_ring_double": "hold:fn",
        }, mode="wait")
        self._mx4(engine, hook)
        hook.pointer_free_calls.clear()
        order = []
        engine.set_ring_show_callback(lambda *a: order.append("ring"))
        original = hook.set_gesture_pointer_free
        hook.set_gesture_pointer_free = (
            lambda free: (order.append(f"free={free}"), original(free))[1])
        with patch("core.actions_ring.threading.Timer", _ManualTimer):
            hook.fire("sense_button_down")
            hook.fire("sense_button_up")
            _ManualTimer.expire_all()
        self.assertEqual(order, ["free=True", "free=False", "ring"])

    def test_double_press_on_an_os_button_never_touches_the_panel(self):
        engine, hook = self._make_engine({
            "actions_ring": "activate_actions_ring",
            "xbutton1": "copy",
            "xbutton1_double": "hold:fn",
        })
        self._mx4(engine, hook)
        hook.pointer_free_calls.clear()
        with (
            patch("core.engine.execute_action"),
            patch("core.engine.hold_action_press"),
            patch("core.engine.hold_action_release"),
            patch("core.engine.threading.Timer"),
        ):
            for evt in ("xbutton1_down", "xbutton1_up", "xbutton1_down", "xbutton1_up"):
                hook.fire(evt)
        self.assertEqual(hook.pointer_free_calls, [])

    def test_rewiring_cancels_a_pending_single(self):
        engine, hook = self._make_engine({
            "xbutton2": "copy",
            "xbutton2_double": "paste",
        }, mode="wait")
        with patch("core.engine.execute_action") as execute:
            hook.fire("xbutton2_down")
            hook.fire("xbutton2_up")
            engine.stop()
            _ManualTimer.expire_all()
        execute.assert_not_called()

if __name__ == "__main__":
    unittest.main()


class _RecordingMouseHook(_FakeMouseHook):
    """Fake hook that remembers what the engine wires so tests can fire the
    registered callbacks like the real HID / OS layer would."""

    def __init__(self):
        super().__init__()
        self.blocked = set()
        self.handlers = {}
        self.pointer_free_calls = []

    def set_gesture_pointer_free(self, free):
        self.pointer_free_calls.append(bool(free))
        return True

    def block(self, event_type):
        self.blocked.add(event_type)

    def register(self, event_type, callback):
        self.handlers.setdefault(event_type, []).append(callback)

    def reset_bindings(self):
        self.blocked.clear()
        self.handlers.clear()

    def fire(self, event_type):
        for cb in self.handlers.get(event_type, []):
            cb(MouseEvent(event_type))


class HoldShortcutEngineTests(unittest.TestCase):
    """End to end through the engine: a ``hold:`` mapping presses the combo
    on button down and releases it on button up, for both OS-level buttons
    (Back / Forward) and the HID-diverted Sense Panel."""

    def _make_engine(self, mappings):
        from core.engine import Engine

        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["profiles"]["default"]["mappings"].update(mappings)
        hook = _RecordingMouseHook()
        with (
            patch("core.engine.MouseHook", lambda: hook),
            patch("core.engine.AppDetector", _FakeAppDetector),
            patch("core.engine.load_config", return_value=cfg),
        ):
            engine = Engine()
        return engine, hook

    def test_sense_panel_hold_presses_on_down_and_releases_on_up(self):
        engine, hook = self._make_engine({"actions_ring": "hold:alt+grave"})
        self.assertIn("sense_click", hook.blocked)
        self.assertIn("sense_button_down", hook.blocked)
        self.assertIn("sense_button_up", hook.blocked)
        with (
            patch("core.engine.hold_action_press") as press,
            patch("core.engine.hold_action_release") as release,
            patch("core.engine.execute_action") as execute,
            patch("core.engine.threading.Timer"),
        ):
            hook.fire("sense_button_down")
            press.assert_called_once_with("hold:alt+grave")
            release.assert_not_called()
            hook.fire("sense_click")
            hook.fire("sense_button_up")
            release.assert_called_once_with("hold:alt+grave")
        execute.assert_not_called()

    def test_back_button_hold_uses_its_down_and_up_events(self):
        engine, hook = self._make_engine({"xbutton1": "hold:ctrl+shift+a"})
        with (
            patch("core.engine.hold_action_press") as press,
            patch("core.engine.hold_action_release") as release,
            patch("core.engine.threading.Timer"),
        ):
            hook.fire("xbutton1_down")
            hook.fire("xbutton1_up")
        press.assert_called_once_with("hold:ctrl+shift+a")
        release.assert_called_once_with("hold:ctrl+shift+a")

    def test_single_fire_source_taps_the_hold_shortcut(self):
        engine, hook = self._make_engine({"gesture_left": "hold:ctrl+a"})
        with (
            patch("core.engine.execute_action") as execute,
            patch("core.engine.hold_action_press") as press,
        ):
            hook.fire("gesture_swipe_left")
        execute.assert_called_once_with("hold:ctrl+a")
        press.assert_not_called()

    def test_stop_releases_a_shortcut_that_is_still_held(self):
        engine, hook = self._make_engine({"xbutton2": "hold:alt+tab"})
        with (
            patch("core.engine.hold_action_press"),
            patch("core.engine.hold_action_release") as release,
            patch("core.engine.threading.Timer"),
        ):
            hook.fire("xbutton2_down")
            engine.stop()
            release.assert_called_once_with("hold:alt+tab")
            # Nothing left to release on a second stop.
            engine.stop()
            release.assert_called_once()

    def test_reload_releases_held_keys_before_rewiring(self):
        engine, hook = self._make_engine({"xbutton2": "hold:alt+tab"})
        with (
            patch("core.engine.hold_action_press"),
            patch("core.engine.hold_action_release") as release,
            patch("core.engine.threading.Timer"),
            patch("core.engine.load_config", return_value=engine.cfg),
        ):
            hook.fire("xbutton2_down")
            engine.reload_mappings()
        release.assert_called_once_with("hold:alt+tab")

    def test_safety_timer_releases_when_up_never_arrives(self):
        engine, hook = self._make_engine({"xbutton1": "hold:ctrl+a"})
        with (
            patch("core.engine.hold_action_press"),
            patch("core.engine.hold_action_release") as release,
            patch("core.engine.threading.Timer") as timer,
        ):
            hook.fire("xbutton1_down")
            timer.assert_called_once()
            delay, fire_release = timer.call_args[0][:2]
            self.assertGreaterEqual(delay, 5.0)
            fire_release()
            release.assert_called_once_with("hold:ctrl+a")
            # The safety release already let go; the late UP must not double-release.
            hook.fire("xbutton1_up")
            release.assert_called_once()
