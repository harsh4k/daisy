import json
import tempfile
import unittest
from PyQt6.QtTest import QTest
import motion_trace
import settle
import test_hover


def row(t, **k):
    base = dict(t=t, event='size', w=180, h=40, y=10, state='Hover', win_x=100, win_y=0, win_w=800, win_h=400,
                opacity=1., snapshot=False)
    base.update(k)
    return base


class FindingsTests(unittest.TestCase):
    def test_a_clean_trace_has_no_findings(self):
        rows = [row(i * 16, w=180 + i * 20, h=40 + i * 10) for i in range(20)]
        self.assertEqual(motion_trace.findings(rows), [])

    def test_each_kind_of_glitch_is_named(self):
        text = ' | '.join(motion_trace.findings([row(0), row(16, y=2)]))
        self.assertIn('top edge jumped', text)
        self.assertIn('width jumped', ' '.join(motion_trace.findings([row(0), row(16, w=600)])))
        self.assertIn('froze', ' '.join(motion_trace.findings([row(0), row(400, w=200)])))
        self.assertIn('clipped', ' '.join(motion_trace.findings([row(0), row(16, w=900)])))
        self.assertIn('sideways', ' '.join(motion_trace.findings([row(0), row(16, win_x=140)])))

    def test_a_window_that_grows_around_its_centre_is_fine(self):
        self.assertEqual(motion_trace.findings([row(0), row(16, win_x=0, win_w=1000)]), [])


class RecorderTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def test_a_real_open_and_close_is_recorded_clean_and_saved(self):
        w = self.window({'motion_mode': 'full'})
        motion_trace.clear()
        w.change_state('Hover')
        self.assertTrue(settle.settle_shell(w))
        if test_hover.APP.focusWidget():
            test_hover.APP.focusWidget().clearFocus()
        w.change_state('Idle')
        self.assertTrue(settle.settle_shell(w))
        rows = motion_trace.frames()
        self.assertGreater(len(rows), 20)
        self.assertIn('state', {r['event'] for r in rows})
        self.assertEqual([f for f in motion_trace.findings(rows) if 'froze' not in f], [])
        with tempfile.TemporaryDirectory() as folder:
            path = motion_trace.save(w, folder)
            report = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(len(report['frames']), len(rows))
            self.assertTrue(path.with_suffix('.png').exists())

    def test_the_buffer_is_bounded(self):
        w = self.window({'motion_mode': 'reduced'})
        for _ in range(motion_trace.KEEP + 50):
            motion_trace.record(w, 'size')
        self.assertEqual(len(motion_trace.frames()), motion_trace.KEEP)


if __name__ == '__main__':
    unittest.main()
