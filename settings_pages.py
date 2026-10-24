"""Small native Settings forms; all edits target a detached draft callback."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from settings_draft import CHOICES


class SettingsPages:
    def __init__(self, draft, changed, controls, actions, diagnostics, sources):
        self.draft, self.changed, self.controls = draft, changed, controls
        self.actions, self.diagnostics = actions or {}, diagnostics or {}
        self.sources = sources or []
        self.action_buttons = {}

    def _form(self, explanation):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(16)
        label = QLabel(explanation)
        label.setWordWrap(True)
        label.setObjectName('SettingsDescription')
        layout.addWidget(label)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(16)
        layout.addLayout(form)
        layout.addStretch()
        return page, form

    def _combo(self, form, title, key, values):
        combo = QComboBox()
        for text, value in values:
            combo.addItem(text, value)
        combo.setMinimumContentsLength(1)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setCurrentIndex(combo.findData(self.draft[key]))
        combo.currentIndexChanged.connect(lambda _: self.changed(key, combo.currentData()))
        combo.setAccessibleName(title)
        self.controls[key] = combo
        form.addRow(title, combo)
        return combo

    def _check(self, form, title, key):
        checkbox = QCheckBox(title)
        checkbox.setChecked(self.draft[key])
        checkbox.toggled.connect(lambda value: self.changed(key, value))
        self.controls[key] = checkbox
        form.addRow('', checkbox)

    def appearance(self):
        page, form = self._form('Preview changes before saving.')
        self._combo(form, 'Surface', 'surface_treatment',
                    [('Neutral — black and charcoal', 'neutral'), ('Tinted — theme-colored surfaces', 'tinted')])
        self._combo(form, 'Motion', 'motion_mode',
                    [('Auto — follow Windows', 'auto'), ('Full — smooth transitions', 'full'),
                     ('Reduced — immediate changes', 'reduced')])
        self._check(form, 'Enable decorative effects', 'decorative_effects_enabled')
        for title, key in (('Color theme', 'theme'), ('Shell style', 'island_style'),
                           ('Background motion', 'animation_style'), ('Idle icon', 'idle_icon')):
            self._combo(form, title, key, [(value, value) for value in CHOICES[key]])
        line = QHBoxLayout()
        path = QLineEdit(self.draft['custom_idle_icon'])
        path.setPlaceholderText('Choose your own animated GIF')
        path.setAccessibleName('Custom idle GIF path')
        path.textChanged.connect(lambda value: self.changed('custom_idle_icon', value))
        self.controls['custom_idle_icon'] = path
        line.addWidget(path)
        button = QPushButton('Browse…')
        def browse():
            file, _ = QFileDialog.getOpenFileName(page, 'Choose idle animation', '', 'GIF animation (*.gif)')
            if file:
                path.setText(file)
        button.clicked.connect(browse)
        line.addWidget(button)
        form.addRow('Custom GIF', line)
        self._combo(form, 'Auto-hide after', 'autohide_delay',
                    [('Off', 0), ('5 seconds', 5), ('10 seconds', 10), ('30 seconds', 30)])
        note = QLabel('Decorative effects animate the background when motion allows. '
                      'Reduced motion shows idle icons as still images. The edge line stays black.')
        note.setWordWrap(True)
        form.addRow(note)
        return page

    def media(self):
        page, form = self._form('Automatic follows the active media app and prefers playing Spotify. '
                               'A preferred app is remembered when it temporarily disappears.')
        sources = [('', 'Automatic')]
        seen = {''}
        for item in self.sources:
            if isinstance(item, dict) and isinstance(item.get('id'), str) and item['id'] not in seen:
                sources.append((item['id'], str(item.get('name') or item['id'])))
                seen.add(item['id'])
        preferred = self.draft['preferred_media_source']
        if preferred and preferred not in seen:
            sources.append((preferred, preferred + ' (unavailable)'))
        self._combo(form, 'Preferred media app', 'preferred_media_source',
                    [(name, source_id) for source_id, name in sources])
        note = QLabel('Playback and seeking are available only when the selected app supports them. '
                      'Full song and artist names appear in tooltips.')
        note.setWordWrap(True)
        form.addRow(note)
        return page

    def tools(self):
        page, form = self._form('Focus timer and file shelf live in Daisy’s Tools view.')
        timer = QSpinBox()
        timer.setRange(1, 180)
        timer.setSuffix(' min')
        timer.setValue(self.draft['timer_default_minutes'])
        timer.valueChanged.connect(lambda value: self.changed('timer_default_minutes', value))
        timer.setAccessibleName('Default focus duration in minutes')
        self.controls['timer_default_minutes'] = timer
        form.addRow('Default focus duration', timer)
        label = QLabel('Timers reset when Daisy restarts. The shelf remembers up to 20 file or folder '
                       'references. Removing an item never deletes the original.')
        label.setWordWrap(True)
        form.addRow(label)
        return page

    def general(self):
        page, form = self._form('Local status and recovery. Diagnostics stay on this computer.')
        self._check(form, 'Start Daisy when I sign in', 'start_with_windows')
        self._check(form, 'Keep a notification inbox', 'notification_inbox_enabled')
        note = QLabel('The inbox keeps notifications that apps published to Windows. '
                      'Daisy reads nothing else, and nothing is kept until you ask for it.')
        note.setWordWrap(True)
        form.addRow(note)
        self._check(form, 'Use compatibility mode', 'compatibility_mode')
        info = self.diagnostics
        for title, keys in (('Version', ('version',)), ('Installed path', ('path', 'installed_path')),
                            ('Startup status', ('startup_status', 'startup')),
                            ('Log location', ('log_directory', 'log_dir', 'logs'))):
            value = next((info[key] for key in keys if key in info), 'Unavailable')
            if isinstance(value, dict):
                value = value.get('state', 'Unavailable') + (' — ' + value['detail'] if value.get('detail') else '')
            label = QLabel(str(value))
            label.setWordWrap(True)
            label.setTextInteractionFlags(label.textInteractionFlags() | Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(title, label)
        for key, title in (('startup_settings', 'Open Windows Startup Settings'),
                           ('logs', 'Open Logs'), ('restart', 'Restart Daisy')):
            button = QPushButton(title)
            button.setEnabled(callable(self.actions.get(key)))
            if button.isEnabled():
                button.clicked.connect(self.actions[key])
            self.action_buttons[key] = button
            form.addRow('', button)
        return page
