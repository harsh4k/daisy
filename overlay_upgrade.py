"""Upgrade integration kept separate from the legacy native shell painter."""
import logging
import sys
from pathlib import Path

from PyQt6.QtCore import QUrl, QTimer
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication, QMessageBox

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
from approval_setup import frozen_entries, install_hooks
from notification_banner import summarize
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
        bridge.decided.connect(self.on_approval_decided)
        self.refresh_approvals()

    def connect_claude_code(self):
        """Right-click → Connect Claude Code: register Daisy's two hooks, with a backup, after a yes."""
        exe = (Path(sys.executable) if getattr(sys, 'frozen', False)
               else Path(__file__).resolve().parent / 'dist' / 'Daisy.exe')
        if not exe.is_file():
            QMessageBox.information(self, 'Daisy', 'Install Daisy first: the hooks run the installed Daisy.exe.')
            return
        target = Path.home() / '.claude' / 'settings.json'
        self.is_dialog_open = True
        try:
            ask = QMessageBox.question(
                self, 'Connect Claude Code',
                'Daisy will add two hooks to Claude Code:\n\n'
                '- Permission requests: appear on the island with Allow and Deny.\n'
                '- Stop: the eyes look proud when Claude finishes.\n\n'
                f'File: {target}\nA backup is saved beside it. Daisy never allows anything by itself.')
            if ask != QMessageBox.StandardButton.Yes:
                return
            try:
                backup = install_hooks(target, frozen_entries(exe))
            except (OSError, ValueError) as error:
                QMessageBox.warning(self, 'Daisy', f'Could not connect Claude Code: {error}')
                return
            QMessageBox.information(self, 'Daisy', 'Claude Code is connected. Start a new Claude session to use it.'
                                    + (f'\nBackup: {backup}' if backup else '\nIt was already connected.'))
        finally:
            self.is_dialog_open = False

    def attach_event_bridge(self, bridge):
        self.event_bridge = bridge
        bridge.event_received.connect(self.on_agent_event)

    def on_agent_event(self, event):
        """An agent finished its work: the eyes are proud, and a hidden pill comes out to show it."""
        if event.get('event') != 'done' or self.game_suspended:
            return
        self.daisy_eyes.react('proud', 4.5)
        if self.current_state == 'Hidden':
            self.change_state('Idle')
        self.idle_behavior.note_interaction()

    def pending_approval_for(self, sender):
        provider = {'Codex': 'codex', 'Claude': 'claude'}.get(sender)
        bridge = getattr(self, 'approval_bridge', None)
        if bridge is None or provider is None:
            return None
        return next((item for item in bridge.pending() if item['provider'] == provider), None)

    def refresh_approvals(self):
        pending = self.approval_bridge.pending()
        count = len(pending)
        self.tools_panel.tabs.setTabText(self.approvals_tab,
            f'Approvals ({count})' if count else 'Approvals')
        if not count:
            self.daisy_eyes.release('alert')
        sender = getattr(self, 'event_title', '')
        if getattr(self, '_answering', False):
            return  # the answer is on screen; let it finish before the card changes
        self.notification_banner.set_review_available(self.has_pending_approval(sender))
        if self.current_state == 'Notify':
            record = self.pending_approval_for(sender)
            self.notification_banner.set_approval(record)
            if record is None and getattr(self, '_approval_card', False):
                self._approval_card = False
                self.dismiss_notification()  # the request ended (expired or answered elsewhere)

    def has_pending_approval(self, sender):
        bridge = getattr(self, 'approval_bridge', None)
        provider = {'Codex': 'codex', 'Claude': 'claude'}.get(sender)
        return bool(bridge is not None and provider and
                    any(item['provider'] == provider for item in bridge.pending()))

    def on_approval_requested(self, record):
        provider = 'Codex' if record['provider'] == 'codex' else 'Claude'
        self.daisy_eyes.react('alert')   # held wide-eyed until the request is answered or ends
        self._approval_card = True
        # It must reach you even when the island is open: the request expires in two minutes.
        self.show_notification(provider, 'Permission requested', summarize(record), force=True)

    def answer_approval(self, request_id, decision):
        """Allow or Deny pressed on the card: send exactly that answer, then show it landing."""
        self._answering = True
        QTimer.singleShot(1600, lambda: setattr(self, '_answering', False))
        if not self.approval_bridge.resolve(request_id, decision):
            self._answering = False
            self.dismiss_notification()   # it ended before the press: nothing was sent
            return
        self._approval_card = False
        self.notification_banner.show_result(decision)
        self.revert_timer.start(1400)

    def on_approval_decided(self, _request_id, decision):
        """Answered from the card or from Tools → Approvals: Daisy is pleased, or sorry."""
        if decision == 'allow':
            self.daisy_eyes.react('happy', 2.6)
        else:
            self.daisy_eyes.react('sad', 2.4)

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
        self.daisy_eyes.react('happy', 3.5)
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

    def sync_spectrum(self):
        # Listen to the output only while music plays and the bars can be seen.
        # Only a running Daisy listens: never a half-built window, and never a test.
        wanted = (getattr(self, '_monitors_started', False)
                  and self.media_state == 'Playing' and self.isVisible() and not self.game_suspended
                  and not self.reduced_motion and self.current_state in ('Idle', 'Hover'))
        monitor = getattr(self, 'spectrum_monitor', None)
        if wanted and (monitor is None or not monitor.isRunning()):
            if monitor is None:
                import audio_spectrum
                monitor = self.spectrum_monitor = audio_spectrum.SpectrumMonitor(parent=self)
                monitor.levels_ready.connect(self.on_spectrum)
            if not monitor.error:      # an unsupported device is not retried
                monitor.start()
        elif not wanted and monitor is not None and monitor.isRunning():
            monitor.stop()

    def on_spectrum(self, levels):
        self.now_playing.set_levels(levels)
        self.dashboard.spectrum.set_tint(self.ambient_tint())
        self.dashboard.spectrum.set_levels(levels)

    def save_glitch_report(self):
        """Write the last seconds of motion beside the logs and show where it went."""
        import motion_trace
        directory = diagnostic_info()['log_directory']
        if directory == 'Unavailable':
            return None
        try:
            path = motion_trace.save(self, directory)
        except OSError:
            logging.getLogger(__name__).exception('glitch_report_failed')
            return None
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(directory))))
        return path

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
