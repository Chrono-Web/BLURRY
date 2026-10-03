"""Image view with editable boxes.

Scene coordinates are the pixels of the (possibly downscaled) preview image;
boxes are exchanged with the rest of the app in original-image coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView

from blurry_opsec.gui import style
from blurry_opsec.gui.widgets import corner_ticks
from blurry_opsec.plan import Box

HANDLE_PX = 9  # corner grab area, in screen pixels
MIN_BOX_PX = 6


@dataclass
class CanvasBox:
    key: object
    box: Box  # original-image coordinates
    kind: str  # "auto", "manual" or "off" (a disabled track)
    editable: bool


class BoxItem(QGraphicsRectItem):
    def __init__(self, canvas: Canvas, spec: CanvasBox, rect: QRectF) -> None:
        super().__init__(rect)
        self.canvas = canvas
        self.spec = spec
        self._drag: tuple[str, QPointF, QRectF] | None = None
        flags = QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        if spec.editable:
            flags |= QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
        self.setFlags(flags if spec.editable else QGraphicsItem.GraphicsItemFlag(0))
        self.setAcceptHoverEvents(spec.editable)
        self.color = QColor({"auto": style.AUTO, "manual": style.MANUAL}.get(spec.kind, style.OFF))
        self.setPen(Qt.PenStyle.NoPen)
        self.setZValue(2 if spec.editable else 1)

    def _handle(self) -> float:
        return HANDLE_PX / max(1e-6, self.canvas.transform().m11())

    def _corner_at(self, pos: QPointF) -> str | None:
        r, h = self.rect(), self._handle()
        corners = {
            "tl": r.topLeft(),
            "tr": r.topRight(),
            "bl": r.bottomLeft(),
            "br": r.bottomRight(),
        }
        for name, pt in corners.items():
            if abs(pos.x() - pt.x()) <= h and abs(pos.y() - pt.y()) <= h:
                return name
        return None

    def hoverMoveEvent(self, event) -> None:  # noqa: N802
        corner = self._corner_at(event.pos())
        shape = {
            "tl": Qt.CursorShape.SizeFDiagCursor,
            "br": Qt.CursorShape.SizeFDiagCursor,
            "tr": Qt.CursorShape.SizeBDiagCursor,
            "bl": Qt.CursorShape.SizeBDiagCursor,
        }.get(corner, Qt.CursorShape.SizeAllCursor)
        self.setCursor(shape)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if not self.spec.editable or event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        self.canvas.scene().clearSelection()
        self.setSelected(True)
        self.setFocus()
        self._drag = (self._corner_at(event.pos()) or "move", event.scenePos(), QRectF(self.rect()))
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag is None:
            return
        mode, start, orig = self._drag
        d = event.scenePos() - start
        r = QRectF(orig)
        if mode == "move":
            r.translate(d)
        else:
            if "l" in mode:
                r.setLeft(orig.left() + d.x())
            if "r" in mode:
                r.setRight(orig.right() + d.x())
            if "t" in mode:
                r.setTop(orig.top() + d.y())
            if "b" in mode:
                r.setBottom(orig.bottom() + d.y())
            r = r.normalized()
        self.setRect(r.intersected(self.canvas.image_rect()))

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._drag is None:
            return
        self._drag = None
        self.canvas.box_changed.emit(self.spec.key, self.canvas.to_box(self.rect()))

    def paint(self, painter: QPainter, option, widget=None) -> None:
        """Reticle style: hairline frame, firm corner brackets."""
        r = self.rect()
        off = self.spec.kind == "off"
        fill = QColor(self.color)
        fill.setAlpha(0 if off else 22)
        frame = QColor(self.color)
        frame.setAlpha(255 if self.isSelected() else 150)
        pen = QPen(frame, 1, Qt.PenStyle.DashLine if off else Qt.PenStyle.SolidLine)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(QBrush(fill))
        painter.drawRect(r)
        if not off:
            px = max(1e-6, self.canvas.transform().m11())
            n = min(r.width(), r.height()) * 0.28
            n = max(9 / px, min(n, 26 / px))
            pen = QPen(self.color, 3)
            pen.setCosmetic(True)
            pen.setCapStyle(Qt.PenCapStyle.SquareCap)
            painter.setPen(pen)
            corner_ticks(painter, r, n)
        if self.isSelected():
            h = self._handle() * 0.6
            painter.setBrush(QColor(style.TEXT))
            painter.setPen(Qt.PenStyle.NoPen)
            for pt in (r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()):
                painter.drawRect(QRectF(pt.x() - h / 2, pt.y() - h / 2, h, h))


class Canvas(QGraphicsView):
    box_added = Signal(object)  # Box
    box_changed = Signal(object, object)  # key, Box
    box_deleted = Signal(object)  # key

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._pixmap_item = self.scene().addPixmap(QPixmap())
        self._scale = 1.0
        self._items: list[BoxItem] = []
        self._rubber: QGraphicsRectItem | None = None
        self._rubber_start: QPointF | None = None
        self.drawing_enabled = True
        self._show_boxes = True

    # -- coordinates ---------------------------------------------------------
    def image_rect(self) -> QRectF:
        return self._pixmap_item.boundingRect()

    def to_box(self, r: QRectF) -> Box:
        s = self._scale
        return Box(int(round(r.x() / s)), int(round(r.y() / s)),
                   max(1, int(round(r.width() / s))), max(1, int(round(r.height() / s))),
                   None, "manual")  # fmt: skip

    def to_rect(self, b: Box) -> QRectF:
        s = self._scale
        return QRectF(b.x * s, b.y * s, b.w * s, b.h * s)

    # -- content -------------------------------------------------------------
    def set_image(self, image: QImage, scale: float) -> None:
        first = self._pixmap_item.pixmap().isNull()
        self._pixmap_item.setPixmap(QPixmap.fromImage(image))
        self._scale = scale
        self.scene().setSceneRect(self.image_rect())
        if first:
            self.fit()

    def set_boxes(self, specs: list[CanvasBox], selected_key=None) -> None:
        for item in self._items:
            self.scene().removeItem(item)
        self._items = []
        for spec in specs:
            item = BoxItem(self, spec, self.to_rect(spec.box))
            item.setVisible(self._show_boxes)
            self.scene().addItem(item)
            self._items.append(item)
            if selected_key is not None and spec.key == selected_key and spec.editable:
                item.setSelected(True)

    def show_boxes(self, show: bool) -> None:
        self._show_boxes = show
        for item in self._items:
            item.setVisible(show)

    def fit(self) -> None:
        if not self._pixmap_item.pixmap().isNull():
            self.fitInView(self.image_rect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.fit()

    # -- drawing new boxes ---------------------------------------------------
    def mousePressEvent(self, event) -> None:  # noqa: N802
        item = self.itemAt(event.position().toPoint())
        if isinstance(item, BoxItem) and item.spec.editable:
            super().mousePressEvent(event)
            return
        self.scene().clearSelection()
        if (
            self.drawing_enabled
            and self._show_boxes
            and event.button() == Qt.MouseButton.LeftButton
            and self.image_rect().contains(self.mapToScene(event.position().toPoint()))
        ):
            self._rubber_start = self.mapToScene(event.position().toPoint())
            self._rubber = self.scene().addRect(QRectF(self._rubber_start, self._rubber_start))
            pen = QPen(QColor(style.MANUAL), 1.5, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            self._rubber.setPen(pen)
            self._rubber.setZValue(3)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._rubber is not None and self._rubber_start is not None:
            end = self.mapToScene(event.position().toPoint())
            r = QRectF(self._rubber_start, end).normalized().intersected(self.image_rect())
            self._rubber.setRect(r)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._rubber is not None:
            r = self._rubber.rect()
            self.scene().removeItem(self._rubber)
            self._rubber = None
            self._rubber_start = None
            px = self.transform().m11()
            if r.width() * px >= MIN_BOX_PX and r.height() * px >= MIN_BOX_PX:
                self.box_added.emit(self.to_box(r))
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            for item in self.scene().selectedItems():
                if isinstance(item, BoxItem) and item.spec.editable:
                    self.box_deleted.emit(item.spec.key)
                    return
        super().keyPressEvent(event)
