"""Read-only Windows motion preference; unknown system state keeps full motion."""
import ctypes

def windows_animations_enabled():
    try:
        enabled = ctypes.c_int()
        if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0):
            return bool(enabled.value)
    except (AttributeError, OSError):
        pass
    return None

def effective_reduced_motion(mode='auto'):
    if mode == 'reduced':
        return True
    if mode == 'full':
        return False
    return windows_animations_enabled() is False
