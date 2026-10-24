"""Inactivity of Daisy itself, independent of system idle time and Qt timers."""
import time


class IdleBehavior:
    """Keep the hide deadline measurable without touching desktop input state."""

    def __init__(self, timeout=10, clock=time.monotonic):
        self._clock = clock
        self.set_timeout(timeout)

    @property
    def timeout(self):
        return self._timeout

    def set_timeout(self, seconds):
        self._timeout = seconds if type(seconds) is int and seconds in (0, 5, 10, 30) else 10
        self.note_interaction()

    def note_interaction(self):
        self._last_interaction = self._clock()

    def tick(self, pointer_inside, protected, state):
        now = self._clock()
        if pointer_inside or protected or state != 'Idle':
            self._last_interaction = now
            return False
        return self._timeout > 0 and now - self._last_interaction >= self._timeout
