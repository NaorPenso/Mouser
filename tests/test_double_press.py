"""DoublePressDetector: single vs. double press in both modes.

Timers are driven by hand so every window boundary is deterministic.
"""

import unittest

from core.double_press import (
    DoublePressDetector,
    coerce_double_press_mode,
    coerce_double_press_window_ms,
)


class FakeTimer:
    """Stands in for threading.Timer; tests call fire() to end the window."""

    created = []

    def __init__(self, interval, callback):
        self.interval = interval
        self.callback = callback
        self.cancelled = False
        self.started = False
        self.daemon = False
        FakeTimer.created.append(self)

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True

    def fire(self):
        if not self.cancelled:
            self.callback()


def _live_timer():
    live = [t for t in FakeTimer.created if t.started and not t.cancelled]
    return live[-1] if live else None


class _Recorder:
    def __init__(self):
        self.calls = []

    def handler(self, name):
        return lambda event: self.calls.append((name, event))

    def cancel(self):
        self.calls.append(("cancel", None))


def _detector(mode, window_ms=300, with_cancel=True):
    FakeTimer.created = []
    rec = _Recorder()
    detector = DoublePressDetector(
        single_down=rec.handler("single_down"),
        single_up=rec.handler("single_up"),
        double_down=rec.handler("double_down"),
        double_up=rec.handler("double_up"),
        cancel_single=rec.cancel if with_cancel else None,
        window_ms=window_ms,
        mode=mode,
        timer_factory=FakeTimer,
    )
    return detector, rec


def _names(rec):
    return [name for name, _ in rec.calls]


class InstantModeTests(unittest.TestCase):
    def test_single_press_fires_immediately_with_no_added_latency(self):
        detector, rec = _detector("instant")
        detector.on_down("d1")
        self.assertEqual(rec.calls, [("single_down", "d1")])
        detector.on_up("u1")
        self.assertEqual(_names(rec), ["single_down", "single_up"])
        _live_timer().fire()
        self.assertEqual(_names(rec), ["single_down", "single_up"])
        self.assertEqual(detector.state, DoublePressDetector.IDLE)

    def test_second_press_cancels_the_single_and_holds_the_double(self):
        detector, rec = _detector("instant")
        detector.on_down("d1")
        detector.on_up("u1")
        detector.on_down("d2")
        self.assertEqual(
            _names(rec), ["single_down", "single_up", "cancel", "double_down"]
        )
        # The double stays pressed until the second release.
        self.assertEqual(detector.state, DoublePressDetector.SECOND_DOWN)
        detector.on_up("u2")
        self.assertEqual(rec.calls[-1], ("double_up", "u2"))
        self.assertEqual(detector.state, DoublePressDetector.IDLE)

    def test_a_press_after_the_window_is_a_new_single(self):
        detector, rec = _detector("instant")
        detector.on_down("d1")
        detector.on_up("u1")
        _live_timer().fire()
        detector.on_down("d2")
        detector.on_up("u2")
        self.assertEqual(
            _names(rec), ["single_down", "single_up", "single_down", "single_up"]
        )

    def test_long_first_press_is_still_a_single(self):
        detector, rec = _detector("instant")
        detector.on_down("d1")
        self.assertIsNone(_live_timer())  # no window while the press is held
        detector.on_up("u1")
        self.assertEqual(_names(rec), ["single_down", "single_up"])


class WaitModeTests(unittest.TestCase):
    def test_single_click_fires_only_after_the_window(self):
        detector, rec = _detector("wait")
        detector.on_down("d1")
        detector.on_up("u1")
        self.assertEqual(rec.calls, [])
        _live_timer().fire()
        self.assertEqual(rec.calls, [("single_down", "d1"), ("single_up", "u1")])
        self.assertEqual(detector.state, DoublePressDetector.IDLE)

    def test_double_press_never_fires_the_single(self):
        detector, rec = _detector("wait")
        detector.on_down("d1")
        detector.on_up("u1")
        detector.on_down("d2")
        detector.on_up("u2")
        self.assertEqual(rec.calls, [("double_down", "d2"), ("double_up", "u2")])
        for timer in FakeTimer.created:
            timer.fire()
        self.assertEqual(_names(rec), ["double_down", "double_up"])

    def test_long_first_press_commits_to_the_single_and_holds_it(self):
        detector, rec = _detector("wait")
        detector.on_down("d1")
        _live_timer().fire()  # still held when the window ends
        self.assertEqual(rec.calls, [("single_down", "d1")])
        self.assertEqual(detector.state, DoublePressDetector.SINGLE_HELD)
        detector.on_up("u1")
        self.assertEqual(rec.calls[-1], ("single_up", "u1"))
        self.assertEqual(detector.state, DoublePressDetector.IDLE)

    def test_wait_mode_never_calls_cancel(self):
        detector, rec = _detector("wait")
        detector.on_down("d1")
        detector.on_up("u1")
        detector.on_down("d2")
        self.assertNotIn("cancel", _names(rec))


class RobustnessTests(unittest.TestCase):
    def test_stale_timer_after_a_new_press_does_nothing(self):
        detector, rec = _detector("wait")
        detector.on_down("d1")
        first = _live_timer()
        detector.on_up("u1")          # cancels the long-press timer
        detector.on_down("d2")        # double press
        first.callback()              # a late tick from the old timer
        self.assertEqual(_names(rec), ["double_down"])

    def test_shutdown_drops_a_pending_single_without_firing(self):
        detector, rec = _detector("wait")
        detector.on_down("d1")
        detector.on_up("u1")
        pending = _live_timer()
        detector.shutdown()
        self.assertTrue(pending.cancelled)
        pending.callback()
        self.assertEqual(rec.calls, [])
        self.assertEqual(detector.state, DoublePressDetector.IDLE)

    def test_repeated_down_without_up_is_ignored(self):
        detector, rec = _detector("instant")
        detector.on_down("d1")
        detector.on_down("d1-again")
        self.assertEqual(_names(rec), ["single_down"])

    def test_handler_errors_do_not_wedge_the_detector(self):
        FakeTimer.created = []
        def boom(_event):
            raise RuntimeError("handler failed")
        detector = DoublePressDetector(
            single_down=boom, single_up=boom, double_down=boom, double_up=boom,
            mode="instant", timer_factory=FakeTimer,
        )
        detector.on_down("d1")
        detector.on_up("u1")
        self.assertEqual(detector.state, DoublePressDetector.ARMED)

    def test_window_is_configurable(self):
        detector, _ = _detector("instant", window_ms=450)
        detector.on_down("d1")
        detector.on_up("u1")
        self.assertAlmostEqual(_live_timer().interval, 0.45)


class TransitionHookTests(unittest.TestCase):
    def _detector(self, mode):
        FakeTimer.created = []
        rec = _Recorder()
        detector = DoublePressDetector(
            single_down=rec.handler("single_down"),
            single_up=rec.handler("single_up"),
            double_down=rec.handler("double_down"),
            double_up=rec.handler("double_up"),
            on_armed=lambda: rec.calls.append(("armed", None)),
            on_idle=lambda: rec.calls.append(("idle", None)),
            mode=mode, timer_factory=FakeTimer,
        )
        return detector, rec

    def test_armed_runs_before_a_second_press_can_arrive(self):
        detector, rec = self._detector("wait")
        detector.on_down("d1")
        detector.on_up("u1")
        detector.on_down("d2")
        detector.on_up("u2")
        self.assertEqual(_names(rec), ["armed", "double_down", "double_up", "idle"])

    def test_idle_runs_before_a_held_back_single(self):
        detector, rec = self._detector("wait")
        detector.on_down("d1")
        detector.on_up("u1")
        _live_timer().fire()
        self.assertEqual(_names(rec), ["armed", "idle", "single_down", "single_up"])

    def test_instant_mode_arms_after_the_single_release(self):
        detector, rec = self._detector("instant")
        detector.on_down("d1")
        detector.on_up("u1")
        _live_timer().fire()
        self.assertEqual(_names(rec), ["single_down", "armed", "single_up", "idle"])

    def test_long_press_returns_to_idle_on_release(self):
        detector, rec = self._detector("wait")
        detector.on_down("d1")
        _live_timer().fire()
        detector.on_up("u1")
        self.assertEqual(_names(rec), ["single_down", "single_up", "idle"])


class CoercionTests(unittest.TestCase):
    def test_mode_falls_back_to_instant(self):
        self.assertEqual(coerce_double_press_mode("wait"), "wait")
        self.assertEqual(coerce_double_press_mode("instant"), "instant")
        self.assertEqual(coerce_double_press_mode("sometimes"), "instant")
        self.assertEqual(coerce_double_press_mode(None), "instant")

    def test_window_is_clamped_to_a_usable_range(self):
        self.assertEqual(coerce_double_press_window_ms(250), 250)
        self.assertEqual(coerce_double_press_window_ms("400"), 400)
        self.assertEqual(coerce_double_press_window_ms(5), 50)
        self.assertEqual(coerce_double_press_window_ms(99999), 1000)
        self.assertEqual(coerce_double_press_window_ms("soon"), 300)


if __name__ == "__main__":
    unittest.main()
