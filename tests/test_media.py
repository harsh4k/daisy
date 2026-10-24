import asyncio
import datetime as dt
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from media_monitor import MediaMonitor
from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status


class Session:
    def __init__(self, source, status=Status.PLAYING, title="Song"):
        self.source_app_user_model_id = source
        self.status = status
        self.props = NS(title=title, artist="Artist", thumbnail=None)
        self.events = {}
        self.timeline = NS(position=dt.timedelta(seconds=20), start_time=dt.timedelta(),
                           end_time=dt.timedelta(seconds=100),
                           last_updated_time=dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=30))
        self.timeline_reads = 0

    def get_playback_info(self):
        return NS(playback_status=self.status)

    async def try_get_media_properties_async(self):
        return self.props

    def get_timeline_properties(self):
        self.timeline_reads += 1
        return self.timeline

    def __getattr__(self, name):
        if name.startswith("add_"):
            def add(callback):
                token = len(self.events) + 1
                self.events[token] = (name[4:], callback)
                return token
            return add
        if name.startswith("remove_"):
            return lambda token: self.events.pop(token)
        raise AttributeError(name)


class Manager:
    def __init__(self, sessions, current):
        self.sessions, self.current = sessions, current

    def get_current_session(self):
        return self.current

    def get_sessions(self):
        return self.sessions


class MediaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.monitor = MediaMonitor()
        self.monitor.loop = asyncio.get_running_loop()
        self.fetch_patch = patch.object(self.monitor, "fetch_lyrics", new=AsyncMock())
        self.fetch_patch.start()
        self.addCleanup(self.fetch_patch.stop)

    def test_additive_signal_contract(self):
        for name in ("artwork_updated", "timeline_updated", "source_updated"):
            self.assertTrue(hasattr(self.monitor, name), name)

    def test_playing_spotify_wins_over_current_browser(self):
        browser, spotify = Session("Chrome"), Session("Spotify.exe")
        self.monitor.manager = Manager([browser, spotify], browser)
        self.monitor.subscribe_to_current_session()
        self.assertIs(self.monitor.current_session, spotify)

    def test_paused_spotify_does_not_override_playing_current(self):
        browser, spotify = Session("Chrome"), Session("Spotify.exe", Status.PAUSED)
        self.monitor.manager = Manager([browser, spotify], browser)
        self.monitor.subscribe_to_current_session()
        self.assertIs(self.monitor.current_session, browser)

    async def test_same_app_replacement_detaches_old_session(self):
        first, second = Session("Spotify.exe"), Session("Spotify.exe")
        self.monitor.manager = Manager([first], first)
        self.monitor.subscribe_to_current_session()
        self.monitor.manager.sessions = [second]
        self.monitor.manager.current = second
        self.monitor.on_sessions_changed(None, None)
        await asyncio.sleep(0)
        self.monitor.subscribe_to_current_session()
        self.assertIs(self.monitor.current_session, second)
        self.assertEqual(first.events, {})
        self.assertEqual(len(second.events), 3)

    async def test_missing_session_clears_all_visible_state(self):
        self.assertTrue(hasattr(self.monitor, "artwork_updated"))
        artwork, timeline, source, media = [], [], [], []
        self.monitor.artwork_updated.connect(artwork.append)
        self.monitor.timeline_updated.connect(lambda *args: timeline.append(args))
        self.monitor.source_updated.connect(source.append)
        self.monitor.media_updated.connect(lambda *args: media.append(args))
        session = Session("Spotify.exe")
        self.monitor.manager = Manager([session], session)
        await self.monitor.update_media_info()
        self.monitor.manager.sessions = []
        self.monitor.manager.current = None
        self.monitor.subscribe_to_current_session()
        await self.monitor.update_media_info()
        self.assertEqual((artwork[-1], timeline[-1], source[-1]), (b"", (0., 0.), ""))
        self.assertEqual(media[-1][:3], ("Idle", "", ""))
        self.assertEqual(session.events, {})

    async def test_paused_timeline_stays_at_position_and_clamps(self):
        self.assertTrue(hasattr(self.monitor, "timeline_updated"))
        emitted = []
        self.monitor.timeline_updated.connect(lambda *args: emitted.append(args))
        self.monitor.current_session = Session("Spotify.exe", Status.PAUSED)
        self.monitor.last_state = "Paused"
        await self.monitor.check_lyric_sync()
        await self.monitor.check_lyric_sync()
        self.assertEqual(emitted, [(20., 100.), (20., 100.)])
        self.monitor.current_session.timeline.position = dt.timedelta(seconds=150)
        await self.monitor.check_lyric_sync()
        self.assertEqual(emitted[-1], (100., 100.))

    async def test_latest_song_lyrics_are_requested_after_blocked_old_request(self):
        self.fetch_patch.stop()
        session = Session("Spotify.exe", title="Old")
        self.monitor.manager = Manager([session], session)
        started, release = __import__('threading').Event(), __import__('threading').Event()
        requests_seen = []
        def response(*args, **kwargs):
            title = kwargs["params"]["track_name"]
            requests_seen.append(title)
            if title == "Old":
                started.set()
                release.wait(2)
            return NS(status_code=200, json=lambda: {"syncedLyrics": f"[00:00]{title} lyric"}, close=lambda: None)
        with patch("media_monitor.requests.get", side_effect=response):
            try:
                await self.monitor.update_media_info()
                self.assertTrue(await asyncio.to_thread(started.wait, 1))
                session.props.title = "New"
                await self.monitor.update_media_info()
                await asyncio.sleep(.05)
                self.assertEqual(requests_seen, ["Old"], "HTTP jobs must not overlap")
                release.set()
                await asyncio.wait_for(self.monitor._lyric_task, 1)
            finally:
                release.set()
        self.assertEqual(requests_seen, ["Old", "New"])
        self.assertEqual(self.monitor.lyrics, [(0., "New lyric")])


    async def test_idle_then_same_song_restores_source(self):
        sources = []
        self.monitor.source_updated.connect(sources.append)
        session = Session("Spotify.exe")
        self.monitor.manager = Manager([session], session)
        await self.monitor.update_media_info()
        session.status = Status.STOPPED
        await self.monitor.update_media_info()
        session.status = Status.PLAYING
        await self.monitor.update_media_info()
        self.assertEqual(sources[-1], "Spotify.exe")

    async def test_thumbnail_emits_original_bytes_and_closes_stream(self):
        import io
        from PIL import Image
        data = io.BytesIO()
        Image.new("RGB", (2, 2), (60, 120, 180)).save(data, format="PNG")
        original = data.getvalue()
        class Stream:
            size, closed = len(original), False
            def get_input_stream_at(self, offset):
                return self
            def close(self):
                self.closed = True
        stream = Stream()
        class Reader:
            def __init__(self, source):
                pass
            async def load_async(self, size):
                return size
            def read_buffer(self, size):
                return original
            def close(self):
                pass
        session = Session("Spotify.exe")
        session.props.thumbnail = NS(open_read_async=AsyncMock(return_value=stream))
        self.monitor.manager = Manager([session], session)
        artwork = []
        self.monitor.artwork_updated.connect(artwork.append)
        with patch("media_sessions.DataReader", Reader):
            await self.monitor.update_media_info()
        self.assertEqual(artwork[-1], original)
        self.assertTrue(stream.closed)

    async def test_disconnect_clears_source_artwork_and_timeline(self):
        session = Session("Spotify.exe")
        self.monitor.manager = Manager([session], session)
        await self.monitor.update_media_info()
        sources, art, timeline = [], [], []
        self.monitor.source_updated.connect(sources.append)
        self.monitor.artwork_updated.connect(art.append)
        self.monitor.timeline_updated.connect(lambda *args: timeline.append(args))
        async def disconnected():
            raise OSError("remote procedure call failed")
        session.try_get_media_properties_async = disconnected
        await self.monitor.update_media_info()
        self.assertIsNone(self.monitor.current_session)
        self.assertEqual((sources[-1], art[-1], timeline[-1]), ("", b"", (0., 0.)))
        self.assertEqual(session.events, {})

    async def test_playing_timeline_is_clamped_at_track_end(self):
        values = []
        self.monitor.timeline_updated.connect(lambda *args: values.append(args))
        self.monitor.current_session = Session("Spotify.exe")
        self.monitor.last_state = "Playing"
        self.monitor.current_session.timeline.position = dt.timedelta(seconds=90)
        await self.monitor.check_lyric_sync()
        self.assertEqual(values[-1], (100., 100.))


class MediaLifecycleTests(unittest.TestCase):
    def test_stop_before_start_does_not_request_session_access(self):
        monitor = MediaMonitor()
        monitor.stop()
        request = AsyncMock(return_value=Manager([], None))
        with patch("media_monitor.GlobalSystemMediaTransportControlsSessionManager", NS(request_async=request)):
            monitor.start()
            self.assertTrue(monitor.wait(1000))
        self.assertEqual(request.await_count, 0)

    def test_stop_cancels_pending_setup_and_closes_loop(self):
        import threading
        monitor = MediaMonitor()
        entered, finished = threading.Event(), threading.Event()
        async def request():
            entered.set()
            await asyncio.sleep(.8)
            return Manager([], None)
        def stop():
            monitor.stop()
            finished.set()
        with patch("media_monitor.GlobalSystemMediaTransportControlsSessionManager", NS(request_async=request)):
            monitor.start()
            self.assertTrue(entered.wait(2))
            stopper = threading.Thread(target=stop)
            stopper.start()
            stopped_promptly = finished.wait(.3)
            stopper.join(2)
        self.assertTrue(stopped_promptly, "stop must cancel pending async setup")
        self.assertFalse(monitor.isRunning())
        self.assertIsNone(monitor.loop)

    def test_stop_during_blocked_lyrics_is_prompt_and_has_no_late_updates(self):
        import threading
        import time
        from PyQt6.QtCore import Qt
        monitor = MediaMonitor()
        entered, release, returned = threading.Event(), threading.Event(), threading.Event()
        signals = []
        monitor.lyrics_updated.connect(signals.append, Qt.ConnectionType.DirectConnection)
        session = Session("Spotify.exe")
        request = AsyncMock(return_value=Manager([session], session))
        def get(*args, **kwargs):
            entered.set()
            release.wait(1.2)
            returned.set()
            return NS(status_code=200, json=lambda: {"syncedLyrics": "[00:00]Late lyric"}, close=lambda: None)
        with patch("media_monitor.GlobalSystemMediaTransportControlsSessionManager", NS(request_async=request)), patch("media_monitor.requests.get", side_effect=get):
            monitor.start()
            self.assertTrue(entered.wait(2))
            started = time.monotonic()
            stopped = monitor.stop()
            elapsed = time.monotonic() - started
            stopped_signals = list(signals)
            release.set()
            self.assertTrue(returned.wait(1))
            time.sleep(.05)
        self.assertLess(elapsed, .3, "shutdown must not wait for blocked HTTP/DNS")
        self.assertTrue(stopped)
        self.assertFalse(monitor.isRunning())
        self.assertIsNone(monitor.loop)
        self.assertEqual(monitor.lyrics, [])
        self.assertEqual(signals, stopped_signals)
