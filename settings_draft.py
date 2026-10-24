"""Detached preference drafts; persistence belongs to the application controller."""
from copy import deepcopy

from app_rules import normalize_rules
from idle_icon import ICON_STYLES
from theme_tokens import THEMES

CHOICES = {
    'theme': tuple(THEMES),
    'island_style': ('Default', 'Liquid Glass', 'Notch Nook'),
    'animation_style': ('None', 'Glow Sweep', 'Fluid Blobs', 'Neon Border'),
    'idle_icon': ICON_STYLES,
    'surface_treatment': ('neutral', 'tinted'),
    'motion_mode': ('auto', 'full', 'reduced'),
}
DEFAULTS = dict(theme='Dark Matter', island_style='Default', animation_style='Fluid Blobs',
    notification_inbox_enabled=False,
    surface_treatment='neutral', motion_mode='auto', decorative_effects_enabled=False,
    idle_icon='Clock', custom_idle_icon='', autohide_delay=10, compatibility_mode=False,
    start_with_windows=True, app_rules={}, preferred_media_source='', timer_default_minutes=25)


def create_draft(settings):
    draft = deepcopy(settings) if isinstance(settings, dict) else {}
    for key, default in DEFAULTS.items():
        value = draft.get(key, deepcopy(default))
        if key in CHOICES:
            value = value if isinstance(value, str) and value in CHOICES[key] else default
        elif key == 'app_rules':
            try:
                value = normalize_rules(value)
            except ValueError:
                value = {}
        elif key == 'autohide_delay':
            value = value if type(value) is int and value in (0, 5, 10, 30) else default
        elif key == 'timer_default_minutes':
            value = value if type(value) is int and 1 <= value <= 180 else default
        elif type(value) is not type(default):
            value = deepcopy(default)
        draft[key] = value
    return draft


def validate_draft(draft):
    if not isinstance(draft, dict):
        raise ValueError('Settings must be a preference dictionary.')
    normalize_rules(draft.get('app_rules'))
    for key, choices in CHOICES.items():
        if not isinstance(draft.get(key), str) or draft[key] not in choices:
            raise ValueError('Choose a valid ' + key.replace('_', ' ') + '.')
    if type(draft.get('autohide_delay')) is not int or draft['autohide_delay'] not in (0, 5, 10, 30):
        raise ValueError('Choose Off, 5, 10, or 30 seconds for auto-hide.')
    for key in ('compatibility_mode', 'start_with_windows', 'decorative_effects_enabled',
                'notification_inbox_enabled'):
        if type(draft.get(key)) is not bool:
            raise ValueError('Choose an on or off value for ' + key.replace('_', ' ') + '.')
    for key in ('preferred_media_source', 'custom_idle_icon'):
        if not isinstance(draft.get(key), str):
            raise ValueError('Choose a valid ' + key.replace('_', ' ') + '.')
    if type(draft.get('timer_default_minutes')) is not int or not 1 <= draft['timer_default_minutes'] <= 180:
        raise ValueError('Focus timer must be between 1 and 180 minutes.')
    if draft.get('idle_icon') == 'Custom GIF':
        # Same decoder as production, with no running timer or filesystem writes.
        from idle_icon import IdleIcon
        icon = IdleIcon()
        icon.set_active(False)
        valid = icon.set_style('Custom GIF', draft.get('custom_idle_icon', ''))
        icon.deleteLater()
        if not valid:
            raise ValueError('Choose a readable, valid GIF file for the custom idle icon.')
