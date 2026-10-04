"""View ▸ Queue: every file of this session, as a list. Double-click opens a
file in the guide; the folder button shows it (the export, once there is one).
Port of QueueWindow.swift."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from blurry_opsec.gui import store as S
from blurry_opsec.gui import strings as L
from blurry_opsec.gui import style
from blurry_opsec.gui.widgets import button, glyph, label

STATUS_COLOR = {
    S.READY: style.ACCENT,
    S.EXPORTED: style.ACCENT,
    S.REVIEW: style.ORANGE,
    S.NO_FACES: style.RED,
    S.ERROR: style.RED,
}


class Row(QWidget):
    reveal = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 5, 8, 5)
        row.setSpacing(12)
        self.thumb = QLabel()
        self.thumb.setFixedSize(48, 36)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setStyleSheet("background: rgba(0,0,0,0.3); border-radius: 5px;")
        text = QVBoxLayout()
        text.setSpacing(3)
        line = QHBoxLayout()
        line.setSpacing(6)
        self.name = QLabel()
        self.current = QLabel()
        self.current.setFixedSize(5, 5)
        self.current.setStyleSheet("background: white; border-radius: 2px;")
        line.addWidget(self.name)
        line.addWidget(self.current)
        line.addStretch(1)
        status = QHBoxLayout()
        status.setSpacing(6)
        self.dot = QLabel()
        self.dot.setFixedSize(6, 6)
        self.status = label("", "caption")
        self.faces = label("", "caption")
        status.addWidget(self.dot)
        status.addWidget(self.status)
        status.addWidget(self.faces)
        status.addStretch(1)
        text.addLayout(line)
        text.addLayout(status)
        self.folder = button("", "quiet")
        self.folder.setIcon(glyph("folder", style.SECONDARY, 18))
        self.folder.setIconSize(QSize(18, 18))
        self.folder.setToolTip(L.show_in_folder())
        self.folder.setAccessibleName(L.show_in_folder())
        self.folder.clicked.connect(lambda: self.reveal.emit(self.target))
        row.addWidget(self.thumb)
        row.addLayout(text, 1)
        row.addWidget(self.folder)
        self.target: Path | None = None
        self._thumb_of = None

    def sync(self, item: S.Item, current: bool) -> None:
        if item.thumb is not self._thumb_of:
            self._thumb_of = item.thumb
            if item.thumb is not None and not item.thumb.isNull():
                pm = QPixmap.fromImage(item.thumb).scaled(
                    96,
                    72,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                pm = pm.copy((pm.width() - 96) // 2, (pm.height() - 72) // 2, 96, 72)
                pm.setDevicePixelRatio(2)
                self.thumb.setPixmap(pm)
            else:
                self.thumb.setText("▢" if item.kind == "image" else "▶")
        self.name.setText(
            self.name.fontMetrics().elidedText(item.name, Qt.TextElideMode.ElideMiddle, 300)
        )
        self.name.setToolTip(item.name)
        self.current.setVisible(current)
        color = STATUS_COLOR.get(item.status, style.SECONDARY)
        self.dot.setStyleSheet(f"background: {color}; border-radius: 3px;")
        self.status.setText(L.status(item.status, item.progress))
        self.status.setStyleSheet(f"color: {color};")
        self.status.setToolTip(item.error)
        show_faces = item.faces is not None and item.status != S.NO_FACES
        self.faces.setVisible(show_faces)
        self.faces.setText("·  " + L.faces(item.faces or 0))
        self.target = item.output or item.path
        self.folder.setToolTip(L.show_in_folder())


class QueueWindow(QWidget):
    open_item = Signal(int)
    reveal = Signal(object)

    def __init__(self, store: S.Store, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setObjectName("queueWindow")
        self.store = store
        self.setMinimumSize(460, 260)
        self.resize(560, 420)
        self.stack = QStackedWidget()
        self.empty = label("", "secondary")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        self.list.itemDoubleClicked.connect(
            lambda it: self._open(it.data(Qt.ItemDataRole.UserRole))
        )
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self.list)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.addWidget(self.stack)
        delete = QAction(self)
        delete.setShortcuts([QKeySequence.StandardKey.Delete, QKeySequence(Qt.Key.Key_Backspace)])
        delete.triggered.connect(self._remove_selected)
        self.list.addAction(delete)
        self._rows: dict[int, Row] = {}
        store.changed.connect(self.sync)
        self.sync()

    def sync(self) -> None:
        self.setWindowTitle(L.queue())
        self.empty.setText(L.queue_empty())
        items = self.store.items
        self.stack.setCurrentWidget(self.list if items else self.empty)
        ids = [it.id for it in items]
        if ids != list(self._rows):
            selected = set(self._selected())
            self.list.clear()
            self._rows = {}
            for it in items:
                entry = QListWidgetItem()
                entry.setData(Qt.ItemDataRole.UserRole, it.id)
                entry.setSizeHint(QSize(0, 52))
                row = Row()
                row.reveal.connect(self.reveal)
                self.list.addItem(entry)
                self.list.setItemWidget(entry, row)
                self._rows[it.id] = row
                entry.setSelected(it.id in selected)
        for it in items:
            self._rows[it.id].sync(it, it.id == self.store.current_id)

    def _selected(self) -> list[int]:
        return [it.data(Qt.ItemDataRole.UserRole) for it in self.list.selectedItems()]

    def _open(self, item_id: int) -> None:
        self.open_item.emit(item_id)

    def _remove_selected(self) -> None:
        if ids := set(self._selected()):
            self.store.remove(ids)

    def _menu(self, pos) -> None:
        ids = self._selected()
        if not ids:
            return
        menu = QMenu(self)
        if len(ids) == 1:
            menu.addAction(L.open_in_guide(), lambda: self._open(ids[0]))
            menu.addSeparator()
        menu.addAction(L.remove(), lambda: self.store.remove(set(ids)))
        menu.exec(self.list.viewport().mapToGlobal(pos))
