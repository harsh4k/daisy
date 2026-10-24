import datetime
import unittest
from PyQt6.QtCore import QPoint, QPointF
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

    def test_no_icon_dock_remains(self):
        w = self.open_now()
        self.assertFalse([b for b in w.findChildren(QToolButton) if b.objectName() == 'NavButton'])
        self.assertTrue(w.dashboard.isVisible())
        self.assertTrue(w.dashboard.glance_column.isVisible())

    def test_crumb_reads_now_at_home_and_leads_back_from_any_page(self):
        w = self.open_now()
        crumb = w.stage_bar.crumb
        self.assertEqual(crumb.text(), 'Now')
        self.assertTrue(crumb.property('home'))
        for feature in ('weather', 'calendar', 'month', 'tools'):
            w.select_feature(feature)
            self.assertTrue(settle.settle_shell(w))
            self.assertFalse(crumb.property('home'), feature)
            self.assertEqual(crumb.toolTip(), 'Back to Now')
            crumb.click()
            self.assertTrue(settle.settle_shell(w))
            self.assertEqual(w.features[w.current_feature_index], 'dashboard')

    def test_each_glance_opens_its_page(self):
        w = self.open_now()
        for key, feature in (('tools', 'tools'), ('calendar', 'calendar'), ('month', 'month'), ('weather', 'weather')):
            w.select_feature('dashboard')
            self.assertTrue(settle.settle_shell(w))
            w.dashboard.glances[key].click()
            self.assertTrue(settle.settle_shell(w))
            self.assertEqual(w.features[w.current_feature_index], feature)

    def test_glances_show_focus_next_task_date_and_weather(self):
        w = self.open_now({'tasks': [{'name': 'Late review', 'time': '11:59 PM', 'category': 'Work', 'color': '#6aa9ff'}]})
        w.update_weather({'temp': '31°', 'city': 'Mumbai', 'desc': 'Partly cloudy', 'hourly': []})
        w.refresh_glances()
        g = w.dashboard.glances
        self.assertEqual(g['tools'].heading.full_text, 'Focus')
        self.assertEqual(g['tools'].value.text(), w.tools_panel.time_text.text())
        self.assertEqual(g['calendar'].heading.full_text, 'Late review')
        self.assertEqual(g['calendar'].detail.full_text, 'Today · 11:59 PM')
        now = datetime.datetime.now()
        self.assertEqual(g['month'].heading.full_text, f"{now.strftime('%A')} {now.day}")
        self.assertEqual(g['weather'].heading.full_text, 'Mumbai')
        self.assertEqual(g['weather'].value.text(), '31°')

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
        colours = {}
        for feature in ('dashboard', 'weather', 'month', 'tools'):
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

    def test_now_page_follows_the_album_colour(self):
        w = self.open_now()
        w.update_media('Playing', 'Midnight City', 'M83', '#1db954')
        self.assertEqual(stage_wash.spots(w, 'dashboard')[0][0], QColor('#1db954'))
        self.assertEqual(w.dashboard.eyebrow.text(), 'NOW PLAYING')
        w.update_media('Paused', 'Midnight City', 'M83', '#1db954')
        self.assertEqual(w.dashboard.eyebrow.text(), 'PAUSED')

    def test_system_usage_moved_to_tools(self):
        w = self.open_now()
        tabs = w.tools_panel.tabs
        labels = [tabs.tabText(i) for i in range(tabs.count())]
        self.assertIn('System', labels)
        w.update_perf({'cpu': 12, 'ram': 48, 'disk': 70, 'down': 0, 'up': 0})
        self.assertEqual(w.system_card.metric_values['ram'].text(), '48%')
        self.assertFalse(hasattr(w.dashboard, 'metric_values'), 'Now no longer shows RAM')


    def test_focus_ring_shows_for_keyboard_only(self):
        from PyQt6.QtCore import Qt
        w = self.open_now()
        crumb, glance = w.stage_bar.crumb, w.dashboard.glances['weather']
        w.activateWindow()
        glance.setFocus(Qt.FocusReason.MouseFocusReason)
        APP.processEvents()
        self.assertFalse(glance.property('keyboard'), 'a click leaves no ring')
        glance.clearFocus()
        glance.setFocus(Qt.FocusReason.TabFocusReason)
        APP.processEvents()
        self.assertTrue(glance.property('keyboard'), 'Tab shows the ring')
        crumb.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        APP.processEvents()
        self.assertFalse(crumb.property('keyboard'), 'window activation leaves no ring')
        self.assertFalse(glance.property('keyboard'))
        self.assertEqual(w.dashboard.play.focusPolicy(), Qt.FocusPolicy.TabFocus)


if __name__ == '__main__':
    unittest.main()
