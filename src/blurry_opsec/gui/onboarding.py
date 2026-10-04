"""The first-run guide, as on the Mac (WelcomeView.swift, Onboarding.swift):
an introduction in three pages with Blurry at the top, then three tips shown
next to what they talk about (step bar, "Correct the boxes", the saved file).
Only an explicit action advances the guide; dismissing a tip only hides it.
Only a boolean is kept ("onboarded", allowed by R2)."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from blurry_opsec.gui import strings as L
from blurry_opsec.gui import style
from blurry_opsec.gui.mascot import Mascot
from blurry_opsec.gui.store import Store
from blurry_opsec.gui.widgets import ACCENT, button, label, white


class PageDots(QWidget):
    """Where the introduction is: one capsule per page, the current one long and green."""

    def __init__(self, count: int, parent=None) -> None:
        super().__init__(parent)
        self.count = count
        self.current = 0
        self.setFixedSize(28 + (count - 1) * 16, 6)

    def set_current(self, index: int) -> None:
        self.current = index
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        x = 0.0
        for i in range(self.count):
            on = i == self.current
            w = 28 if on else 8
            p.setBrush(ACCENT if on else white(0.15))
            p.drawRoundedRect(QRectF(x, 0.5, w, 5), 2.5, 2.5)
            x += w + 8


def _number(n: str) -> QLabel:
    lab = QLabel(n)
    lab.setFixedSize(24, 24)
    lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lab.setStyleSheet(
        f"color: {style.ACCENT}; background: rgba(73, 220, 24, 0.12); "
        f"border-radius: 12px; font-family: '{style.MONO}'; font-size: 11px;"
    )
    return lab


class WelcomeDialog(QDialog):
    """An introduction before any file is loaded. Blurry stays still at the top,
    centred; only the text below changes."""

    PAGES = 3

    def __init__(self, store: Store, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self.setModal(True)
        self.setFixedSize(500, 420)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        col = QVBoxLayout(self)
        col.setContentsMargins(30, 30, 30, 30)
        col.setSpacing(18)
        self.mascot = Mascot(88)
        col.addWidget(self.mascot, 0, Qt.AlignmentFlag.AlignHCenter)
        self.dots = PageDots(self.PAGES)
        col.addWidget(self.dots, 0, Qt.AlignmentFlag.AlignHCenter)
        self.title = label("", "title2")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(self.title)
        self.pages = QStackedWidget()
        col.addWidget(self.pages, 1)

        def page(*widgets) -> None:
            w = QWidget()
            v = QVBoxLayout(w)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(14)
            for x in widgets:
                v.addWidget(x) if isinstance(x, QWidget) else v.addLayout(x)
            v.addStretch(1)
            self.pages.addWidget(w)

        def centred(name: str) -> QLabel:
            lab = label("", name, wrap=True)
            lab.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            return lab

        self.subtitle, self.privacy = centred("subtitle"), centred("secondary")
        page(self.subtitle, self.privacy)
        self.safety, self.limits = centred(""), centred("secondary")
        page(self.safety, self.limits)
        rows = QVBoxLayout()
        rows.setSpacing(12)
        self.steps: list[QLabel] = []
        for n in ("1", "2", "3"):
            r = QHBoxLayout()
            r.setSpacing(12)
            text = label("", "", wrap=True)
            r.addStretch(1)
            r.addWidget(_number(n))
            r.addWidget(text, 8)
            r.addStretch(1)
            rows.addLayout(r)
            self.steps.append(text)
        self.original = centred("calloutSecondary")
        page(rows, self.original)

        nav = QHBoxLayout()
        nav.setSpacing(14)
        self.skip_btn = button("", "quiet", self._skip)
        self.back_btn = button("", "large", lambda: self.go(self.pages.currentIndex() - 1))
        self.next_btn = button("", "primary", self._forward)
        self.next_btn.setDefault(True)
        nav.addWidget(self.skip_btn)
        nav.addStretch(1)
        nav.addWidget(self.back_btn)
        nav.addWidget(self.next_btn)
        col.addLayout(nav)
        self.go(0)

    def retranslate(self) -> None:
        index = self.pages.currentIndex()
        self.setWindowTitle("Blurry")
        self.title.setText(
            (L.welcome_title(), L.welcome_safety_title(), L.welcome_workflow_title())[index]
        )
        self.subtitle.setText(L.welcome_subtitle())
        self.privacy.setText(L.welcome_privacy())
        self.safety.setText(L.welcome_safety())
        self.limits.setText(L.welcome_limits())
        for text, value in zip(
            self.steps, (L.welcome_drop(), L.welcome_review(), L.welcome_export()), strict=True
        ):
            text.setText(value)
        self.original.setText(L.welcome_original())
        self.skip_btn.setText(L.tip_skip())
        self.back_btn.setText(L.back())
        self.next_btn.setText(L.start() if index == self.PAGES - 1 else L.tip_next())

    def go(self, index: int) -> None:
        index = max(0, min(self.PAGES - 1, index))
        if index != self.pages.currentIndex():
            self.mascot.nudge()
        self.pages.setCurrentIndex(index)
        self.dots.set_current(index)
        self.back_btn.setVisible(index > 0)
        self.retranslate()

    def _forward(self) -> None:
        if self.pages.currentIndex() == self.PAGES - 1:
            self.store.begin_guided_session()
            self.accept()
        else:
            self.go(self.pages.currentIndex() + 1)

    def _skip(self) -> None:
        self.store.finish_onboarding()
        self.accept()

    def reject(self) -> None:
        """Esc does nothing; closing the window is the same as skipping."""

    def closeEvent(self, e) -> None:  # noqa: N802
        if self.isVisible():
            self._skip()
        e.accept()


class TipPopover(QWidget):
    """A tip next to the widget it talks about, with an arrow, inside the window
    (top-level popups are unreliable on Wayland). A click outside hides it."""

    action = Signal()
    skip = Signal()
    dismissed = Signal()

    ARROW = 8
    WIDTH = 300

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("tip")
        self.setFixedWidth(self.WIDTH)
        col = QVBoxLayout(self)
        col.setContentsMargins(16, 16 + self.ARROW, 16, 16 + self.ARROW)
        col.setSpacing(12)
        line = QHBoxLayout()
        line.setSpacing(8)
        dot = QLabel()
        dot.setFixedSize(6, 6)
        dot.setStyleSheet(f"background: {style.ACCENT}; border-radius: 3px; margin-top: 0px;")
        self.text = label("", "callout", wrap=True)
        line.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)
        line.addWidget(self.text, 1)
        col.addLayout(line)
        nav = QHBoxLayout()
        self.skip_btn = button("", "quiet", self.skip.emit)
        self.skip_btn.setStyleSheet("font-size: 11px;")
        self.action_btn = button("", "", self.action.emit)
        nav.addWidget(self.skip_btn)
        nav.addStretch(1)
        nav.addWidget(self.action_btn)
        col.addLayout(nav)
        self.below = True  # the arrow points up, at a widget above
        self.arrow_x = self.WIDTH / 2
        self.anchor: QWidget | None = None
        self.hide()
        parent.installEventFilter(self)

    def show_at(self, anchor: QWidget, text: str, action: str, prefer_below: bool) -> None:
        self.anchor = anchor
        self.text.setText(text)
        self.skip_btn.setText(L.tip_skip())
        self.action_btn.setText(action)
        self.adjustSize()
        self.place(prefer_below)
        self.show()
        self.raise_()

    def place(self, prefer_below: bool | None = None) -> None:
        if self.anchor is None:
            return
        parent = self.parentWidget()
        top_left = self.anchor.mapTo(parent, QPoint(0, 0))
        a = QRectF(top_left.x(), top_left.y(), self.anchor.width(), self.anchor.height())
        h = self.sizeHint().height()
        below = self.below if prefer_below is None else prefer_below
        # Turn around if there is no room on the preferred side.
        if below and a.bottom() + h > parent.height():
            below = False
        elif not below and a.top() - h < 0:
            below = True
        self.below = below
        x = min(max(8.0, a.center().x() - self.WIDTH / 2), parent.width() - self.WIDTH - 8)
        y = a.bottom() + 2 if below else a.top() - h - 2
        self.arrow_x = a.center().x() - x
        self.setGeometry(int(x), int(y), self.WIDTH, h)
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        a = self.ARROW
        body = QRectF(self.rect()).adjusted(0.5, a + 0.5, -0.5, -a - 0.5)
        path = QPainterPath()
        path.addRoundedRect(body, 10, 10)
        ax = min(max(18.0, self.arrow_x), self.width() - 18.0)
        arrow = QPainterPath()
        if self.below:
            arrow.moveTo(ax - a, body.top() + 1)
            arrow.lineTo(ax, body.top() - a + 1)
            arrow.lineTo(ax + a, body.top() + 1)
        else:
            arrow.moveTo(ax - a, body.bottom() - 1)
            arrow.lineTo(ax, body.bottom() + a - 1)
            arrow.lineTo(ax + a, body.bottom() - 1)
        arrow.closeSubpath()
        path = path.united(arrow)
        p.setPen(QPen(white(0.14), 1))
        p.setBrush(QColor(style.POPOVER))
        p.drawPath(path)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if not self.isVisible():
            return False
        if event.type() == QEvent.Type.Resize:
            self.place()
        return False

    def outside_click(self, global_pos: QPointF) -> None:
        """Called by the window for every press: one outside the tip hides it."""
        if self.isVisible() and not self.rect().contains(self.mapFromGlobal(global_pos.toPoint())):
            self.hide()
            self.dismissed.emit()
