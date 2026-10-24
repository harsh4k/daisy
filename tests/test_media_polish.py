"""Media commands use fake sessions; no external player is controlled."""
import asyncio
import datetime as dt
import io
import os
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QSlider
from PIL import Image
from dashboard_panel import DashboardPanel
from media_monitor import MediaMonitor
from media_sessions import select_session
from test_media import Session, Manager

APP = QApplication.instance() or QApplication([])


class ControlledSession(Session):
    def __init__(self, source='Spotify.exe'):
        super().__init__(source)
        self.controls = NS(is_previous_enabled=False, is_next_enabled=True,
                           is_play_pause_toggle_enabled=True, is_playback_position_enabled=True)
        self.commands = []
        self.accept = True

    def get_playback_info(self):
        return NS(playback_status=self.status, controls=self.controls)

    async def try_skip_next_async(self):
        self.commands.append(('next',))
        return self.accept

    async def try_change_playback_position_async(self, ticks):
        self.commands.append(('seek', ticks))
        return self.accept


class MediaPolishTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.monitor = MediaMonitor()
        self.monitor.loop = asyncio.get_running_loop()
        self.session = ControlledSession()
        self.monitor.manager = Manager([self.session], self.session)
        self.results = []
        if hasattr(self.monitor, 'transport_result'):
            self.monitor.transport_result.connect(lambda *args: self.results.append(args))
        self.fetch = patch.object(self.monitor, 'fetch_lyrics', new=AsyncMock())
        self.fetch.start()
        self.addCleanup(self.fetch.stop)

    async def settle(self):
        for _ in range(8):
            await asyncio.sleep(0)

    async def test_session_capabilities_control_supported_actions(self):
        self.assertTrue(hasattr(self.monitor, 'capabilities_updated'), 'Missing capability signal')
        values = []
        self.monitor.capabilities_updated.connect(values.append)
        await self.monitor.update_media_info()
        self.assertEqual(values[-1], {'previous': False, 'play_pause': True, 'next': True, 'seek': True})
        self.monitor.prev_track()
        await self.settle()
        self.assertEqual(self.results[-1], ('previous', False))

    async def test_rejected_transport_is_reported_without_optimistic_success(self):
        await self.monitor.update_media_info()
        self.session.accept = False
        self.monitor.next_track()
        await self.settle()
        self.assertEqual(self.session.commands, [('next',)])
        self.assertEqual(self.results, [('next', False)])

    async def test_queued_command_is_discarded_after_session_generation_changes(self):
        await self.monitor.update_media_info()
        self.monitor.next_track()
        self.monitor._generation += 1
        await self.settle()
        self.assertEqual(self.session.commands, [])
        self.assertEqual(self.results, [])

    async def test_pending_command_does_not_report_for_replacement_session(self):
        await self.monitor.update_media_info()
        entered, release = asyncio.Event(), asyncio.Event()
        async def blocked():
            entered.set()
            await release.wait()
            return True
        self.session.try_skip_next_async = blocked
        self.monitor.next_track()
        await asyncio.wait_for(entered.wait(), .5)
        self.monitor._generation += 1
        release.set()
        await self.settle()
        self.assertEqual(self.results, [])

    async def test_seek_clamps_relative_position_and_preserves_start_offset_ticks(self):
        self.assertTrue(hasattr(self.monitor, 'seek_to'), 'Missing seek control')
        self.session.timeline.start_time = dt.timedelta(seconds=30)
        self.session.timeline.end_time = dt.timedelta(seconds=130)
        await self.monitor.update_media_info()
        self.monitor.seek_to(12.5)
        await self.settle()
        self.monitor.seek_to(1000)
        await self.settle()
        self.assertEqual(self.session.commands, [('seek', 425000000), ('seek', 1300000000)])
        self.assertEqual(self.results, [('seek', True), ('seek', True)])

    async def test_track_change_clears_cover_before_slow_artwork_read(self):
        await self.monitor.update_media_info()
        self.monitor._artwork = b'old cover'
        artwork = []
        self.monitor.artwork_updated.connect(artwork.append)
        entered, release = asyncio.Event(), asyncio.Event()
        async def slow(_thumbnail):
            entered.set()
            await release.wait()
            return b'new cover', '#000000'
        self.session.props.title = 'New track'
        with patch('media_monitor.read_artwork', slow):
            task = asyncio.create_task(self.monitor.update_media_info())
            await asyncio.wait_for(entered.wait(), .5)
            cleared = artwork[:]
            release.set()
            await task
        self.assertEqual(cleared, [b''])
        self.assertEqual(artwork[-1], b'new cover')

    async def test_preference_change_invalidates_queued_transport_before_refresh(self):
        await self.monitor.update_media_info()
        self.monitor.next_track()
        self.monitor.set_preferred_source('Chrome.exe')
        await self.settle()
        self.assertEqual(self.session.commands, [])

    async def test_play_pause_uses_pause_capability_without_toggle_support(self):
        self.session.controls.is_play_pause_toggle_enabled = False
        self.session.controls.is_pause_enabled = True
        async def pause():
            self.session.commands.append(('pause',))
            return True
        self.session.try_pause_async = pause
        capabilities = []
        self.monitor.capabilities_updated.connect(capabilities.append)
        await self.monitor.update_media_info()
        self.monitor.toggle_play_pause()
        await self.settle()
        self.assertTrue(capabilities[-1]['play_pause'])
        self.assertEqual(self.session.commands, [('pause',)])

    async def test_invalid_seek_and_transport_exception_report_failure(self):
        await self.monitor.update_media_info()
        self.monitor.seek_to(float('nan'))
        await self.settle()
        async def rejected():
            raise OSError('Fake player disconnected')
        self.session.try_skip_next_async = rejected
        self.monitor.next_track()
        await self.settle()
        self.assertEqual(self.results, [('seek', False), ('next', False)])
        self.assertEqual(self.session.commands, [])

    async def test_hung_command_times_out_without_blocking_later_commands(self):
        await self.monitor.update_media_info()
        async def hung():
            await asyncio.Event().wait()
        self.session.try_skip_next_async = hung
        self.monitor.next_track()
        await asyncio.sleep(4.1)
        self.assertEqual(self.results, [('next', False)])
        self.monitor.seek_to(5)
        await self.settle()
        self.assertEqual(self.results[-1], ('seek', True))

    async def test_preferred_absent_source_falls_back_then_returns(self):
        self.assertTrue(hasattr(self.monitor, 'set_preferred_source'), 'Missing source preference')
        browser = ControlledSession('Chrome.exe')
        self.monitor.set_preferred_source('Chrome.exe')
        await self.monitor.update_media_info()
        self.assertIs(self.monitor.current_session, self.session)
        self.monitor.manager.sessions.append(browser)
        await self.monitor.update_media_info()
        self.assertIs(self.monitor.current_session, browser)
        sources = []
        self.monitor.sources_updated.connect(sources.append)
        self.monitor.manager.sessions.remove(browser)
        await self.monitor.update_media_info()
        self.assertIs(self.monitor.current_session, self.session)
        self.assertEqual(sources[-1], [{'id': 'Spotify.exe', 'name': 'Spotify'}])


class MediaPanelPolishTests(unittest.TestCase):
    def panel(self):
        panel = DashboardPanel()
        panel.show()
        APP.processEvents()
        self.addCleanup(panel.close)
        panel.update_media('Playing', 'Track', 'Artist', '')
        return panel

    def test_controls_disabled_individually_and_timeline_invalidates_seek(self):
        panel = self.panel()
        self.assertTrue(hasattr(panel, 'set_capabilities'), 'Missing UI capabilities')
        panel.set_capabilities({'previous': False, 'play_pause': True, 'next': False, 'seek': True})
        panel.update_timeline(10, 120)
        self.assertFalse(panel.prev.isEnabled())
        self.assertTrue(panel.play.isEnabled())
        self.assertFalse(panel.next.isEnabled())
        self.assertTrue(panel.progress.isEnabled())
        panel.update_timeline(float('nan'), 0)
        self.assertFalse(panel.progress.isEnabled())
        self.assertEqual(panel.duration.text(), '—')

    def test_artwork_crops_square_and_fallback_has_only_one_logo(self):
        panel = self.panel()
        panel.update_source('Spotify.exe')
        data = io.BytesIO()
        Image.new('RGB', (200, 100), 'red').save(data, format='PNG')
        panel.update_artwork(data.getvalue())
        from dashboard_panel import ART
        art = panel.artwork.pixmap()
        # A centred square crop, drawn at twice the pixels for crisp rounded corners.
        self.assertEqual((art.width() / art.devicePixelRatio(), art.height() / art.devicePixelRatio()), (ART, ART))
        for corrupt in (b'bad', b''):
            panel.update_artwork(corrupt)
            self.assertFalse(panel.artwork.pixmap().isNull())
            self.assertTrue(panel.source_badge.isHidden())

    def test_long_unicode_text_has_full_accessibility_and_fixed_geometry(self):
        panel = self.panel()
        before = panel.media_card.geometry()
        title, artist = '東京🎵' * 80, 'मुंबई artist ' * 60
        panel.update_media('Playing', title, artist, '')
        APP.processEvents()
        self.assertEqual(panel.title.accessibleName(), title)
        self.assertEqual(panel.artist.accessibleName(), artist)
        self.assertEqual(panel.media_card.geometry(), before)
        self.assertEqual(panel.title.toolTip(), title)

    def test_seek_drag_resists_poll_and_keyboard_submits(self):
        panel = self.panel()
        self.assertIsInstance(panel.progress, QSlider)
        panel.set_capabilities({'seek': True})
        panel.update_timeline(12, 100)
        values = []
        panel.seek_requested.connect(values.append)
        panel.progress.setSliderDown(True)
        panel.progress.setValue(600)
        panel.update_timeline(13, 100)
        self.assertEqual(panel.progress.value(), 600)
        panel.progress.setSliderDown(False)
        self.assertEqual(values, [60.])
        QTest.keyClick(panel.progress, Qt.Key.Key_Right)
        self.assertGreater(values[-1], 60.)

    def test_source_picker_does_not_emit_during_poll_and_reports_rejection(self):
        panel = self.panel()
        self.assertTrue(hasattr(panel, 'set_sources'), 'Missing source picker')
        values = []
        panel.preferred_source_requested.connect(values.append)
        panel.set_sources([{'id': 'Spotify.exe', 'name': 'Spotify'}])
        self.assertEqual(values, [])
        panel.source_picker.setCurrentIndex(1)
        self.assertEqual(values, ['Spotify.exe'])
        panel.show_transport_result('next', False)
        self.assertFalse(panel.transport_status.isHidden())
        self.assertIn('unavailable', panel.transport_status.text().lower())

    def test_track_change_cancels_drag_instead_of_seeking_new_track(self):
        panel = self.panel()
        panel.set_capabilities({'seek': True})
        panel.update_timeline(10, 100)
        values = []
        panel.seek_requested.connect(values.append)
        panel.progress.setSliderDown(True)
        panel.progress.setValue(800)
        panel.update_media('Playing', 'New track', 'Artist', '')
        panel.update_timeline(0, 200)
        panel.progress.setSliderDown(False)
        self.assertEqual(values, [])
        self.assertEqual(panel.progress.value(), 0)
