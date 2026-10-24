"""Permission review binds deliberate button presses to exact live requests."""
import json
import time
import unittest

from PyQt6.QtCore import QObject, Qt, QEvent, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton

from approvals_panel import ApprovalsPanel
from theme_tokens import get_theme

APP = QApplication.instance() or QApplication([])


def request(identifier='one'):
    return dict(id=identifier, provider='codex', session_id='session-one',
                cwd='C:/example', tool_name='Bash',
                tool_input={'command': 'echo <b>hello</b>\u202e\nnext'},
                expires_at=time.monotonic() + 120)


class Bridge(QObject):
    changed = pyqtSignal()

    def __init__(self, records):
        super().__init__()
        self.records = records
        self.answers = []
        self.error = ''

    def pending(self):
        return list(self.records)

    def resolve(self, identifier, answer):
        self.answers.append((identifier, answer))
        matching = [r for r in self.records if r['id'] == identifier]
        if not matching or matching[0]['expires_at'] <= time.monotonic():
            return False
        self.records = [r for r in self.records if r['id'] != identifier]
        self.changed.emit()
        return True


class ApprovalPanelTests(unittest.TestCase):
    def panel(self, records):
        panel = ApprovalsPanel()
        bridge = Bridge(records)
        panel.attach_bridge(bridge)
        panel.resize(500, 168)
        panel.show()
        APP.processEvents()
        self.addCleanup(panel.close)
        return panel, bridge

    def test_exact_escaped_plain_json_and_real_provider_mark(self):
        item = request()
        panel, _ = self.panel([item])
        self.assertEqual(panel.details.toPlainText(), json.dumps(item['tool_input'], ensure_ascii=True, indent=2))
        self.assertTrue(panel.details.isReadOnly())
        self.assertNotIn('\u202e', panel.details.toPlainText())
        self.assertFalse(panel.provider_icon.pixmap().isNull())
        for bar in (panel.details.horizontalScrollBarPolicy(), panel.details.verticalScrollBarPolicy()):
            self.assertEqual(bar, Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def test_compact_geometry_and_keyboard_actions(self):
        panel, bridge = self.panel([request()])
        for width in (500, 576):
            panel.resize(width, 168)
            APP.processEvents()
            self.assertLessEqual(panel.minimumSizeHint().height(), 168)
            for button in panel.findChildren(QPushButton):
                self.assertGreaterEqual(button.height(), 32)
                self.assertTrue(panel.rect().contains(button.geometry()))
                self.assertTrue(button.accessibleName())
        panel.allow_button.setFocus()
        QTest.keyClick(panel.allow_button, Qt.Key.Key_Space)
        self.assertEqual(bridge.answers, [('one', 'allow')])

    def test_identical_requests_are_distinct_and_navigation_selects_exact_id(self):
        panel, bridge = self.panel([request('one'), request('two')])
        panel.review('two')
        panel.deny_button.click()
        self.assertEqual(bridge.answers, [('two', 'deny')])
        self.assertEqual(panel.current_id, 'one')

    def test_changed_queue_during_press_never_approves_replacement(self):
        panel, bridge = self.panel([request('one')])
        QTest.mousePress(panel.allow_button, Qt.MouseButton.LeftButton)
        bridge.records = [request('replacement')]
        bridge.changed.emit()
        QTest.mouseRelease(panel.allow_button, Qt.MouseButton.LeftButton)
        self.assertNotIn(('replacement', 'allow'), bridge.answers)
        self.assertTrue(all(identifier == 'one' for identifier, _ in bridge.answers))

    def test_double_click_cannot_approve_automatically_selected_next_request(self):
        panel, bridge = self.panel([request('one'), request('two')])
        QTest.mouseClick(panel.allow_button, Qt.MouseButton.LeftButton)
        QTest.mouseDClick(panel.allow_button, Qt.MouseButton.LeftButton)
        QTest.mouseRelease(panel.allow_button, Qt.MouseButton.LeftButton)
        self.assertEqual(bridge.answers, [('one', 'allow')])
        self.assertFalse(panel.allow_button.isEnabled())
        self.assertFalse(panel.deny_button.isEnabled())
        self.assertTrue(panel.next_button.isEnabled())
        panel.next_button.click()
        panel.allow_button.click()
        self.assertEqual(bridge.answers, [('one', 'allow'), ('two', 'allow')])

    def test_repeated_space_and_bridge_updates_require_explicit_review(self):
        panel, bridge = self.panel([request('one'), request('two')])
        panel.allow_button.setFocus()
        QTest.keyClick(panel.allow_button, Qt.Key.Key_Space)
        for _ in range(3):
            bridge.changed.emit()
            QTest.keyClick(panel.allow_button, Qt.Key.Key_Space)
            for event_type in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
                APP.sendEvent(panel.allow_button, QKeyEvent(
                    event_type, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier,
                    ' ', True, 2))
        self.assertEqual(bridge.answers, [('one', 'allow')])
        self.assertFalse(panel.allow_button.isEnabled())
        panel.review('two')
        self.assertTrue(panel.allow_button.isEnabled())

    def test_review_guard_survives_empty_queue_until_explicit_review(self):
        panel, bridge = self.panel([request('one')])
        panel.allow_button.click()
        bridge.records = [request('new')]
        bridge.changed.emit()
        self.assertFalse(panel.allow_button.isEnabled())
        self.assertIn('Review next', panel.caption.text())
        panel.review('unknown')
        self.assertFalse(panel.allow_button.isEnabled())
        panel.review('new')
        self.assertTrue(panel.allow_button.isEnabled())

    def test_expired_requests_and_disconnection_disable_actions(self):
        item = request()
        item['expires_at'] = time.monotonic() - 1
        panel, bridge = self.panel([item])
        self.assertFalse(panel.allow_button.isEnabled())
        self.assertFalse(panel.deny_button.isEnabled())
        panel.attach_bridge(None)
        panel.allow_button.click()
        self.assertFalse(bridge.answers)
        self.assertIn('No pending', panel.empty_text.text())

    def test_themes_and_error_are_visible_without_rich_text(self):
        panel, bridge = self.panel([])
        for name in ('Dark Matter', 'Graphite', 'Amethyst', 'Midnight', 'Rose'):
            panel.set_theme(get_theme(name, 'tinted'))
            self.assertIn(get_theme(name, 'tinted')['danger'], panel.styleSheet())
        bridge.error = '<b>Connection unavailable</b>'
        bridge.changed.emit()
        self.assertIn('Connection unavailable', panel.empty_text.text())
        self.assertEqual(panel.empty_text.textFormat(), Qt.TextFormat.PlainText)

    def test_long_arguments_remain_inspectable_with_hidden_scrollbars(self):
        item = request()
        item['tool_input'] = {'lines': [f'argument-{i}' for i in range(200)]}
        panel, _ = self.panel([item])
        panel.details.setFocus()
        QTest.keyClick(panel.details, Qt.Key.Key_PageDown)
        APP.processEvents()
        self.assertGreater(panel.details.verticalScrollBar().value(), 0)
        self.assertIn('argument-199', panel.details.toPlainText())


if __name__ == '__main__':
    unittest.main()
