import unittest
import test_hover
import emotions
from emotions import EmotionMachine, MOODS, is_night
from daisy_eyes import DaisyEyes

APP = test_hover.APP


class Clock:
    now = 100.

    def __call__(self):
        return self.now


class EmotionMachineTests(unittest.TestCase):
    def test_night_runs_from_22_to_6(self):
        self.assertEqual([h for h in range(24) if is_night(h)], [0, 1, 2, 3, 4, 5, 22, 23])

    def test_baseline_follows_the_clock(self):
        m = EmotionMachine()
        m.set_hour(23)
        self.assertEqual(m.current(), 'sleepy')
        m.set_hour(14)
        self.assertEqual(m.current(), 'neutral')

    def test_reaction_expires_and_baseline_returns(self):
        clock = Clock()
        m = EmotionMachine(clock)
        m.set_hour(23)
        m.react('proud', 4)
        self.assertEqual(m.current(), 'proud')
        clock.now += 3.9
        self.assertEqual(m.current(), 'proud')
        clock.now += .2
        self.assertEqual(m.current(), 'sleepy', 'back to sleepy once proud is over')

    def test_held_reaction_lasts_until_released(self):
        clock = Clock()
        m = EmotionMachine(clock)
        m.react('alert')
        clock.now += 3600
        self.assertEqual(m.current(), 'alert')
        m.release('alert')
        self.assertEqual(m.current(), 'neutral')

    def test_what_needs_you_most_wins(self):
        m = EmotionMachine()
        m.react('happy', 5)
        m.react('proud', 5)
        self.assertEqual(m.current(), 'proud')
        m.react('alert')
        self.assertEqual(m.current(), 'alert')
        m.release('alert')
        self.assertEqual(m.current(), 'proud')

    def test_unknown_or_baseline_names_are_refused(self):
        m = EmotionMachine()
        for name in ('grumpy', 'neutral', 'sleepy'):
            with self.assertRaises(ValueError):
                m.react(name)

    def test_the_face_eases_toward_the_mood_without_overshoot(self):
        m = EmotionMachine()
        m.react('happy')
        last = 0.
        for _ in range(40):
            smile = m.step(.025)['smile']
            self.assertGreaterEqual(smile, last)
            self.assertLessEqual(smile, 1.)
            last = smile
        self.assertGreater(last, .95)
        m.step(0, instant=True)
        self.assertEqual(m.params['smile'], MOODS['happy']['smile'])

    def test_every_mood_defines_every_parameter(self):
        for name, mood in MOODS.items():
            self.assertEqual(set(mood), set(emotions.NEUTRAL), name)


class EyesMoodTests(unittest.TestCase):
    def eyes(self):
        eyes = DaisyEyes()
        eyes.set_reduced_motion(True)
        self.addCleanup(eyes.deleteLater)
        return eyes

    def test_night_makes_the_eyes_sleepy_and_morning_wakes_them(self):
        eyes = self.eyes()
        eyes.set_hour(23)
        self.assertEqual(eyes.emotion, 'sleepy')
        self.assertGreater(eyes.mood.params['lid'], .5)
        eyes.set_hour(9)
        self.assertEqual(eyes.emotion, 'neutral')
        self.assertEqual(eyes.mood.params['lid'], 0.)

    def test_proud_shows_sparkle_and_happy_arcs(self):
        eyes = self.eyes()
        eyes.react('proud', 4)
        self.assertEqual(eyes.emotion, 'proud')
        self.assertEqual(eyes.mood.params['smile'], 1.)
        self.assertEqual(eyes.mood.params['sparkle'], 1.)

    def test_every_mood_paints_without_error_and_differs(self):
        eyes = self.eyes()
        eyes.show()
        pictures = {}
        for name in ('neutral', 'happy', 'proud', 'alert', 'sad'):
            for other in ('happy', 'proud', 'alert', 'sad'):
                eyes.release(other)
            if name != 'neutral':
                eyes.react(name)
            pictures[name] = eyes.grab().toImage()
            self.assertFalse(pictures[name].isNull())
        eyes.release('sad')
        eyes.set_hour(23)
        pictures['sleepy'] = eyes.grab().toImage()
        self.assertEqual(len(pictures), 6)
        names = list(pictures)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                self.assertNotEqual(pictures[a], pictures[b], (a, b))

    def test_hidden_eyes_do_not_run_a_timer_for_a_mood(self):
        eyes = self.eyes()
        eyes.hide()
        eyes.react('happy', 3)
        self.assertFalse(eyes._anim_timer.isActive())
        self.assertEqual(eyes.mood.params['smile'], 1., 'with nothing running the face jumps to the mood')


if __name__ == '__main__':
    unittest.main()
