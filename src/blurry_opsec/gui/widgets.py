"""Small building blocks: glass panel, segmented control, switch, HUD frame,
status pills, draggable title area."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyledItemDelegate,
    QWidget,
)

from blurry_opsec.gui import style


def corner_ticks(p: QPainter, r: QRectF, n: float) -> None:
    """Four L-shaped corner marks of length n, with the painter's current pen."""
    corners = ((r.left(), r.top(), 1, 1), (r.right(), r.top(), -1, 1),
               (r.left(), r.bottom(), 1, -1), (r.right(), r.bottom(), -1, -1))  # fmt: skip
    for cx, cy, dx, dy in corners:
        p.drawLine(QPointF(cx, cy), QPointF(cx + dx * n, cy))
        p.drawLine(QPointF(cx, cy), QPointF(cx, cy + dy * n))


def label(text: str = "", name: str = "label") -> QLabel:
    lab = QLabel(text)
    lab.setObjectName(name)
    return lab


class GlassPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("glass")


class Segmented(QFrame):
    """A row of mutually exclusive options, like macOS segmented controls."""

    changed = Signal(object)

    def __init__(self, options: list[tuple[object, str]], value=None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("segmented")
        self._group = QButtonGroup(self)
        self._buttons: dict[object, QPushButton] = {}
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 2, 2, 2)
        row.setSpacing(2)
        for key, text in options:
            b = QPushButton(text)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self._group.addButton(b)
            self._buttons[key] = b
            row.addWidget(b, 1)
            b.clicked.connect(lambda _c=False, k=key: self.changed.emit(k))
        self.set_value(value if value is not None else options[0][0])

    def value(self):
        for key, b in self._buttons.items():
            if b.isChecked():
                return key
        return None

    def set_value(self, key) -> None:
        if key in self._buttons:
            self._buttons[key].setChecked(True)

    def set_texts(self, texts: dict) -> None:
        for key, text in texts.items():
            if key in self._buttons:
                self._buttons[key].setText(text)


class Switch(QAbstractButton):
    """An on/off switch."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(QSize(30, 18))

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        on = self.isChecked()
        p.setPen(QPen(QColor(style.TEXT if on else "#555555"), 1))
        p.setBrush(QColor(style.TEXT) if on else QColor(255, 255, 255, 10))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.right() - d - 3 if on else r.left() + 3
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(style.BG) if on else QColor("#9a9a9a"))
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))


class HudFrame(QFrame):
    """Drop area with thin corner ticks (the one HUD detail of the home screen)."""

    def paintEvent(self, e) -> None:  # noqa: N802
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        active = self.property("active") == "true"
        p.setPen(QPen(QColor(style.ACCENT if active else "#9a9a9a"), 1))
        corner_ticks(p, QRectF(self.rect()).adjusted(10, 10, -11, -11), 12)

    def set_active(self, active: bool) -> None:
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class DragArea(QWidget):
    """Top strip that moves the window, as a title bar does."""

    def mousePressEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton and self.window().windowHandle():
            self.window().windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self, _e) -> None:  # noqa: N802
        w = self.window()
        w.showNormal() if w.isMaximized() else w.showMaximized()


# Status column: (text colour, border colour) per state.
PILL_COLORS = {
    "ready": (style.ACCENT, "rgba(73,220,24,0.45)"),
    "review": (style.WARN, "rgba(251,146,60,0.45)"),
    "no_faces": (style.DANGER, "rgba(239,68,68,0.55)"),
    "error": (style.DANGER, "rgba(239,68,68,0.55)"),
    "exported": (style.MUTED, "rgba(255,255,255,0.18)"),
}
STATUS_ROLE = Qt.ItemDataRole.UserRole + 1


class PillDelegate(QStyledItemDelegate):
    """Draws the status as a small monospace pill."""

    def paint(self, painter: QPainter, option, index) -> None:
        state = index.data(STATUS_ROLE)
        if state not in PILL_COLORS:
            super().paint(painter, option, index)
            return
        self.initStyleOption(option, index)
        text = option.text
        option.text = ""
        option.widget.style().drawControl(
            option.widget.style().ControlElement.CE_ItemViewItem, option, painter, option.widget
        )
        fg, border = PILL_COLORS[state]
        font = QFont(style.MONO)
        font.setPixelSize(10)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(font)
        fm = painter.fontMetrics()
        w = min(option.rect.width() - 8, fm.horizontalAdvance(text) + 16)
        r = QRectF(option.rect.left() + 4, option.rect.center().y() - 9, w, 18)
        painter.setPen(QPen(QColor(border), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(r, 4, 4)
        painter.setPen(QColor(fg))
        painter.drawText(
            r,
            Qt.AlignmentFlag.AlignCenter,
            fm.elidedText(text, Qt.TextElideMode.ElideRight, int(w) - 10),
        )
        painter.restore()
