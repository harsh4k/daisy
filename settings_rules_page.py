"""Exact app overrides with browse, running-app selection and reversible defaults."""
from pathlib import Path

import psutil
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QGridLayout, QInputDialog, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView)

from app_rules import DEFAULT_RULES, MODES, normalize_rules


class RulesPage(QWidget):
    def __init__(self, rules, changed, parent=None):
        super().__init__(parent)
        self.rules = dict(rules)
        self.changed = changed
        layout = QVBoxLayout(self)
        help_text = QLabel('Choose how Daisy behaves in each app. Removing an override restores its default.')
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Executable', 'Behavior', 'Rule'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAccessibleName('App behavior rules')
        self.table.doubleClicked.connect(lambda _: self.edit_rule())
        layout.addWidget(self.table)
        row = QGridLayout()
        for index, (title, callback) in enumerate((('Add app…', self.add_rule), ('Running apps…', self.add_running),
                                ('Edit', self.edit_rule), ('Remove override', self.remove_rule),
                                ('Restore defaults', self.restore_defaults))):
            button = QPushButton(title)
            if title == 'Remove override':
                button.setObjectName('DangerAction')
            button.clicked.connect(callback)
            row.addWidget(button, index // 3, index % 3)
        layout.addLayout(row)
        self.error = QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.refresh()

    def refresh(self):
        effective = {**DEFAULT_RULES, **self.rules}
        self.table.setRowCount(len(effective))
        for row, (name, mode) in enumerate(sorted(effective.items())):
            for column, value in enumerate((name, MODES[mode], 'Override' if name in self.rules else 'Default')):
                self.table.setItem(row, column, QTableWidgetItem(value))

    def _commit(self, rules):
        self.rules = normalize_rules(rules)
        self.changed(dict(self.rules))
        self.error.clear()
        self.refresh()

    def set_rule(self, name, mode, previous=None):
        """Validate a single user edit before replacing the detached rule dictionary."""
        try:
            entry = normalize_rules({name: mode})
            canonical = next(iter(entry))
            if canonical in self.rules and canonical != previous:
                raise ValueError('This executable already has an override. Select Edit instead.')
            rules = dict(self.rules)
            if previous:
                rules.pop(previous, None)
            rules.update(entry)
            self._commit(rules)
            return True
        except ValueError as exc:
            self.error.setText(str(exc))
            return False

    def selected_name(self):
        row = self.table.currentRow()
        return self.table.item(row, 0).text() if row >= 0 else None

    def add_rule(self):
        self._editor()

    def edit_rule(self):
        if self.selected_name():
            self._editor(self.selected_name())

    def remove_rule(self):
        name = self.selected_name()
        if name in self.rules:
            rules = dict(self.rules)
            rules.pop(name)
            self._commit(rules)

    def restore_defaults(self):
        self._commit({})

    def add_running(self):
        names = set()
        for process in psutil.process_iter(['name']):
            try:
                name = process.info['name']
                if name and name.casefold().endswith('.exe'):
                    names.add(name)
            except (psutil.Error, OSError):
                continue
        if names:
            name, ok = QInputDialog.getItem(self, 'Running apps', 'Executable', sorted(names), 0, False)
            if ok:
                self._editor(name, existing=False)
        else:
            self.error.setText('No running executable names are available. Use Add app instead.')

    def _editor(self, name='', existing=True):
        dialog = QDialog(self)
        dialog.setWindowTitle('App behavior')
        layout = QFormLayout(dialog)
        executable = QLineEdit(name)
        executable.setPlaceholderText('example.exe')
        layout.addRow('Executable name', executable)
        browse = QPushButton('Choose .exe…')
        def choose():
            path, _ = QFileDialog.getOpenFileName(dialog, 'Choose an application', '', 'Applications (*.exe)')
            if path:
                executable.setText(Path(path).name)
        browse.clicked.connect(choose)
        layout.addRow('', browse)
        mode = QComboBox()
        for key, title in MODES.items():
            mode.addItem(title, key)
        current = self.rules.get(name, DEFAULT_RULES.get(name, 'hover'))
        mode.setCurrentIndex(mode.findData(current))
        layout.addRow('Behavior', mode)
        error = QLabel()
        error.setWordWrap(True)
        layout.addRow(error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        def accept():
            if self.set_rule(executable.text(), mode.currentData(), name if existing else None):
                dialog.accept()
            else:
                error.setText(self.error.text())
        buttons.accepted.connect(accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        dialog.exec()
