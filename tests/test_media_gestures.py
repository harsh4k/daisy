"""Regressions for media gestures crossing a delayed metadata transition."""
import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from dashboard_panel import DashboardPanel
from media_monitor import MediaMonitor
from test_media import Manager
from test_media_polish import ControlledSession

APP = QApplication.instance() or QApplication([])


class MetadataGestureTests(unittest.IsolatedAsyncioTestCase):
    async def test_slow_new_cover_cancels_old_drag_before_any_new_seek(self):
        monitor, panel = MediaMonitor(), DashboardPanel()
        monitor.loop = asyncio.get_running_loop()
        session = ControlledSession()
        monitor.manager = Manager([session], session)
        monitor.media_updated.connect(panel.update_media)
        monitor.capabilities_updated.connect(panel.set_capabilities)
        monitor.timeline_updated.connect(panel.update_timeline)
        panel.seek_requested.connect(monitor.seek_to)
        self.addCleanup(panel.close)
        with patch.object(monitor, 'fetch_lyrics', new=AsyncMock()):
            await monitor.update_media_info()
            await monitor.check_lyric_sync()
            panel.progress.setSliderDown(True)
            panel.progress.setValue(800)
            entered, release = asyncio.Event(), asyncio.Event()
            async def slow(_thumbnail):
                entered.set()
                await release.wait()
                return b'', '#000000'
            session.props.title = 'Replacement'
            with patch('media_monitor.read_artwork', slow):
                task = asyncio.create_task(monitor.update_media_info())
                await asyncio.wait_for(entered.wait(), .5)
                try:
                    self.assertFalse(panel.progress.isEnabled())
                    self.assertFalse(panel.progress.isSliderDown())
                    self.assertFalse(panel.play.isEnabled())
                    panel.progress.setSliderDown(False)
                    monitor.seek_to(80)  # Also reject commands queued during metadata loading.
                    for _ in range(8):
                        await asyncio.sleep(0)
                    self.assertEqual(session.commands, [])
                finally:
                    release.set()
                    await task
            await monitor.check_lyric_sync()
            self.assertTrue(panel.progress.isEnabled())
            self.assertTrue(panel.play.isEnabled())
            self.assertEqual(session.commands, [])


class GrooveGestureTests(unittest.TestCase):
    def test_groove_click_submits_once_and_poll_does_not_fight_pressed_gesture(self):
        panel = DashboardPanel()
        self.addCleanup(panel.close)
        panel.show()
        panel.update_media('Playing', 'Track', 'Artist', '')
        panel.set_capabilities({'seek': True})
        panel.update_timeline(10, 100)
        APP.processEvents()
        values = []
        panel.seek_requested.connect(values.append)
        position = QPoint(panel.progress.width() * 3 // 4, panel.progress.height() // 2)
        QTest.mousePress(panel.progress, Qt.MouseButton.LeftButton, pos=position)
        pressed_value = panel.progress.value()
        panel.update_timeline(12, 100)
        self.assertEqual(panel.progress.value(), pressed_value)
        QTest.mouseRelease(panel.progress, Qt.MouseButton.LeftButton, pos=position)
        self.assertEqual(len(values), 1)
        self.assertGreater(values[0], 60.)
        APP.processEvents()
        self.assertEqual(len(values), 1)
