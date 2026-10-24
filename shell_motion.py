"""Interruptible native shell transitions; content is never scaled.

Every frame does one size update and repaints only the island. Content changes
are drawn from snapshots (content_layer.py): the old picture fades out, the new
one arrives, and the live widgets return when the motion settles.
"""
from PyQt6.QtCore import (QObject, QParallelAnimationGroup, QSequentialAnimationGroup,
                         QPauseAnimation, QVariantAnimation, QEasingCurve)
from ui_tokens import MOTION
import ignite_motion as ignite
import overlay_fit

OUT_CUBIC = QEasingCurve.Type.OutCubic
IN_CUBIC = QEasingCurve.Type.InCubic


class ShellMotion(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.group = QParallelAnimationGroup(self)
        self.target = None
        self.generation = 0

    def cancel(self):
        self.generation += 1
        self.target = None
        self.group.stop()
        ignite.settle(self.window)
        self.window.content_layer.release()
        self.window.content_layer.setOpacity(1.)
        self.window.notification_card.settle()
        overlay_fit.rest(self.window)

    def _clock(self, duration, easing, step, start=0., end=1.):
        clock = QVariantAnimation()
        clock.setStartValue(float(start))
        clock.setEndValue(float(end))
        clock.setDuration(duration)
        clock.setEasingCurve(easing)
        clock.valueChanged.connect(step)
        return clock

    def _fade(self, start, end, duration, easing=OUT_CUBIC):
        return self._clock(duration, easing, self.window.content_layer.setOpacity, start, end)

    def _eased_size(self, start, end, duration):
        window = self.window
        def step(p):
            window.set_island_size(round(start[0] + (end[0] - start[0]) * p),
                                   round(start[1] + (end[1] - start[1]) * p))
        return self._clock(duration, OUT_CUBIC, step)

    def transition(self, key, size, apply_view, reduced=False, force=False):
        if key == self.target and not force:
            return False
        old = self.target
        self.target = key
        self.generation += 1
        generation = self.generation
        self.group.stop()
        self.group.clear()
        window = self.window
        layer = window.content_layer
        ignite.settle(window)

        def apply():
            if generation == self.generation:
                apply_view()
                window.update_island_geometry(window.get_island_rect(), window.get_current_radius())

        def swap(reveal=None):
            """Show the new view as a snapshot, hidden until it is revealed."""
            def run():
                if generation == self.generation:
                    apply()
                    layer.capture()
                    if reveal is None:
                        layer.setOpacity(0.)
                    else:
                        reveal()
            return run

        def finish():
            if generation == self.generation:
                layer.release()
                apply()
                layer.setOpacity(1.)
                ignite.settle(window)
                window.notification_card.settle()
                overlay_fit.rest(window)
        try:
            self.group.finished.disconnect()
        except TypeError:
            pass
        if reduced:
            layer.release()
            apply()
            window.set_island_size(*size)
            layer.setOpacity(1.)
            window.card_motion(key[0], old[0] if old is not None else None, reduced=True)
            overlay_fit.rest(window)
            return True
        state = key[0]
        previous = old[0] if old is not None else None
        page = previous == state == 'Hover' and old[1] != key[1]
        # Leaving the edge line is an opening: it expands and reveals its content.
        restoring = previous == 'Hidden'
        hiding = state == 'Hidden'
        # Shrinking to the compact pill or to the edge line fades the content first.
        shrinking = state == 'Idle' and previous not in (None, 'Hidden', 'Idle')
        fade_close = shrinking or hiding
        edge = hiding or restoring
        duration = MOTION['edge'] if edge else (MOTION['close'] if shrinking else MOTION['open'])
        if page:
            duration = MOTION['page_out'] + MOTION['page_in']
        # Ignite springs every resize between visible shapes; the edge line, page
        # swaps and the first frame keep their quiet eased timing.
        start = (window.island_w, window.island_h)
        # After launch or a cancel there is no previous target; the pill's height says it.
        was_pill = previous == 'Idle' if old is not None else abs(start[1] - window.IDLE_H) <= 8
        from_pill = was_pill and state in ('Hover', 'Notify')
        springy = not (edge or page) and (old is not None or from_pill)
        # The card decides first, so the overlay can make room for it too.
        card = window.card_motion(state, previous, reduced=False)
        # Room for both shapes before the first frame; the overlay never resizes mid-motion.
        overlay_fit.grow_for(window, start, size, springy)
        if springy:
            growing = size[0] * size[1] >= start[0] * start[1]
            profile = (ignite.SQUASH_OPEN if from_pill else ignite.OPEN) if growing else ignite.CLOSE
            geometry = ignite.size_animation(window, start, size, profile)
        else:
            geometry = self._eased_size(start, size, duration)

        if fade_close:
            layer.capture()
            sequence = QSequentialAnimationGroup()
            fade = self._fade(layer.opacity(), 0., MOTION['close_fade'], IN_CUBIC)
            fade.finished.connect(swap())
            sequence.addAnimation(fade)
            sequence.addAnimation(geometry)
            if not hiding:
                sequence.addAnimation(self._fade(0., 1., MOTION['reveal']))
            self.group.addAnimation(sequence)
        elif page:
            layer.capture()
            self.group.addAnimation(geometry)
            sequence = QSequentialAnimationGroup()
            fade = self._fade(layer.opacity(), 0., MOTION['page_out'], IN_CUBIC)
            fade.finished.connect(swap())
            sequence.addAnimation(fade)
            sequence.addAnimation(self._fade(0., 1., MOTION['page_in']))
            self.group.addAnimation(sequence)
        elif old is not None and state == previous:
            # Same state at a new size: the live content stays and the mask follows.
            layer.release()
            layer.setOpacity(1.)
            apply()
            self.group.addAnimation(geometry)
        else:
            # A new state: the old picture leaves as the shell starts to move,
            # then the new picture arrives.
            out_ms = ignite.SQUASH_OPEN['squash'] if springy and from_pill else 60
            layer.capture()
            sequence = QSequentialAnimationGroup()
            fade = self._fade(layer.opacity(), 0., out_ms, IN_CUBIC)
            sequence.addAnimation(fade)
            if springy:
                fade.finished.connect(swap(lambda: ignite.apply_reveal(window, 0.)))
                delay = ignite.REVEAL_DELAY if from_pill else 60
                sequence.addAnimation(QPauseAnimation(max(0, delay - out_ms)))
                sequence.addAnimation(ignite.reveal_animation(window))
            else:
                fade.finished.connect(swap())
                sequence.addAnimation(QPauseAnimation(max(0, duration - MOTION['reveal'] - out_ms)))
                sequence.addAnimation(self._fade(0., 1., MOTION['reveal']))
            self.group.addAnimation(geometry)
            self.group.addAnimation(sequence)
            if springy and from_pill and state == 'Notify':
                # One light runs once around the edge when something arrives;
                # opening the island yourself stays quiet.
                rim = QSequentialAnimationGroup()
                rim.addAnimation(QPauseAnimation(ignite.RIM_DELAY))
                rim.addAnimation(ignite.rim_animation(window))
                self.group.addAnimation(rim)
        if card is not None:
            self.group.addAnimation(card)
        self.group.finished.connect(finish)
        self.group.start()
        return True
