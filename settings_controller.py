"""One atomic preference commit; preview never enters this persistence path."""
import copy
import json
import os

from app_runtime import (capture_startup_entries, restore_startup_entries, set_autostart)
from app_rules import normalize_rules
from settings_draft import validate_draft, DEFAULTS


def write_preferences(path, settings):
    temporary = path + '.tmp'
    try:
        with open(temporary, 'w', encoding='utf-8') as stream:
            json.dump(settings, stream, indent=4)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def apply_preferences(window, draft):
    if not isinstance(draft, dict):
        return False, 'Choose valid preferences before saving.'
    candidate = copy.deepcopy(window.settings)
    # Only Settings-owned values may replace live data changed while it was open.
    candidate.update({key: copy.deepcopy(value) for key, value in draft.items() if key in DEFAULTS})
    try:
        validate_draft(candidate)
        candidate['app_rules'] = normalize_rules(candidate['app_rules'])
    except (ValueError, TypeError) as error:
        return False, str(error)
    snapshot = None
    startup_changed = candidate['start_with_windows'] != window.settings['start_with_windows']
    try:
        if startup_changed:
            snapshot = capture_startup_entries()
            if not set_autostart(candidate['start_with_windows']):
                restored = restore_startup_entries(snapshot)
                return False, ('Could not change startup settings.' if restored else
                               'Startup could not be changed or restored. Check Windows Startup Settings.')
        write_preferences(window.config_path, candidate)
    except OSError:
        restored = snapshot is None or restore_startup_entries(snapshot)
        return False, ('Could not save preferences. Your previous settings are still active.' if restored else
                       'Could not save preferences or restore startup. Check Windows Startup Settings.')
    window.settings = candidate
    window.refresh_upgrade_preferences()
    return True, ''
