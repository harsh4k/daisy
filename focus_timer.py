"""Monotonic focus timer; its result never depends on UI polling frequency."""
import time


class FocusTimer:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.reset()

    def start(self, minutes):
        if type(minutes) is not int or not 1 <= minutes <= 180:
            raise ValueError('Choose a duration between 1 and 180 minutes.')
        self._left = minutes * 60.0
        self._deadline = self.clock() + self._left
        self._completion = False
        self.state = 'running'

    def remaining(self):
        if self.state == 'running':
            self._left = max(0.0, self._deadline - self.clock())
            if self._left == 0:
                self.state = 'completed'
                self._completion = True
        return self._left

    def pause(self):
        self.remaining()
        if self.state == 'running':
            self.state = 'paused'

    def resume(self):
        if self.state == 'paused':
            self._deadline = self.clock() + self._left
            self.state = 'running'

    def reset(self):
        self.state = 'idle'
        self._left = 0.0
        self._deadline = 0.0
        self._completion = False

    def take_completion(self):
        self.remaining()
        completed, self._completion = self._completion, False
        return completed
