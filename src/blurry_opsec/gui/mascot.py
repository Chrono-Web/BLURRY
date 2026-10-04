"""Blurry as a small character: the app icon's mosaic, alive.

It blinks, follows the pointer and greets when it appears. Repainting only
runs while something moves; when it is still or hidden, no timer fires except
the pointer check and the blink, both stopped while hidden.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QPainter
from PySide6.QtWidgets import QWidget

from blurry_opsec.gui import mascot_face as face

# Cell gap and corner radius, as fractions of a cell (as in the app icon).
GAP = 9 / 74.3
RADIUS = 16 / 74.3


class Mascot(QWidget):
    def __init__(self, size: int = 96, greet: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(QSize(size, size))
        self.setAccessibleName("Blurry")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.anim = face.Animator()
        self.greet = greet
        self.cells = face.cells()
        self.grey = face.values(face.Pose())
        self.frame = QTimer(self, interval=33, timeout=self._frame)  # 30 fps while moving
        self.pointer = QTimer(self, interval=100, timeout=self._pointer)
        self.blinker = QTimer(self, interval=int(face.BLINK_EVERY * 1000), timeout=self._blink)
        self.ungreet = QTimer(self, singleShot=True, interval=1400)
        self.ungreet.timeout.connect(lambda: self.smile(False))

    @staticmethod
    def now() -> float:
        return time.monotonic()

    def wake(self, duration: float = 0.0) -> None:
        """Repaint for `duration` seconds, or until what the animator asked for ends."""
        t = self.now()
        if duration:
            self.anim.wake(t, duration)
        if self.anim.active_until > t and self.isVisible() and not self.frame.isActive():
            self.frame.start()

    def smile(self, on: bool) -> None:
        self.anim.set_smiling(self.now(), on)
        self.wake()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.anim.last_t = None
        self.pointer.start()
        self.blinker.start()
        if self.greet:
            self.smile(True)
            self.ungreet.start()
        self.wake(1.0)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        for timer in (self.frame, self.pointer, self.blinker, self.ungreet):
            timer.stop()
        if self.anim.smiling:
            self.anim.set_smiling(self.now(), False)

    def _blink(self) -> None:
        self.anim.tick_blink(self.now())
        self.wake()

    def _pointer(self) -> None:
        centre = self.mapToGlobal(self.rect().center())
        pos = QCursor.pos()
        self.anim.look(self.now(), face.gaze_goal(pos.x() - centre.x(), pos.y() - centre.y()))
        self.wake()

    def _frame(self) -> None:
        self.grey, moving = self.anim.frame(self.now())
        self.update()
        if not moving:
            self.frame.stop()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        n = face.GRID
        cell = self.width() / n
        gap, radius = cell * GAP, cell * RADIUS
        for (col, row), v in zip(self.cells, self.grey, strict=True):
            g = round(min(1.0, max(0.0, v)) * 255)
            p.setBrush(QColor(g, g, g))
            rect = QRectF(col * cell + gap / 2, row * cell + gap / 2, cell - gap, cell - gap)
            p.drawRoundedRect(rect, radius, radius)
        p.end()
