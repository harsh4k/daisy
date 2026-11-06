"""Upgrade integration kept separate from the legacy native shell painter."""
import logging
from pathlib import Path

from PyQt6.QtCore import QUrl, QTimer
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication

from app_rules import ForegroundPolicy, RuleGuard
from app_runtime import get_startup_status
from app_styles import get_stylesheet
from runtime_diagnostics import diagnostic_info
from settings_draft import create_draft
from settings_controller import apply_preferences
from settings_window import SettingsDialog
from theme_tokens import get_theme
from tools_panel import ToolsPanel
from notification_inbox import NotificationInbox
from approvals_panel import ApprovalsPanel
from system_card import SystemCard


class OverlayUpgradeMixin:
    def initialize_upgrade(self):
        self.settings = create_draft(self.settings)
        self.app_policy = ForegroundPolicy(self.settings['app_rules'])
        self.game_guard = RuleGuard(self.app_policy, 'hidden')
        self.browser_guard = RuleGuard(self.app_policy, 'click')
        self.restart_requested = False
        self._settings_dialog = None
        self._media_sources = []
        self._timer_compact = False

    def create_tools_panel(self):
        self.tools_panel = ToolsPanel(self.settings.get('shelf_paths', []))
        self.notification_inbox = NotificationInbox()
        self.tools_panel.tabs.addTab(self.notification_inbox, 'Inbox')
        self.approvals_panel = ApprovalsPanel()
        self.tools_panel.approvals_panel = self.approvals_panel
        self.approvals_tab = self.tools_panel.tabs.addTab(self.approvals_panel, 'Approvals')
        # System usage moved here from the island's first page.
        self.system_card = SystemCard()
        self.tools_panel.tabs.addTab(self.system_card, 'System')
        self.tools_panel.minutes.setValue(self.settings['timer_default_minutes'])
        self.tools_panel.set_theme(self.theme)
        self.tools_panel.shelf_changed.connect(self.save_shelf)
        self.tools_panel.timer_changed.connect(self.on_timer_changed)
        self.tools_panel.timer_completed.connect(self.on_timer_completed)
        self.tools_panel.dialog_active.connect(self.on_tool_dialog)
        self.tools_panel.hide()
        return self.tools_panel

    def attach_approval_bridge(self, bridge):
        self.approval_bridge = bridge
        self.approvals_panel.attach_bridge(bridge)
        bridge.changed.connect(self.refresh_approvals)
        bridge.request_received.connect(self.on_approval_requested)
        self.refresh_approvals()

    def refresh_approvals(self):
        count = len(self.approval_bridge.pending())
        self.tools_panel.tabs.setTabText(self.approvals_tab,
            f'Approvals ({count})' if count else 'Approvals')
        self.notification_banner.set_review_available(self.has_pending_approval(
            getattr(self, 'event_title', '')))

    def has_pending_approval(self, sender):
        bridge = getattr(self, 'approval_bridge', None)
        provider = {'Codex': 'codex', 'Claude': 'claude'}.get(sender)
        return bool(bridge is not None and provider and
                    any(item['provider'] == provider for item in bridge.pending()))

    def on_approval_requested(self, record):
        provider = 'Codex' if record['provider'] == 'codex' else 'Claude'
        self.show_notification(provider, 'Permission requested', 'Review in Tools → Approvals')

    def open_approvals(self):
        # Review is navigation only. It cannot answer or broaden a permission.
        self.revert_timer.stop()
        self.tools_panel.tabs.setCurrentWidget(self.approvals_panel)
        bridge = getattr(self, 'approval_bridge', None)
        pending = bridge.pending() if bridge is not None else []
        self.approvals_panel.review(pending[0]['id'] if pending else None)
        if self.browser_mode:
            self.browser_open = True
        self.select_feature('tools')

    def on_tool_dialog(self, active):
        self.is_dialog_open = active
        self.idle_behavior.note_interaction()
        if not active:
            self.rearm_notification_timer()
            self.flush_pending_notification()

    def save_shelf(self, paths):
        previous = self.settings.get('shelf_paths', [])
        self.settings['shelf_paths'] = list(paths)
        if not self.save_settings():
            self.settings['shelf_paths'] = previous
            self.tools_panel.shelf.model.paths = list(previous)
            self.tools_panel.shelf.refresh()

    def on_timer_changed(self):
        active = bool(self.tools_panel.compact_text())
        if active != self._timer_compact:
            self._timer_compact = active
            if self.current_state == 'Idle':
                self.execute_liquid_transition()
        if len(self.nav_buttons) > 4:
            pending = self.tools_panel.completion_pending
            self.nav_buttons[4].setToolTip('Tools — timer complete' if pending else 'Tools')
        self.update_content()

    def on_timer_completed(self):
        self.tools_panel.completion_pending = True
        if (self.current_state == 'Idle' and not self.game_suspended and not self.browser_mode
                and not self.is_dialog_open and not self.is_editing_tasks):
            self.show_notification('Focus timer', 'Complete', 'Your focus session is complete.')

    def update_media_sources(self, sources):
        self._media_sources = sources
        self.dashboard.set_sources(sources)

    def choose_media_source(self, source):
        old = self.settings['preferred_media_source']
        self.settings['preferred_media_source'] = source
        if not self.save_settings():
            self.settings['preferred_media_source'] = old
            self.dashboard.set_preferred_source(old)
            return
        if hasattr(self.media_monitor, 'set_preferred_source'):
            self.media_monitor.set_preferred_source(source)

    def apply_preferences(self, draft):
        return apply_preferences(self, draft)

    def refresh_upgrade_preferences(self):
        settings = self.settings
        self.theme = get_theme(settings['theme'], settings['surface_treatment'])
        self.accent_color = self.theme['accent']
        self.island_style = settings['island_style']
        self.animation_style = settings['animation_style']
        self.compatibility_mode = settings['compatibility_mode']
        self.idle_behavior.set_timeout(settings['autohide_delay'])
        if (self.current_state == 'Hidden' and settings['autohide_delay'] == 0
                and not self.browser_mode and not self.game_suspended):
            self.current_state = 'Idle'
        self.app_policy.set_rules(settings['app_rules'])
        self.setStyleSheet(get_stylesheet(theme=self.theme))
        self.dashboard.set_theme(self.theme)
        self.dashboard.set_preferred_source(settings['preferred_media_source'])
        self.tools_panel.set_theme(self.theme)
        self.tools_panel.minutes.setValue(settings['timer_default_minutes'])
        if hasattr(self.media_monitor, 'set_preferred_source'):
            self.media_monitor.set_preferred_source(settings['preferred_media_source'])
        for dot in self.month_panel.findChildren(type(self.month_panel)):
            if dot.property('monthComplete') is not None:
                color = self.theme['accent'] if dot.property('monthComplete') else self.theme['border']
                dot.setStyleSheet(f'background-color: {color}; border-radius: 6px;')
        self.recenter_window()
        self.execute_liquid_transition()
        self.update_content()
        if hasattr(self, 'runtime_tray'):
            self.runtime_tray.refresh()
        self.apply_visual_preferences()

    def open_settings(self):
        if self._settings_dialog is not None:
            self._settings_dialog.show()
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        self.is_dialog_open = True
        self.revert_timer.stop()
        info = diagnostic_info()
        startup = get_startup_status()
        info.update(path=info['application_path'], startup_status=startup)
        try:
            dialog = SettingsDialog(self.settings, self.apply_preferences, diagnostics=info,
                actions={'restart': self.request_restart, 'logs': self.open_logs,
                         'startup_settings': lambda: QDesktopServices.openUrl(QUrl('ms-settings:startupapps'))},
                media_sources=self._media_sources)
            self._settings_dialog = dialog
            dialog.exec()
        finally:
            self._settings_dialog = None
            self.is_dialog_open = False
            self.idle_behavior.note_interaction()
            self.rearm_notification_timer()
            self.flush_pending_notification()

    def open_logs(self):
        directory = diagnostic_info()['log_directory']
        if directory != 'Unavailable':
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(directory))))

    def request_restart(self):
        logging.getLogger(__name__).info('restart_requested')
        self.restart_requested = True
        if self._settings_dialog is not None:
            self._settings_dialog.reject()
        QTimer.singleShot(0, self.close)
