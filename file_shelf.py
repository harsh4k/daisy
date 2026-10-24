"""A shelf stores references. Removing an item never changes its original file."""
import os
from pathlib import Path
import qtawesome as qta

from PyQt6.QtCore import Qt, QSize, QMimeData, QUrl, QFileInfo, pyqtSignal
from PyQt6.QtGui import QDrag, QDesktopServices
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QListWidget, QListWidgetItem, QFileIconProvider,
                             QFileDialog, QLabel, QAbstractItemView)

from theme_tokens import get_theme


class ShelfModel:
    def __init__(self, paths=None):
        self.paths = []
        if isinstance(paths, list):
            for value in paths:
                try:
                    self.add([value])
                except ValueError:
                    continue

    def add(self, paths):
        result = list(self.paths)
        seen = {os.path.normcase(p) for p in result}
        for value in paths:
            if not isinstance(value, str) or not value.strip() or value.startswith('\\\\'):
                raise ValueError('Choose files or folders on a local drive.')
            path = os.path.abspath(value)
            if path.replace('/', '\\').startswith('\\\\'):
                raise ValueError('Choose files or folders on a local drive.')
            key = os.path.normcase(path)
            if key not in seen:
                if len(result) >= 20:
                    raise ValueError('The shelf holds up to 20 items. Remove an item first.')
                result.append(path)
                seen.add(key)
        self.paths = result

    def remove(self, index):
        if 0 <= index < len(self.paths):
            self.paths.pop(index)

    def available(self, index):
        return 0 <= index < len(self.paths) and Path(self.paths[index]).exists()

    def mime_data(self, indices):
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(self.paths[i]) for i in indices
                      if 0 <= i < len(self.paths)])
        return mime


class ShelfList(QListWidget):
    files_dropped = pyqtSignal(list)

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAccessibleName('File shelf; drop local files or use Add files')

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and all(u.isLocalFile() for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls and all(url.isLocalFile() for url in urls):
            self.files_dropped.emit([url.toLocalFile() for url in urls])
            event.acceptProposedAction()

    def startDrag(self, actions):
        indices = [self.row(item) for item in self.selectedItems()]
        indices = [i for i in indices if self.model.available(i)]
        if indices:
            drag = QDrag(self)
            drag.setMimeData(self.model.mime_data(indices))
            drag.exec(Qt.DropAction.CopyAction)


class FileShelf(QWidget):
    changed = pyqtSignal(list)
    dialog_active = pyqtSignal(bool)

    def __init__(self, paths=None, parent=None):
        super().__init__(parent)
        self.model = ShelfModel(paths)
        self.icons = QFileIconProvider()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 4)
        layout.setSpacing(8)
        self.message = QLabel('Drop files here')
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.list = ShelfList(self.model)
        self.list.files_dropped.connect(self.add_paths)
        self.list.itemDoubleClicked.connect(lambda _: self.open_selected())
        self.list.currentRowChanged.connect(self._update_actions)
        layout.addWidget(self.list, 1)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.action_buttons = []
        for label, icon, callback in [('Add files', 'file-plus', self.choose_files),
                                     ('Add folder', 'folder-plus', self.choose_folder),
                                     ('Open', 'arrow-square-out', self.open_selected),
                                     ('Show in Explorer', 'folder-open', self.reveal_selected),
                                     ('Remove', 'minus-circle', self.remove_selected)]:
            button = QPushButton()
            button.setProperty('shelfIcon', icon)
            button.setFixedSize(32, 32)
            button.setIconSize(QSize(20, 20))
            button.setAccessibleName(label + (' from shelf' if label == 'Remove' else ''))
            button.setToolTip(button.accessibleName())
            if label == 'Remove':
                button.setObjectName('DangerAction')
            button.clicked.connect(callback)
            actions.addWidget(button)
            self.action_buttons.append(button)
            if label == 'Open':
                self.open_button = button
            elif label == 'Show in Explorer':
                self.reveal_button = button
            elif label == 'Remove':
                self.remove_button = button
        actions.addStretch()
        layout.addLayout(actions)
        self.set_theme(get_theme())
        self.refresh()

    def set_theme(self, theme):
        for button in self.action_buttons:
            color = theme['danger'] if button is self.remove_button else theme['text']
            button.setIcon(qta.icon('ph.' + button.property('shelfIcon'), color=color))

    def refresh(self):
        selected = self.list.currentRow()
        self.list.clear()
        for index, path in enumerate(self.model.paths):
            present = self.model.available(index)
            info = QFileInfo(path)
            label = info.fileName() or path
            if not present:
                label += ' — unavailable'
            item = QListWidgetItem(self.icons.icon(info), label)
            item.setToolTip(path)
            self.list.addItem(item)
        if 0 <= selected < self.list.count():
            self.list.setCurrentRow(selected)
        self._update_actions()

    def _update_actions(self):
        index = self.list.currentRow()
        available = self.model.available(index)
        self.open_button.setEnabled(available)
        self.reveal_button.setEnabled(available)
        self.remove_button.setEnabled(index >= 0)

    def add_paths(self, paths):
        try:
            self.model.add(paths)
            self.message.setText(f'{len(self.model.paths)} of 20 items · originals stay in place')
            self.refresh()
            self.changed.emit(list(self.model.paths))
        except ValueError as error:
            self.message.setText(str(error))

    def choose_files(self):
        self.dialog_active.emit(True)
        try:
            paths, _ = QFileDialog.getOpenFileNames(self, 'Add files to Daisy')
            if paths:
                self.add_paths(paths)
        finally:
            self.dialog_active.emit(False)

    def choose_folder(self):
        self.dialog_active.emit(True)
        try:
            path = QFileDialog.getExistingDirectory(self, 'Add folder to Daisy')
            if path:
                self.add_paths([path])
        finally:
            self.dialog_active.emit(False)

    def open_selected(self):
        index = self.list.currentRow()
        if self.model.available(index):
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(self.model.paths[index])):
                self.message.setText('This item could not be opened. Try Show in Explorer.')

    def reveal_selected(self):
        import subprocess
        index = self.list.currentRow()
        if self.model.available(index):
            path = self.model.paths[index]
            try:
                subprocess.Popen(['explorer.exe', '/select,', path], shell=False)
            except OSError:
                self.message.setText('Explorer could not be opened.')

    def remove_selected(self):
        index = self.list.currentRow()
        if index >= 0:
            self.model.remove(index)
            self.refresh()
            self.changed.emit(list(self.model.paths))
