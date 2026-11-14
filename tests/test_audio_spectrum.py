import math
import unittest
from unittest.mock import patch
import test_hover
import audio_spectrum as a
from spectrum_strip import SpectrumStrip

APP = test_hover.APP


def tone(hz, rate=48000, amp=.3):
    return [amp * math.sin(2 * math.pi * hz * i / rate) for i in range(a.N)]


class SpectrumMathTests(unittest.TestCase):
    def test_silence_and_short_input_are_all_zero(self):
        self.assertEqual(a.levels([0.] * a.N, 12), [0.] * 12)
        self.assertEqual(a.levels([.5] * 10, 12), [0.] * 12)

    def test_a_tone_lights_the_bar_for_its_pitch(self):
        low, mid, high = (a.levels(tone(hz), 12) for hz in (120, 1000, 8000))
        self.assertLess(low.index(max(low)), mid.index(max(mid)))
        self.assertLess(mid.index(max(mid)), high.index(max(high)))
        self.assertEqual(mid.index(max(mid)), 6)
        self.assertGreater(max(mid), .6)

    def test_levels_stay_between_zero_and_one_even_when_clipping(self):
        for value in a.levels(tone(1000, amp=50.), 24):
            self.assertTrue(0. <= value <= 1.)

    def test_fft_finds_the_right_bin(self):
        bins = a.fft(tone(48000 * 32 / a.N))
        magnitudes = [abs(b) for b in bins[:a.N // 2]]
        self.assertEqual(magnitudes.index(max(magnitudes)), 32)

    def test_bands_cover_the_range_without_empty_bars(self):
        edges = a.band_edges(24, 48000)
        self.assertEqual(len(edges), 24)
        for low, high in edges:
            self.assertLess(low, high)

    def test_bars_rise_fast_and_fall_slowly(self):
        self.assertGreater(a.smooth([0.], [1.])[0], .5)
        self.assertGreater(a.smooth([1.], [0.])[0], .7)


class FakeSignal:
    def connect(self, _slot):
        pass


class FakeMonitor:
    error = ''
    started = stopped = 0

    def __init__(self, parent=None):
        self.running = False
        self.levels_ready = FakeSignal()

    def isRunning(self):
        return self.running

    def start(self):
        self.running = True
        FakeMonitor.started += 1

    def stop(self):
        self.running = False
        FakeMonitor.stopped += 1


class VisualTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def test_strip_rests_as_dots_and_moves_with_levels(self):
        strip = SpectrumStrip()
        self.addCleanup(strip.deleteLater)
        strip.show()
        rest = strip.grab().toImage()
        strip.set_levels([.9] * 24)
        self.assertTrue(strip.live())
        self.assertNotEqual(rest, strip.grab().toImage())
        strip.set_levels([])
        self.assertFalse(strip.live())
        self.assertEqual(rest, strip.grab().toImage())

    def test_the_monitor_runs_only_while_music_plays_and_motion_is_allowed(self):
        w = self.window({'motion_mode': 'full'})
        FakeMonitor.started = FakeMonitor.stopped = 0
        w._monitors_started = True
        with patch.object(a, 'SpectrumMonitor', FakeMonitor):
            w.update_media('Playing', 'Song', 'Artist', '#1db954')
            self.assertEqual(FakeMonitor.started, 1)
            w.update_content()
            self.assertEqual(FakeMonitor.started, 1, 'not restarted while it runs')
            w.update_media('Paused', 'Song', 'Artist', '#1db954')
            self.assertEqual(FakeMonitor.stopped, 1)
            w.update_media('Playing', 'Song', 'Artist', '#1db954')
            w.reduced_motion = True
            w.update_content()
            self.assertEqual(FakeMonitor.stopped, 2, 'reduced motion never listens')
        w.spectrum_monitor = None

    def test_levels_reach_the_pill_bars_and_the_now_page(self):
        w = self.window({'motion_mode': 'full'})
        w.on_spectrum([.8] * 24)
        self.assertTrue(w.dashboard.spectrum.live())
        self.assertEqual(len(w.now_playing._live), 6)
        w.on_spectrum([])
        self.assertIsNone(w.now_playing._live)


if __name__ == '__main__':
    unittest.main()
