"""The notification inbox keeps what Windows published, and only when asked."""
import unittest

from PyQt6.QtWidgets import QApplication

import test_hover


class NotificationInboxTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def record(self, app='Discord', title='A message', body='Hello', identifier=''):
        from notification_inbox import NotificationRecord
        return NotificationRecord(identifier=identifier, app_id=f'{app}.app_1',
                                  app_name=app, title=title, body=body)

    def test_records_are_kept_bounded_and_deduplicated(self):
        from notification_inbox import MAX_ITEMS, NotificationInbox
        inbox = NotificationInbox()
        self.addCleanup(inbox.close)
        self.assertTrue(inbox.add(self.record()))
        self.assertFalse(inbox.add(self.record()), 'a repeat must not be stored twice')
        for index in range(MAX_ITEMS + 10):
            inbox.add(self.record(title=f'Title {index}', identifier=str(index)))
        self.assertLessEqual(len(inbox.records()), MAX_ITEMS)
        self.assertEqual(inbox.records()[0].title, f'Title {MAX_ITEMS + 9}')

    def test_unread_count_read_and_clear(self):
        from notification_inbox import NotificationInbox
        inbox = NotificationInbox()
        self.addCleanup(inbox.close)
        inbox.add(self.record())
        inbox.add(self.record(title='Another'))
        self.assertEqual(inbox.unread_count(), 2)
        inbox.mark_all_read()
        self.assertEqual(inbox.unread_count(), 0)
        inbox.clear()
        self.assertEqual(inbox.records(), [])

    def test_app_filter_narrows_the_list(self):
        from notification_inbox import NotificationInbox
        inbox = NotificationInbox()
        self.addCleanup(inbox.close)
        inbox.add(self.record(app='Discord'))
        inbox.add(self.record(app='WhatsApp', title='Hi'))
        self.assertEqual(inbox.list.count(), 2)
        index = inbox.filter_combo.findData('WhatsApp')
        inbox.filter_combo.setCurrentIndex(index)
        self.assertEqual(inbox.list.count(), 1)
        self.assertIn('WhatsApp', inbox.list.item(0).text())

    def test_the_inbox_stays_empty_until_it_is_enabled(self):
        w = self.window({'motion_mode': 'reduced'})
        self.assertFalse(w.settings.get('notification_inbox_enabled'))
        w.record_notification(self.record())
        self.assertEqual(w.notification_inbox.records(), [])
        w.settings['notification_inbox_enabled'] = True
        w.record_notification(self.record())
        self.assertEqual(len(w.notification_inbox.records()), 1)
        self.assertEqual(w.notification_inbox.records()[0].app_name, 'Discord')

    def test_the_inbox_is_part_of_the_tools_view(self):
        w = self.window({'motion_mode': 'reduced'})
        labels = [w.tools_panel.tabs.tabText(i) for i in range(w.tools_panel.tabs.count())]
        self.assertIn('Inbox', labels)

    def test_access_state_is_explained(self):
        from notification_inbox import NotificationInbox
        inbox = NotificationInbox()
        self.addCleanup(inbox.close)
        inbox.set_access_note('Notification access is off.')
        self.assertIn('access is off', inbox.note.text())


if __name__ == '__main__':
    unittest.main()
