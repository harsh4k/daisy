import os
import tempfile
import unittest
from PyQt6.QtTest import QTest
import test_hover
import free_ram


class FreeRamTests(unittest.TestCase):
    def test_command_runs_only_that_file_hidden_without_a_profile(self):
        args = free_ram.command(r'X:\a b\free-ram.ps1')
        self.assertEqual(args[-2:], ['-File', r'X:\a b\free-ram.ps1'])
        for flag in ('-NoProfile', '-NonInteractive', 'Hidden'):
            self.assertIn(flag, args)

    def test_summary_is_the_last_printed_line(self):
        self.assertEqual(free_ram.summary('x\nRAM free: 9.1 GB / 15.7 GB\n\n', 0), 'RAM free: 9.1 GB / 15.7 GB')
        self.assertEqual(free_ram.summary('', 0), 'Done')
        self.assertTrue(free_ram.summary('boom', 1).startswith('Free RAM failed'))

    def test_a_missing_script_is_reported_not_run(self):
        runner = free_ram.FreeRam(r'X:\nope\missing.ps1')
        got = []
        runner.finished.connect(got.append)
        self.assertFalse(runner.run())
        self.assertIn('Script not found', got[0])

    def test_the_script_runs_and_its_result_reaches_the_card(self):
        with tempfile.TemporaryDirectory() as folder:
            script = os.path.join(folder, 'fake.ps1')
            with open(script, 'w') as stream:
                stream.write('"RAM free: 1.0 GB / 2.0 GB"\n')
            w = test_hover.HoverTests.window(self, {'free_ram_script': script})
            w.free_ram.script = free_ram.Path(script)
            w.system_card.free_ram.click()
            self.assertFalse(w.system_card.free_ram.isEnabled(), 'one run at a time')
            for _ in range(200):
                if w.system_card.free_ram.isEnabled():
                    break
                QTest.qWait(50)
            self.assertEqual(w.system_card.free_ram_status.text(), 'RAM free: 1.0 GB / 2.0 GB')


if __name__ == '__main__':
    unittest.main()
