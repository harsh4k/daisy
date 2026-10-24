"""One power menu for Daisy, with destructive entries marked by the danger token."""
import qtawesome as qta
from PyQt6.QtWidgets import QMenu

# label, action id, icon, destructive
POWER_ACTIONS = (('Sleep', 'sleep', 'ph.moon', False),
                 ('Restart PC', 'restart', 'ph.arrow-clockwise', True),
                 ('Shut down', 'shutdown', 'ph.power', True))


def build_power_menu(parent, theme, on_action, on_open=None, on_close=None):
    """Build the single power menu; destructive entries carry the danger colour."""
    menu = QMenu(parent)
    menu.setObjectName('PowerMenu')
    for label, action, icon, destructive in POWER_ACTIONS:
        item = menu.addAction(label)
        item.setData(action)
        item.setIcon(qta.icon(icon, color=theme['danger'] if destructive else theme['text']))
        item.triggered.connect(lambda _checked=False, value=action: on_action(value))
    if on_open is not None:
        menu.aboutToShow.connect(on_open)
    if on_close is not None:
        menu.aboutToHide.connect(on_close)
    return menu


def refresh_power_menu(menu, theme):
    """Re-tint the power menu after a theme change."""
    for item, (_, _, icon, destructive) in zip(menu.actions(), POWER_ACTIONS):
        item.setIcon(qta.icon(icon, color=theme['danger'] if destructive else theme['text']))
