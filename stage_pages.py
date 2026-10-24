"""Stage pages for Weather and Calendar: large thin numbers, calm detail beside them.

Weather pairs the temperature with a sunlit curve of the coming hours; Calendar
pairs today's date and agenda with a compact month that rings today.
"""
import datetime
import re

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
import qtawesome as qta

from media_widgets import ElidedLabel
from ui_tokens import font, font_css, resolved_family


def degrees(text):
    match = re.search(r'-?\d+', str(text or ''))
    return int(match.group()) if match else None


def open_button(open_app, kind, tooltip):
    button = QPushButton(objectName='StageOpen')
    button.setFixedSize(32, 32)
    button.setToolTip(tooltip)
    button.setAccessibleName(tooltip)
    button.setProperty('daisyIcon', 'ph.arrow-square-out')
    button.clicked.connect(lambda: open_app(kind))
    return button


class TemperatureCurve(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.points, self.theme = [], None
        self.setMinimumHeight(140)
        self.setAccessibleName('Temperature over the next hours')

    def set_points(self, points):
        self.points = [(str(label), value) for label, value in points if value is not None]
        self.setAccessibleDescription(', '.join(f'{label} {value}°' for label, value in self.points))
        self.update()

    def paintEvent(self, _event):
        if len(self.points) < 2 or self.theme is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        sun, text, muted = QColor(self.theme['wash_sun']), QColor(self.theme['text']), QColor(self.theme['muted'])
        values = [v for _, v in self.points]
        low, high = min(values) - 1, max(values) + 1
        pad, top, bottom = 18., 24., self.height() - 26.
        step = (self.width() - 2 * pad) / (len(values) - 1)
        spots = [QPointF(pad + i * step, bottom - (v - low) / (high - low) * (bottom - top)) for i, v in enumerate(values)]
        line = QPainterPath(spots[0])
        for a, b in zip(spots, spots[1:]):
            middle = (a.x() + b.x()) / 2
            line.cubicTo(QPointF(middle, a.y()), QPointF(middle, b.y()), b)
        area = QPainterPath(line)
        area.lineTo(spots[-1].x(), self.height() - 18)
        area.lineTo(spots[0].x(), self.height() - 18)
        area.closeSubpath()
        fill = QLinearGradient(0, top, 0, self.height() - 18)
        start, end = QColor(sun), QColor(sun)
        start.setAlphaF(.28)
        end.setAlphaF(0.)
        fill.setColorAt(0., start)
        fill.setColorAt(1., end)
        painter.fillPath(area, fill)
        painter.setPen(QPen(sun, 2., Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(line)
        painter.setFont(font('caption'))
        for index, (spot, (label, value)) in enumerate(zip(spots, self.points)):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(sun if index == 0 else muted)
            painter.drawEllipse(spot, 3.5 if index == 0 else 2.2, 3.5 if index == 0 else 2.2)
            painter.setPen(text)
            painter.drawText(QRectF(spot.x() - 24, spot.y() - 22, 48, 14), Qt.AlignmentFlag.AlignCenter, f'{value}°')
            painter.setPen(muted)
            painter.drawText(QRectF(spot.x() - 30, self.height() - 16, 60, 14), Qt.AlignmentFlag.AlignCenter, label)
        painter.end()


class WeatherPage(QWidget):
    def __init__(self, city, open_app, parent=None):
        super().__init__(parent)
        self.setObjectName('StagePage')
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(24)
        left = QVBoxLayout()
        left.setSpacing(2)
        # Empty until a forecast arrives; its height is kept so nothing jumps.
        self.temp = QLabel('', objectName='BigTemp')
        self.temp.setMinimumHeight(92)
        self.city = ElidedLabel(city)
        self.city.setObjectName('Strong')
        self.desc = ElidedLabel('Loading weather…')
        self.desc.setObjectName('Muted')
        left.addWidget(self.temp)
        left.addSpacing(8)
        left.addWidget(self.city)
        left.addWidget(self.desc)
        left.addStretch()
        right = QVBoxLayout()
        right.setSpacing(0)
        header = QHBoxLayout()
        caption = QLabel('NEXT HOURS', objectName='Caption')
        self.open = open_button(open_app, 'weather', 'Open Weather')
        header.addWidget(caption)
        header.addStretch()
        header.addWidget(self.open)
        right.addLayout(header)
        self.curve = TemperatureCurve()
        right.addWidget(self.curve, 1)
        holder = QWidget()
        holder.setFixedWidth(200)
        holder.setLayout(left)
        row.addWidget(holder)
        row.addLayout(right, 1)

    def update_weather(self, data):
        self.temp.setText(str(data.get('temp', '')))
        self.city.setText(str(data.get('city', '')))
        self.desc.setText(str(data.get('desc', '')))
        self.curve.set_points([(slot.get('time', ''), degrees(slot.get('temp'))) for slot in data.get('hourly', [])])

    def set_theme(self, theme):
        self.curve.theme = theme
        self.open.setIcon(qta.icon('ph.arrow-square-out', color=theme['muted'], color_active=theme['text']))
        self.setStyleSheet(page_css(theme))
        self.curve.update()


class MonthGrid(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme, self.today = None, datetime.date.today()
        self.setMinimumHeight(150)

    def set_today(self, today):
        self.today = today
        self.setAccessibleName(today.strftime('%B %Y, today is %A %d'))
        self.update()

    def paintEvent(self, _event):
        if self.theme is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        first = self.today.replace(day=1)
        days = ((first.replace(month=first.month % 12 + 1, year=first.year + first.month // 12)) - first).days
        cell_w, cell_h = self.width() / 7, (self.height() - 18) / 6
        painter.setFont(font('caption'))
        muted, faint = QColor(self.theme['muted']), QColor(self.theme['muted'])
        faint.setAlphaF(.45)
        for column, letter in enumerate('MTWTFSS'):
            painter.setPen(muted)
            painter.drawText(QRectF(column * cell_w, 0, cell_w, 14), Qt.AlignmentFlag.AlignCenter, letter)
        painter.setFont(font('secondary'))
        offset = first.weekday()
        for day in range(1, days + 1):
            slot = offset + day - 1
            cell = QRectF((slot % 7) * cell_w, 18 + (slot // 7) * cell_h, cell_w, cell_h)
            if day == self.today.day:
                painter.setPen(QPen(QColor(self.theme['accent']), 1.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                side = min(cell_h, cell_w) - 2
                painter.drawEllipse(cell.center(), side / 2, side / 2)
                painter.setPen(QColor(self.theme['text']))
            else:
                painter.setPen(faint if day < self.today.day else (muted if slot % 7 > 4 else QColor(self.theme['text'])))
            painter.drawText(cell, Qt.AlignmentFlag.AlignCenter, str(day))
        painter.end()


class CalendarPage(QWidget):
    def __init__(self, open_app, parent=None):
        super().__init__(parent)
        self.setObjectName('StagePage')
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(28)
        left = QVBoxLayout()
        left.setSpacing(0)
        self.day = QLabel(objectName='BigDay')
        self.weekday = QLabel(objectName='Strong')
        self.month = QLabel(objectName='Muted')
        left.addWidget(self.day)
        left.addSpacing(6)
        left.addWidget(self.weekday)
        left.addWidget(self.month)
        left.addSpacing(12)
        self.agenda = QVBoxLayout()
        self.agenda.setSpacing(8)
        left.addLayout(self.agenda)
        left.addStretch()
        holder = QWidget()
        holder.setFixedWidth(176)
        holder.setLayout(left)
        right = QVBoxLayout()
        right.setSpacing(0)
        header = QHBoxLayout()
        header.addStretch()
        self.open = open_button(open_app, 'month', 'Open date and time settings')
        header.addWidget(self.open)
        right.addLayout(header)
        self.grid = MonthGrid()
        right.addWidget(self.grid, 1)
        row.addWidget(holder)
        row.addLayout(right, 1)
        self.theme = None

    def refresh(self, agenda, today=None):
        today = today or datetime.date.today()
        self.day.setText(str(today.day))
        self.weekday.setText(today.strftime('%A'))
        self.month.setText(today.strftime('%B %Y'))
        self.grid.set_today(today)
        while self.agenda.count():
            item = self.agenda.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for title, when in agenda[:2]:
            entry = QWidget()
            line = QHBoxLayout(entry)
            line.setContentsMargins(0, 0, 0, 0)
            line.setSpacing(10)
            bar = QWidget(objectName='AgendaBar')
            bar.setFixedWidth(3)
            text = QVBoxLayout()
            text.setSpacing(0)
            name = ElidedLabel(title)
            name.setObjectName('Strong')
            time = QLabel(when, objectName='Muted')
            text.addWidget(name)
            text.addWidget(time)
            line.addWidget(bar)
            line.addLayout(text, 1)
            self.agenda.addWidget(entry)

    def set_theme(self, theme):
        self.theme = self.grid.theme = theme
        self.open.setIcon(qta.icon('ph.arrow-square-out', color=theme['muted'], color_active=theme['text']))
        self.setStyleSheet(page_css(theme))
        self.grid.update()


def page_css(t):
    return f'''
        QWidget#StagePage, QWidget {{ background: transparent; }}
        QLabel {{ color: {t['text']}; background: transparent; border: none; }}
        QLabel#BigTemp, QLabel#BigDay {{ font-family: "{resolved_family()}"; font-weight: 200; color: {t['text']}; }}
        QLabel#BigTemp {{ font-size: 84px; }}
        QLabel#BigDay {{ font-size: 76px; }}
        QLabel#Strong {{ {font_css('title')} color: {t['text']}; }}
        QLabel#Muted {{ {font_css('secondary')} color: {t['muted']}; }}
        QLabel#Caption {{ {font_css('caption')} color: {t['muted']}; }}
        QWidget#AgendaBar {{ background: {t['accent']}; border-radius: 1px; }}
        QPushButton#StageOpen {{ background: transparent; border: 1px solid transparent; border-radius: 16px; }}
        QPushButton#StageOpen:hover {{ background: {t['surface']}; }}
        QPushButton#StageOpen:focus {{ border-color: {t['accent']}; }}
    '''
