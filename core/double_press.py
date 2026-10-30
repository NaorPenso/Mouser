"""Single press vs. double press on one mouse button.

A button with a ``<button>_double`` mapping routes its press and release
events through a :class:`DoublePressDetector`. The detector decides whether
each press belongs to the button's normal (single) action or to the second
press of a double press, and calls the matching down/up handlers. The second
press is held like any other: a ``hold:`` shortcut stays down until the
second release, so "click, then click and hold" works as push-to-talk.

Two modes trade latency against certainty:

``instant``
    The single action fires on the first press, exactly as without a double
    action. A second press within the window then cancels whatever the single
    action left open (the Actions Ring closes) and starts the double action.
    No added latency, but the single action has already run.

``wait``
    The single action is held back until the window passes with no second
    press. A first press held longer than the window commits to the single
    action straight away, so press-and-hold actions keep working. Nothing
    fires twice, but every single click lands ``window_ms`` late.

The window is measured from the first release to the second press (and, in
``wait`` mode, also caps how long the first press may be held before it
counts as a long press).
"""

from __future__ import annotations

import threading

DOUBLE_PRESS_MODES = ("instant", "wait")
DEFAULT_DOUBLE_PRESS_MODE = "instant"
DEFAULT_DOUBLE_PRESS_WINDOW_MS = 300
MIN_DOUBLE_PRESS_WINDOW_MS = 50
MAX_DOUBLE_PRESS_WINDOW_MS = 1000


def _noop(_event):
    return None


def coerce_double_press_mode(value):
    return value if value in DOUBLE_PRESS_MODES else DEFAULT_DOUBLE_PRESS_MODE


def coerce_double_press_window_ms(value):
    try:
        window = int(value)
    except (TypeError, ValueError):
        return DEFAULT_DOUBLE_PRESS_WINDOW_MS
    return max(MIN_DOUBLE_PRESS_WINDOW_MS, min(MAX_DOUBLE_PRESS_WINDOW_MS, window))


class DoublePressDetector:
    IDLE = "idle"
    FIRST_DOWN = "first_down"      # first press is down, not yet classified
    SINGLE_HELD = "single_held"    # wait mode: long first press committed
    ARMED = "armed"                # first press released, watching for a second
    SECOND_DOWN = "second_down"    # double press is down

    def __init__(self, *, single_down, single_up, double_down, double_up,
                 window_ms=DEFAULT_DOUBLE_PRESS_WINDOW_MS,
                 mode=DEFAULT_DOUBLE_PRESS_MODE, cancel_single=None,
                 timer_factory=None):
        self._single_down = single_down or _noop
        self._single_up = single_up or _noop
        self._double_down = double_down or _noop
        self._double_up = double_up or _noop
        self._cancel_single = cancel_single
        self._window_s = coerce_double_press_window_ms(window_ms) / 1000.0
        self._mode = coerce_double_press_mode(mode)
        self._timer_factory = timer_factory or threading.Timer
        self._lock = threading.Lock()
        self._state = self.IDLE
        self._timer = None
        self._first_down_event = None
        self._first_up_event = None

    @property
    def state(self):
        return self._state

    @property
    def mode(self):
        return self._mode

    def on_down(self, event):
        calls = []
        with self._lock:
            if self._state == self.IDLE:
                self._state = self.FIRST_DOWN
                if self._mode == "instant":
                    calls.append(lambda f=self._single_down, e=event: f(e))
                else:
                    self._first_down_event = event
                    self._start_timer(self._on_long_first_press)
            elif self._state == self.ARMED:
                self._cancel_timer()
                self._state = self.SECOND_DOWN
                if self._mode == "instant" and self._cancel_single is not None:
                    calls.append(self._cancel_single)
                calls.append(lambda f=self._double_down, e=event: f(e))
            # A down while already down (lost release) is ignored; the
            # release that eventually arrives resolves the press.
        self._run(calls)

    def on_up(self, event):
        calls = []
        with self._lock:
            if self._state == self.FIRST_DOWN:
                if self._mode == "instant":
                    calls.append(lambda f=self._single_up, e=event: f(e))
                else:
                    self._cancel_timer()
                    self._first_up_event = event
                self._state = self.ARMED
                self._start_timer(self._on_window_expired)
            elif self._state == self.SINGLE_HELD:
                self._state = self.IDLE
                calls.append(lambda f=self._single_up, e=event: f(e))
            elif self._state == self.SECOND_DOWN:
                self._state = self.IDLE
                calls.append(lambda f=self._double_up, e=event: f(e))
        self._run(calls)

    def shutdown(self):
        """Cancel the pending window. Nothing is fired."""
        with self._lock:
            self._cancel_timer()
            self._state = self.IDLE
            self._first_down_event = None
            self._first_up_event = None

    # ── timers ────────────────────────────────────────────────────────

    def _on_long_first_press(self, timer):
        calls = []
        with self._lock:
            if self._timer is not timer or self._state != self.FIRST_DOWN:
                return
            self._timer = None
            self._state = self.SINGLE_HELD
            calls.append(lambda f=self._single_down, e=self._first_down_event: f(e))
            self._first_down_event = None
        self._run(calls)

    def _on_window_expired(self, timer):
        calls = []
        with self._lock:
            if self._timer is not timer or self._state != self.ARMED:
                return
            self._timer = None
            self._state = self.IDLE
            if self._mode == "wait":
                # No second press came: the held-back click was a single.
                calls.append(lambda f=self._single_down, e=self._first_down_event: f(e))
                calls.append(lambda f=self._single_up, e=self._first_up_event: f(e))
            self._first_down_event = None
            self._first_up_event = None
        self._run(calls)

    def _start_timer(self, callback):
        self._cancel_timer()
        holder = []
        timer = self._timer_factory(self._window_s, lambda: callback(holder[0]))
        holder.append(timer)
        timer.daemon = True
        self._timer = timer
        timer.start()

    def _cancel_timer(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    @staticmethod
    def _run(calls):
        for call in calls:
            try:
                call()
            except Exception as exc:
                print(f"[DoublePress] handler error: {exc}")
