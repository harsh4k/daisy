import asyncio
from PyQt6.QtCore import QThread, pyqtSignal
from winsdk.windows.ui.notifications.management import UserNotificationListener, UserNotificationListenerAccessStatus

from notification_inbox import NotificationRecord

class NotificationMonitor(QThread):
                                   
    notification_received = pyqtSignal(str, str, str)
    # Additive: the inbox needs the exact app id, not only a display name.
    notification_recorded = pyqtSignal(object)
    access_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = True
        self.loop = None
        self.listener = None
        self._task = None

    def run(self):
        if not self._is_running:
            return
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self._task = self.loop.create_task(self.setup_listener())
            if not self._is_running:
                self._task.cancel()
            self.loop.run_until_complete(self._task)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print("NotificationMonitor setup error:", e)
        finally:
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                task.cancel()
            if pending:
                self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()
            asyncio.set_event_loop(None)
            self.listener = None

    async def setup_listener(self):
        try:
            from winsdk.windows.foundation.metadata import ApiInformation
            if not ApiInformation.is_type_present("Windows.UI.Notifications.Management.UserNotificationListener"):
                self.access_changed.emit('This Windows build does not publish notifications to listeners.')
                return

            self.listener = UserNotificationListener.current
            if not self.listener:
                self.access_changed.emit('Windows did not provide a notification listener.')
                return

            access_status = await asyncio.wait_for(self.listener.request_access_async(), 10)
            if access_status != UserNotificationListenerAccessStatus.ALLOWED:
                self.access_changed.emit('Notification access is off. Allow Daisy in Windows Settings > Privacy & security > Notifications.')
                return
            self.access_changed.emit('Only notifications published to Windows are shown.')
        except Exception as e:
            print(f"Notification setup error: {e}")
            return

                                                                                       
                                                                                 
                                                 
        
        known_ids = set()
                        
        initial = await asyncio.wait_for(self.listener.get_notifications_async(0x1), 5)
        for n in initial:
            known_ids.add(n.id)

        while self._is_running:
            try:
                notifications = await asyncio.wait_for(self.listener.get_notifications_async(0x1), 5)
                current_ids = {n.id for n in notifications}
                for n in notifications:
                    if n.id not in known_ids:
                        known_ids.add(n.id)
                        try:
                            app_name = n.app_info.display_info.display_name
                                           
                            bindings = n.notification.visual.bindings
                            title = ""
                            body = ""
                            for b in bindings:
                                text_elements = b.get_text_elements()
                                if len(text_elements) > 0: title = text_elements[0].text
                                if len(text_elements) > 1: body = text_elements[1].text
                            
                            self.notification_received.emit(app_name, title, body)
                            # The exact package family name, never a body match.
                            app_id = ''
                            try:
                                app_id = str(n.app_info.package_family_name or '')
                            except Exception:
                                app_id = ''
                            self.notification_recorded.emit(NotificationRecord(
                                identifier=str(n.id or ''), app_id=app_id, app_name=app_name,
                                title=title, body=body))
                        except Exception: pass
                known_ids.intersection_update(current_ids)
            except Exception: pass
            await asyncio.sleep(1.0)                                    

    def stop(self):
        self._is_running = False
        if self.loop and not self.loop.is_closed():
            try:
                self.loop.call_soon_threadsafe(self._cancel_pending)
            except RuntimeError:
                pass  # The worker finished and closed its loop concurrently.
        return self.wait(1000)

    def _cancel_pending(self):
        if self._task and not self._task.done():
            self._task.cancel()

