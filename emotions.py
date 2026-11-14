"""The eyes' moods: a baseline from the time of day, plus short-lived reactions.

Pure logic, no Qt, so it can be tested without a window. Each mood is a target
for a handful of face parameters; the machine eases the face toward the target.

  lid     0 open .. 1 shut: the upper lid sags (sleepy)
  smile   0 round eyes .. 1 happy arcs (^ ^)
  wide    size of the eyes, 1 is normal
  tilt    degrees, outer corners down (sad)
  sparkle 0..1 a small star above the eyes (proud)
  zzz     0..1 drifting z letters (asleep)
  lift    pixels the face rides up (negative) or sags down
  bounce  pixels of happy bobbing
"""
import math
import time

NIGHT_FROM, NIGHT_TO = 22, 6   # sleepy from 22:00 until 06:00

NEUTRAL = dict(lid=0., smile=0., wide=1., tilt=0., sparkle=0., zzz=0., lift=0., bounce=0.)
MOODS = {
    'neutral': NEUTRAL,
    'sleepy': dict(NEUTRAL, lid=.62, wide=.95, zzz=1., lift=1.),
    'happy': dict(NEUTRAL, smile=1., wide=1.05, bounce=1.4),
    'proud': dict(NEUTRAL, smile=1., wide=1.15, sparkle=1., lift=-1.5, bounce=.8),
    'alert': dict(NEUTRAL, wide=1.32),
    'curious': dict(NEUTRAL, wide=1.2, lift=-.6),   # a notification arrived: a quick look
    'sad': dict(NEUTRAL, lid=.25, wide=.92, tilt=14., lift=1.5),
}
# When two reactions overlap, the one that needs you most wins.
PRIORITY = ('alert', 'sad', 'proud', 'happy', 'curious')
RATE = 9.  # how fast the face eases toward a mood, per second


def is_night(hour):
    return hour >= NIGHT_FROM or hour < NIGHT_TO


class EmotionMachine:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.baseline = 'neutral'
        self._reactions = {}          # name -> expiry time, or None until released
        self.params = dict(NEUTRAL)

    def set_hour(self, hour):
        self.baseline = 'sleepy' if is_night(hour) else 'neutral'

    def react(self, name, seconds=None):
        """Show a mood for `seconds`, or until release(name) when seconds is None."""
        if name not in MOODS or name in ('neutral', 'sleepy'):
            raise ValueError('Unknown reaction: %r' % (name,))
        self._reactions[name] = None if seconds is None else self.clock() + max(0., seconds)

    def release(self, name):
        self._reactions.pop(name, None)

    def current(self):
        now = self.clock()
        for name in [n for n, until in self._reactions.items() if until is not None and until <= now]:
            del self._reactions[name]
        for name in PRIORITY:
            if name in self._reactions:
                return name
        return self.baseline

    def step(self, dt, instant=False):
        """Ease the face toward the current mood; returns the face parameters."""
        target = MOODS[self.current()]
        k = 1. if instant else 1. - math.exp(-RATE * max(0., dt))
        for key, goal in target.items():
            self.params[key] += (goal - self.params[key]) * k
        return self.params
