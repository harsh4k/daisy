"""The battery percentage and charging state are shown, and never break the clock."""
import unittest
from unittest.mock import patch

from PyQt6.QtCore import QPoint, QRect

import test_hover


class BatteryTests(unittest.TestCase):
    window = test_hover.HoverTests.window

    def test_open_island_and_system_tab_show_the_battery_level(self):
        w = self.window({'motion_mode': 'reduced'})
        w.change_state('Hover')
        w.select_feature('dashboard')
        test_hover.APP.processEvents()
        w.publish_battery({'percent': 87, 'plugged': False, 'secsleft': 3600})
        test_hover.APP.processEvents()
        # The top bar carries the level beside the time, as on a Mac menu bar.
        self.assertTrue(w.stage_bar.status.text().startswith('87% · '))
        self.assertTrue(w.stage_bar.battery_icon.isVisible())
        self.assertIn('87 percent', w.stage_bar.status.accessibleName())
        # Tools → System keeps the detailed readout.
        card = w.system_card
        self.assertEqual(card.battery_value.text(), '87%')
        self.assertFalse(card.battery_icon.isHidden())
        self.assertEqual(card.battery_bar.value(), 87)
        self.assertIn('87 percent', card.battery_icon.accessibleName())

    def test_no_battery_is_graceful(self):
        w = self.window({'motion_mode': 'reduced'})
        w.change_state('Hover')
        w.select_feature('dashboard')
        test_hover.APP.processEvents()
        w.publish_battery({'percent': None, 'plugged': False, 'secsleft': None})
        test_hover.APP.processEvents()
        self.assertFalse(w.stage_bar.battery_icon.isVisible())
        self.assertNotIn('%', w.stage_bar.status.text())
        self.assertTrue(w.system_card.battery_icon.isHidden())
        self.assertEqual(w.system_card.battery_value.text(), '—')
        self.assertFalse(w.battery_indicator.isVisible())

    def test_compact_readout_only_while_charging_and_clock_stays_centred(self):
        w = self.window({'motion_mode': 'reduced'})
        w.change_state('Idle')
        test_hover.APP.processEvents()
        w.publish_battery({'percent': 42, 'plugged': False, 'secsleft': 900})
        test_hover.APP.processEvents()
        self.assertFalse(w.battery_indicator.isVisible(),
                         'the idle pill must stay uncluttered')
        w.publish_battery({'percent': 42, 'plugged': True, 'secsleft': 900})
        test_hover.APP.processEvents()
        # The compact pill is only wide enough while the charging island is open.
        self.assertFalse(w.battery_indicator.isVisible())
        w.is_charging = True
        w.update_battery_indicator(w.battery_state)
        test_hover.APP.processEvents()
        self.assertTrue(w.battery_indicator.isVisible())
        self.assertEqual(w.battery_indicator.text(), '42%')
        icon = QRect(w.status_icon.mapTo(w, QPoint()), w.status_icon.size())
        text = QRect(w.status_text.mapTo(w, QPoint()), w.status_text.size())
        group = icon.united(text).united(QRect(w.trailing_slot.mapTo(w, QPoint()), w.trailing_slot.size()))  # leading slot, clock, trailing slot
        shell = w.get_island_rect()
        self.assertLessEqual(abs(group.center().x() - shell.center().x()), 1,
                             'the clock must stay centred next to the readout')

    def test_poll_publishes_a_stable_state(self):
        w = self.window({'motion_mode': 'reduced'})
        battery = type('B', (), {'percent': 64.0, 'power_plugged': False,
                                 'secsleft': 1200})()
        with patch.object(test_hover.main.psutil, 'sensors_battery', return_value=battery):
            w.check_power_status()
            first = w.battery_state
            w.check_power_status()
            self.assertEqual(w.battery_state, first, 'a steady battery must not flicker')
        self.assertEqual(w.battery_state['percent'], 64)
        self.assertFalse(w.battery_state['plugged'])

    def test_missing_battery_is_not_an_error(self):
        w = self.window({'motion_mode': 'reduced'})
        with patch.object(test_hover.main.psutil, 'sensors_battery', return_value=None):
            w.check_power_status()
        self.assertIsNone(w.battery_state)
        with patch.object(test_hover.main.psutil, 'sensors_battery', side_effect=OSError('no sensor')):
            w.check_power_status()
        self.assertIsNone(w.battery_state)


if __name__ == '__main__':
    unittest.main()
