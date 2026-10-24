"""Wait for animations to finish instead of guessing durations."""
from PyQt6.QtCore import QAbstractAnimation
from PyQt6.QtTest import QTest


def wait_for_animation(animation, timeout_ms=3000):
    """Block until an animation stops running. Returns False on timeout."""
    waited = 0
    while waited < timeout_ms:
        if animation.state() != QAbstractAnimation.State.Running:
            return True
        QTest.qWait(10)
        waited += 10
    return False


def wait_for_shell(window, timeout_ms=3000):
    """Block until the shell transition group settles."""
    return wait_for_animation(window.anim_group, timeout_ms)


def settle_shell(window, extra_ms=30):
    """Wait for the shell to settle, then let the final frame paint."""
    finished = wait_for_shell(window)
    QTest.qWait(extra_ms)
    return finished
