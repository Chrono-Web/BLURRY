"""Review screens: image editor and video review."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from blurry_opsec import tracking
from blurry_opsec.gui import style
from blurry_opsec.gui.canvas import Canvas, CanvasBox
from blurry_opsec.gui.model import Item, decode_preview, preview_result
from blurry_opsec.gui.widgets import Switch, label
from blurry_opsec.i18n import t
from blurry_opsec.plan import NEAR_THRESHOLD, SMALL_FACE, TRACK_GAP, Box, ImagePlan, VideoPlan

SettingsFn = Callable[[], dict]


def _legend(color: str) -> QLabel:
    mark = QLabel("⌜⌟")
    mark.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 700;")
    return mark


class _ReviewBase(QWidget):
    finished = Signal()
    changed = Signal()

    def __init__(self, item: Item, settings: SettingsFn, parent=None) -> None:
        super().__init__(parent)
        self.item = item
        self.settings = settings
        self.back_btn = QPushButton()
        self.back_btn.setObjectName("link")
        self.back_btn.clicked.connect(self.finished)
        self.name = QLabel(item.name)
        self.name.setObjectName("muted")
        self.legend_auto = label()
        self.legend_manual = label()
        self.preview_label = label()
        self.preview_box = Switch()
        self.preview_box.toggled.connect(self._on_preview)
        self.done_btn = QPushButton()
        self.done_btn.setObjectName("primary")
        self.done_btn.clicked.connect(self.finished)
        top = QHBoxLayout()
        top.addWidget(self.back_btn)
        top.addSpacing(8)
        top.addWidget(self.name)
        top.addStretch(1)
        for color, legend in ((style.AUTO, self.legend_auto), (style.MANUAL, self.legend_manual)):
            top.addWidget(_legend(color))
            top.addWidget(legend)
            top.addSpacing(10)
        top.addWidget(self.preview_label)
        top.addWidget(self.preview_box)
        top.addSpacing(14)
        top.addWidget(self.done_btn)
        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.hide()
        self.help = QLabel()
        self.help.setObjectName("hint")
        self.help.setWordWrap(True)
        self.canvas = Canvas()
        self.canvas.box_added.connect(self._on_added)
        self.canvas.box_changed.connect(self._on_changed)
        self.canvas.box_deleted.connect(self._on_deleted)
        self.top = top

    def retranslate(self) -> None:
        self.back_btn.setText(t("back"))
        self.done_btn.setText(t("done"))
        self.preview_label.setText(t("preview").upper())
        self.legend_auto.setText(t("legend_auto").upper())
        self.legend_manual.setText(t("legend_manual").upper())
        self.update_banner()

    def update_banner(self) -> None:
        if self.item.uncovered_risk:
            self.banner.setObjectName("banner")
            self.banner.setText(t("banner_no_faces"))
            self.banner.show()
        elif self.item.review_flags() and not self.item.edited:
            self.banner.setObjectName("bannerInfo")
            self.banner.setText(t("banner_flags", n=len(self.item.review_flags())))
            self.banner.show()
        else:
            self.banner.hide()
        self.banner.style().unpolish(self.banner)
        self.banner.style().polish(self.banner)

    def mark_edited(self) -> None:
        self.item.edited = True
        self.item.settle()
        self.update_banner()
        self.changed.emit()

    def refresh_settings(self) -> None:
        """Mode/padding/level changed: redraw the preview if it is on."""
        if self.preview_box.isChecked():
            self._on_preview(True)

    # Implemented by subclasses
    def _on_preview(self, on: bool) -> None: ...
    def _on_added(self, box: Box) -> None: ...
    def _on_changed(self, key, box: Box) -> None: ...
    def _on_deleted(self, key) -> None: ...


class ImageReview(_ReviewBase):
    def __init__(self, item: Item, settings: SettingsFn, parent=None) -> None:
        super().__init__(item, settings, parent)
        if not isinstance(item.plan, ImagePlan) or item.preview is None:
            raise TypeError("ImageReview needs an analysed image")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.top)
        layout.addWidget(self.banner)
        layout.addWidget(self.canvas, 1)
        layout.addWidget(self.help)
        self.canvas.set_image(item.preview, item.preview_scale)
        self.refresh_boxes()
        self.retranslate()

    @property
    def plan(self) -> ImagePlan:
        return self.item.plan  # type: ignore[return-value]

    def retranslate(self) -> None:
        super().retranslate()
        self.help.setText(t("editor_help_image"))

    def refresh_boxes(self, selected=None) -> None:
        specs = [CanvasBox(i, b, b.source, True) for i, b in enumerate(self.plan.boxes)]
        self.canvas.set_boxes(specs, selected)

    def _on_added(self, box: Box) -> None:
        self.plan.add_box(box)
        self.refresh_boxes(len(self.plan.boxes) - 1)
        self.mark_edited()

    def _on_changed(self, key, box: Box) -> None:
        self.plan.boxes[key] = Box(box.x, box.y, box.w, box.h, None, "manual")
        self.refresh_boxes(key)
        self.mark_edited()

    def _on_deleted(self, key) -> None:
        self.plan.remove_box(key)
        self.refresh_boxes()
        self.mark_edited()

    def _on_preview(self, on: bool) -> None:
        if on:
            s = self.settings()
            img = preview_result(self.item.preview, self.plan.boxes, self.item.preview_scale,
                                 s["mode"], s["padding"], s["level"])  # fmt: skip
            self.canvas.set_image(img, self.item.preview_scale)
        else:
            self.canvas.set_image(self.item.preview, self.item.preview_scale)
        self.canvas.show_boxes(not on)


class Timeline(QWidget):
    seek = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(56)
        self.frame_count = 1
        self.position = 0
        self.rows: list[tuple[list[tuple[int, int]], str, bool]] = []
        self.markers: list[int] = []

    def x_of(self, frame: int) -> float:
        return 6 + (self.width() - 12) * frame / max(1, self.frame_count - 1)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(255, 255, 255, 26), 1))
        p.setBrush(QColor(style.SURFACE))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
        n = max(1, len(self.rows))
        row_h = max(3.0, min(10.0, (self.height() - 16) / n))
        for i, (spans, color, dashed) in enumerate(self.rows):
            y = 8 + i * row_h
            c = QColor(color)
            c.setAlpha(70 if dashed else 200)
            for a, b in spans:
                p.fillRect(QRectF(self.x_of(a), y, max(2.0, self.x_of(b) - self.x_of(a)),
                                  row_h - 1), c)  # fmt: skip
        p.setPen(QPen(QColor(style.WARN), 2))
        for f in self.markers:
            x = self.x_of(f)
            p.drawLine(int(x), self.height() - 7, int(x), self.height() - 2)
        p.setPen(QPen(QColor(style.TEXT), 1))
        x = int(self.x_of(self.position))
        p.drawLine(x, 0, x, self.height())

    def _seek_to(self, x: float) -> None:
        frac = (x - 6) / max(1, self.width() - 12)
        self.seek.emit(int(round(min(1, max(0, frac)) * (self.frame_count - 1))))

    def mousePressEvent(self, e) -> None:  # noqa: N802
        self._seek_to(e.position().x())

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        self._seek_to(e.position().x())


def _spans(frames) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for f in sorted(frames):
        if out and f == out[-1][1] + 1:
            out[-1] = (out[-1][0], f)
        else:
            out.append((f, f))
    return out


class VideoReview(_ReviewBase):
    def __init__(self, item: Item, settings: SettingsFn, frames, parent=None) -> None:
        super().__init__(item, settings, parent)
        if not isinstance(item.plan, VideoPlan):
            raise TypeError("VideoReview needs an analysed video")
        self.frames = frames
        self.index = 0
        self.wanted = 0
        self.loading = False
        self.image: QImage | None = None
        self.scale = 1.0
        self.selected_manual: int | None = None
        self.coverage = {
            tr.id: tracking.track_coverage(tr, self.plan.extend_frames, self.plan.frame_count)
            for tr in self.plan.tracks
        }

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, self.plan.frame_count - 1)
        self.slider.valueChanged.connect(self.go_to)
        self.prev_btn = QPushButton("◀")
        self.next_btn = QPushButton("▶")
        self.prev_btn.clicked.connect(lambda: self.go_to(self.index - 1))
        self.next_btn.clicked.connect(lambda: self.go_to(self.index + 1))
        self.pos_label = QLabel()
        self.pos_label.setObjectName("muted")
        self.timeline = Timeline()
        self.timeline.frame_count = self.plan.frame_count
        self.timeline.seek.connect(self.go_to)

        controls = QHBoxLayout()
        controls.addWidget(self.prev_btn)
        controls.addWidget(self.slider, 1)
        controls.addWidget(self.next_btn)
        controls.addWidget(self.pos_label)

        left = QVBoxLayout()
        left.addWidget(self.canvas, 1)
        left.addLayout(controls)
        left.addWidget(self.timeline)
        left.addWidget(self.help)

        self.tracks_title = label()
        self.track_list = QListWidget()
        self.track_list.itemChanged.connect(self._on_track_toggled)
        self.track_list.itemClicked.connect(self._on_track_clicked)
        self.manual_title = label()
        self.manual_list = QListWidget()
        self.manual_list.currentRowChanged.connect(self._on_manual_selected)
        self.from_label, self.to_label = QLabel(), QLabel()
        self.start_spin, self.end_spin = QDoubleSpinBox(), QDoubleSpinBox()
        duration = self.plan.frame_count / self.plan.fps
        for spin in (self.start_spin, self.end_spin):
            spin.setDecimals(2)
            spin.setSuffix(" s")
            spin.setRange(0.0, duration)
            spin.setSingleStep(0.1)
            spin.editingFinished.connect(self._on_range_edited)
        self.set_start_btn, self.set_end_btn = QPushButton(), QPushButton()
        self.set_start_btn.clicked.connect(lambda: self._set_range_edge(start=True))
        self.set_end_btn.clicked.connect(lambda: self._set_range_edge(start=False))
        self.delete_btn = QPushButton()
        self.delete_btn.clicked.connect(lambda: self._on_deleted(("m", self.selected_manual)))
        range_row = QHBoxLayout()
        range_row.addWidget(self.from_label)
        range_row.addWidget(self.start_spin)
        range_row.addWidget(self.to_label)
        range_row.addWidget(self.end_spin)
        edge_row = QHBoxLayout()
        edge_row.addWidget(self.set_start_btn)
        edge_row.addWidget(self.set_end_btn)
        edge_row.addWidget(self.delete_btn)
        self.range_editor = QWidget()
        rl = QVBoxLayout(self.range_editor)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addLayout(range_row)
        rl.addLayout(edge_row)

        side = QVBoxLayout()
        side.addWidget(self.tracks_title)
        side.addWidget(self.track_list, 2)
        side.addSpacing(8)
        side.addWidget(self.manual_title)
        side.addWidget(self.manual_list, 1)
        side.addWidget(self.range_editor)
        side_w = QWidget()
        side_w.setLayout(side)
        side_w.setFixedWidth(300)

        body = QHBoxLayout()
        body.addLayout(left, 1)
        body.addWidget(side_w)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.top)
        layout.addWidget(self.banner)
        layout.addLayout(body, 1)

        QShortcut(QKeySequence(Qt.Key.Key_Left), self, lambda: self.go_to(self.index - 1))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, lambda: self.go_to(self.index + 1))

        self.retranslate()
        self.refresh_side()
        self.request_frame()

    @property
    def plan(self) -> VideoPlan:
        return self.item.plan  # type: ignore[return-value]

    def seconds(self, frame: int) -> float:
        return frame / self.plan.fps

    def frame_of(self, seconds: float) -> int:
        return int(round(seconds * self.plan.fps))

    def retranslate(self) -> None:
        super().retranslate()
        self.help.setText(t("editor_help_video"))
        self.tracks_title.setText(t("tracks").upper())
        self.manual_title.setText(t("manual_ranges").upper())
        self.from_label.setText(t("from"))
        self.to_label.setText(t("to"))
        self.set_start_btn.setText(t("set_start"))
        self.set_end_btn.setText(t("set_end"))
        self.delete_btn.setText(t("delete"))
        self.refresh_side()
        self._update_pos_label()

    # -- frames ----------------------------------------------------------------
    def go_to(self, index: int) -> None:
        index = max(0, min(self.plan.frame_count - 1, int(index)))
        self.wanted = index
        if self.slider.value() != index:
            self.slider.blockSignals(True)
            self.slider.setValue(index)
            self.slider.blockSignals(False)
        self.timeline.position = index
        self.timeline.update()
        self._update_pos_label()
        self.request_frame()

    def request_frame(self) -> None:
        if self.loading:
            return
        self.loading = True
        target = self.wanted
        self.frames.request(
            "frame",
            {"path": str(self.item.path), "index": target, "max_side": 1600},
            on_result=self._on_frame,
            on_error=lambda _m: setattr(self, "loading", False),
        )

    def _on_frame(self, msg: dict) -> None:
        self.loading = False
        self.image = decode_preview(msg["preview"])
        self.scale = msg["scale"]
        self.index = msg["index"]
        self.show_frame()
        if self.wanted != self.index:
            self.request_frame()

    def show_frame(self) -> None:
        if self.image is None:
            return
        if self.preview_box.isChecked():
            s = self.settings()
            img = preview_result(self.image, self.plan.boxes_for(self.index), self.scale,
                                 s["mode"], s["padding"], s["level"])  # fmt: skip
            self.canvas.set_image(img, self.scale)
        else:
            self.canvas.set_image(self.image, self.scale)
        self.refresh_boxes()

    def _update_pos_label(self) -> None:
        s = self.seconds(self.wanted)
        self.pos_label.setText(f"{int(s // 60)}:{s % 60:05.2f}")
        self.pos_label.setToolTip(t("frame_of", i=self.wanted + 1, n=self.plan.frame_count))

    # -- boxes -----------------------------------------------------------------
    def refresh_boxes(self) -> None:
        specs = []
        for tr in self.plan.tracks:
            box = self.coverage[tr.id].get(self.index)
            if box is not None:
                specs.append(CanvasBox(("t", tr.id), box, "auto" if tr.enabled else "off", False))
        for i, m in enumerate(self.plan.manual):
            if m.start <= self.index <= m.end:
                specs.append(CanvasBox(("m", i), m.box, "manual", True))
        sel = ("m", self.selected_manual) if self.selected_manual is not None else None
        self.canvas.set_boxes(specs, sel)

    def _on_added(self, box: Box) -> None:
        start = self.index
        end = min(self.plan.frame_count - 1, start + int(round(self.plan.fps * 2)) - 1)
        self.plan.add_manual(start, end, box)
        self.selected_manual = len(self.plan.manual) - 1
        self.after_edit()

    def _on_changed(self, key, box: Box) -> None:
        _, i = key
        m = self.plan.manual[i]
        self.plan.update_manual(i, m.start, m.end, box)
        self.selected_manual = i
        self.after_edit()

    def _on_deleted(self, key) -> None:
        _, i = key
        if i is None:
            return
        self.plan.remove_manual(i)
        self.selected_manual = None
        self.after_edit()

    def after_edit(self) -> None:
        self.refresh_side()
        self.show_frame()
        self.mark_edited()

    def _on_preview(self, _on: bool) -> None:
        self.canvas.show_boxes(not self.preview_box.isChecked())
        self.canvas.drawing_enabled = not self.preview_box.isChecked()
        self.show_frame()

    # -- side panel --------------------------------------------------------------
    def refresh_side(self) -> None:
        flags_by_track: dict[int, list[str]] = {}
        labels = {NEAR_THRESHOLD: "flag_near_threshold", SMALL_FACE: "flag_small_face",
                  TRACK_GAP: "flag_track_gap"}  # fmt: skip
        for f in self.plan.flags:
            if f.track is not None and f.kind in labels:
                flags_by_track.setdefault(f.track, []).append(t(labels[f.kind]))
        self.track_list.blockSignals(True)
        self.track_list.clear()
        for n, tr in enumerate(self.plan.tracks, 1):
            frames = self.coverage[tr.id]
            a, b = min(frames), max(frames)
            text = f"{t('track_label', n=n)}   {self._clock(a)}–{self._clock(b)}"
            flags = flags_by_track.get(tr.id)
            if flags:
                text += "   ⚠ " + ", ".join(sorted(set(flags)))
            it = QListWidgetItem(text)
            it.setData(Qt.ItemDataRole.UserRole, tr.id)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if tr.enabled else Qt.CheckState.Unchecked)
            self.track_list.addItem(it)
        self.track_list.blockSignals(False)

        self.manual_list.blockSignals(True)
        self.manual_list.clear()
        for n, m in enumerate(self.plan.manual, 1):
            self.manual_list.addItem(
                f"{t('manual_label', n=n)}   {self._clock(m.start)}–{self._clock(m.end)}"
            )
        if self.selected_manual is not None and self.selected_manual < len(self.plan.manual):
            self.manual_list.setCurrentRow(self.selected_manual)
        self.manual_list.blockSignals(False)
        self._update_range_editor()

        rows = []
        for tr in self.plan.tracks:
            rows.append((_spans(self.coverage[tr.id]), style.AUTO if tr.enabled else style.OFF,
                         not tr.enabled))  # fmt: skip
        for m in self.plan.manual:
            rows.append(([(m.start, m.end)], style.MANUAL, False))
        self.timeline.rows = rows
        self.timeline.markers = sorted({f.frame for f in self.plan.flags if f.frame is not None})
        self.timeline.update()

    def _clock(self, frame: int) -> str:
        s = self.seconds(frame)
        return f"{int(s // 60)}:{s % 60:04.1f}"

    def _update_range_editor(self) -> None:
        has = self.selected_manual is not None and self.selected_manual < len(self.plan.manual)
        self.range_editor.setEnabled(has)
        if has:
            m = self.plan.manual[self.selected_manual]
            for spin, f in ((self.start_spin, m.start), (self.end_spin, m.end)):
                spin.blockSignals(True)
                spin.setValue(self.seconds(f))
                spin.blockSignals(False)

    def _on_track_toggled(self, it: QListWidgetItem) -> None:
        self.plan.set_track_enabled(
            it.data(Qt.ItemDataRole.UserRole), it.checkState() == Qt.CheckState.Checked
        )
        self.after_edit()

    def _on_track_clicked(self, it: QListWidgetItem) -> None:
        tid = it.data(Qt.ItemDataRole.UserRole)
        self.go_to(min(self.coverage[tid]))

    def _on_manual_selected(self, row: int) -> None:
        self.selected_manual = row if row >= 0 else None
        self._update_range_editor()
        if self.selected_manual is not None:
            m = self.plan.manual[row]
            if not m.start <= self.index <= m.end:
                self.go_to(m.start)
            else:
                self.refresh_boxes()

    def _on_range_edited(self) -> None:
        i = self.selected_manual
        if i is None:
            return
        m = self.plan.manual[i]
        start = self.frame_of(self.start_spin.value())
        end = self.frame_of(self.end_spin.value())
        if (start, end) != (m.start, m.end):
            self.plan.update_manual(i, start, end, m.box)
            self.after_edit()

    def _set_range_edge(self, start: bool) -> None:
        i = self.selected_manual
        if i is None:
            return
        m = self.plan.manual[i]
        s, e = (self.index, m.end) if start else (m.start, self.index)
        self.plan.update_manual(i, s, e, m.box)
        self.after_edit()
