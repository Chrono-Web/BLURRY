"""Face detection with YuNet (OpenCV DNN). No fallback detector, on purpose."""

from __future__ import annotations

import cv2
import numpy as np

from blurry_opsec import levels, model
from blurry_opsec.plan import Box


class FaceDetector:
    def __init__(self, level: str = levels.DEFAULT_LEVEL, model_bytes: bytes | None = None):
        self.level = levels.get(level)
        data = model_bytes if model_bytes is not None else model.load_verified()
        self._net = cv2.FaceDetectorYN.create(
            "onnx",
            np.frombuffer(data, dtype=np.uint8),
            np.empty(0, dtype=np.uint8),
            (320, 320),
            self.level.confidence,
            levels.YUNET_NMS,
            levels.YUNET_TOPK,
        )
        self._size: tuple[int, int] | None = None

    @property
    def confidence(self) -> float:
        return self.level.confidence

    def detect(self, bgr: np.ndarray) -> list[Box]:
        """Detect faces in a BGR uint8 image. Boxes are clipped to the image."""
        h, w = bgr.shape[:2]
        if self._size != (w, h):
            self._net.setInputSize((w, h))
            self._size = (w, h)
        _, faces = self._net.detect(np.ascontiguousarray(bgr))
        if faces is None:
            return []
        boxes = []
        for face in faces:
            x, y, bw, bh = int(face[0]), int(face[1]), int(face[2]), int(face[3])
            # YuNet can return boxes that go past the frame edges.
            x, y = max(0, x), max(0, y)
            bw, bh = min(w - x, bw), min(h - y, bh)
            if bw > 0 and bh > 0:
                boxes.append(Box(x, y, bw, bh, score=float(face[-1])))
        return boxes
