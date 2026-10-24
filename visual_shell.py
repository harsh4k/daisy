"""Live visual preferences and legacy panel typography, without persistence."""
import qtawesome as qta
from PyQt6.QtWidgets import QLabel, QPushButton
from motion_policy import effective_reduced_motion
from theme_tokens import get_theme
from app_styles import get_stylesheet
from ui_tokens import font, font_css
from hover_feedback import install_hover_feedback
from power_menu import refresh_power_menu

# A reduced-motion user still needs to see that Daisy noticed the charger.
STATIC_CHARGING_PHASE = 0.5


def _retint_icon(widget, theme):
    """Repaint a themed icon after a colour change."""
    name = widget.property('daisyIcon')
    if not name:
        return
    if isinstance(widget, QPushButton):
        widget.setIcon(qta.icon(name, color=theme['text']))
        return
    current = widget.pixmap()
    width = current.width() if not current.isNull() else widget.width()
    height = current.height() if not current.isNull() else widget.height()
    widget.setPixmap(qta.icon(name, color=theme['text']).pixmap(width, height))


def style_legacy_panels(window):
    theme = window.theme
    # Weather and Calendar are Stage pages with their own styles.
    window.weather_page.set_theme(theme)
    window.calendar_page.set_theme(theme)
    for panel in (window.calendar_panel, window.perf_panel):
        for label in panel.findChildren(QLabel):
            role = label.property('daisyTypeRole') or 'body'
            muted = label.property('daisyMuted') is True
            accent = label.property('daisyAccent') is True
            color = theme['accent'] if accent else theme['muted'] if muted else theme['text']
            label.setStyleSheet(font_css(role) + f'color: {color}; background: transparent; border: none; padding: 0;')
            label.setFont(font(role))
            _retint_icon(label, theme)
        for button in panel.findChildren(QPushButton):
            if button.objectName() != 'PrimaryAction':
                button.setStyleSheet('')
            _retint_icon(button, theme)
    for label in (window.status_text, window.cpu_label, window.ram_label):
        label.setFont(font('compact' if label is window.status_text else 'time'))
    for values in (window.cpu_bar_L, window.ram_bar_L, window.disk_bar_L):
        values[1].setFont(font('time'))
    for label in (window.net_down_L, window.net_up_L):
        label.setFont(font('time'))


def apply_visual_preferences(window):
    settings = window.settings
    window.theme = get_theme(settings.get('theme'), settings.get('surface_treatment', 'neutral'))
    window.accent_color = window.theme['accent']
    previous_reduced = getattr(window, "reduced_motion", None)
    window.reduced_motion = effective_reduced_motion(settings.get('motion_mode', 'auto'))
    # Decorative motion needs the master switch, a concrete effect and motion allowed.
    window.decorative_motion = (settings.get('decorative_effects_enabled', False) is True
                                and settings.get('animation_style', 'None') != 'None'
                                and not window.reduced_motion)
    window.setStyleSheet(get_stylesheet(theme=window.theme))
    window.dashboard.set_theme(window.theme)
    window.system_card.set_theme(window.theme)
    window.stage_bar.set_theme(window.theme)
    window.tools_panel.set_theme(window.theme)
    if hasattr(window, 'notification_inbox'):
        window.notification_inbox.set_theme(window.theme)
    window.notification_banner.set_theme(window.theme)
    if window.power_buttons and window.power_buttons[0].menu() is not None:
        refresh_power_menu(window.power_buttons[0].menu(), window.theme)
    window.status_icon.set_reduced_motion(window.reduced_motion)
    style_legacy_panels(window)
    if window.decorative_motion:
        window.anim_timer.start(16)
    else:
        window.anim_timer.stop()
        window.shine_anim.stop()
        window.shine_phase = -1.
    if window.reduced_motion:
        for animation in (window.charging_anim, window.weather_bg_anim, window.perf_bg_anim,
                          window.calendar_bg_anim, window.month_bg_anim):
            animation.stop()
        window.charging_phase = STATIC_CHARGING_PHASE if window.is_charging else 0.
    if hasattr(window, 'shell_motion') and previous_reduced != window.reduced_motion:
        window.shell_motion.cancel()
        window.execute_liquid_transition()
    install_hover_feedback(window, window.theme["hover"], window.reduced_motion)
    window.update()
