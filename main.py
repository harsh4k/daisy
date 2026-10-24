import sys
if __name__ == '__main__' and len(sys.argv) == 3 and sys.argv[1] == '--daisy-fatal-sink':
    from runtime_fatal import run_sink_command
    raise SystemExit(run_sink_command(sys.argv))

import psutil
import winreg
import ctypes
import datetime
import math
import qtawesome as qta
from PyQt6.QtCore import Qt, QTimer, QRect, QRectF, QPropertyAnimation, QEasingCurve, QPoint, QParallelAnimationGroup, QPointF, QSize, pyqtProperty
from PyQt6.QtGui import (QCursor, QPainter, QColor, QBrush, QPaintEvent, 
                         QLinearGradient, QRadialGradient, QConicalGradient, QAction, QPen, QPainterPath, QRegion, QPixmap)
import json
import os
import webbrowser
import subprocess

from app_styles import get_stylesheet
from dashboard_panel import DashboardPanel
from media_widgets import ElidedLabel
from idle_behavior import IdleBehavior
from shell_motion import ShellMotion
import ignite_motion
from content_layer import ContentLayer
import overlay_fit
from motion_policy import effective_reduced_motion
from visual_shell import apply_visual_preferences, style_legacy_panels, STATIC_CHARGING_PHASE
from overlay_upgrade import OverlayUpgradeMixin
from idle_icon import IdleIcon, ICON_STYLES
from aurora import AudioBars
from stage_bar import StageBar, HEIGHT as BAR_HEIGHT
from stage_pages import WeatherPage, CalendarPage
import stage_wash
from theme_tokens import THEMES, get_theme
from ui_tokens import SPACING, RADIUS, font, font_css, tag_role
from power_menu import build_power_menu, refresh_power_menu
from branding import APP_NAME, app_icon, notification_icon
from app_runtime import configure_application, acquire_instance_lock, set_autostart
from perf_monitor import PerfMonitor
from media_monitor import MediaMonitor
from event_monitor import KeyLockMonitor
from notification_monitor import NotificationMonitor
from notification_banner import NotificationBanner
from notification_card import CardMotion
from weather_monitor import WeatherMonitor
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QMenu, QPushButton, 
                             QGridLayout, QFrame, QProgressBar, QInputDialog,
                             QDialog, QLineEdit, QListWidget, QListWidgetItem,
                             QComboBox, QScrollArea, QMessageBox, QToolButton, QFileDialog)

               
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMSBT_DISABLE = 1
DWMWCP_DONOTROUND = 1

DEFAULT_TASKS = [
    {"name": "Project Sync", "category": "Work", "color": "#00A0FF", "time": "2:00 PM"},
    {"name": "Gym Session", "category": "Health", "color": "#00FF80", "time": "5:30 PM"},
    {"name": "Dinner with Family", "category": "Personal", "color": "#FF5050", "time": "8:00 PM"}
]

class DynamicIsland(OverlayUpgradeMixin, QWidget):
    def __init__(self):
        super().__init__()
        
                                                                        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | 
                            Qt.WindowType.WindowStaysOnTopHint | 
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.game_suspended = False
        self.browser_mode = False
        self.browser_open = False
        
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.theme = get_theme()
        self._content_size = (180, 40)
        self._pending_notification = None
        self.compatibility_mode = False
        
        self.accent_color = self.theme['accent']
        self.album_accent_color = QColor(0, 0, 0)
        self.gradient_phase = 0.0
        self.animation_style = "Fluid Blobs"
        self.island_style = "Default" 
        
        self.setObjectName("IslandWidget")
        self.setStyleSheet(get_stylesheet(theme=self.theme))
        
        self.last_power_plugged = psutil.sensors_battery().power_plugged if psutil.sensors_battery() else False
        self.battery_state = None
        
                                                         
        self._island_w = 180
        self._island_h = 40
        self.shine_phase = -1.0
        self.shine_anim = QPropertyAnimation(self, b"shine_phase")
        self.shine_anim.setDuration(1800)
        self.shine_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        self.charging_phase = 0.0
        self.charging_anim = QPropertyAnimation(self, b"charging_phase")
        self.charging_anim.setDuration(3000)
        self.charging_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        
        self.is_dialog_open = False
        self.is_editing_tasks = False
        
        self._weather_bg_opacity = 0.0
        self.weather_bg_anim = QPropertyAnimation(self, b"weather_bg_opacity")
        self.weather_bg_anim.setDuration(1200)
        self.weather_bg_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        
        self.weather_bg_phase = 0.0
        
        self._perf_bg_opacity = 0.0
        self.perf_bg_anim = QPropertyAnimation(self, b"perf_bg_opacity")
        self.perf_bg_anim.setDuration(1200)
        self.perf_bg_anim.setEasingCurve(QEasingCurve.Type.InOutSine)

        self._calendar_bg_opacity = 0.0
        self.calendar_bg_anim = QPropertyAnimation(self, b"calendar_bg_opacity")
        self.calendar_bg_anim.setDuration(1200)
        self.calendar_bg_anim.setEasingCurve(QEasingCurve.Type.InOutSine)

        self._month_bg_opacity = 0.0
        self.month_bg_anim = QPropertyAnimation(self, b"month_bg_opacity")
        self.month_bg_anim.setDuration(1200)
        self.month_bg_anim.setEasingCurve(QEasingCurve.Type.InOutSine)

        self.power_timer = QTimer(self)
        self.power_timer.timeout.connect(self.check_power_status)
        self.power_timer.start(2000)
        
                              
        self.IDLE_W, self.IDLE_H = 180, 40
        self.EXP_W, self.EXP_H = 340, 100
        self.PERF_W, self.PERF_H = 360, 180
        self.MUSIC_W, self.MUSIC_H = 420, 40
        # A notification swells the pill into a sender chip; the porcelain card hangs below.
        self.NOTIFY_W, self.NOTIFY_H = 204, 40
        self.WEATHER_W, self.WEATHER_H = 576, 208
        self.CALENDAR_W, self.CALENDAR_H = 576, 208
        self.MONTH_W, self.MONTH_H = 576, 208
        self.EDIT_W, self.EDIT_H = 576, 208
        self.WIDE_W = 1200                                             
        
        self.is_charging = False
        
        self.current_state = "Idle"
        self.media_state = "Idle"
        self.media_title, self.media_artist = "", ""
        self.features = ["dashboard", "weather", "calendar", "month", "tools"]
        self.current_feature_index = 0
        self.showing_lyrics = False
        self.media_lyric_text = ""
        self.LYRIC_W = 640
        
                            
        self.event_title, self.event_text = "", ""
        self.revert_timer = QTimer(self); self.revert_timer.setSingleShot(True); self.revert_timer.timeout.connect(lambda: self.change_state("Idle"))
        
        self.load_settings()
        self.initialize_upgrade()
        self.reduced_motion = effective_reduced_motion(self.settings['motion_mode'])
        self.decorative_motion = self.settings['decorative_effects_enabled'] and not self.reduced_motion
        self.idle_behavior = IdleBehavior(self.settings['autohide_delay'])
        self._defer_monitor_start = True
        self._monitors_started = False
        self.setup_monitors()
        self.init_ui()
        self.setup_autostart()
        
        self.master_timer = QTimer(self); self.master_timer.timeout.connect(self.update_content); self.master_timer.start(1000)
        self.anim_timer = QTimer(self); self.anim_timer.timeout.connect(self.update_animation); self.anim_timer.start(16)
        self.hit_timer = QTimer(self); self.hit_timer.timeout.connect(self.check_mouse_position); self.hit_timer.start(25)
        
                                                                            
        self.recenter_window()
        
        self._defer_monitor_start = False
        self.shell_motion = ShellMotion(self)
        self.anim_group = self.shell_motion.group
        self.apply_visual_preferences()

    def apply_visual_preferences(self):
        apply_visual_preferences(self)

    @pyqtProperty(float)
    def weather_bg_opacity(self): return self._weather_bg_opacity
    @weather_bg_opacity.setter
    def weather_bg_opacity(self, val): self._weather_bg_opacity = val; self.update()

    @pyqtProperty(float)
    def perf_bg_opacity(self): return self._perf_bg_opacity
    @perf_bg_opacity.setter
    def perf_bg_opacity(self, val): self._perf_bg_opacity = val; self.update()

    @pyqtProperty(float)
    def calendar_bg_opacity(self): return self._calendar_bg_opacity
    @calendar_bg_opacity.setter
    def calendar_bg_opacity(self, val): self._calendar_bg_opacity = val; self.update()

    @pyqtProperty(float)
    def month_bg_opacity(self): return self._month_bg_opacity
    @month_bg_opacity.setter
    def month_bg_opacity(self, val): self._month_bg_opacity = val; self.update()

    def load_settings(self):
        base_path = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
        self.config_path = os.path.join(base_path, "config.json")
        try:
            with open(self.config_path, encoding="utf-8") as stream:
                settings = json.load(stream)
        except (OSError, ValueError):
            settings = {}
        self.settings = settings if isinstance(settings, dict) else {}
        tasks = self.settings.get("tasks", DEFAULT_TASKS)
        if not isinstance(tasks, list):
            tasks = DEFAULT_TASKS
        self.settings["tasks"] = [dict(t) for t in tasks if isinstance(t, dict)
                                  and isinstance(t.get("name"), str) and isinstance(t.get("time"), str)]
        for task in self.settings['tasks']:
            if not isinstance(task.get('category'), str):
                task['category'] = 'Task'
            if not isinstance(task.get('color'), str) or not QColor(task.get('color')).isValid():
                task['color'] = get_theme()['accent']
        if not isinstance(self.settings.get('location'), str):
            self.settings['location'] = 'Varanasi, India'
        for key, default, limit in [('lat', 25.3333, 90), ('lon', 83.0, 180)]:
            value = self.settings.get(key, default)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > limit:
                self.settings[key] = default
        self.compatibility_mode = bool(self.settings.get("compatibility_mode", False))
        style = self.settings.get("island_style", "Default")
        self.island_style = style if style in ("Default", "Liquid Glass", "Notch Nook") else "Default"
        animation = self.settings.get("animation_style", "Fluid Blobs")
        self.animation_style = animation if animation in ("None", "Glow Sweep", "Fluid Blobs", "Neon Border") else "Fluid Blobs"
        self.theme = get_theme(self.settings.get("theme", "Dark Matter"), self.settings.get("surface_treatment", "neutral"))
        self.accent_color = self.theme['accent']
        self.settings["start_with_windows"] = self.settings.get("start_with_windows", True) is True
        delay = self.settings.get('autohide_delay', 10)
        self.settings['autohide_delay'] = delay if type(delay) is int and delay in (0, 5, 10, 30) else 10
        icon = self.settings.get('idle_icon', 'Aurora')
        version = self.settings.get('design_version')
        if type(version) is not int or version < 2:
            # The redesign replaces the plain clock and custom GIFs with the Aurora
            # orb once; animated styles chosen on purpose stay, and any can be re-picked.
            if icon in ('Clock', 'Custom GIF'):
                icon = 'Aurora'
            self.settings['design_version'] = 2
        self.settings['idle_icon'] = icon if isinstance(icon, str) and icon in ICON_STYLES else 'Aurora'
        if not isinstance(self.settings.get('custom_idle_icon'), str):
            self.settings['custom_idle_icon'] = ''
        self.setStyleSheet(get_stylesheet(theme=self.theme))

    def save_settings(self):
        self.settings.update(location=self.weather_monitor.city, lat=self.weather_monitor.lat,
                             lon=self.weather_monitor.lon, compatibility_mode=self.compatibility_mode,
                             island_style=self.island_style, animation_style=self.animation_style,
                             theme=self.theme['name'])
        temporary = self.config_path + ".tmp"
        try:
            with open(temporary, "w", encoding="utf-8") as stream:
                json.dump(self.settings, stream, indent=4)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.config_path)
            return True
        except OSError as error:
            self.is_dialog_open = True
            try:
                QMessageBox.warning(self, APP_NAME, f"Could not save preferences: {error}")
            finally:
                self.is_dialog_open = False
            return False

    def change_location_dialog(self):
        self.is_dialog_open = True
        try:
            city, ok = QInputDialog.getText(self, "Change Location", "Enter City Name:", text=self.weather_monitor.city)
            if ok and city.strip():
                self.weather_monitor.request_location(city.strip())
        finally:
            self.is_dialog_open = False
            self.flush_pending_notification()

    def flush_pending_notification(self):
        if self._pending_notification and not self.is_dialog_open and not self.is_editing_tasks:
            pending, self._pending_notification = self._pending_notification, None
            self.show_notification(*pending)

    def on_location_updated(self, success, message):
        if success:
            self.save_settings()
        self.show_notification("Weather", "Location updated" if success else "Location unavailable", message)

    def get_current_radius(self):
        if self.island_style == "Notch Nook":
            # A Mac notch: modest bottom corners that grow with the expanded shell.
            return min(self._island_h / 2.0, max(12.0, min(RADIUS['panel'], self._island_h * .18)))
        return min(self._island_h / 2.0, float(RADIUS['panel']))

    @pyqtProperty(int)
    def island_w(self): return self._island_w
    @island_w.setter
    def island_w(self, val):
        self.set_island_size(val, self._island_h)

    @pyqtProperty(int)
    def island_h(self): return self._island_h
    @island_h.setter
    def island_h(self, val):
        self.set_island_size(self._island_w, val)

    def set_island_size(self, width, height):
        """One geometry update and one island-sized repaint per animation frame."""
        if (width, height) == (self._island_w, self._island_h):
            return
        self._island_w, self._island_h = width, height
        self.update_island_geometry(self.get_island_rect(), self.get_current_radius())
        self.update_island_region()

    def update_island_region(self):
        """Repaint only where the island was and is, plus room for shadow and glow."""
        rect = self.get_island_rect().toAlignedRect()
        previous = getattr(self, '_painted_island', rect)
        self._painted_island = rect
        self.update(rect.united(previous).adjusted(-40, -12, 40, 40))

    NOTCH_EAR = 8.0
    ARC = 0.5523  # cubic handle length for a quarter circle

    def notch_outline(self, rect, closed=True):
        """A Mac notch: small concave ears at the screen edge, round lower corners."""
        r, ear = self.get_current_radius(), self.NOTCH_EAR
        k, kr = ear * self.ARC, r * self.ARC
        left, right, top, bottom = rect.left(), rect.right(), rect.top(), rect.bottom()
        path = QPainterPath()
        path.moveTo(left - ear, top)
        path.cubicTo(left - ear + k, top, left, top + ear - k, left, top + ear)
        path.lineTo(left, bottom - r)
        path.cubicTo(left, bottom - r + kr, left + r - kr, bottom, left + r, bottom)
        path.lineTo(right - r, bottom)
        path.cubicTo(right - r + kr, bottom, right, bottom - r + kr, right, bottom - r)
        path.lineTo(right, top + ear)
        path.cubicTo(right, top + ear - k, right + ear - k, top, right + ear, top)
        if closed:
            path.closeSubpath()
        return path

    def build_notch_path(self, rect):
        return self.notch_outline(rect)

    def _draw_shape(self, painter, rect, radius):
        if self.island_style == "Notch Nook":
            painter.drawPath(self.build_notch_path(rect))
        else:
            painter.drawRoundedRect(rect, radius, radius)

    def paintEvent(self, a0: QPaintEvent):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.get_island_rect()
        if self.current_state == 'Hidden':
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self.theme['edge_line']))
            edge_radius = min(rect.height() / 2, 30)
            painter.drawRoundedRect(rect, edge_radius, edge_radius)
            return
        # The card drops from behind the island, so it is painted first.
        self.notification_card.paint(painter)
        p_rect = rect.adjusted(1, 1, -1, -1)
        radius = self.get_current_radius()
        is_notch = self.island_style == "Notch Nook"

        if self.charging_phase > 0.0:
            self.paint_charging_ears(painter, rect, radius)
        
        painter.setPen(Qt.PenStyle.NoPen)

        # The opaque fill is the whole shape: inset "shadow" layers under it were
        # never visible and cost five full-size paths per frame.
        painter.setBrush(QBrush(QColor(self.theme['island'])))
        if is_notch:
            painter.drawPath(self.build_notch_path(rect))
        else:
            painter.drawRoundedRect(rect, radius, radius)

        if self._weather_bg_opacity > 0.0:
            self.paint_weather_bg(painter, rect, radius)
        if self._perf_bg_opacity > 0.0:
            self.paint_perf_bg(painter, rect, radius)
        if self._calendar_bg_opacity > 0.0:
            self.paint_calendar_bg(painter, rect, radius)
        if self._month_bg_opacity > 0.0:
            self.paint_month_bg(painter, rect, radius)
            
        clip_path = QPainterPath()
        if is_notch:
            clip_path = self.build_notch_path(rect)
        else:
            clip_path.addRoundedRect(QRectF(rect), radius, radius)
        painter.setClipPath(clip_path)
        # Each page brings its own light: album colour, sky, night, amber.
        stage_wash.paint(self, painter, rect)

        can_anim = (self.decorative_motion and self.animation_style != "None" and self.features[self.current_feature_index] == "dashboard"
                    and (self.current_state == "Hover" or
                         (self.current_state == "Idle" and self.media_state in ("Playing", "Paused"))))
        
        if can_anim:
            if self.animation_style == "Glow Sweep": self.paint_glow_sweep(painter, rect, radius)
            elif self.animation_style == "Fluid Blobs": self.paint_fluid_blobs(painter, rect, radius)
            elif self.animation_style == "Neon Border": self.paint_neon_border(painter, rect, radius)
        else:
            if not is_notch:
                painter.setBrush(Qt.BrushStyle.NoBrush); painter.setPen(QPen(QColor(self.theme['border']), 0.6))
                painter.drawRoundedRect(p_rect, radius, radius)

        if self.decorative_motion and self.animation_style != "None" and self.shine_phase > 0.0 and self.shine_phase < 1.0:
            self.paint_shine_sweep(painter, rect, radius)
        self.content_layer.paint(painter, rect)

        painter.setClipping(False)
        if getattr(self, 'ignite_phase', 0.) > 0.:
            ignite_motion.paint_rim(painter, rect, clip_path, self.edge_path(rect, radius),
                                    self.ignite_phase, self.theme['accent'])
                                     

    def paint_shine_sweep(self, painter, rect, radius):
        import math
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        
                                                               
        p = self.shine_phase
        if p <= 0 or p >= 1.0: return
        
                                                    
        opacity = math.sin(p * math.pi)
        
        start_x = 35
        max_reach = rect.width() * 1.5
        current_expansion = max_reach * p
        base_alpha = int(220 * math.sin(p * math.pi))
        for i in range(2):
            jitter_x = 0; jitter_y = 0
            W = current_expansion * (0.6 + i * 0.1)
            h = rect.height()
            target_x = start_x + (current_expansion * 0.4) + jitter_x
            target_y = (h / 2) + jitter_y
            painter.save()
            painter.translate(target_x, target_y)
            painter.scale(2.5, 0.8) 
            grad = QRadialGradient(QPointF(0, 0), W / 2)
            alpha = int(base_alpha * (1.0 - i * 0.3))
            grad.setColorAt(0.0, QColor(255, 255, 255, alpha))
            grad.setColorAt(0.3, QColor(0, 160, 255, int(alpha * 0.6)))
            grad.setColorAt(0.6, QColor(90, 0, 255, int(alpha * 0.15)))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(grad); painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(0, 0), W / 2, W / 2)
            painter.restore()
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

    def paint_glow_sweep(self, painter, rect, radius):
        from PyQt6.QtGui import QTransform
        glow = QColor(self.theme['accent']); glow.setAlpha(28)
        gradient = QLinearGradient(0, 0, rect.width(), 0); gradient.setSpread(QLinearGradient.Spread.RepeatSpread)
        gradient.setColorAt(0.0, Qt.GlobalColor.transparent); gradient.setColorAt(0.5, glow); gradient.setColorAt(1.0, Qt.GlobalColor.transparent)
        brush = QBrush(gradient); transform = QTransform(); transform.translate(self.gradient_phase * rect.width() * 2, 0); brush.setTransform(transform)
        painter.setBrush(brush); self._draw_shape(painter, rect, radius)

    def paint_fluid_blobs(self, painter, rect, radius):
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        glow_color = QColor(self.theme['accent']); glow_color.setAlpha(20); p = self.gradient_phase * 2 * math.pi
        x1, y1 = rect.width() * (0.2 + 0.15 * math.sin(p)), rect.height() * (0.5 + 0.25 * math.cos(p))
        g1 = QRadialGradient(x1, y1, rect.width() * 0.45); g1.setColorAt(0, glow_color); g1.setColorAt(1, Qt.GlobalColor.transparent)
        painter.setBrush(g1); self._draw_shape(painter, rect, radius)
        x2, y2 = rect.width() * (0.8 + 0.15 * math.cos(p * 0.7)), rect.height() * (0.5 + 0.25 * math.sin(p * 1.2))
        g2 = QRadialGradient(x2, y2, rect.width() * 0.35); g2.setColorAt(0, QColor(glow_color).lighter(125)); g2.setColorAt(1, Qt.GlobalColor.transparent)
        painter.setBrush(g2); self._draw_shape(painter, rect, radius)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

    def paint_neon_border(self, painter, rect, radius):
        conical = QConicalGradient(QPointF(rect.center()), self.gradient_phase * 360)
        accent = QColor(self.theme['accent'])
        for stop, alpha in ((0., 0), (.25, 32), (.5, 160), (.75, 32), (1., 0)):
            color = QColor(accent)
            color.setAlpha(alpha)
            conical.setColorAt(stop, color)
        painter.setBrush(Qt.BrushStyle.NoBrush); painter.setPen(QPen(QBrush(conical), 2.2))
        painter.drawPath(self.edge_path(rect, radius))

    def edge_path(self, rect, radius):
        """The island's visible edge; a notch has no top edge to light."""
        if self.island_style == "Notch Nook":
            return self.notch_outline(rect.adjusted(1, 0, -1, -1), closed=False)
        border = QPainterPath()
        border.addRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)
        return border

    def update_animation(self):
        if self.game_suspended or self.current_state == 'Hidden' or not self.decorative_motion:
            return
        self.gradient_phase = (self.gradient_phase + 0.005) % 1.0
        self.weather_bg_phase = (self.weather_bg_phase + 0.003) % 1.0
        if self.current_state in ("Hover", "Notify") or self.media_state in ("Playing", "Paused") or\
           self._weather_bg_opacity > 0.0 or self._perf_bg_opacity > 0.0 or\
           self._calendar_bg_opacity > 0.0 or self._month_bg_opacity > 0.0: 
            self.update()

    def get_windows_accent_color(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM")
            v, _ = winreg.QueryValueEx(key, "ColorizationColor"); winreg.CloseKey(key); return f"#{(v & 0xFFFFFF):06x}"
        except: return "#0078D7"

    def get_shine_phase(self): return self._shine_phase
    def set_shine_phase(self, value): self._shine_phase = value; self.update()
    shine_phase = pyqtProperty(float, get_shine_phase, set_shine_phase)

    def get_charging_phase(self): return self._charging_phase
    def set_charging_phase(self, value): self._charging_phase = value; self.update()
    charging_phase = pyqtProperty(float, get_charging_phase, set_charging_phase)

    def setup_autostart(self):
        if not getattr(sys, 'frozen', False):
            return True
        return set_autostart(self.settings.get("start_with_windows", True))

    def toggle_autostart(self):
        enabled = not self.settings.get("start_with_windows", True)
        if set_autostart(enabled):
            self.settings["start_with_windows"] = enabled
            self.save_settings()

    def init_ui(self):
        self.main_layout = QVBoxLayout(self); self.main_layout.setContentsMargins(0, 0, 0, 0); self.main_layout.setSpacing(0)
        self.island_root = QWidget(self)
        self.island_root.setObjectName("IslandRoot")
        # Reduced horizontal margins from 15 to 5 to prevent clipping of wide content
        self.island_root_layout = QVBoxLayout(self.island_root); self.island_root_layout.setContentsMargins(5, 0, 5, 0); self.island_root_layout.setSpacing(0)
        self.content_container = QWidget(self.island_root); self.content_layout = QVBoxLayout(self.content_container); self.content_layout.setContentsMargins(0, 0, 0, 0); self.content_layout.setSpacing(0)
        # Motion animates a snapshot of the content; live widgets carry no effects.
        self.content_layer = ContentLayer(self)
        self.content_opacity = self.content_layer
        ignite_motion.install(self)
        self.header_widget = QWidget(); self.header_widget.setFixedHeight(self.IDLE_H)
        # Dynamic Island compact layout: a leading slot, the centred clock, and a
        # trailing slot of the same width so the clock stays optically centred.
        self.header_layout = QHBoxLayout(self.header_widget)
        self.header_layout.setContentsMargins(SPACING['inset'] - 2, 0, SPACING['inset'] - 2, 0)
        self.header_layout.setSpacing(SPACING['control'])
        self.status_icon = IdleIcon(); self.status_icon.setObjectName("IconLabel"); self.status_icon.setFixedSize(22, 22)
        self.status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_text = QLabel(""); self.status_text.setObjectName("TitleLabel")
        # The battery sits beside the clock; a matching spacer keeps the clock centred.
        self.battery_spacer = QWidget(); self.battery_spacer.setFixedWidth(0); self.battery_spacer.hide()
        self.battery_indicator = QLabel(""); self.battery_indicator.setObjectName("BatteryLabel")
        self.battery_indicator.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.battery_indicator.setAccessibleName('Battery')
        self.battery_indicator.hide()
        self.header_layout.addWidget(self.battery_spacer)
        self.header_layout.addWidget(self.status_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.status_text, 0, Qt.AlignmentFlag.AlignCenter)
        self.now_playing = AudioBars()
        self.trailing_slot = QWidget()
        self.trailing_slot.setFixedSize(22, 22)
        trailing = QHBoxLayout(self.trailing_slot)
        trailing.setContentsMargins(0, 0, 0, 0)
        trailing.addWidget(self.now_playing)
        self.media_controls = QWidget(); self.media_controls_layout = QHBoxLayout(self.media_controls); self.media_controls_layout.setContentsMargins(0, 0, 0, 0); self.media_controls_layout.setSpacing(2)
        self.btn_prev = QPushButton(icon=qta.icon('ph.skip-back', color=self.theme['text'])); self.btn_play = QPushButton(icon=qta.icon('ph.play', color=self.theme['text'])); self.btn_next = QPushButton(icon=qta.icon('ph.skip-forward', color=self.theme['text']))
        for button, name in ((self.btn_prev, 'Previous track'), (self.btn_play, 'Play or pause'),
                               (self.btn_next, 'Next track')):
            button.setObjectName('MediaButton')
            button.setAccessibleName(name)
            button.setToolTip(name)
            button.setFixedSize(32, 32)
        for b in [self.btn_prev, self.btn_play, self.btn_next]: b.setObjectName("MediaButton")
        self.btn_prev.clicked.connect(self.media_monitor.prev_track); self.btn_play.clicked.connect(self.media_monitor.toggle_play_pause); self.btn_next.clicked.connect(self.media_monitor.next_track)
        for b in [self.btn_prev, self.btn_play, self.btn_next]: self.media_controls_layout.addWidget(b)
        self.perf_widget = QWidget(); self.perf_layout = QHBoxLayout(self.perf_widget); self.perf_layout.setContentsMargins(0, 0, 0, 0); self.perf_layout.setSpacing(8)
        self.cpu_label = QLabel("CPU: 0%"); self.cpu_label.setObjectName("PerfLabel")
        self.ram_label = QLabel("RAM: 0%"); self.ram_label.setObjectName("PerfLabel")
        self.perf_layout.addWidget(self.cpu_label); self.perf_layout.addWidget(self.ram_label)
        self.header_layout.addStretch(); self.header_layout.addWidget(self.trailing_slot, 0, Qt.AlignmentFlag.AlignVCenter); self.header_layout.addWidget(self.battery_indicator); self.header_layout.addWidget(self.media_controls); self.header_layout.addWidget(self.perf_widget); self.media_controls.hide(); self.perf_widget.hide()
        
                            
        self.perf_panel = self.create_perf_panel()
        self.weather_panel = self.create_weather_panel()
        self.calendar_panel = self.create_calendar_panel()
        self.month_panel = self.create_month_panel()
        self.dashboard = DashboardPanel()
        self.dashboard.action_requested.connect(self.request_action)
        self.dashboard.seek_requested.connect(lambda seconds: getattr(self.media_monitor, 'seek_to', lambda _: None)(seconds))
        self.dashboard.preferred_source_requested.connect(self.choose_media_source)
        self.dashboard.set_preferred_source(self.settings['preferred_media_source'])
        self.dashboard.set_theme(self.theme)
        self.create_tools_panel()
        # Stage: no dock. A top bar says where you are; the glances on Now open pages.
        self.stage_bar = StageBar()
        self.stage_bar.set_theme(self.theme)
        self.stage_bar.home_requested.connect(lambda: self.select_feature('dashboard'))
        self.navigation = self.stage_bar
        self.power_buttons = []
        button = QToolButton(objectName='PowerButton')
        button.setIcon(qta.icon('ph.power', color=self.theme['muted'], color_active=self.theme['text']))
        button.setAccessibleName('Power options')
        button.setToolTip('Power options')
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        power_menu = build_power_menu(button, self.theme, self.request_action,
                                      on_open=lambda: self.on_tool_dialog(True),
                                      on_close=lambda: self.on_tool_dialog(False))
        button.setMenu(power_menu)
        self.stage_bar.add_power(button)
        self.power_buttons.append(button)
        # Every page's entry point, in feature order: the crumb, then each glance.
        glances = self.dashboard.glances
        self.nav_buttons = [self.stage_bar.crumb, glances['weather'], glances['calendar'],
                            glances['month'], glances['tools']]
        self.dashboard.glance_requested.connect(self.select_feature)
        self.navigation.hide()
        self.dashboard.hide()
        
        for p in [self.perf_panel, self.weather_panel, self.calendar_panel, self.month_panel]: p.hide()
        
                                                         
        self.content_layout.addWidget(self.header_widget)
        # The island's notification chip: the sender in the same slots as the pill.
        self.notify_chip = QWidget()
        self.notify_chip.setFixedHeight(self.IDLE_H)
        chip = QHBoxLayout(self.notify_chip)
        chip.setContentsMargins(SPACING['inset'] - 2, 0, SPACING['inset'] - 2, 0)
        chip.setSpacing(SPACING['control'])
        self.chip_icon = QLabel()
        self.chip_icon.setFixedSize(22, 22)
        self.chip_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chip_text = ElidedLabel()
        self.chip_text.setObjectName('TitleLabel')
        self.chip_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chip_end = QWidget()
        chip_end.setFixedSize(22, 22)
        chip.addWidget(self.chip_icon)
        chip.addWidget(self.chip_text, 1)
        chip.addWidget(chip_end)
        self.notify_chip.hide()
        self.content_layout.addWidget(self.notify_chip)
        # The porcelain card hangs below the island, outside its clipped content.
        self.notification_banner = NotificationBanner(self)
        self.notification_banner.dismissed.connect(self.dismiss_notification)
        self.notification_banner.review_requested.connect(self.open_approvals)
        self.notification_kind = 'card'
        self.notification_card = CardMotion(self, self.notification_banner)
        # A stable viewport keeps navigation in place while tall pages scroll.
        self.feature_scroll = QScrollArea()
        self.feature_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.feature_scroll.setWidgetResizable(True)
        self.feature_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.feature_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.feature_scroll.setAccessibleName('Feature content')
        self.feature_pages = QWidget()
        pages = QVBoxLayout(self.feature_pages)
        pages.setContentsMargins(0, 0, 0, 0)
        pages.setSpacing(0)
        for panel in (self.dashboard, self.weather_panel, self.calendar_panel,
                      self.month_panel, self.tools_panel):
            pages.addWidget(panel, 0, Qt.AlignmentFlag.AlignHCenter)
        pages.addStretch()
        self.feature_scroll.setWidget(self.feature_pages)
        self.feature_scroll.viewport().setAutoFillBackground(False)
        self.feature_pages.setAutoFillBackground(False)
        self.feature_scroll.hide()
        self.content_layout.addWidget(self.navigation)
        self.content_layout.addWidget(self.feature_scroll, 0, Qt.AlignmentFlag.AlignHCenter)
        
        self.content_layout.addStretch(); self.update_content()
        # Removed hardcoded move(15, 0) which was causing right-side clipping
        self.update_island_geometry(self.get_island_rect(), self.get_current_radius())

    def setup_monitors(self):
        self.perf_monitor = PerfMonitor(parent=self); self.perf_monitor.metrics_updated.connect(self.update_perf)
        self.media_monitor = MediaMonitor(self); self.media_monitor.media_updated.connect(self.update_media)
        self.media_monitor.lyrics_updated.connect(self.update_lyrics)
        for signal, handler in [('artwork_updated', lambda data: self.dashboard.update_artwork(data)),
                                ('timeline_updated', lambda pos, duration: self.dashboard.update_timeline(pos, duration)),
                                ('source_updated', lambda source: self.dashboard.update_source(source)),
                                ('capabilities_updated', lambda caps: self.dashboard.set_capabilities(caps)),
                                ('sources_updated', self.update_media_sources),
                                ('transport_result', lambda action, success: self.dashboard.show_transport_result(action, success))]:
            if hasattr(self.media_monitor, signal):
                getattr(self.media_monitor, signal).connect(handler)
        if hasattr(self.media_monitor, 'set_preferred_source'):
            self.media_monitor.set_preferred_source(self.settings['preferred_media_source'])
        self.key_monitor = KeyLockMonitor(self); self.key_monitor.lock_changed.connect(self.show_key_event)
        self.notif_monitor = NotificationMonitor(self); self.notif_monitor.notification_received.connect(self.show_notification)
        if hasattr(self, 'notification_inbox'):
            self.notif_monitor.notification_recorded.connect(self.record_notification)
            self.notif_monitor.access_changed.connect(self.notification_inbox.set_access_note)
        
                                              
        loc = self.settings.get("location", "Varanasi, India")
        lat = self.settings.get("lat", 25.3333)
        lon = self.settings.get("lon", 83.0)
        self.weather_monitor = WeatherMonitor(city=loc, lat=lat, lon=lon)
        self.weather_monitor.weather_updated.connect(self.update_weather)
        if hasattr(self.weather_monitor, 'location_updated'):
            self.weather_monitor.location_updated.connect(self.on_location_updated)
        if not getattr(self, '_defer_monitor_start', False):
            self.start_monitors()

    def start_monitors(self):
        if self._monitors_started:
            return
        for monitor in (self.perf_monitor, self.media_monitor, self.key_monitor,
                        self.notif_monitor, self.weather_monitor):
            start = getattr(monitor, 'start', None)
            if start is not None:
                start()
        self._monitors_started = True

    def update_island_geometry(self, rect, radius):
        if not hasattr(self, 'island_root'): return
        width, height = self._content_size
        self.content_container.setGeometry(int((rect.width() - width) / 2), 0, width, height)
        self.island_root.setGeometry(int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height()))
        if self.island_root.isHidden():
            return  # A moving snapshot is clipped while painting; the mask waits for rest.
        path = QPainterPath()
        if self.island_style == "Notch Nook":
            path.moveTo(0, 0)
            path.lineTo(rect.width(), 0)
            path.lineTo(rect.width(), rect.height() - radius)
            path.quadTo(rect.width(), rect.height(), rect.width() - radius, rect.height())
            path.lineTo(radius, rect.height())
            path.quadTo(0, rect.height(), 0, rect.height() - radius)
            path.closeSubpath()
        else:
            path.addRoundedRect(QRectF(0, 0, rect.width(), rect.height()), radius, radius)
        self.island_root.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def paint_charging_ears(self, painter, rect, radius):
        p = self.charging_phase
        if p <= 0: return
        
        # Reduced motion paints one steady frame instead of a pulsing loop.
        opacity = 1.0 if self.reduced_motion else math.sin(p * math.pi)
        centerX = rect.center().x()
        centerY = rect.top() + rect.height() / 2
        
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)

                                                    
        glow_path = QPainterPath()
        glow_path.addRoundedRect(rect.adjusted(-20*opacity, -10*opacity, 20*opacity, 10*opacity), radius+10, radius+10)
        
                                 
        for i in range(5):
            alpha = int(70 * opacity / (i + 1))
            glow_grad = QRadialGradient(rect.center(), rect.width() / 1.5)
                                                         
            color = QColor(0, 255, 255, alpha) if i % 2 == 0 else QColor(140, 0, 255, alpha)
            painter.setPen(QPen(color, 12 + i*8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawPath(glow_path)

                                                        
        beam_len = 500 * opacity
        left_edge = rect.left()
        right_edge = rect.right()
        
                                   
        for i in range(3):
            beam_w = 4 - i
            if beam_w <= 0: continue
            alpha = int(180 * opacity / (i + 1))
            r_beam_grad = QLinearGradient(right_edge, centerY, right_edge + beam_len, centerY)
            r_beam_grad.setColorAt(0.0, QColor(255, 255, 255, alpha))
            r_beam_grad.setColorAt(0.1, QColor(0, 240, 255, alpha))
            r_beam_grad.setColorAt(0.5, QColor(160, 0, 255, alpha // 2))
            r_beam_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            
            painter.setPen(QPen(QBrush(r_beam_grad), beam_w + 1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(QPointF(right_edge, centerY), QPointF(right_edge + beam_len, centerY))

                                  
        for i in range(3):
            beam_w = 4 - i
            if beam_w <= 0: continue
            alpha = int(180 * opacity / (i + 1))
            l_beam_grad = QLinearGradient(left_edge, centerY, left_edge - beam_len, centerY)
            l_beam_grad.setColorAt(0.0, QColor(255, 255, 255, alpha))
            l_beam_grad.setColorAt(0.1, QColor(0, 240, 255, alpha))
            l_beam_grad.setColorAt(0.5, QColor(160, 0, 255, alpha // 2))
            l_beam_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            
            painter.setPen(QPen(QBrush(l_beam_grad), beam_w + 1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(left_edge, centerY), QPointF(left_edge - beam_len, centerY))

                                      
        painter.setBrush(QColor(255, 255, 255, int(255 * opacity)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(right_edge, centerY), 4, 3)
        painter.drawEllipse(QPointF(left_edge, centerY), 4, 3)
        
        painter.restore()

    def check_power_status(self):
        try:
            battery = psutil.sensors_battery()
        except Exception:
            battery = None
        if not battery:
            self.publish_battery(None)
            return
        percent = battery.percent
        percent = int(percent) if percent is not None and percent >= 0 else None
        plugged = bool(battery.power_plugged)
        if plugged and not self.last_power_plugged:
            self.trigger_charging_anim()
        self.last_power_plugged = plugged
        self.publish_battery({'percent': percent, 'plugged': plugged,
                              'secsleft': battery.secsleft})

    def publish_battery(self, state):
        """Show the battery state; an unknown battery is simply not shown."""
        if state == self.battery_state:
            return
        self.battery_state = state
        self.system_card.set_battery(state)
        self.refresh_stage_status()
        self.update_battery_indicator(state)
        self.update()

    def update_battery_indicator(self, state):
        """The charge readout only appears while the island is wide enough for it.

        The compact pill is 180px and the clock needs it. The charging island is
        wide, so the readout lives there and the level stays in the Overview card.
        """
        visible = bool(self.is_charging and state and state.get('percent') is not None
                       and state.get('plugged'))
        self.battery_indicator.setVisible(visible)
        # The balancer is hidden with the readout, so the idle layout is untouched.
        self.battery_spacer.setVisible(visible)
        if not visible:
            return
        percent = max(0, min(100, int(state['percent'])))
        self.battery_indicator.setText(f'{percent}%')
        self.battery_indicator.setToolTip(f'Battery {percent}%')
        self.battery_indicator.setAccessibleName(f'Battery {percent} percent, charging')
        # The spacer balances the readout exactly, so the clock stays centred.
        self.battery_spacer.setFixedWidth(self.battery_indicator.sizeHint().width())

    def trigger_charging_anim(self):
        if self.game_suspended or self.browser_mode:
            return
        self.is_charging = True
        if self.current_state == 'Hidden':
            self.change_state('Idle')
        else:
            self.execute_liquid_transition()
        self.charging_anim.stop()
        self.charging_anim.setStartValue(0.0)
        self.charging_anim.setEndValue(1.0)
        if self.reduced_motion:
            # Reduced motion shows one steady frame, never a wide empty pill.
            self.charging_phase = STATIC_CHARGING_PHASE
        else:
            self.charging_anim.start()
        self.update_battery_indicator(self.battery_state)
        QTimer.singleShot(3100, self.cleanup_charging_anim)

    def cleanup_charging_anim(self):
        self.is_charging = False
        self.charging_phase = STATIC_CHARGING_PHASE if self.reduced_motion else 0.0
        self.update_battery_indicator(self.battery_state)
        self.execute_liquid_transition()

    def show_key_event(self, name, is_on):
        if self.game_suspended or self.browser_mode:
            return
        if self.is_dialog_open or self.is_editing_tasks:
            self._pending_notification = (name, "", "On" if is_on else "Off")
            return
        self.event_title = name; self.event_text = ("On" if is_on else "Off")
        self.notification_title, self.notification_message = '', self.event_text
        self.notification_kind = 'key'  # a status change lives in the pill, without a card
        if self.current_state == "Notify": self.update_feature_view(); self.execute_liquid_transition()
        else: self.change_state("Notify")
        self.revert_timer.start(2500)

    def rearm_notification_timer(self):
        """A banner must never outlive its timeout, even across a menu or dialog."""
        if self.current_state == 'Notify' and not self.revert_timer.isActive():
            self.revert_timer.start(3500)

    def record_notification(self, record):
        """Keep a notification in the inbox only when the reader opted in."""
        if not self.settings.get('notification_inbox_enabled'):
            return
        self.notification_inbox.add(record)

    def show_notification(self, app, title, text):
        if self.game_suspended or self.browser_mode:
            return
        if self.is_dialog_open or self.is_editing_tasks:
            self._pending_notification = (app, title, text)
            return
        self.event_title = app; self.event_text = (f"{title}: {text}" if title else text)
        self.notification_title, self.notification_message = title, text
        self.notification_kind = 'card'
        if self.current_state == "Notify": self.update_feature_view(); self.execute_liquid_transition()
        else: self.change_state("Notify")
        self.revert_timer.start(3500)

    def dismiss_notification(self):
        if self.current_state != 'Notify':
            return
        self.revert_timer.stop()
        focused = QApplication.focusWidget()
        if focused is not None and self.notification_banner.isAncestorOf(focused):
            focused.clearFocus()
        self.change_state('Idle')

    def paint_panel_bg(self, painter, rect, radius, opacity):
        painter.save()
        painter.setOpacity(opacity)
        painter.setBrush(QColor(self.theme['background']))
        self._draw_shape(painter, rect, radius)
        painter.restore()

    def paint_weather_bg(self, painter, rect, radius):
        self.paint_panel_bg(painter, rect, radius, self._weather_bg_opacity)

    def paint_perf_bg(self, painter, rect, radius):
        self.paint_panel_bg(painter, rect, radius, self._perf_bg_opacity)

    def paint_calendar_bg(self, painter, rect, radius):
        self.paint_panel_bg(painter, rect, radius, self._calendar_bg_opacity)

    def paint_month_bg(self, painter, rect, radius):
        self.paint_panel_bg(painter, rect, radius, self._month_bg_opacity)

    def create_action_button(self, app_type):
        btn = QPushButton(icon=qta.icon('ph.arrow-square-out', color=self.theme['text']))
        btn.setObjectName("ActionButton")
        btn.setProperty('daisyIcon', 'ph.arrow-square-out')
        btn.setFixedSize(32, 32)
        btn.clicked.connect(lambda: self.open_app(app_type))
        return btn

    def open_app(self, app_type):
        schemes = {"weather": "bingweather:", "month": "ms-settings:dateandtime"}
        if app_type in schemes: webbrowser.open(schemes[app_type])

    def create_weather_panel(self):
        self.weather_page = WeatherPage(self.settings.get("location", "Varanasi, India"), self.open_app)
        self.weather_page.setFixedSize(self.WEATHER_W, self.WEATHER_H)
        return self.weather_page

    def update_weather(self, data):
        self._weather = data
        self.weather_page.update_weather(data)
        if self.current_state == 'Hover' and self.features[self.current_feature_index] == 'dashboard':
            self.refresh_glances()

    def create_calendar_panel(self):
        self.calendar_panel_widget = QWidget()
        # Initial size for View Mode
        self.calendar_panel_widget.setFixedSize(self.CALENDAR_W, self.CALENDAR_H)
        cal_layout = QVBoxLayout(self.calendar_panel_widget)
        cal_layout.setContentsMargins(0, 0, 0, 0); cal_layout.setSpacing(0)
        
        # View Mode Container
        self.task_view_widget = QWidget()
        view_layout = QVBoxLayout(self.task_view_widget)
        view_layout.setContentsMargins(24, 12, 24, 12); view_layout.setSpacing(12)
        
        h = QHBoxLayout(); t = tag_role(QLabel("Next up"), 'section')
        self.ev_count_label = tag_role(QLabel("0 tasks"), 'secondary', muted=True)
        eb = self.create_action_button("calendar"); eb.setProperty('daisyIcon', 'ph.pencil-simple'); eb.setIcon(qta.icon("ph.pencil-simple", color=self.theme['text'])); eb.clicked.connect(self.open_task_editor)
        eb.setAccessibleName('Edit tasks'); eb.setToolTip('Edit tasks')
        h.addWidget(t); h.addWidget(self.ev_count_label); h.addStretch(); h.addWidget(eb)
        view_layout.addLayout(h)
        
        self.tasks_container_widget = QWidget()
        self.tasks_container_layout = QVBoxLayout(self.tasks_container_widget)
        self.tasks_container_layout.setContentsMargins(0, 0, 0, 0); self.tasks_container_layout.setSpacing(0)
        # The card keeps one fixed size; a long task list scrolls inside it.
        self.tasks_scroll = QScrollArea()
        self.tasks_scroll.setWidgetResizable(True)
        self.tasks_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.tasks_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tasks_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.tasks_scroll.setWidget(self.tasks_container_widget)
        self.tasks_scroll.viewport().setAutoFillBackground(False)
        self.tasks_container_widget.setAutoFillBackground(False)
        self.tasks_scroll.setAccessibleName('Task list')
        view_layout.addWidget(self.tasks_scroll, 1)
        
        # Edit Mode Container
        self.task_edit_widget = QWidget(); self.task_edit_widget.hide()
        edit_layout = QHBoxLayout(self.task_edit_widget)
        edit_layout.setContentsMargins(24, 16, 24, 16); edit_layout.setSpacing(16)
        task_list_column = QVBoxLayout(); task_list_column.setSpacing(8)
        form_column = QVBoxLayout(); form_column.setSpacing(8)
        
        # Syncing with TaskEditorDialog's premium style but within panel
        self.edit_list = QListWidget()
        self.edit_list.setAccessibleName("Tasks")
        self.edit_list.setMinimumHeight(0)
        self.edit_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.edit_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Form fields follow the shared app stylesheet; the panel adds no private palette.
        input_grid = QGridLayout(); input_grid.setSpacing(8)
        self.edit_name = QLineEdit(); self.edit_name.setPlaceholderText("Task name"); self.edit_name.setAccessibleName("Task name")
        self.edit_time = QLineEdit(); self.edit_time.setPlaceholderText("Time (e.g. 3:00 PM)"); self.edit_time.setAccessibleName("Task time")
        self.edit_cat = QComboBox(); self.edit_cat.addItems(["Work", "Health", "Personal", "Study", "Other"]); self.edit_cat.setAccessibleName("Task category")
        for field in (self.edit_name, self.edit_time, self.edit_cat):
            field.setFixedHeight(32)
            field.setMinimumWidth(0)
        self.edit_time.setPlaceholderText("Time")
        
        input_grid.addWidget(self.edit_name, 0, 0, 1, 2)
        input_grid.addWidget(self.edit_time, 1, 0)
        input_grid.addWidget(self.edit_cat, 1, 1)
        
        # Buttons with premium feel
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add"); add_btn.clicked.connect(self.add_task_integrated)
        del_btn = QPushButton("Remove"); del_btn.clicked.connect(self.delete_task_integrated)
        # Using "and" instead of "&" to avoid mnemonic behavior in Qt
        save_btn = QPushButton("Save and close"); save_btn.setObjectName("PrimaryAction")
        save_btn.clicked.connect(self.save_and_close_editor)
        for button in (add_btn, del_btn, save_btn):
            button.setFixedHeight(32)
        
        btn_layout.addWidget(add_btn); btn_layout.addWidget(del_btn)
        
        task_list_column.addWidget(tag_role(QLabel("Tasks"), 'title'))
        task_list_column.addWidget(self.edit_list, 1)
        form_column.addLayout(input_grid)
        form_column.addLayout(btn_layout)
        form_column.addStretch()
        form_column.addWidget(save_btn)
        edit_layout.addLayout(task_list_column, 1)
        edit_layout.addLayout(form_column, 1)
        
        cal_layout.addWidget(self.task_view_widget)
        cal_layout.addWidget(self.task_edit_widget)
        
        self.refresh_calendar_panel()
        return self.calendar_panel_widget

    def add_task_integrated(self):
        name = self.edit_name.text()
        if name:
            tasks = self.settings.get("tasks", [])
            tasks.append({"name": name, "category": self.edit_cat.currentText(), "time": self.edit_time.text() or "N/A", "color": self.theme["accent"]})
            self.settings["tasks"] = tasks
            self.refresh_calendar_panel(); self.edit_name.clear(); self.edit_time.clear()

    def delete_task_integrated(self):
        idx = self.edit_list.currentRow()
        if idx >= 0:
            tasks = self.settings.get("tasks", [])
            tasks.pop(idx); self.settings["tasks"] = tasks
            self.refresh_calendar_panel()

    def save_and_close_editor(self):
        self.open_task_editor()
        self.save_settings()
        self.flush_pending_notification()

    def open_task_editor(self):
        self.is_editing_tasks = not self.is_editing_tasks
        self.task_view_widget.setVisible(not self.is_editing_tasks)
        self.task_edit_widget.setVisible(self.is_editing_tasks)
        
        # Adjust internal widget size based on mode
        if self.is_editing_tasks:
            self.calendar_panel_widget.setFixedSize(self.EDIT_W, self.EDIT_H)
        else:
            self.calendar_panel_widget.setFixedSize(self.CALENDAR_W, self.CALENDAR_H)
            
        # Toggle compatibility mode for stability
        if self.is_editing_tasks:
            self._prev_comp = self.compatibility_mode
            self.compatibility_mode = True
        else:
            self.compatibility_mode = getattr(self, "_prev_comp", self.compatibility_mode)
            
        self.recenter_window()
        self.execute_liquid_transition()

        self._fit_feature_content()

    def refresh_calendar_panel(self):
        # Deep clean existing tasks to prevent overlapping ghost widgets
        for child in self.tasks_container_widget.findChildren(QWidget):
            child.hide()
            child.setParent(None)
            child.deleteLater()
            
        while self.tasks_container_layout.count():
            item = self.tasks_container_layout.takeAt(0)
            if item.layout():
                # Manually clear sub-layouts if any remain
                while item.layout().count():
                    si = item.layout().takeAt(0)
                    if si.widget(): si.widget().deleteLater()
            
        tasks = self.settings.get("tasks", DEFAULT_TASKS)
        self.ev_count_label.setText(f"{len(tasks)} tasks")
        
        # Update integrated edit list
        self.edit_list.clear()
        for t in tasks:
            item = QListWidgetItem(f"{t['name']} • {t['time']}\n{t.get('category', 'Task')}")
            self.edit_list.addItem(item)
        
        # Rebuild view list
        shown_count = 0
        for t in tasks:
            shown_count += 1
            row_widget = QWidget()
            row_widget.setFixedHeight(44)
            row = QHBoxLayout(row_widget)
            row.setContentsMargins(0, 4, 0, 4)
            row.setSpacing(8)
            bar = QFrame(); bar.setFixedWidth(3); bar.setStyleSheet(f"background-color: {t.get('color') or self.theme['accent']}; border-radius: 1px;")
            det = QVBoxLayout(); det.setContentsMargins(0, 0, 0, 0); det.setSpacing(1)
            n = tag_role(ElidedLabel(t['name']), 'title')
            c = tag_role(QLabel(t.get('category', 'Task')), 'caption', muted=True)
            det.addWidget(n); det.addWidget(c)
            tm = tag_role(QLabel(t.get('time', '')), 'time')
            row.addWidget(bar); row.addLayout(det, 1); row.addWidget(tm)
            self.tasks_container_layout.addWidget(row_widget)
            
        if hasattr(self, 'shell_motion'):
            style_legacy_panels(self)
        self.tasks_scroll.verticalScrollBar().setValue(0)
        # Every expanded card is the same size; the list scrolls instead of growing.
        self.CALENDAR_H = 208
        
        if not self.is_editing_tasks:
            self.calendar_panel_widget.setFixedSize(self.CALENDAR_W, self.CALENDAR_H)
            # If we are in Hover state and looking at calendar, trigger a smooth transition to new size
            if self.current_state == "Hover" and self.features[self.current_feature_index] == "calendar":
                self.execute_liquid_transition()

    def create_perf_panel(self):
        w = QWidget(); l = QVBoxLayout(w); l.setContentsMargins(25, 12, 25, 18); l.setSpacing(12)
        header = QHBoxLayout(); title = tag_role(QLabel("System Status"), 'section')
        header.addWidget(title); header.addStretch(); header.addWidget(self.create_action_button("month"))           
        l.addLayout(header)

                         
        def add_item(layout, icon, label):
            v = QVBoxLayout(); v.setSpacing(4)
            h = QHBoxLayout(); ico = QLabel(); ico.setProperty('daisyIcon', icon); ico.setPixmap(qta.icon(icon, color=self.theme['text']).pixmap(14, 14))
            txt = tag_role(QLabel(label), 'secondary', muted=True)
            h.addWidget(ico); h.addWidget(txt); h.addStretch()
            val = tag_role(QLabel("0%"), 'metric')
            bar = QProgressBar(); bar.setFixedHeight(4); bar.setTextVisible(False); bar.setMaximum(100)
            bar.setObjectName("SystemProgress")
            v.addLayout(h); v.addWidget(val); v.addWidget(bar)
            layout.addLayout(v); return bar, val

        r1 = QHBoxLayout(); r1.setSpacing(30)
        self.cpu_bar_L = add_item(r1, "ph.cpu", "CPU")
        self.ram_bar_L = add_item(r1, "ph.database", "RAM")
        l.addLayout(r1)

        r2 = QHBoxLayout(); r2.setSpacing(30)
        self.disk_bar_L = add_item(r2, "ph.hard-drives", "STORAGE")
        
        nv = QVBoxLayout(); nv.setSpacing(4)
        nh = QHBoxLayout(); nico = QLabel(); nico.setProperty('daisyIcon', "ph.globe"); nico.setPixmap(qta.icon("ph.globe", color=self.theme['text']).pixmap(14, 14))
        ntxt = tag_role(QLabel("NETWORK"), 'secondary', muted=True)
        nh.addWidget(nico); nh.addWidget(ntxt); nh.addStretch(); nv.addLayout(nh)
        self.net_down_L = tag_role(QLabel("↓ 0 KB/s"), 'time')
        self.net_up_L = tag_role(QLabel("↑ 0 KB/s"), 'time')
        nv.addWidget(self.net_down_L); nv.addWidget(self.net_up_L); r2.addLayout(nv)
        l.addLayout(r2); return w

    def create_month_panel(self):
        self.calendar_page = CalendarPage(self.open_app)
        self.calendar_page.setFixedSize(self.MONTH_W, self.MONTH_H)
        self.calendar_page.refresh(self.agenda())
        return self.calendar_page

    def agenda(self):
        """Today's tasks still ahead, as (name, time), soonest first."""
        now = datetime.datetime.now().time()
        upcoming = []
        for task in self.settings.get('tasks', []):
            try:
                when = datetime.datetime.strptime(task.get('time', ''), '%I:%M %p').time()
            except ValueError:
                continue
            if when >= now:
                upcoming.append((when, task['name'], task['time']))
        return [(name, time) for _, name, time in sorted(upcoming)]

    def update_content(self):
        if hasattr(self, 'tools_panel'):
            self.tools_panel.tick()
        if self.current_state == "Idle":
            now = datetime.datetime.now()
            ts = now.strftime("%I:%M %p").lstrip("0")
            timer_text = self.tools_panel.compact_text() if hasattr(self, 'tools_panel') else ''
            # macOS menu-bar format: "Tue 2:07 PM".
            self.status_text.setText(f"{now.strftime('%a')} {ts}" + (f' · {timer_text}' if timer_text else ''))
            self.status_text.setToolTip('')
            self.status_icon.set_color(self.theme['text'])
            self.status_icon.set_tint(self.ambient_tint())
            self.now_playing.set_state(self.media_state, self.ambient_tint())
            self.now_playing.set_reduced_motion(self.reduced_motion)
            self.status_icon.set_style(self.settings['idle_icon'], self.settings['custom_idle_icon'])
            self.status_icon.set_reduced_motion(self.reduced_motion)
            self.status_icon.set_active(not self.game_suspended)
        elif self.current_state == 'Hover':
            self.refresh_stage_status()
            if self.features[self.current_feature_index] == 'dashboard':
                self.refresh_glances()
        self.update_island_region()

    def refresh_stage_status(self):
        self.stage_bar.set_status(self.battery_state, datetime.datetime.now().strftime('%I:%M %p').lstrip('0'))

    def next_task(self, now=None):
        """The first of today's tasks still ahead, by its listed time."""
        now = now or datetime.datetime.now()
        upcoming = []
        for task in self.settings.get('tasks', []):
            try:
                when = datetime.datetime.strptime(task.get('time', ''), '%I:%M %p').time()
            except ValueError:
                continue
            if when >= now.time():
                upcoming.append((when, task))
        return min(upcoming, key=lambda pair: pair[0])[1] if upcoming else None

    def refresh_glances(self):
        """Fill the Now page's glances from the timer, tasks, date and weather."""
        panel, dash = self.tools_panel, self.dashboard
        state = {'running': 'Running', 'paused': 'Paused'}.get(getattr(panel.timer, 'state', ''), 'Ready')
        dash.set_glance('tools', 'Focus', f'{state} · {panel.minutes.value()} min',
                        panel.time_text.text(), tint=self.theme['timer_accent'])
        task = self.next_task()
        if task:
            dash.set_glance('calendar', task['name'], f"Today · {task['time']}", chevron=True)
        else:
            count = len(self.settings.get('tasks', []))
            dash.set_glance('calendar', 'No more tasks today', f'{count} on your list', chevron=True)
        now = datetime.datetime.now()
        dash.set_glance('month', f"{now.strftime('%A')} {now.day}", now.strftime('%B %Y'), chevron=True)
        weather = getattr(self, '_weather', None)
        if weather:
            dash.set_glance('weather', weather['city'], weather['desc'], weather['temp'], tint=self.theme['wash_sun'])
        else:
            dash.set_glance('weather', self.settings.get('location', 'Weather'), 'Loading weather…',
                            tint=self.theme['wash_sun'])

    def ambient_tint(self):
        """The orb and bars glow in the album's colour while music plays, else the accent."""
        album = self.album_accent_color
        if self.media_state in ('Playing', 'Paused') and album.isValid() and album.valueF() > .15:
            return album
        return QColor(self.theme['accent'])

    def update_perf(self, data):
        self.system_card.update_metrics(data)
        cpu, ram, disk = data["cpu"], data["ram"], data["disk"]
        down, up = data["down"], data["up"]
        
                                              
        self.cpu_label.setText(f"CPU: {int(cpu)}%"); self.ram_label.setText(f"RAM: {int(ram)}%")
        
                                      
        self.cpu_bar_L[0].setValue(int(cpu)); self.cpu_bar_L[1].setText(f"{int(cpu)}%")
        self.ram_bar_L[0].setValue(int(ram)); self.ram_bar_L[1].setText(f"{int(ram)}%")
        self.disk_bar_L[0].setValue(int(disk)); self.disk_bar_L[1].setText(f"{int(disk)}%")
        
                                     
        def fmt(b):
            if b < 1024: return f"{int(b)} B/s"
            if b < 1024*1024: return f"{int(b/1024)} KB/s"
            return f"{b/(1024*1024):.1f} MB/s"
            
        self.net_down_L.setText(f"↓ {fmt(down)}"); self.net_up_L.setText(f"↑ {fmt(up)}")

    def update_media(self, state, title, artist, accent_hex):
        self.dashboard.update_media(state, title, artist, accent_hex)
        self.media_state, self.media_title, self.media_artist = state, title, artist; self.album_accent_color = QColor(accent_hex)
        if state == "Idle":
            self.showing_lyrics = False
            self.media_lyric_text = ""
        self.btn_play.setIcon(qta.icon('ph.pause' if state == "Playing" else 'ph.play', color=self.theme['text'])); self.update_content()

    def update_lyrics(self, text):
        was_showing = self.showing_lyrics
        self.media_lyric_text = text
        self.showing_lyrics = bool(text)
        
                                                                                  
        if was_showing != self.showing_lyrics:
            self.execute_liquid_transition()
        else:
            self.update_content()

    def select_feature(self, feature):
        self.current_feature_index = self.features.index(feature)
        if feature == 'tools':
            self.tools_panel.completion_pending = False
            self.tools_panel.shelf.refresh()
            self.on_timer_changed()
        self.change_state("Hover") if self.current_state != "Hover" else self.execute_liquid_transition()

    def _fit_feature_content(self):
        if self.current_state != 'Hover':
            return
        panel = {'dashboard': self.dashboard, 'weather': self.weather_panel,
                 'calendar': self.calendar_panel, 'month': self.month_panel,
                 'tools': self.tools_panel}[self.features[self.current_feature_index]]
        self.feature_pages.setMinimumHeight(panel.height())
        self.feature_pages.resize(self.feature_scroll.viewport().width(),
            max(panel.height(), self.feature_scroll.viewport().height()))
        self.feature_pages.layout().activate()
        self.feature_scroll.verticalScrollBar().setValue(0)
        # The task list scrolls inside the card and must start at the top.
        self.tasks_scroll.verticalScrollBar().setValue(0)

    def update_feature_view(self):
        feature = self.features[self.current_feature_index]
        hover = self.current_state == "Hover"
        self.content_container.setVisible(self.current_state != 'Hidden')
        self.header_widget.setVisible(self.current_state == 'Idle')
        self.notify_chip.setVisible(self.current_state == 'Notify')
        self.status_icon.set_active(self.current_state == 'Idle' and not self.game_suspended)
        self.navigation.setVisible(hover)
        self.feature_scroll.setVisible(hover)
        self.dashboard.setVisible(hover and feature == 'dashboard')
        self.perf_panel.hide()
        self.perf_widget.hide()
        self.media_controls.hide()
        self.weather_panel.setVisible(hover and feature == 'weather')
        self.calendar_panel.setVisible(hover and feature == 'calendar')
        self.month_panel.setVisible(hover and feature == 'month')
        self.tools_panel.setVisible(hover and feature == 'tools')
        self._fit_feature_content()
        self.stage_bar.set_page(feature == 'dashboard')
        stage_wash.set_page(self, feature if hover else None)
        if hover and feature == 'month':
            self.calendar_page.refresh(self.agenda())
        if hover:
            self.refresh_stage_status()
            if feature == 'dashboard':
                self.refresh_glances()
        if self.current_state == 'Notify':
            # The card carries the whole notification; the island shows who sent it.
            message = getattr(self, 'notification_message', self.event_text)
            self.notification_banner.set_message(self.event_title,
                getattr(self, 'notification_title', ''), message)
            self.notification_banner.set_review_available(self.has_pending_approval(self.event_title))
            key = self.notification_kind == 'key'
            self.chip_text.setText(f'{self.event_title} · {message}' if key else str(self.event_title or 'Notification'))
            icon = (qta.icon('ph.keyboard', color=self.theme['text']) if key
                    else notification_icon(self.event_title, self.theme['accent']))
            self.chip_icon.setPixmap(icon.pixmap(20, 20))
            if self.notification_card.wanted:
                self.notification_card.layout()
        elif not hover:
            self.update_content()

    def request_action(self, action):
        transport = {'previous': self.media_monitor.prev_track, 'play_pause': self.media_monitor.toggle_play_pause,
                     'next': self.media_monitor.next_track}
        if action in transport:
            transport[action]()
            return
        commands = {'sleep': ['rundll32.exe', 'powrprof.dll,SetSuspendState', '0,1,0'],
                    'restart': ['shutdown', '/r', '/t', '0'], 'shutdown': ['shutdown', '/s', '/t', '0']}
        if action not in commands:
            return
        self.is_dialog_open = True
        try:
            if action != 'sleep':
                answer = QMessageBox.question(self, f'{action.title()} this PC?',
                    f'{action.title()} now? Save your work before continuing.',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                if answer != QMessageBox.StandardButton.Yes:
                    return
            subprocess.Popen(commands[action], shell=False)
        except OSError as error:
            QMessageBox.warning(self, APP_NAME, f'Could not {action}: {error}')
        finally:
            self.is_dialog_open = False

    def wheelEvent(self, event):
        if (self.current_state == 'Hover'
                and self.feature_scroll.rect().contains(
                    self.feature_scroll.mapFrom(self, event.position().toPoint()))):
            # The scroll area's viewport handles its own wheel input. At a limit
            # Qt may bubble the event here; never turn that into page navigation.
            event.accept()
            return
        if self.current_state == "Hover" and not self.is_editing_tasks:
            delta = event.angleDelta().y()
            self.current_feature_index = (self.current_feature_index + (1 if delta < 0 else -1)) % len(self.features)
            self.execute_liquid_transition()
        super().wheelEvent(event)

    def keyPressEvent(self, event):
        if self.browser_mode and event.key() == Qt.Key.Key_Escape:
            self.close_browser_panel()
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        line = QRect(self.width() // 2 - 48, 0, 96, 4)
        if (self.browser_mode and not self.browser_open and not self.game_suspended
                and event.button() == Qt.MouseButton.LeftButton
                and line.contains(event.position().toPoint())):
            self.browser_open = True
            self.revert_timer.stop()
            self.change_state('Hover')
            self.activateWindow()
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            event.accept()
            return
        super().mousePressEvent(event)

    def close_browser_panel(self):
        if not self.browser_mode or self.is_dialog_open or self.is_editing_tasks:
            return
        self.browser_open = False
        self.revert_timer.stop()
        focused = QApplication.focusWidget()
        if focused is not None and (focused is self or self.isAncestorOf(focused)):
            focused.clearFocus()
        self.charging_anim.stop()
        self.is_charging = False
        self.charging_phase = 0.0
        self.change_state('Hidden')
        self.browser_guard.restore_focus()

    def check_browser_pointer(self):
        if self.is_dialog_open or self.is_editing_tasks:
            return
        local_cursor = self.mapFromGlobal(QCursor.pos())
        if self.browser_open:
            target = self.get_island_rect().toAlignedRect()
            target.setTop(0)  # Bridge the small gap between the edge and pill.
            if not target.contains(local_cursor):
                self.close_browser_panel()
        else:
            self.close_browser_panel()
        target = (self.get_island_rect().toAlignedRect() if self.browser_open
                  else QRect(self.width() // 2 - 48, 0, 96, 4))
        hwnd = int(self.winId())
        ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        wanted = ex & ~0x20 if target.contains(local_cursor) else ex | 0x20
        if wanted != ex:
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, wanted)

    def get_centered_x(self, width):
        sr = self.screen().availableGeometry(); return sr.x() + (sr.width() // 2) - (width // 2)

    def execute_liquid_transition(self):
        if self.game_suspended:
            return
        feature = self.features[self.current_feature_index]
        outer = SPACING['outer']
        if self.is_charging:
            w, h = 850, 40
        elif self.current_state == 'Hidden':
            w, h = 96, 4
        elif self.current_state == 'Idle':
            w, h = self.IDLE_W + (100 if self._timer_compact else 0), self.IDLE_H
        elif self.current_state == 'Notify':
            w, h = self.NOTIFY_W, self.NOTIFY_H
        else:
            w, h = 624, 272
        available = self.screen().availableGeometry()
        w = min(w, available.width())
        h = min(h, available.height() - (0 if self.island_style == 'Notch Nook' else 10))
        if self.current_state == 'Hover':
            viewport_width, viewport_height = max(1, w - outer * 2), max(1, h - BAR_HEIGHT - outer)
            self.feature_scroll.setFixedSize(viewport_width, viewport_height)
            selected = {'dashboard': self.dashboard, 'weather': self.weather_panel,
                        'calendar': self.calendar_panel, 'month': self.month_panel,
                        'tools': self.tools_panel}[feature]
            page_width = viewport_width
            self.dashboard.set_available_width(page_width)
            self.weather_panel.setFixedSize(page_width, viewport_height)
            self.month_panel.setFixedSize(page_width, viewport_height)
            self.tools_panel.setFixedSize(page_width, viewport_height)
            self.calendar_panel.setFixedWidth(page_width)
        def apply_view():
            self._content_size = (w, h)
            self.update_feature_view()
        # A status change replacing a card (or the reverse) is a transition of its own.
        kind = self.notification_kind if self.current_state == 'Notify' else None
        key = (self.current_state, feature, w, h, self.island_style, kind)
        self.shell_motion.transition(key, (w, h), apply_view,
                                     reduced=getattr(self, 'reduced_motion', False))

    def has_keyboard_focus(self):
        focused = QApplication.focusWidget()
        return (self.isActiveWindow() and focused is not None and focused.isVisible()
                and (focused is self or self.isAncestorOf(focused)))

    def change_state(self, new):
        if self.current_state == new: return
        if new == 'Idle' and (self.is_editing_tasks or
                              (self.current_state not in ('Hidden', 'Notify') and self.has_keyboard_focus())):
            return
        self.current_state = new
        if new != 'Hidden':
            self.idle_behavior.note_interaction()
        self.execute_liquid_transition()

    def set_autohide_delay(self, seconds):
        self.idle_behavior.set_timeout(seconds)
        self.settings['autohide_delay'] = self.idle_behavior.timeout
        if self.current_state == 'Hidden' and self.idle_behavior.timeout == 0:
            self.change_state('Idle')
        self.save_settings()

    def set_idle_icon(self, name, custom_path=None):
        path = self.settings['custom_idle_icon'] if custom_path is None else custom_path
        if name not in ICON_STYLES or not self.status_icon.set_style(name, path):
            self.status_icon.set_style(self.settings['idle_icon'], self.settings['custom_idle_icon'])
            return False
        self.settings.update(idle_icon=name, custom_idle_icon=path)
        self.update_feature_view()
        self.save_settings()
        return True

    def choose_idle_gif(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Choose a looping icon', '', 'GIF animation (*.gif)')
        if path and not self.set_idle_icon('Custom GIF', path):
            QMessageBox.warning(self, APP_NAME, 'Choose a valid GIF animation. Your previous icon is unchanged.')

    def set_island_style(self, style):
        self.island_style = style
        self.save_settings()
        self.recenter_window()
        self.execute_liquid_transition()
        self.update_island_geometry(self.get_island_rect(), self.get_current_radius())
        self.update()

    def set_animation_style(self, style):
        """Record the chosen effect. The decorative master switch stays in Settings."""
        self.animation_style = style
        self.settings['animation_style'] = style
        self.apply_visual_preferences()
        self.save_settings()
        self.update()

    def get_island_rect(self):
        W = self._island_w
        H = self._island_h
        centerX = self.width() / 2
        if self.current_state == 'Hidden' or self.island_style == "Notch Nook":
            return QRectF(centerX - W/2, 0, W, H)
        return QRectF(centerX - W/2, 10, W, H)

    def recenter_window(self):
        """Fit the overlay to the island and centre it on the screen's top edge."""
        overlay_fit.rest(self)
        self.update_island_geometry(self.get_island_rect(), self.get_current_radius())

    def overlay_extra_height(self):
        """Room the overlay keeps below the island for anything hanging from it."""
        return self.notification_card.extent() if hasattr(self, 'notification_card') else 0

    def overlay_min_width(self):
        return self.notification_card.min_width() if hasattr(self, 'notification_card') else 0

    def card_motion(self, state, previous, reduced):
        """The porcelain card's part in a shell transition, if any."""
        card = self.notification_card
        wanted = state == 'Notify' and self.notification_kind == 'card'
        if reduced:
            card.apply_now(wanted)
            return None
        if wanted:
            if card.wanted and card.progress >= 1.:
                card.layout()  # a replacement updates in place
                return None
            return card.present()
        return card.retract() if card.present_on_screen() else None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'island_root'):
            self.update_island_geometry(self.get_island_rect(), self.get_current_radius())
        if hasattr(self, 'notification_card') and self.notification_card.present_on_screen():
            self.notification_card.layout()

    def showEvent(self, event):
        super().showEvent(event)
        # Windows rounds the entire transparent host HWND unless explicitly disabled.
        # Daisy paints its own pill/notch; native rounding adds a desktop-sized border.
        if sys.platform == 'win32':
            try:
                preference = ctypes.c_int(DWMWCP_DONOTROUND)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    ctypes.c_void_p(int(self.winId())), DWMWA_WINDOW_CORNER_PREFERENCE,
                    ctypes.byref(preference), ctypes.sizeof(preference))
            except (AttributeError, OSError):
                pass  # Older Windows versions do not expose this DWM preference.

    def toggle_compatibility_mode(self):
        self.compatibility_mode = not self.compatibility_mode
        self.save_settings()
        self.recenter_window()
        self.update_island_geometry(self.get_island_rect(), self.get_current_radius())
        self.update()

    def check_mouse_position(self):
        if self.game_guard.is_active():
            if not self.game_suspended:
                self.game_suspended = True
                self.browser_open = False
                self.revert_timer.stop()
                self.shell_motion.cancel()
                self.charging_anim.stop()
                self.status_icon.set_active(False)
                self.hide()
            return
        if self.game_suspended:
            self.game_suspended = False
            self.is_charging = False
            self.charging_phase = 0.0
            self.idle_behavior.note_interaction()
            if not self.is_editing_tasks and not self.is_dialog_open:
                self.current_state = 'Idle'
            self.execute_liquid_transition()
            self.show()
        was_browser = self.browser_mode
        self.browser_mode = self.browser_guard.is_active()
        if self.browser_mode:
            self.check_browser_pointer()
            return
        if was_browser:
            self.browser_open = False
            if not self.is_dialog_open and not self.is_editing_tasks:
                self.current_state = 'Idle'
                self.execute_liquid_transition()
        cursor_pos = QCursor.pos()
        rect = self.get_island_rect()
        global_top_left = self.mapToGlobal(QPoint(int(rect.x()), int(rect.y())))
        global_bottom_right = self.mapToGlobal(QPoint(int(rect.right()), int(rect.bottom())))
        global_rect = QRect(global_top_left, global_bottom_right)
        hit_rect = global_rect.adjusted(-12, -8, 12, 16)
        if self.current_state == 'Hidden':
            hit_rect = QRect(global_rect.left() - 12, self.y(), global_rect.width() + 24, 12)
        else:
            hit_rect.setTop(min(hit_rect.top(), self.y()))
        hwnd = int(self.winId())
        ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        WS_EX_TRANSPARENT = 0x20
        card = self.notification_card
        over_card = False
        if card.progress > 0.:
            resting = card.rest_rect().toAlignedRect()
            over_card = QRect(self.mapToGlobal(resting.topLeft()), resting.size()).contains(cursor_pos)
        over_island = hit_rect.contains(cursor_pos) or over_card
        # Poll fast only near the island; far away the pointer cannot reach it within a tick.
        near = hit_rect.adjusted(-200, -200, 200, 200).contains(cursor_pos)
        interval = 25 if near or self.current_state != 'Idle' else 80
        if self.hit_timer.interval() != interval:
            self.hit_timer.setInterval(interval)
        interactive = over_island or self.has_keyboard_focus()
        if interactive:
            if ex & WS_EX_TRANSPARENT:
                # A banner or an editor carries real controls, so it must stay
                # clickable even though the rest of the overlay is click-through.
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex & ~WS_EX_TRANSPARENT)
        elif not (ex & WS_EX_TRANSPARENT):
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex | WS_EX_TRANSPARENT)
        if self.current_state == "Notify" or self.is_dialog_open or self.is_editing_tasks or self.is_charging:
            self.idle_behavior.note_interaction()
            if self.current_state == 'Notify':
                # Like macOS, a notification stays while the pointer rests on it.
                if over_island:
                    self.revert_timer.stop()
                    self._notification_held = True
                elif getattr(self, '_notification_held', False):
                    self._notification_held = False
                    self.revert_timer.start(2000)
            return

        if interactive:
            self.idle_behavior.note_interaction()
            if ex & WS_EX_TRANSPARENT: 
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex & ~WS_EX_TRANSPARENT)
            if self.current_state != "Hover": 
                self.change_state("Hover")
            self.revert_timer.stop()
        else:
            if not (ex & WS_EX_TRANSPARENT): 
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex | WS_EX_TRANSPARENT)
            if self.current_state == "Hover":
                if not self.revert_timer.isActive():
                    self.revert_timer.start(1200)
            if self.idle_behavior.tick(False, False, self.current_state):
                self.change_state('Hidden')

    def set_theme(self, name):
        self.theme = get_theme(name, self.settings.get('surface_treatment', 'neutral'))
        self.settings['theme'] = self.theme['name']
        self.accent_color = self.theme['accent']
        self.setStyleSheet(get_stylesheet(theme=self.theme))
        self.dashboard.set_theme(self.theme)
        self.tools_panel.set_theme(self.theme)
        self.stage_bar.set_theme(self.theme)
        self.power_buttons[0].setIcon(qta.icon('ph.power', color=self.theme['muted'], color_active=self.theme['text']))
        self.apply_visual_preferences()
        self.save_settings()
        self.update_content()

    def contextMenuEvent(self, event):
        self.is_dialog_open = True
        self.revert_timer.stop()
        try:
            menu = QMenu(self)
            menu.addAction('Settings…').triggered.connect(self.open_settings)
            menu.addAction('Restart Daisy').triggered.connect(self.request_restart)
            menu.addSeparator()
            hiding = menu.addMenu('Auto-hide')
            for label, seconds in [('Off', 0), ('After 5 seconds', 5), ('After 10 seconds', 10), ('After 30 seconds', 30)]:
                action = hiding.addAction(label)
                action.setCheckable(True)
                action.setChecked(self.settings['autohide_delay'] == seconds)
                action.triggered.connect(lambda _, delay=seconds: self.set_autohide_delay(delay))
            icons = menu.addMenu('Idle Icon')
            for name in ICON_STYLES:
                label = 'Choose custom GIF…' if name == 'Custom GIF' else ('Clock (no animation)' if name == 'Clock' else name)
                action = icons.addAction(label)
                action.setCheckable(True)
                action.setChecked(self.settings['idle_icon'] == name)
                action.triggered.connect(lambda _, choice=name: self.choose_idle_gif() if choice == 'Custom GIF' else self.set_idle_icon(choice))
            themes = menu.addMenu("Theme")
            for name in THEMES:
                action = themes.addAction(name)
                action.setCheckable(True)
                action.setChecked(self.theme['name'] == name)
                action.triggered.connect(lambda _, n=name: self.set_theme(n))
            am = menu.addMenu("Background Animation")
            for style in ["None", "Glow Sweep", "Fluid Blobs", "Neon Border"]:
                action = am.addAction(style)
                action.setCheckable(True)
                action.setChecked(self.animation_style == style)
                action.triggered.connect(lambda _, s=style: self.set_animation_style(s))
            sm = menu.addMenu("Island Style")
            for style in ["Default", "Liquid Glass", "Notch Nook"]:
                action = sm.addAction(style)
                action.setCheckable(True)
                action.setChecked(self.island_style == style)
                action.triggered.connect(lambda _, s=style: self.set_island_style(s))
            startup = menu.addAction("Start with Windows")
            startup.setCheckable(True)
            startup.setChecked(self.settings.get('start_with_windows', True))
            startup.triggered.connect(self.toggle_autostart)
            menu.addSeparator()
            compatibility = menu.addAction("Compatibility Mode")
            compatibility.setCheckable(True)
            compatibility.setChecked(self.compatibility_mode)
            compatibility.triggered.connect(self.toggle_compatibility_mode)
            menu.addAction("Change Location").triggered.connect(self.change_location_dialog)
            menu.addSeparator()
            menu.addAction("Quit Daisy").triggered.connect(self.close)
            menu.exec(self.mapToGlobal(event.pos()))
        finally:
            self.is_dialog_open = False
            self.idle_behavior.note_interaction()
            self.rearm_notification_timer()
            self.flush_pending_notification()

    def closeEvent(self, event):
        self.status_icon.set_active(False)
        for timer in (self.power_timer, self.master_timer, self.anim_timer, self.hit_timer, self.revert_timer):
            timer.stop()
        pending = False
        for monitor in (self.perf_monitor, self.media_monitor, self.key_monitor, self.notif_monitor, self.weather_monitor):
            if monitor.stop() is False:
                pending = True
        if pending:
            event.ignore()
            QTimer.singleShot(250, self.close)
            return
        self.anim_group.stop()
        super().closeEvent(event)
        if hasattr(self, 'runtime_tray'):
            self.runtime_tray.tray.hide()
            QApplication.instance().quit()

if __name__ == "__main__":
    from desktop_entry import run
    sys.exit(run(DynamicIsland))

