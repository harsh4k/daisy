"""WinRT projects fresh unequal wrappers for the same underlying session."""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch
import test_media
from media_monitor import MediaMonitor


class FreshWrapper:
    def __init__(self, session):
        self.session = session

    def __getattr__(self, name):
        return getattr(self.session, name)


class WrapperManager(test_media.Manager):
    def get_current_session(self):
        return FreshWrapper(self.current) if self.current else None

    def get_sessions(self):
        return [FreshWrapper(session) for session in self.sessions]


class SessionIdentityTests(unittest.IsolatedAsyncioTestCase):
    async def test_fresh_wrappers_keep_current_subscription_and_visible_state(self):
        monitor = MediaMonitor()
        monitor.loop = asyncio.get_running_loop()
        session = test_media.Session('BraveBrowser', title='Netflix')
        monitor.manager = WrapperManager([session], session)
        media, sources, artwork = [], [], []
        monitor.media_updated.connect(lambda *args: media.append(args))
        monitor.source_updated.connect(sources.append)
        monitor.artwork_updated.connect(artwork.append)
        with patch.object(monitor, 'fetch_lyrics', new=AsyncMock()):
            await monitor.update_media_info()
            original = monitor.current_session
            subscriptions = dict(session.events)
            media.clear(); sources.clear(); artwork.clear()
            for _ in range(4):
                await monitor.update_media_info()
                await monitor.check_lyric_sync()
            self.assertIs(monitor.current_session, original)
            self.assertEqual(session.events, subscriptions)
            self.assertEqual((media, sources, artwork), ([], [], []))

    async def test_same_app_manager_event_rebinds_replacement(self):
        monitor = MediaMonitor()
        monitor.loop = asyncio.get_running_loop()
        first, second = test_media.Session('BraveBrowser'), test_media.Session('BraveBrowser')
        monitor.manager = WrapperManager([first], first)
        monitor.subscribe_to_current_session()
        monitor.manager.sessions, monitor.manager.current = [second], second
        monitor.on_sessions_changed(None, None)
        await asyncio.sleep(0)
        monitor.subscribe_to_current_session()
        self.assertEqual(first.events, {})
        self.assertEqual(len(second.events), 3)
        self.assertIs(monitor.current_session.session, second)
