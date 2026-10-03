"""Queue items and image helpers. Everything here lives in memory only."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QImage, QPixmap

from blurry_opsec import levels, redact
from blurry_opsec.plan import NO_FACES, Box, ImagePlan, VideoPlan

# Item states
WAITING = "waiting"
ANALYZING = "analyzing"
READY = "ready"
REVIEW = "review"
NO_FACES_FOUND = "no_faces"
EXPORTING = "exporting"
EXPORTED = "exported"
ERROR = "error"
CANCELLED = "cancelled"

ANALYSED = (READY, REVIEW, NO_FACES_FOUND, EXPORTED)


@dataclass
class Item:
    path: Path
    kind: str  # "image" or "video"
    status: str = WAITING
    progress: int = 0
    plan: ImagePlan | VideoPlan | None = None
    metadata_found: list[str] = field(default_factory=list)
    has_audio: bool = False
    preview: QImage | None = None  # images: display copy of the analysed pixels
    preview_scale: float = 1.0
    thumb: QIcon | None = None
    error: str = ""
    output_name: str = ""
    edited: bool = False

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def faces(self) -> int | None:
        if self.plan is None:
            return None
        if isinstance(self.plan, ImagePlan):
            return len(self.plan.boxes)
        return sum(1 for t in self.plan.tracks if t.enabled) + len(self.plan.manual)

    @property
    def uncovered_risk(self) -> bool:
        """No face found and nothing added by hand."""
        return self.plan is not None and self.plan.faces_expected and not self.faces

    def review_flags(self) -> list:
        if self.plan is None:
            return []
        return [f for f in self.plan.flags if f.kind != NO_FACES]

    def settle(self) -> None:
        """Status after analysis or after an edit."""
        if self.uncovered_risk:
            self.status = NO_FACES_FOUND
        elif self.review_flags() and not self.edited:
            self.status = REVIEW
        else:
            self.status = READY


def decode_preview(b64: str) -> QImage:
    image = QImage.fromData(base64.b64decode(b64), "JPG")
    return image.convertToFormat(QImage.Format.Format_RGB888)


def qimage_to_array(image: QImage) -> np.ndarray:
    image = image.convertToFormat(QImage.Format.Format_RGB888)
    w, h, bpl = image.width(), image.height(), image.bytesPerLine()
    arr = np.frombuffer(image.constBits(), dtype=np.uint8, count=bpl * h).reshape(h, bpl)
    return arr[:, : w * 3].reshape(h, w, 3).copy()


def array_to_qimage(arr: np.ndarray) -> QImage:
    arr = np.ascontiguousarray(arr)
    h, w = arr.shape[:2]
    return QImage(arr.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()


def scaled(box: Box, s: float) -> Box:
    return Box(int(box.x * s), int(box.y * s), max(1, int(round(box.w * s))),
               max(1, int(round(box.h * s))), box.score, box.source)  # fmt: skip


def preview_result(image: QImage, boxes: list[Box], scale: float, mode: str, padding: float,
                   level: str) -> QImage:  # fmt: skip
    """What the export will look like, on the display copy."""
    arr = qimage_to_array(image)
    redact.apply(arr, [scaled(b, scale) for b in boxes], mode, padding, levels.get(level).blocks)
    return array_to_qimage(arr)


def icon_from(image: QImage, side: int = 40) -> QIcon:
    return QIcon(QPixmap.fromImage(image.scaled(side, side, Qt.AspectRatioMode.KeepAspectRatio)))
