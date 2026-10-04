"""Small building blocks, drawn as in the Mac app: drop frame with corner
ticks, option cards, the step bar, the timeline, a spinner, the capsule badge."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from blurry_opsec.gui import style

ACCENT = QColor(style.ACCENT)
HAIRLINE = QColor(255, 255, 255, 26)


def white(alpha: float) -> QColor:
    return QColor(255, 255, 255, round(alpha * 255))


def corner_ticks(p: QPainter, r: QRectF, n: float) -> None:
    """Four L-shaped corner marks of length n, with the painter's current pen."""
    corners = (
        (r.left(), r.top(), 1, 1),
        (r.right(), r.top(), -1, 1),
        (r.left(), r.bottom(), 1, -1),
        (r.right(), r.bottom(), -1, -1),
    )
    for cx, cy, dx, dy in corners:
        p.drawLine(QPointF(cx + dx * n, cy), QPointF(cx, cy))
        p.drawLine(QPointF(cx, cy), QPointF(cx, cy + dy * n))


def label(text: str = "", name: str = "", wrap: bool = False) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def button(text: str = "", name: str = "", slot=None) -> QPushButton:
    b = QPushButton(text)
    if name:
        b.setObjectName(name)
    if slot is not None:
        b.clicked.connect(slot)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def primary(text: str = "", slot=None) -> QPushButton:
    """White button with black text: the one primary action, 180 wide."""
    b = button(text, "primary", slot)
    b.setFixedWidth(180)
    return b


def mono_font(px: int, spacing: float = 0.0) -> QFont:
    font = QFont(style.MONO)
    font.setPixelSize(px)
    if spacing:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return font


def clock(frame: int, fps: float) -> str:
    seconds = int(frame / max(fps, 1))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


class DropFrame(QWidget):
    """The drop frame: corner ticks, and green while something is dragged over it."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.active = False

    def set_active(self, active: bool) -> None:
        if active != self.active:
            self.active = active
            self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        on = self.active
        p.setBrush(QColor(73, 220, 24, 18) if on else white(0.025))
        pen = QPen(QColor(73, 220, 24, 180) if on else white(0.12), 1)
        if not on:
            pen.setDashPattern([5, 4])
        p.setPen(pen)
        p.drawRoundedRect(r, 12, 12)
        p.setPen(QPen(ACCENT if on else white(0.55), 1))
        corner_ticks(p, r.adjusted(10, 10, -10, -10), 12)


class PhotoGlyph(QWidget):
    """Two photos, one tilted: the landing's thin-line picture."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(64, 52)
        self.active = False

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = ACCENT if self.active else QColor(style.SECONDARY)
        p.setPen(QPen(color, 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.save()
        p.translate(38, 22)
        p.rotate(-12)
        p.drawRoundedRect(QRectF(-20, -15, 40, 30), 4, 4)
        p.restore()
        front = QRectF(6, 16, 42, 32)
        p.setBrush(QColor(style.BG))
        p.drawRoundedRect(front, 4, 4)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(18, 26), 3, 3)
        mountains = QPainterPath(QPointF(9, 44))
        for x, y in ((21, 32), (29, 40), (35, 34), (45, 44)):
            mountains.lineTo(x, y)
        p.drawPath(mountains)


class Spinner(QWidget):
    """A small turning arc, like the system's activity indicator."""

    def __init__(self, size: int = 16, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.angle = 0
        self.timer = QTimer(self, interval=33, timeout=self._turn)

    def _turn(self) -> None:
        self.angle = (self.angle + 12) % 360
        self.update()

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        self.timer.start()

    def hideEvent(self, e) -> None:  # noqa: N802
        super().hideEvent(e)
        self.timer.stop()

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = max(1.5, self.width() / 9)
        r = QRectF(self.rect()).adjusted(w, w, -w, -w)
        p.setPen(QPen(white(0.18), w))
        p.drawEllipse(r)
        pen = QPen(white(0.85), w)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(r, -self.angle * 16, 100 * 16)


class Badge(QFrame):
    """A capsule on the picture: a dot (or a spinner) and a short text."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("badge")
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 5, 12, 5)
        row.setSpacing(7)
        self.spinner = Spinner(12)
        self.dot = QLabel()
        self.dot.setFixedSize(6, 6)
        self.text = QLabel()
        row.addWidget(self.spinner)
        row.addWidget(self.dot)
        row.addWidget(self.text)

    def set(self, text: str, color: str, busy: bool) -> None:
        self.text.setText(text)
        self.spinner.setVisible(busy)
        self.dot.setVisible(not busy)
        self.dot.setStyleSheet(f"background: {color}; border-radius: 3px;")
        self.adjustSize()


class OptionCard(QAbstractButton):
    """One choice in a step: a card, green when chosen."""

    def __init__(self, symbol: str | None = None, warning: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.symbol = symbol  # "solid", "pixel", "mute", "sound" or None
        self.warning = warning
        self.title = ""
        self.hint = ""
        self.selected = False
        self.hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setMinimumHeight(64)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_texts(self, title: str, hint: str) -> None:
        self.title, self.hint = title, hint
        self.setAccessibleName(title)
        self.setAccessibleDescription(hint)
        self.updateGeometry()
        self.update()

    def set_selected(self, selected: bool) -> None:
        if selected != self.selected:
            self.selected = selected
            self.update()

    def enterEvent(self, e) -> None:  # noqa: N802
        self.hover = True
        self.update()

    def leaveEvent(self, e) -> None:  # noqa: N802
        self.hover = False
        self.update()

    def _text_left(self) -> int:
        return 12 + (30 if self.symbol else 0)

    def _hint_rect(self, width: int) -> QRectF:
        fm = QFontMetrics(self._hint_font())
        w = max(40, width - self._text_left() - 12)
        return QRectF(fm.boundingRect(0, 0, w, 1000, Qt.TextFlag.TextWordWrap, self.hint))

    def _hint_font(self) -> QFont:
        font = QFont(self.font())
        font.setPixelSize(11)
        return font

    def _title_font(self) -> QFont:
        font = QFont(self.font())
        font.setPixelSize(13)
        font.setWeight(QFont.Weight.Medium)
        return font

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return max(64, int(12 + 18 + 3 + self._hint_rect(width).height() + 12))

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(180, 64)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        sel = self.selected
        p.setBrush(white(0.07 if sel else 0.05 if self.hover else 0.025))
        p.setPen(QPen(QColor(73, 220, 24, 217) if sel else HAIRLINE, 1))
        if self.hasFocus():
            p.setPen(QPen(QColor(73, 220, 24, 140), 2))
        p.drawRoundedRect(r, 10, 10)
        if self.symbol:
            self._draw_symbol(p, QRectF(12, 13, 20, 18), ACCENT if sel else QColor(style.SECONDARY))
        left = self._text_left()
        p.setPen(QColor(style.TEXT))
        p.setFont(self._title_font())
        p.drawText(
            QRectF(left, 11, self.width() - left - 12, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.title,
        )
        hint_color = style.ORANGE if self.warning and sel else style.SECONDARY
        p.setPen(QColor(hint_color))
        p.setFont(self._hint_font())
        p.drawText(
            QRectF(left, 33, self.width() - left - 12, self.height() - 38),
            Qt.TextFlag.TextWordWrap,
            self.hint,
        )

    def _draw_symbol(self, p: QPainter, r: QRectF, color: QColor) -> None:
        p.save()
        p.setPen(QPen(color, 1.4))
        if self.symbol == "solid":
            p.setBrush(color)
            p.drawRoundedRect(r.adjusted(1, 2, -1, -2), 2, 2)
        elif self.symbol == "pixel":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            s = 5.0
            for i in range(3):
                for j in range(3):
                    p.drawRoundedRect(
                        QRectF(r.left() + 2 + i * (s + 1.5), r.top() + 1 + j * (s + 1.5), s, s),
                        1,
                        1,
                    )
        else:
            # A speaker, with waves or crossed out.
            body = QPainterPath(QPointF(r.left() + 1, r.center().y() - 3))
            for x, y in ((4, -3), (9, -8), (9, 8), (4, 3), (1, 3)):
                body.lineTo(r.left() + x, r.center().y() + y)
            body.closeSubpath()
            p.setBrush(color)
            p.drawPath(body)
            p.setBrush(Qt.BrushStyle.NoBrush)
            cx, cy = r.left() + 12, r.center().y()
            if self.symbol == "mute":
                p.drawLine(QPointF(cx, cy - 4), QPointF(cx + 7, cy + 4))
                p.drawLine(QPointF(cx, cy + 4), QPointF(cx + 7, cy - 4))
            else:
                for k, rad in enumerate((4.0, 7.5)):
                    p.drawArc(
                        QRectF(cx - rad + 1 + k, cy - rad, rad * 2, rad * 2), -50 * 16, 100 * 16
                    )
        p.restore()


class StepButton(QAbstractButton):
    """One step in the step bar: a dot and a monospace capital title."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.state = 1  # 0 done, 1 current, 2 to do
        self.struck = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.font_ = mono_font(10, 1.5)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(11 + QFontMetrics(self.font_).horizontalAdvance(self.text()) + 2, 22)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        dot = (ACCENT, QColor(style.TEXT), white(0.2))[self.state]
        text = (white(0.6), QColor(style.TEXT), white(0.3))[self.state]
        if not self.isEnabled():
            text = white(0.25)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(dot)
        p.drawEllipse(QRectF(0, self.height() / 2 - 2.5, 5, 5))
        font = QFont(self.font_)
        font.setStrikeOut(self.struck)
        p.setFont(font)
        p.setPen(text)
        p.drawText(
            QRectF(11, 0, self.width() - 11, self.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.text(),
        )
        if self.hasFocus():
            p.setPen(QPen(QColor(73, 220, 24, 140), 1))
            p.drawLine(11, self.height() - 2, self.width(), self.height() - 2)


class StepBar(QWidget):
    """Where you are in the guide: done steps green, the current one white. Every
    step can be clicked; a video's audio step is struck through without sound."""

    chosen = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(18)
        self.buttons: dict[str, StepButton] = {}

    def set_steps(
        self, steps, current: str, titles: dict[str, str], struck: set[str], locked: bool
    ) -> None:
        if list(self.buttons) != list(steps):
            for b in self.buttons.values():
                self.row.removeWidget(b)
                b.hide()
                b.deleteLater()
            self.buttons = {}
            for step in steps:
                b = StepButton()
                b.clicked.connect(lambda _c=False, s=step: self.chosen.emit(s))
                self.row.addWidget(b)
                self.buttons[step] = b
        index = list(steps).index(current) if current in steps else 0
        for i, (step, b) in enumerate(self.buttons.items()):
            b.setText(titles[step])
            b.setAccessibleName(titles[step])
            b.state = 0 if i < index else 1 if i == index else 2
            b.struck = step in struck
            b.setEnabled(not locked)
            b.updateGeometry()
            b.update()


class Timeline(QWidget):
    """A track to drag, with the covered stretches marked in green."""

    seek = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(16)
        self.setMinimumWidth(120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.frame_count = 1
        self.ranges: list[tuple[int, int]] = []
        self.position = 0

    def set_state(self, frame_count: int, ranges, position: int) -> None:
        self.frame_count, self.ranges, self.position = frame_count, ranges, position
        self.update()

    def _x(self, frame: int) -> float:
        total = max(self.frame_count - 1, 1)
        return 6 + (self.width() - 12) * frame / total

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        y = self.height() / 2 - 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(white(0.14))
        p.drawRoundedRect(QRectF(6, y, self.width() - 12, 4), 2, 2)
        p.setBrush(white(0.35))
        p.drawRoundedRect(QRectF(6, y, self._x(self.position) - 6, 4), 2, 2)
        green = QColor(ACCENT)
        green.setAlphaF(0.8)
        for lo, hi in self.ranges:
            p.fillRect(QRectF(self._x(lo), y, max(2.0, self._x(hi) - self._x(lo)), 4), green)
        p.setBrush(QColor(style.TEXT))
        p.setPen(QPen(QColor(0, 0, 0, 100), 1))
        p.drawEllipse(QPointF(self._x(self.position), self.height() / 2), 6, 6)

    def _seek_to(self, x: float) -> None:
        frac = (x - 6) / max(1, self.width() - 12)
        self.seek.emit(round(min(1.0, max(0.0, frac)) * max(self.frame_count - 1, 1)))

    def mousePressEvent(self, e) -> None:  # noqa: N802
        self._seek_to(e.position().x())

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        if e.buttons() & Qt.MouseButton.LeftButton:
            self._seek_to(e.position().x())


def glyph(kind: str, color: str = style.TEXT, size: int = 14):
    """Small drawn icons, the same on every system (no emoji fonts):
    "play", "pause", "dashed" (a dashed square), "folder", "lock"."""
    from PySide6.QtGui import QIcon, QPixmap

    scale = 3
    pm = QPixmap(size * scale, size * scale)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(scale, scale)
    c = QColor(color)
    s = float(size)
    if kind == "play":
        path = QPainterPath(QPointF(s * 0.28, s * 0.18))
        path.lineTo(s * 0.82, s * 0.5)
        path.lineTo(s * 0.28, s * 0.82)
        path.closeSubpath()
        p.fillPath(path, c)
    elif kind == "pause":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawRoundedRect(QRectF(s * 0.24, s * 0.2, s * 0.18, s * 0.6), 1, 1)
        p.drawRoundedRect(QRectF(s * 0.58, s * 0.2, s * 0.18, s * 0.6), 1, 1)
    elif kind == "dashed":
        pen = QPen(c, 1.3)
        pen.setDashPattern([2, 1.6])
        p.setPen(pen)
        p.drawRoundedRect(QRectF(s * 0.15, s * 0.15, s * 0.7, s * 0.7), 1.5, 1.5)
    elif kind == "folder":
        p.setPen(QPen(c, 1.2))
        path = QPainterPath(QPointF(s * 0.1, s * 0.25))
        for x, y in ((0.4, 0.25), (0.5, 0.36), (0.9, 0.36), (0.9, 0.82), (0.1, 0.82)):
            path.lineTo(s * x, s * y)
        path.closeSubpath()
        p.drawPath(path)
    elif kind == "lock":
        p.setPen(QPen(c, 1.2))
        p.drawArc(QRectF(s * 0.3, s * 0.12, s * 0.4, s * 0.5), 0, 180 * 16)
        p.drawLine(QPointF(s * 0.3, s * 0.37), QPointF(s * 0.3, s * 0.45))
        p.drawLine(QPointF(s * 0.7, s * 0.37), QPointF(s * 0.7, s * 0.45))
        p.setBrush(c)
        p.drawRoundedRect(QRectF(s * 0.2, s * 0.45, s * 0.6, s * 0.42), 1.5, 1.5)
    p.end()
    pm.setDevicePixelRatio(scale)
    return QIcon(pm)


class Swatch(QWidget):
    """A small outlined square, for the legend of the boxes."""

    def __init__(self, color: QColor, parent=None) -> None:
        super().__init__(parent)
        self.color = color
        self.setFixedSize(10, 10)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(self.color, 1.5))
        p.drawRoundedRect(QRectF(1, 1, 8, 8), 1, 1)


class Combo(QComboBox):
    """A pop-up menu button, with its chevron drawn (Fusion's would be grey on grey)."""

    def paintEvent(self, e) -> None:  # noqa: N802
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(style.SECONDARY), 1.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        x, y = self.width() - 14, self.height() / 2
        for dy in (-1, 1):
            p.drawLine(QPointF(x - 3, y + dy * 2), QPointF(x, y + dy * 5))
            p.drawLine(QPointF(x, y + dy * 5), QPointF(x + 3, y + dy * 2))
