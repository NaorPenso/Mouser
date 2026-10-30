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
import time

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
                 timer_factory=None, name="button", clock=None,
                 on_armed=None, on_idle=None):
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
        self._name = name
        self._clock = clock or time.monotonic
        self._last_down_at = None
        self._last_up_at = None
        # Transition hooks, called outside the lock: on_armed when a second
        # press becomes possible (first release), on_idle when the sequence
        # is over. The engine uses them to prepare the press that may follow.
        self._on_armed = on_armed
        self._on_idle = on_idle

    @property
    def state(self):
        return self._state

    @property
    def mode(self):
        return self._mode

    def on_down(self, event):
        calls = []
        with self._lock:
            now = self._clock()
            gap = self._ms_since(self._last_up_at, now)
            self._last_down_at = now
            prior = self._state
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
            outcome = {
                self.IDLE: "first press" + (" -> single" if self._mode == "instant" else ""),
                self.ARMED: "second press -> double",
            }.get(prior, f"ignored (already {prior})")
        self._log(f"down {outcome}; {gap} since last release")
        self._run(calls)

    def on_up(self, event):
        calls = []
        with self._lock:
            now = self._clock()
            held = self._ms_since(self._last_down_at, now)
            self._last_up_at = now
            prior = self._state
            if self._state == self.FIRST_DOWN:
                if self._mode == "instant":
                    calls.append(lambda f=self._single_up, e=event: f(e))
                else:
                    self._cancel_timer()
                    self._first_up_event = event
                self._state = self.ARMED
                self._start_timer(self._on_window_expired)
                if self._on_armed is not None:
                    calls.insert(0, self._on_armed)
            elif self._state == self.SINGLE_HELD:
                self._state = self.IDLE
                calls.append(lambda f=self._single_up, e=event: f(e))
                self._append_idle(calls)
            elif self._state == self.SECOND_DOWN:
                self._state = self.IDLE
                calls.append(lambda f=self._double_up, e=event: f(e))
                self._append_idle(calls)
            outcome = {
                self.FIRST_DOWN: "first release, waiting for a second press",
                self.SINGLE_HELD: "release of the long press",
                self.SECOND_DOWN: "release of the double",
            }.get(prior, f"ignored (in {prior})")
        self._log(f"up {outcome}; held {held}")
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
            self._log("long first press -> single")
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
            self._log("window passed, no second press"
                      + (" -> single" if self._mode == "wait" else ""))
            if self._mode == "wait":
                # No second press came: the held-back click was a single.
                calls.append(lambda f=self._single_down, e=self._first_down_event: f(e))
                calls.append(lambda f=self._single_up, e=self._first_up_event: f(e))
            self._first_down_event = None
            self._first_up_event = None
            # Back to idle before a held-back single runs, so its press sees
            # the idle preparation (e.g. the Actions Ring's rawXY).
            if self._on_idle is not None:
                calls.insert(0, self._on_idle)
        self._run(calls)

    def _append_idle(self, calls):
        if self._on_idle is not None:
            calls.append(self._on_idle)

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
    def _ms_since(then, now):
        return "n/a" if then is None else f"{(now - then) * 1000:.0f} ms"

    def _log(self, message):
        # One line per decision, in the app log, so a misread press can be
        # traced from the timings the detector actually saw.
        print(f"[DoublePress] {self._name}: {message}")

    @staticmethod
    def _run(calls):
        for call in calls:
            try:
                call()
            except Exception as exc:
                print(f"[DoublePress] handler error: {exc}")
