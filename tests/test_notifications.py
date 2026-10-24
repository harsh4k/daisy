import asyncio
import threading
import time
import unittest
import sys
import types
from unittest.mock import patch
from winsdk.windows.ui.notifications.management import UserNotificationListenerAccessStatus

from notification_monitor import NotificationMonitor


class SlowNotificationMonitor(NotificationMonitor):
    def __init__(self):
        super().__init__()
        self.entered = threading.Event()
        self.cancelled = threading.Event()

    async def setup_listener(self):
        self.entered.set()
        try:
            await asyncio.sleep(.5)
        except asyncio.CancelledError:
            self.cancelled.set()
            raise


class NotificationTests(unittest.TestCase):
    def test_stop_cancels_notification_poll_without_extra_sleep(self):
        entered = threading.Event()
        class Listener:
            calls = 0
            async def request_access_async(self):
                return UserNotificationListenerAccessStatus.ALLOWED
            async def get_notifications_async(self, _kind):
                self.calls += 1
                if self.calls == 1:
                    return []
                entered.set()
                await asyncio.sleep(30)
        metadata = types.ModuleType('winsdk.windows.foundation.metadata')
        metadata.ApiInformation = types.SimpleNamespace(is_type_present=lambda _: True)
        monitor = NotificationMonitor()
        with patch('notification_monitor.UserNotificationListener', types.SimpleNamespace(current=Listener())), patch.dict(sys.modules, {'winsdk.windows.foundation.metadata': metadata}):
            monitor.start()
            try:
                self.assertTrue(entered.wait(1))
                started = time.monotonic()
                self.assertTrue(monitor.stop())
                self.assertLess(time.monotonic() - started, .5)
                self.assertFalse(monitor.isRunning())
            finally:
                monitor.stop()
                monitor.wait(2000)

    def test_stop_cancels_pending_setup_and_closes_loop(self):
        monitor = SlowNotificationMonitor()
        monitor.start()
        self.assertTrue(monitor.entered.wait(1))
        started = time.monotonic()
        monitor.stop()
        self.assertLess(time.monotonic() - started, .25)
        self.assertFalse(monitor.isRunning())
        self.assertTrue(monitor.cancelled.is_set())
        self.assertTrue(monitor.loop.is_closed())

    def test_stop_before_start_does_not_open_notification_access(self):
        monitor = SlowNotificationMonitor()
        monitor.stop()
        monitor.start()
        monitor.wait(1500)
        self.assertFalse(monitor.entered.is_set())
        self.assertFalse(monitor.isRunning())


if __name__ == "__main__":
    unittest.main()

