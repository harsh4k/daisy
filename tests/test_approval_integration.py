"""Approvals remain reachable while transient notifications obey app rules."""
import time
import unittest
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtTest import QTest
import test_hover
import settle


class BridgeFixture(QObject):
    changed = pyqtSignal()
    request_received = pyqtSignal(object)
    decided = pyqtSignal(str, str)
    error = ''

    def __init__(self):
        super().__init__()
        self.records = []
        self.answers = []

    def resolve(self, request_id, decision):
        self.answers.append((request_id, decision))
        self.records = [r for r in self.records if r['id'] != request_id]
        self.changed.emit()
        self.decided.emit(request_id, decision)
        return True

    def pending(self):
        return self.records


class ApprovalIntegrationTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def attach(self, window):
        bridge = BridgeFixture()
        window.attach_approval_bridge(bridge)
        record = dict(id='request-one', provider='codex', session_id='fixture-session',
                      cwd='C:/fixture', tool_name='Bash', tool_input={'command': 'echo fixture'},
                      expires_at=time.monotonic() + 120)
        bridge.records = [record]
        bridge.changed.emit()
        return bridge, record

    def test_review_opens_exact_pending_card_without_answering(self):
        window = self.window()
        bridge, record = self.attach(window)
        bridge.request_received.emit(record)
        self.assertEqual(window.current_state, 'Notify')
        self.assertTrue(settle.settle_shell(window))
        # The card now carries Allow and Deny; Details is how you inspect the full request first.
        self.assertTrue(window.notification_banner.allow.isVisible())
        self.assertTrue(window.notification_banner.details.isVisible())
        window.notification_banner.details.click()
        self.assertTrue(settle.settle_shell(window))
        self.assertEqual(window.features[window.current_feature_index], 'tools')
        self.assertIs(window.tools_panel.tabs.currentWidget(), window.approvals_panel)
        self.assertEqual(window.approvals_panel.current_id, 'request-one')
        self.assertEqual(len(bridge.pending()), 1)

    def test_browser_and_game_keep_request_without_expanding(self):
        for attribute in ('browser_mode', 'game_suspended'):
            window = self.window()
            bridge, record = self.attach(window)
            window.current_state = 'Hidden'
            setattr(window, attribute, True)
            bridge.request_received.emit(record)
            self.assertEqual(window.current_state, 'Hidden')
            self.assertEqual(len(bridge.pending()), 1)
            self.assertIn('1', window.tools_panel.tabs.tabText(window.approvals_tab))
