import datetime
import unittest
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QToolButton
import settle
import stage_wash
import test_hover

APP = test_hover.APP


class StageTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def open_now(self, config=None):
        w = self.window(dict({'motion_mode': 'reduced'}, **(config or {})))
        w.change_state('Hover')
        w.select_feature('dashboard')
        self.assertTrue(settle.settle_shell(w))
        APP.processEvents()
        return w

    def test_home_is_three_cards_and_a_tab_bar(self):
        w = self.open_now()
        self.assertFalse([b for b in w.findChildren(QToolButton) if b.objectName() == 'NavButton'])
        self.assertTrue(w.dashboard.isVisible())
        self.assertTrue(w.tab_bar.isVisible())
        self.assertEqual(list(w.dashboard.glances), ['calendar', 'music', 'tools'])
        for card in w.dashboard.glances.values():
            self.assertTrue(card.isVisible(), card.key)
        xs = [card.x() for card in w.dashboard.glances.values()]
        self.assertEqual(xs, sorted(xs))
        widths = {card.width() for card in w.dashboard.glances.values()}
        self.assertLessEqual(max(widths) - min(widths), 1, 'the three cards are the same size')

    def test_header_shows_date_and_time_and_tab_bar_marks_the_page(self):
        w = self.open_now()
        now = datetime.datetime.now()
        self.assertEqual(w.stage_bar.date.text(), f"{now.strftime('%a')} {now.day} {now.strftime('%b %Y')}")
        self.assertRegex(w.stage_bar.status.text(), r'^\d{1,2}:\d{2} [AP]M$')
        self.assertEqual(w.tab_bar.current, 'dashboard')
        self.assertEqual(w.tab_bar.button('dashboard').text(), 'Home')
        for feature in ('music', 'weather', 'calendar', 'month', 'tools'):
            w.tab_bar.button(feature).click()
            self.assertTrue(settle.settle_shell(w))
            self.assertEqual(w.features[w.current_feature_index], feature)
            self.assertEqual(w.tab_bar.current, feature)
            self.assertTrue(w.tab_bar.button(feature).text(), 'the chosen tab shows its name')
            self.assertFalse(w.tab_bar.button('dashboard').text())
        w.tab_bar.button('dashboard').click()
        self.assertTrue(settle.settle_shell(w))
        self.assertEqual(w.features[w.current_feature_index], 'dashboard')

    def test_every_tab_has_a_tooltip_and_accessible_name(self):
        w = self.open_now()
        for button in w.nav_buttons:
            self.assertTrue(button.toolTip())
            self.assertTrue(button.accessibleName())

    def test_each_card_opens_its_page(self):
        w = self.open_now()
        for key, feature in (('tools', 'tools'), ('calendar', 'calendar'), ('music', 'music')):
            w.select_feature('dashboard')
            self.assertTrue(settle.settle_shell(w))
            w.dashboard.glances[key].click()
            self.assertTrue(settle.settle_shell(w))
            self.assertEqual(w.features[w.current_feature_index], feature)

    def test_cards_show_next_task_music_and_focus(self):
        w = self.open_now({'tasks': [{'name': 'Late review', 'time': '11:59 PM', 'category': 'Work', 'color': '#6aa9ff'}]})
        w.update_media('Paused', 'Midnight City', 'M83', '#1db954')
        w.refresh_glances()
        g = w.dashboard.glances
        self.assertEqual((g['calendar'].label, g['calendar'].title, g['calendar'].detail),
                         ('Next up', 'Late review', 'Today · 11:59 PM'))
        self.assertEqual((g['music'].label, g['music'].title, g['music'].detail), ('Music', 'Midnight City', 'paused'))
        self.assertEqual(g['tools'].label, 'Focus')
        self.assertEqual(g['tools'].title, w.tools_panel.time_text.text())
        self.assertEqual(g['tools'].glyph, 'play')
        w.update_media('Playing', 'Midnight City', 'M83', '#1db954')
        self.assertEqual(g['music'].detail, 'M83')
        self.assertTrue(w.dashboard.play.playing)
        w.update_media('Idle', '', '', '')
        self.assertEqual((g['music'].title, g['music'].detail), ('Nothing playing', 'Play something'))
        self.assertFalse(w.dashboard.play.playing)

    def test_no_task_left_reads_all_clear(self):
        w = self.open_now({'tasks': []})
        w.refresh_glances()
        card = w.dashboard.glances['calendar']
        self.assertEqual((card.title, card.detail), ('All clear', 'No more tasks today'))

    def test_minutes_left_rounds_up_and_survives_bad_text(self):
        import main
        self.assertEqual(main.DynamicIsland.minutes_left('24:56', 25), 25)
        self.assertEqual(main.DynamicIsland.minutes_left('00:01', 25), 1)
        self.assertEqual(main.DynamicIsland.minutes_left('1:00:00', 25), 60)
        self.assertEqual(main.DynamicIsland.minutes_left('soon', 25), 25)

    def test_next_task_is_the_first_still_ahead(self):
        w = self.window({'tasks': [
            {'name': 'Standup', 'time': '10:00 AM', 'category': 'Work', 'color': '#6aa9ff'},
            {'name': 'Gym', 'time': '6:00 PM', 'category': 'Health', 'color': '#5ad19a'},
            {'name': 'Review', 'time': '2:30 PM', 'category': 'Design', 'color': '#c1b7d4'},
            {'name': 'Broken', 'time': 'soon', 'category': 'Task', 'color': '#c1b7d4'}]})
        at = lambda h, m: datetime.datetime(2026, 10, 24, h, m)
        self.assertEqual(w.next_task(at(9, 0))['name'], 'Standup')
        self.assertEqual(w.next_task(at(11, 0))['name'], 'Review')
        self.assertEqual(w.next_task(at(15, 0))['name'], 'Gym')
        self.assertIsNone(w.next_task(at(19, 0)))

    def test_each_page_brings_its_own_light(self):
        w = self.open_now()
        rect = w.get_island_rect()
        point = QPointF(rect.x() + rect.width() * .2, rect.y() + rect.height() * .45)
        def sample():
            image = w.grab().toImage()
            ratio = image.devicePixelRatio()
            return image.pixelColor(round(point.x() * ratio), round(point.y() * ratio))
        self.assertEqual(stage_wash.spots(w, 'dashboard'), (), 'Home is true black; its cards carry the colour')
        colours = {}
        for feature in ('music', 'weather', 'month', 'tools'):
            w.select_feature(feature)
            self.assertTrue(settle.settle_shell(w))
            self.assertEqual(w._wash_page, feature)
            self.assertEqual(w._wash_mix, 1., 'reduced motion switches the light at once')
            self.assertTrue(stage_wash.spots(w, feature))
            colours[feature] = sample().name()
        self.assertEqual(len(set(colours.values())), 4, colours)
        if APP.focusWidget():
            APP.focusWidget().clearFocus()  # focus inside the island keeps it open on purpose
        w.change_state('Idle')
        self.assertTrue(settle.settle_shell(w))
        self.assertEqual(w.current_state, 'Idle')
        self.assertIsNone(w._wash_page, 'the pill carries no page light')

    def test_music_follows_the_album_colour(self):
        w = self.open_now()
        w.update_media('Playing', 'Midnight City', 'M83', '#1db954')
        self.assertEqual(stage_wash.spots(w, 'music')[0][0], QColor('#1db954'))
        self.assertEqual(w.dashboard.glances['music'].wash, QColor('#1db954'))
        self.assertEqual(w.music_page.eyebrow.text(), 'NOW PLAYING')
        w.update_media('Paused', 'Midnight City', 'M83', '#1db954')
        self.assertEqual(w.music_page.eyebrow.text(), 'PAUSED')

    def test_system_usage_moved_to_tools(self):
        w = self.open_now()
        tabs = w.tools_panel.tabs
        labels = [tabs.tabText(i) for i in range(tabs.count())]
        self.assertIn('System', labels)
        w.update_perf({'cpu': 12, 'ram': 48, 'disk': 70, 'down': 0, 'up': 0})
        self.assertEqual(w.system_card.metric_values['ram'].text(), '48%')
        self.assertFalse(hasattr(w.dashboard, 'metric_values'), 'Home no longer shows RAM')

    def test_focus_ring_shows_for_keyboard_only(self):
        w = self.open_now()
        card, tab = w.dashboard.glances['calendar'], w.tab_bar.button('weather')
        w.activateWindow()
        card.setFocus(Qt.FocusReason.MouseFocusReason)
        APP.processEvents()
        self.assertFalse(card.property('keyboard'), 'a click leaves no ring')
        card.clearFocus()
        card.setFocus(Qt.FocusReason.TabFocusReason)
        APP.processEvents()
        self.assertTrue(card.property('keyboard'), 'Tab shows the ring')
        tab.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        APP.processEvents()
        self.assertFalse(tab.property('keyboard'), 'window activation leaves no ring')
        self.assertFalse(card.property('keyboard'))
        self.assertEqual(w.dashboard.play.focusPolicy(), Qt.FocusPolicy.TabFocus)

    def test_play_disc_controls_playback_without_opening_the_music_page(self):
        w = self.open_now()
        calls = []
        w.dashboard.action_requested.disconnect()
        w.dashboard.action_requested.connect(calls.append)
        w.dashboard.play.click()
        self.assertEqual(calls, ['play_pause'])
        self.assertEqual(w.features[w.current_feature_index], 'dashboard')


if __name__ == '__main__':
    unittest.main()
