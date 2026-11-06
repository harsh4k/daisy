"""The Background Animation and Island Style options must actually change what is drawn."""
import unittest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage
import settle
import test_hover

APP = test_hover.APP
STYLES = ('Glow Sweep', 'Fluid Blobs', 'Neon Border')


def picture(w):
    image = QImage(w.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    w.render(image)
    return image


def changed(a, b):
    return sum(1 for y in range(0, a.height(), 2) for x in range(0, a.width(), 2) if a.pixel(x, y) != b.pixel(x, y))


class AnimationOptionTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def open_in(self, state, style='Default'):
        w = self.window({'motion_mode': 'full', 'island_style': style})
        w.change_state(state)
        self.assertTrue(settle.settle_shell(w, 300))
        w.daisy_eyes.set_reduced_motion(True)  # the eyes breathe; the effect is what is compared
        w.status_icon.set_reduced_motion(True)
        return w

    def test_choosing_an_effect_from_the_menu_turns_effects_on(self):
        w = self.window({'motion_mode': 'full'})
        self.assertFalse(w.settings['decorative_effects_enabled'])
        for style in STYLES:
            w.set_animation_style(style)
            self.assertTrue(w.settings['decorative_effects_enabled'], style)
            self.assertTrue(w.decorative_motion, style)
            self.assertTrue(w.anim_timer.isActive(), style)
        w.set_animation_style('None')
        self.assertFalse(w.settings['decorative_effects_enabled'])
        self.assertFalse(w.decorative_motion)
        self.assertFalse(w.anim_timer.isActive())

    def test_each_effect_moves_on_the_pill_and_on_the_open_island(self):
        for island in ('Default', 'Notch Nook'):
            for state in ('Idle', 'Hover'):
                w = self.open_in(state, island)
                w.set_animation_style('None')
                w.gradient_phase = 0.
                base = picture(w)
                for style in STYLES:
                    w.set_animation_style(style)
                    w.daisy_eyes.set_reduced_motion(True)
                    frames = []
                    for phase in (.1, .4, .7):
                        w.gradient_phase = phase
                        frames.append(picture(w))
                    self.assertGreater(changed(base, frames[0]), 50, (island, state, style, 'draws nothing'))
                    self.assertGreater(changed(frames[0], frames[1]) + changed(frames[1], frames[2]), 20,
                                       (island, state, style, 'does not move'))

    def test_effects_are_drawn_inside_the_island(self):
        w = self.open_in('Idle')
        w.set_animation_style('None')
        base = picture(w)
        rect = w.get_island_rect().toAlignedRect().adjusted(-2, -2, 2, 2)
        for style in STYLES:
            w.set_animation_style(style)
            w.daisy_eyes.set_reduced_motion(True)
            w.gradient_phase = .3
            image = picture(w)
            for y in range(0, image.height(), 2):
                for x in range(0, image.width(), 2):
                    if not rect.contains(x, y):
                        self.assertEqual(image.pixel(x, y), base.pixel(x, y), (style, x, y))

    def test_liquid_glass_is_a_see_through_shell_unlike_default(self):
        flat = self.open_in('Hover', 'Default')
        glass = self.open_in('Hover', 'Liquid Glass')
        rect = glass.get_island_rect()
        x, y = round(rect.center().x()), round(rect.bottom() - 6)
        self.assertEqual(picture(flat).pixelColor(x, y).alpha(), 255)
        self.assertLess(picture(glass).pixelColor(x, y).alpha(), 255, 'glass lets the desktop through')
        self.assertGreater(changed(picture(flat), picture(glass)), 500)


if __name__ == '__main__':
    unittest.main()
