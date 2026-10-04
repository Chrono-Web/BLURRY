"""Settings, grouped as on the Mac (PreferencesView.swift): processing, language,
guide, privacy, updates, uninstall."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from blurry_opsec import __version__, i18n, levels
from blurry_opsec.gui import lifecycle, style
from blurry_opsec.gui import strings as L
from blurry_opsec.gui.store import Store
from blurry_opsec.gui.widgets import Combo, button, glyph, label


class Group(QWidget):
    """A section: header, a rounded box of rows, footnotes."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)
        self.header = label("", "formHeader")
        self.box = QFrame()
        self.box.setObjectName("group")
        self.rows = QVBoxLayout(self.box)
        self.rows.setContentsMargins(12, 6, 12, 6)
        self.rows.setSpacing(0)
        self.footer = QVBoxLayout()
        self.footer.setSpacing(6)
        self.footer.setContentsMargins(12, 0, 12, 0)
        col.addWidget(self.header)
        col.addWidget(self.box)
        col.addLayout(self.footer)

    def row(self, text_label=None, control: QWidget | None = None, under=None) -> QWidget:
        """A row: a label on the left and a control on the right, or one widget."""
        if self.rows.count():
            sep = QFrame()
            sep.setObjectName("separator")
            self.rows.addWidget(sep)
        row = QWidget()
        row.setObjectName("row")
        col = QVBoxLayout(row)
        col.setContentsMargins(0, 8, 0, 8)
        col.setSpacing(4)
        line = QHBoxLayout()
        line.setSpacing(10)
        if text_label is not None:
            line.addWidget(text_label)
            line.addStretch(1)
        if control is not None:
            line.addWidget(control)
            if text_label is None:
                line.addStretch(1)
        col.addLayout(line)
        if under is not None:
            col.addWidget(under)
        self.rows.addWidget(row)
        return row

    def note(self) -> object:
        lab = label("", "caption", wrap=True)
        self.footer.addWidget(lab)
        return lab


class PreferencesDialog(QDialog):
    def __init__(self, window, store: Store) -> None:
        super().__init__(window)
        self.window_ = window
        self.store = store
        self.resize(520, 680)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(22, 20, 22, 22)
        col.setSpacing(22)
        scroll.setWidget(body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        # Processing
        self.processing = Group()
        self.level_label = label()
        self.level = Combo()
        for key in levels.LEVELS:
            self.level.addItem("", key)
        self.level.activated.connect(lambda i: store.set_level(self.level.itemData(i)))
        self.level_hint = label("", "caption", wrap=True)
        self.processing.row(self.level_label, self.level, self.level_hint)
        self.mode_label = label()
        self.mode = Combo()
        for key in ("solid", "pixel"):
            self.mode.addItem("", key)
        self.mode.activated.connect(lambda i: store.set_mode(self.mode.itemData(i)))
        self.mode_hint = label("", "caption", wrap=True)
        self.processing.row(self.mode_label, self.mode, self.mode_hint)
        self.margin_label = label()
        margin = QWidget()
        ml = QHBoxLayout(margin)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(10)
        self.margin = QSlider(Qt.Orientation.Horizontal)
        self.margin.setRange(0, 20)  # 0–100% in steps of 5, as on the Mac
        self.margin.setFixedWidth(180)
        self.margin.valueChanged.connect(lambda v: store.set_padding(v * 5 / 100))
        self.margin_value = label("", "secondary")
        self.margin_value.setFixedWidth(44)
        self.margin_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        ml.addWidget(self.margin)
        ml.addWidget(self.margin_value)
        self.processing.row(self.margin_label, margin)
        self.restore = button("", "", store.restore_defaults)
        self.processing.row(None, self.restore)
        self.effect_note = self.processing.note()
        self.audio_note = self.processing.note()
        col.addWidget(self.processing)

        # Language (on the Mac it is the system's; here it can be chosen)
        self.language = Group()
        self.language_combo = Combo()
        for code, name in i18n.LANGUAGES.items():
            self.language_combo.addItem(name, code)
        self.language_combo.activated.connect(
            lambda i: window.set_language(self.language_combo.itemData(i))
        )
        self.language_row_label = label()
        self.language.row(self.language_row_label, self.language_combo)
        self.language_note = self.language.note()
        col.addWidget(self.language)

        # Guide
        self.guide = Group()
        self.guide_btn = button("", "", self._restart_guide)
        self.guide.row(None, self.guide_btn)
        self.guide_note = self.guide.note()
        col.addWidget(self.guide)

        # Privacy
        self.privacy = Group()
        privacy = QWidget()
        pl = QHBoxLayout(privacy)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(8)
        lock = label()
        lock.setPixmap(glyph("lock", style.ACCENT, 16).pixmap(16, 16))
        self.privacy_line = label("", "callout", wrap=True)
        pl.addWidget(lock)
        pl.addWidget(self.privacy_line, 1)
        self.privacy.row(None, privacy)
        self.privacy_note = self.privacy.note()
        col.addWidget(self.privacy)

        # Updates
        self.updates = Group()
        self.version_label = label()
        self.updates.row(self.version_label, label(__version__, "secondary"))
        self.updates_btn = button("", "", lifecycle.open_releases)
        self.updates.row(None, self.updates_btn)
        self.updates_note = self.updates.note()
        col.addWidget(self.updates)

        # Uninstall
        self.uninstall = Group()
        self.uninstall_btn = button("", "destructive", lambda: lifecycle.remove(window))
        self.uninstall.row(None, self.uninstall_btn)
        self.uninstall_note = self.uninstall.note()
        col.addWidget(self.uninstall)
        col.addStretch(1)

        store.changed.connect(self.sync)
        self.sync()

    def _restart_guide(self) -> None:
        self.close()
        self.window_.restart_guide()

    def sync(self) -> None:
        store = self.store
        self.setWindowTitle(L.preferences_title())
        self.processing.header.setText(L.processing())
        self.level_label.setText(L.sensitivity())
        for i in range(self.level.count()):
            self.level.setItemText(i, L.level_label(self.level.itemData(i)))
        self.level.setCurrentIndex(self.level.findData(store.level))
        self.level_hint.setText(L.level_description(store.level))
        self.mode_label.setText(L.cover())
        self.mode.setItemText(0, L.mode_solid())
        self.mode.setItemText(1, L.mode_pixel())
        self.mode.setCurrentIndex(self.mode.findData(store.mode))
        self.mode_hint.setText(
            L.mode_solid_hint() if store.mode == "solid" else L.mode_pixel_hint()
        )
        self.margin_label.setText(L.margin())
        self.margin.setAccessibleName(L.margin())
        step = round(store.padding * 20)
        if self.margin.value() != step:
            self.margin.blockSignals(True)
            self.margin.setValue(step)
            self.margin.blockSignals(False)
        self.margin_value.setText(f"{round(store.padding * 100)}%")
        self.restore.setText(L.restore_defaults())
        self.effect_note.setText(L.preferences_effect())
        self.audio_note.setText(L.audio_default())
        exporting = any(it.status == "exporting" for it in store.items)
        self.processing.box.setEnabled(not exporting)

        self.language.header.setText(L.language_title())
        self.language_row_label.setText(L.language_title())
        self.language_combo.setCurrentIndex(self.language_combo.findData(i18n.language()))
        self.language_note.setText(L.language_description())
        self.guide.header.setText(L.guide_title())
        self.guide_btn.setText(L.restart_guide())
        self.guide_note.setText(L.guide_description())
        self.privacy.header.setText(L.privacy_title())
        self.privacy_line.setText(L.welcome_line())
        self.privacy_note.setText(L.preferences_privacy())
        self.updates.header.setText(L.updates_title())
        self.version_label.setText(L.version())
        self.updates_btn.setText(L.updates())
        self.updates_note.setText(L.updates_description())
        self.uninstall.header.setText(L.uninstall_title())
        self.uninstall_btn.setText(L.uninstall())
        self.uninstall_btn.setEnabled(not store.busy)
        self.uninstall_note.setText(L.uninstall_description())
