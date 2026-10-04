"""After the drop: the file floats in the middle, and below it the settings,
one step at a time, up to the check and the export. Port of GuideView.swift
and EditorView.swift.

Navigation follows the Mac app: Back and Continue side by side at the bottom
right (Enter continues, Alt+Left goes back, Esc does nothing); the step bar
can be clicked; the steps are fixed from the start.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from blurry_opsec.gui import store as S
from blurry_opsec.gui import strings as L
from blurry_opsec.gui import style
from blurry_opsec.gui.edits import EditBox
from blurry_opsec.gui.widgets import (
    ACCENT,
    Badge,
    OptionCard,
    Spinner,
    StepBar,
    Swatch,
    Timeline,
    button,
    clock,
    glyph,
    label,
    primary,
    white,
)

BADGE_ROOM = 16  # below the picture, for the badge that sits on its edge


def centered(widget: QWidget, max_width: int) -> QWidget:
    """The widget, at most max_width wide, in the middle of a row."""
    widget.setMaximumWidth(max_width)
    box = QWidget()
    row = QHBoxLayout(box)
    row.setContentsMargins(0, 0, 0, 0)
    row.addStretch(1)
    row.addWidget(widget, 100)
    row.addStretch(1)
    return box


class Picture(QWidget):
    """The file, lifted off the window: the original while choosing the
    sensitivity (faces outlined in green), then covered as the export will be.
    In edit mode the boxes are drawn over it, and one drag does everything:
    on a corner of the selected box it resizes it, on a box it moves it,
    elsewhere it draws a new one. A click selects."""

    def __init__(self, store: S.Store, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self.setMinimumSize(240, 160)
        self.setMouseTracking(True)
        self.badge = Badge(self)
        self.correct_btn = button("", "capsule", store.start_editing)
        self.correct_btn.setParent(self)
        self.correct_btn.setIcon(glyph("dashed", style.TEXT, 13))
        self.spinner = Spinner(18, self)
        self._image: object = None
        self._pixmap: QPixmap | None = None
        self._pixmap_size = None
        self._op: tuple | None = (
            None  # ("draw", p) | ("move", box, rect) | ("resize", box, rect, fixed)
        )
        self._draft: QRectF | None = None
        self._press: QPointF | None = None

    # -- geometry ------------------------------------------------------------------
    def image_rect(self) -> QRectF:
        img = self.store.preview
        area = QRectF(self.rect()).adjusted(0, 0, 0, -BADGE_ROOM)
        if img is None or img.isNull() or area.width() <= 0 or area.height() <= 0:
            return QRectF()
        s = min(area.width() / img.width(), area.height() / img.height())
        w, h = img.width() * s, img.height() * s
        return QRectF(area.center().x() - w / 2, area.top() + (area.height() - h) / 2, w, h)

    def plan_size(self) -> tuple[float, float] | None:
        cur = self.store.current
        plan = cur.plan if cur else None
        if not plan or not plan.get("width") or not plan.get("height"):
            return None
        return float(plan["width"]), float(plan["height"])

    def _scale(self) -> float:
        size = self.plan_size()
        return self.image_rect().width() / size[0] if size else 1.0

    # -- state -----------------------------------------------------------------------
    def sync(self) -> None:
        store, item = self.store, self.store.current
        r = self.image_rect()
        has_image = not r.isNull()
        self.spinner.setVisible(not has_image or (store.preview_stale and not store.playing))
        self.spinner.move(
            int(self.width() / 2 - 9) if not has_image else int(r.center().x() - 9),
            int(self.height() / 2 - 9) if not has_image else int(r.center().y() - 9),
        )
        badge = None
        if item is not None and has_image:
            badge = {
                S.WAITING: (L.analyzing(item.progress), style.SECONDARY),
                S.ANALYZING: (L.analyzing(item.progress), style.SECONDARY),
                S.NO_FACES: (L.no_face_found(), style.RED),
                S.REVIEW: (L.faces_found(item.faces or 0), style.ORANGE),
                S.READY: (L.faces_found(item.faces or 0), style.ACCENT),
                S.EXPORTED: (L.faces_found(item.faces or 0), style.ACCENT),
                S.EXPORTING: (L.faces_found(item.faces or 0), style.ACCENT),
            }.get(item.status)
        self.badge.setVisible(badge is not None)
        if badge is not None:
            self.badge.set(badge[0], badge[1], item.status in (S.WAITING, S.ANALYZING))
            self.badge.setToolTip(L.to_review() if item.status == S.REVIEW else "")
            self.badge.move(
                int(r.center().x() - self.badge.width() / 2),
                int(r.bottom() + 14 - self.badge.height()),
            )
        show_correct = (
            item is not None
            and has_image
            and item.analysed
            and not store.editing
            and not store.playing
            and item.status != S.EXPORTING
        )
        self.correct_btn.setVisible(show_correct)
        if show_correct:
            review = item.status == S.REVIEW
            self.correct_btn.setText(L.check_boxes() if review else L.correct())
            self.correct_btn.setIcon(glyph("dashed", style.ORANGE if review else style.TEXT, 13))
            if self.correct_btn.property("warn") != review:
                self.correct_btn.setProperty("warn", review)
                self.correct_btn.style().unpolish(self.correct_btn)
                self.correct_btn.style().polish(self.correct_btn)
            self.correct_btn.adjustSize()
            self.correct_btn.move(int(r.right() - 10 - self.correct_btn.width()), int(r.top() + 10))
        self.setCursor(Qt.CursorShape.CrossCursor if store.editing else Qt.CursorShape.ArrowCursor)
        self.update()

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        self.sync()

    # -- painting ----------------------------------------------------------------------
    def _scaled_pixmap(self, r: QRectF) -> QPixmap:
        img = self.store.preview
        dpr = self.devicePixelRatioF()
        size = (round(r.width() * dpr), round(r.height() * dpr))
        if self._image is not img or self._pixmap_size != size:
            self._image = img
            self._pixmap_size = size
            pm = QPixmap.fromImage(
                img.scaled(
                    size[0],
                    size[1],
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            pm.setDevicePixelRatio(dpr)
            self._pixmap = pm
        return self._pixmap

    def paintEvent(self, _e) -> None:  # noqa: N802
        r = self.image_rect()
        if r.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # A soft shadow under the picture: many faint layers, wider and lower.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 4))
        for k in range(1, 25):
            grow = k * 1.2
            p.drawRoundedRect(r.adjusted(-grow, -grow + 14, grow, grow + 14), 10 + grow, 10 + grow)
        clip = QPainterPath()
        clip.addRoundedRect(r, 10, 10)
        p.save()
        p.setClipPath(clip)
        p.drawPixmap(r.topLeft(), self._scaled_pixmap(r))
        store = self.store
        if store.preview_stale and not store.playing:
            # Before the analysis, or while the right preview is on its way, the
            # picture on screen is not what the step shows: dim it.
            p.fillRect(r, QColor(0, 0, 0, 115))
        p.restore()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(white(0.10), 1))
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
        if store.editing and self.plan_size():
            self._paint_boxes(p, r)

    def _box_color(self, box: EditBox) -> QColor:
        if not box.enabled:
            return white(0.6)
        if box.owner[0] in ("drawn", "manual"):
            return QColor(style.TEXT)
        return QColor(style.ORANGE) if box.uncertain else QColor(ACCENT)

    def _paint_boxes(self, p: QPainter, r: QRectF) -> None:
        s = self._scale()

        def scaled(b: QRectF) -> QRectF:
            return QRectF(r.left() + b.x() * s, r.top() + b.y() * s, b.width() * s, b.height() * s)

        for box in self.store.edit_boxes:
            rect = scaled(self._rect_for(box))
            selected = box.id == self.store.selection
            color = self._box_color(box)
            fill = QColor(color)
            fill.setAlphaF(0.18 if selected else 0.06)
            pen = QPen(color, 2 if selected else 1.5)
            if not box.enabled:
                pen.setDashPattern([4, 3])
            p.setPen(pen)
            p.setBrush(fill)
            p.drawRect(rect)
            if selected and box.movable:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(style.TEXT))
                for c in (rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight()):
                    p.drawRect(QRectF(c.x() - 3.5, c.y() - 3.5, 7, 7))
        if self._op is not None and self._op[0] == "draw" and self._draft is not None:
            pen = QPen(QColor(style.TEXT), 1.5)
            pen.setDashPattern([5 / 1.5, 3 / 1.5])
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(scaled(self._draft))

    def _rect_for(self, box: EditBox) -> QRectF:
        if self._op is not None and self._op[0] in ("move", "resize") and self._op[1].id == box.id:
            return self._draft or box.rect
        return box.rect

    # -- editing -------------------------------------------------------------------------
    def _to_plan(self, pos: QPointF) -> QPointF:
        r, s = self.image_rect(), self._scale()
        return QPointF((pos.x() - r.left()) / s, (pos.y() - r.top()) / s)

    def _clamp(self, r: QRectF) -> QRectF:
        w, h = self.plan_size()
        return r.normalized().intersected(QRectF(0, 0, w, h))

    def _hit(self, p: QPointF) -> EditBox | None:
        """The box under the point: the selected one first, then the smallest."""
        under = [b for b in self.store.edit_boxes if b.rect.contains(p)]
        for b in under:
            if b.id == self.store.selection:
                return b
        return min(under, key=lambda b: b.rect.width() * b.rect.height(), default=None)

    def _corner(self, p: QPointF) -> tuple | None:
        grab = 10 / self._scale()  # a corner handle is easy to hit at any zoom
        sel = self.store.selected_box
        if sel is None or not sel.movable:
            return None
        r = sel.rect
        for corner, opposite in (
            (r.topLeft(), r.bottomRight()),
            (r.topRight(), r.bottomLeft()),
            (r.bottomLeft(), r.topRight()),
            (r.bottomRight(), r.topLeft()),
        ):
            if abs(corner.x() - p.x()) < grab and abs(corner.y() - p.y()) < grab:
                return sel, corner, opposite
        return None

    def mousePressEvent(self, e) -> None:  # noqa: N802
        if (
            not self.store.editing
            or not self.plan_size()
            or e.button() != Qt.MouseButton.LeftButton
        ):
            return super().mousePressEvent(e)
        p = self._to_plan(e.position())
        self._press = e.position()
        corner = self._corner(p)
        if corner is not None:
            sel, _, opposite = corner
            self._op = ("resize", sel, QRectF(sel.rect), opposite)
            return
        hit = self._hit(p)
        if hit is not None and hit.movable:
            self.store.select(hit.id)
            self._op = ("move", hit, QRectF(hit.rect), p)
            return
        self._op = ("draw", p)

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        if not self.store.editing or not self.plan_size():
            return super().mouseMoveEvent(e)
        now = self._to_plan(e.position())
        if self._op is None:
            self._hover_cursor(now)
            return
        w, h = self.plan_size()
        kind = self._op[0]
        if kind == "draw":
            start = self._op[1]
            self._draft = self._clamp(QRectF(start, now))
        elif kind == "move":
            _, _, rect, start = self._op
            m = rect.translated(now.x() - start.x(), now.y() - start.y())
            m.moveLeft(min(max(0.0, m.left()), w - m.width()))
            m.moveTop(min(max(0.0, m.top()), h - m.height()))
            self._draft = m
        else:
            fixed = self._op[3]
            self._draft = self._clamp(QRectF(fixed, now))
        self.update()

    def _hover_cursor(self, p: QPointF) -> None:
        corner = self._corner(p)
        if corner is not None:
            sel, c, _ = corner
            r = sel.rect
            diag = (c == r.topLeft()) or (c == r.bottomRight())
            shape = Qt.CursorShape.SizeFDiagCursor if diag else Qt.CursorShape.SizeBDiagCursor
        else:
            hit = self._hit(p)
            shape = (
                Qt.CursorShape.SizeAllCursor if hit and hit.movable else Qt.CursorShape.CrossCursor
            )
        self.setCursor(shape)

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        if self._op is None:
            return super().mouseReleaseEvent(e)
        op, draft = self._op, self._draft
        self._op, self._draft = None, None
        moved = (
            self._press is not None
            and math.hypot(e.position().x() - self._press.x(), e.position().y() - self._press.y())
            >= 3
        )
        if not moved:
            hit = self._hit(self._to_plan(self._press or e.position()))
            self.store.select(hit.id if hit else None)
            return
        if draft is None or draft.width() < 4 or draft.height() < 4:
            self.update()
            return
        if op[0] == "draw":
            self.store.add_box(draft)
        else:
            self.store.move_box(op[1], draft)


class PlayerBar(QWidget):
    """Video, last step: play/pause (space), a timeline to drag with the covered
    stretches marked in green, and the time."""

    def __init__(self, store: S.Store, with_button: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        self.play_btn = button("", "play", self.toggle)
        self.play_btn.setVisible(with_button)
        self.timeline = Timeline()
        self.timeline.seek.connect(store.seek)
        self.time = label("", "monoSmall")
        row.addWidget(self.play_btn)
        row.addWidget(self.timeline, 1)
        row.addWidget(self.time)

    def toggle(self) -> None:
        self.store.stop_playing() if self.store.playing else self.store.play()

    def sync(self) -> None:
        item = self.store.current
        if item is None:
            return
        position = item.preview_index or 0
        self.timeline.set_state(item.frame_count, item.covered_ranges, position)
        self.time.setText(f"{clock(position, item.fps)} / {clock(item.frame_count, item.fps)}")
        playing = self.store.playing
        self.play_btn.setIcon(glyph("pause" if playing else "play", style.TEXT, 13))
        self.play_btn.setToolTip(L.pause() if playing else L.play())
        self.play_btn.setAccessibleName(L.pause() if playing else L.play())


class EditPanel(QWidget):
    """Below the picture, in edit mode: what to do, the video timeline, the
    actions for the selected box, and Cancel / Done."""

    def __init__(self, store: S.Store, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        col = QVBoxLayout(self)
        col.setContentsMargins(28, 0, 28, 20)
        col.setSpacing(12)
        self.title = label("", "title3")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint = label("", "caption", wrap=True)
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.player = PlayerBar(store, with_button=False)
        col.addWidget(self.title)
        col.addWidget(centered(self.hint, 560))
        self.player_row = centered(self.player, 560)
        col.addWidget(self.player_row)
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(14)
        self.legend = QHBoxLayout()
        self.legend.setSpacing(12)
        self.legend_items: list[tuple[QWidget, QLabel, str]] = []
        for color, key in (
            (ACCENT, "found"),
            (QColor(style.ORANGE), "uncertain"),
            (QColor(style.TEXT), "drawn"),
            (white(0.6), "off"),
        ):
            box = QWidget()
            item = QHBoxLayout(box)
            item.setContentsMargins(0, 0, 0, 0)
            item.setSpacing(5)
            text = label("", "caption")
            item.addWidget(Swatch(color))
            item.addWidget(text)
            self.legend.addWidget(box)
            self.legend_items.append((box, text, key))
        actions.addLayout(self.legend)
        actions.addStretch(1)
        self.span = label("", "monoSmall")
        self.start_btn = button("", "", lambda: self._range(True))
        self.end_btn = button("", "", lambda: self._range(False))
        self.track_btn = button("", "", self._toggle_track)
        self.remove_btn = button("", "", self._remove)
        for w in (self.span, self.start_btn, self.end_btn, self.track_btn, self.remove_btn):
            actions.addWidget(w)
        actions_box = QWidget()
        actions_box.setLayout(actions)
        actions_box.setFixedHeight(28)
        col.addWidget(actions_box)
        nav = QHBoxLayout()
        nav.setSpacing(10)
        nav.addStretch(1)
        self.cancel_btn = button("", "large", lambda: store.end_editing(False))
        self.done_btn = primary("", lambda: store.end_editing(True))
        nav.addWidget(self.cancel_btn)
        nav.addWidget(self.done_btn)
        col.addLayout(nav)

    def _range(self, start: bool) -> None:
        box = self.store.selected_box
        if box is not None and box.owner[0] == "manual":
            self.store.set_range(box.owner[1], start)

    def _toggle_track(self) -> None:
        box = self.store.selected_box
        if box is not None and box.owner[0] == "track":
            self.store.toggle_track(box.owner[1])

    def _remove(self) -> None:
        box = self.store.selected_box
        if box is not None:
            self.store.remove_box(box)

    def delete_selected(self) -> None:
        """Delete or Backspace: remove the selected box, or switch its track."""
        box = self.store.selected_box
        if box is None:
            return
        if box.owner[0] == "track":
            self.store.toggle_track(box.owner[1])
        else:
            self.store.remove_box(box)

    def sync(self) -> None:
        item = self.store.current
        if item is None:
            return
        video = item.kind == "video"
        self.title.setText(L.correct())
        self.hint.setText(L.edit_hint_video() if video else L.edit_hint_image())
        self.player_row.setVisible(video)
        if video:
            self.player.sync()
        texts = {
            "found": L.legend_found(),
            "uncertain": L.legend_uncertain(),
            "drawn": L.legend_drawn(),
            "off": L.legend_off(),
        }
        for box, text, key in self.legend_items:
            text.setText(texts[key])
            box.setVisible(key != "off" or video)
        box = self.store.selected_box
        kind = box.owner[0] if box else None
        self.track_btn.setVisible(kind == "track")
        if kind == "track":
            self.track_btn.setText(L.track_off() if box.enabled else L.track_on())
        manual = kind == "manual"
        self.span.setVisible(manual and box.start is not None and box.end is not None)
        if self.span.isVisible():
            # The end is the end of the last covered frame.
            self.span.setText(L.span(clock(box.start, item.fps), clock(box.end + 1, item.fps)))
        self.start_btn.setVisible(manual)
        self.end_btn.setVisible(manual)
        self.start_btn.setText(L.start_here())
        self.end_btn.setText(L.end_here())
        self.remove_btn.setVisible(kind in ("found", "drawn", "manual"))
        self.remove_btn.setText(L.remove_box())
        self.cancel_btn.setText(L.cancel())
        self.done_btn.setText(L.done_editing())


class GuideView(QWidget):
    """The guide for the file on screen."""

    export_requested = Signal()  # the window asks where to save
    reveal_requested = Signal(object)  # a Path to show in its folder

    def __init__(self, store: S.Store, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self.store = store
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        # Header: a notice on the left; skip and where we are on the right.
        header = QHBoxLayout()
        header.setContentsMargins(20, 0, 20, 0)
        header.setSpacing(14)
        self.notice = label("", "caption")
        self.skip_btn = button("", "quiet", store.skip)
        self.position = label("", "section")
        header.addWidget(self.notice)
        header.addStretch(1)
        header.addWidget(self.skip_btn)
        header.addWidget(self.position)
        header_box = QWidget()
        header_box.setLayout(header)
        header_box.setFixedHeight(40)
        col.addWidget(header_box)

        self.picture = Picture(store)
        pic = QVBoxLayout()
        pic.setContentsMargins(40, 6, 40, 22 - BADGE_ROOM)
        pic.addWidget(self.picture)
        col.addLayout(pic, 1)

        self.bottom = QStackedWidget()
        col.addWidget(self.bottom)
        self.steps_page = QWidget()
        steps = QVBoxLayout(self.steps_page)
        steps.setContentsMargins(0, 0, 0, 20)
        steps.setSpacing(0)
        self.step_bar = StepBar()
        self.step_bar.chosen.connect(store.set_step)
        bar_row = QHBoxLayout()
        bar_row.addStretch(1)
        bar_row.addWidget(self.step_bar)
        bar_row.addStretch(1)
        steps.addLayout(bar_row)
        steps.addSpacing(16)
        content = QWidget()
        content.setFixedHeight(124)
        steps.addWidget(content)
        self._build_content(content)
        steps.addWidget(self._build_nav())
        self.bottom.addWidget(self.steps_page)
        self.edit_panel = EditPanel(store)
        self.bottom.addWidget(self.edit_panel)

    # -- step content ---------------------------------------------------------------
    def _build_content(self, content: QWidget) -> None:
        col = QVBoxLayout(content)
        col.setContentsMargins(40, 0, 40, 0)
        col.setSpacing(14)
        self.question = label("", "title3")
        self.question.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.previous_row = QWidget()
        prev = QHBoxLayout(self.previous_row)
        prev.setContentsMargins(0, 0, 0, 0)
        prev.setSpacing(6)
        self.previous_text = label("", "title3")
        self.previous_text.setStyleSheet(f"color: {style.SECONDARY};")
        self.change_btn = button("", "link", lambda: self.store.set_step("sensitivity"))
        self.change_btn.setStyleSheet("font-size: 16px; font-weight: 500;")
        prev.addStretch(1)
        prev.addWidget(self.previous_text)
        prev.addWidget(self.change_btn)
        prev.addStretch(1)
        col.addWidget(self.question)
        col.addWidget(self.previous_row)
        self.pages = QStackedWidget()
        col.addWidget(self.pages, 1)
        store = self.store

        # Sensitivity
        page = QWidget()
        pv = QVBoxLayout(page)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(10)
        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.level_cards: dict[str, OptionCard] = {}
        for key in ("base", "medium", "high"):
            card = OptionCard()
            card.clicked.connect(lambda _c=False, k=key: store.set_level(k))
            cards.addWidget(card)
            self.level_cards[key] = card
        pv.addLayout(cards)
        self.aggressive_btn = button("", "small", lambda: store.set_level("high"))
        pv.addWidget(self.aggressive_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        pv.addStretch(1)
        self.pages.addWidget(page)

        # Cover
        self.mode_cards = {"solid": OptionCard("solid"), "pixel": OptionCard("pixel")}
        self.pages.addWidget(self._cards_page(self.mode_cards, store.set_mode))

        # Margin
        page = QWidget()
        pv = QVBoxLayout(page)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(10)
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(14)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 60)
        self.slider.valueChanged.connect(lambda v: store.set_padding(v / 100))
        self.slider_value = label("", "mono")
        self.slider_value.setFixedWidth(40)
        self.slider_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        rl.addWidget(self.slider, 1)
        rl.addWidget(self.slider_value)
        pv.addWidget(centered(row, 460))
        self.margin_hint = label("", "caption")
        self.margin_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pv.addWidget(self.margin_hint)
        pv.addStretch(1)
        self.pages.addWidget(page)

        # Audio
        page = QWidget()
        pv = QVBoxLayout(page)
        pv.setContentsMargins(0, 0, 0, 0)
        self.no_audio = label("", "secondary")
        self.no_audio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.audio_cards = {False: OptionCard("mute"), True: OptionCard("sound", warning=True)}
        self.audio_row = self._cards_page(self.audio_cards, store.set_keep_audio)
        pv.addWidget(self.no_audio)
        pv.addWidget(self.audio_row)
        pv.addStretch(1)
        self.pages.addWidget(page)

        # Result
        page = QWidget()
        pv = QVBoxLayout(page)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(10)
        self.player = PlayerBar(store)
        self.player_row = centered(self.player, 560)
        self.summary = label("", "mono")
        self.summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.always = label("", "caption")
        self.always.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pv.addWidget(self.player_row)
        pv.addWidget(self.summary)
        pv.addWidget(self.always)
        pv.addStretch(1)
        self.pages.addWidget(page)

    def _cards_page(self, cards: dict, choose) -> QWidget:
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(10)
        for key, card in cards.items():
            card.clicked.connect(lambda _c=False, k=key: choose(k))
            rl.addWidget(card)
        page = QWidget()
        pv = QVBoxLayout(page)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.addWidget(centered(row, 460))
        pv.addStretch(1)
        return page

    # -- navigation -------------------------------------------------------------------
    def _build_nav(self) -> QWidget:
        nav = QWidget()
        nav.setFixedHeight(36)
        row = QHBoxLayout(nav)
        row.setContentsMargins(28, 0, 28, 0)
        row.setSpacing(10)
        # Left of the buttons: export progress, the saved file, or the error.
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(160)
        self.progress_text = label("", "caption")
        self.saved = label("", "accent")
        self.reveal_btn = button("", "link", self._reveal)
        self.error = label("", "captionRed", wrap=True)
        self.error.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        for w in (self.progress, self.progress_text, self.saved, self.reveal_btn):
            row.addWidget(w)
        row.addWidget(self.error, 1)
        row.addStretch(1)
        self.back_btn = button("", "large", lambda: self.store.move(-1))
        self.cancel_btn = button("", "large", self.store.cancel_export)
        self.primary_btn = primary("", self.primary_action)
        row.addWidget(self.back_btn)
        row.addWidget(self.cancel_btn)
        row.addWidget(self.primary_btn)
        return nav

    def _reveal(self) -> None:
        item = self.store.current
        if item is not None and item.output is not None:
            self.reveal_requested.emit(item.output)

    def primary_action(self) -> None:
        store, item = self.store, self.store.current
        if item is None or not self.primary_btn.isEnabled():
            return
        if store.step != "result":
            store.move(1)
        elif item.status == S.EXPORTED:
            store.next()
        elif item.status == S.ERROR:
            store.retry()
        elif item.status != S.EXPORTING:
            self.export_requested.emit()

    # -- state ----------------------------------------------------------------------------
    def sync(self) -> None:
        store, item = self.store, self.store.current
        if item is None:
            return
        editing = store.editing
        self.bottom.setCurrentWidget(self.edit_panel if editing else self.steps_page)
        self.bottom.setFixedHeight(
            (216 if item.kind == "video" else 188) if editing else 124 + 16 + 22 + 36 + 20
        )
        self.notice.setText(store.notice or "")
        index, total = store.position
        many = total > 1 and not editing
        self.position.setVisible(many)
        self.position.setText(L.position(index, total))
        self.skip_btn.setVisible(many and store.has_next and not item.busy)
        self.skip_btn.setText(L.skip())
        self.picture.sync()
        if editing:
            self.edit_panel.sync()
            return

        steps = store.steps
        titles = {s: L.step_title(s) for s in steps}
        struck = {"audio"} if item.has_audio is False else set()
        self.step_bar.set_steps(steps, store.step, titles, struck, item.status == S.EXPORTING)

        step = store.step
        previous = step == "result" and store.using_previous
        self.question.setVisible(not previous)
        self.previous_row.setVisible(previous)
        self.question.setText(L.step_question(step))
        self.previous_text.setText(L.same_settings())
        self.change_btn.setText(L.change())
        self.pages.setCurrentIndex(
            ("sensitivity", "cover", "margin", "audio", "result").index(step)
        )

        for key, card in self.level_cards.items():
            card.set_texts(L.level_label(key), L.level_description(key))
            card.set_selected(store.level == key)
        self.aggressive_btn.setText(L.try_aggressive())
        self.aggressive_btn.setVisible(item.status == S.NO_FACES and store.level != "high")
        self.mode_cards["solid"].set_texts(L.mode_solid(), L.mode_solid_hint())
        self.mode_cards["pixel"].set_texts(L.mode_pixel(), L.mode_pixel_hint())
        for key, card in self.mode_cards.items():
            card.set_selected(store.mode == key)
        pct = round(store.padding * 100)
        if self.slider.value() != pct and not self.slider.isSliderDown():
            self.slider.blockSignals(True)
            self.slider.setValue(pct)
            self.slider.blockSignals(False)
        self.slider_value.setText(f"{pct}%")
        self.slider.setAccessibleName(L.margin())
        self.margin_hint.setText(L.margin_hint())
        self.no_audio.setText(L.no_audio())
        self.no_audio.setVisible(item.has_audio is False)
        self.audio_row.setVisible(item.has_audio is not False)
        self.audio_cards[False].set_texts(L.audio_remove(), L.audio_remove_hint())
        self.audio_cards[True].set_texts(L.audio_keep(), L.audio_keep_hint())
        for key, card in self.audio_cards.items():
            card.set_selected(store.keep_audio == key)
        self.player_row.setVisible(item.kind == "video" and item.analysed)
        if self.player_row.isVisible():
            self.player.sync()
        audio = store.keep_audio if item.kind == "video" and item.has_audio is not False else None
        self.summary.setText(L.summary(store.level, store.mode, pct, audio))
        self.always.setText(L.always_removed())
        self._sync_nav(item)

    def _sync_nav(self, item: S.Item) -> None:
        store = self.store
        result = store.step == "result"
        status = item.status
        self.progress.setVisible(result and status == S.EXPORTING)
        self.progress_text.setVisible(result and status == S.EXPORTING)
        self.progress.setValue(item.progress)
        self.progress_text.setText(L.exporting(item.progress))
        exported = result and status == S.EXPORTED and item.output is not None
        self.saved.setVisible(exported)
        self.reveal_btn.setVisible(exported)
        if exported:
            name = item.output.name
            self.saved.setText(
                "✓  " + self.saved.fontMetrics().elidedText(name, Qt.TextElideMode.ElideMiddle, 260)
            )
            self.saved.setToolTip(name)
        self.reveal_btn.setText(L.show_in_folder())
        self.error.setVisible(result and status == S.ERROR)
        self.error.setText("⚠  " + item.error)
        self.back_btn.setText(L.back())
        self.back_btn.setVisible(store.step != store.steps[0] and status != S.EXPORTING)
        self.cancel_btn.setText(L.cancel())
        self.cancel_btn.setVisible(result and status == S.EXPORTING)
        self.primary_btn.setVisible(not (result and status == S.EXPORTING))
        if not result:
            text, enabled = L.next_step(), True
        elif status == S.EXPORTED:
            text, enabled = (L.next_file() if store.has_next else L.done()), True
        elif status == S.ERROR:
            text, enabled = L.retry(), True
        else:
            text, enabled = L.export(), item.analysed
        self.primary_btn.setText(text)
        self.primary_btn.setEnabled(enabled)

    def on_picture(self) -> None:
        """Only the picture changed (video playback, seeking)."""
        self.picture.sync()
        if self.store.editing:
            self.edit_panel.player.sync()
        elif self.player_row.isVisible():
            self.player.sync()

    def anchor(self, tip: str) -> QWidget | None:
        """Where each first-run tip points."""
        if tip == "steps":
            return self.step_bar
        if tip == "correct":
            return self.picture.correct_btn if self.picture.correct_btn.isVisible() else None
        if tip == "queue":
            return self.saved if self.saved.isVisible() else None
        return None
