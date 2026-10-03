"""Cover regions: solid black (default) or pixelation."""

from __future__ import annotations

import cv2
import numpy as np

from blurry_opsec.plan import Box


def padded_rect(box: Box, padding: float, width: int, height: int) -> tuple[int, int, int, int]:
    """Return (x0, y0, x1, y1) grown by `padding` x long side on every side, clipped."""
    pad = int(box.long_side * padding)
    x0 = max(0, box.x - pad)
    y0 = max(0, box.y - pad)
    x1 = min(width, box.x + box.w + pad)
    y1 = min(height, box.y + box.h + pad)
    return x0, y0, x1, y1


def pixelate(roi: np.ndarray, blocks: int) -> np.ndarray:
    """A fixed number of blocks on the long side, so near and far faces end up
    equally anonymous. INTER_AREA averages every pixel of a block (INTER_LINEAR
    would sample a few and leak detail); INTER_NEAREST keeps the blocks hard."""
    h, w = roi.shape[:2]
    block_px = max(1, int(round(max(w, h) / max(2, blocks))))
    small = cv2.resize(
        roi, (max(1, w // block_px), max(1, h // block_px)), interpolation=cv2.INTER_AREA
    )
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)


def apply(
    image: np.ndarray,
    boxes: list[Box],
    mode: str,
    padding: float,
    blocks: int,
    alpha: np.ndarray | None = None,
) -> np.ndarray:
    """Cover `boxes` in place on an HxWxC uint8 image and return it.

    If an alpha plane is given, covered areas become fully opaque, so that a
    transparent region cannot hide the outline of a face.
    """
    height, width = image.shape[:2]
    for box in boxes:
        x0, y0, x1, y1 = padded_rect(box, padding, width, height)
        if x1 <= x0 or y1 <= y0:
            continue
        if mode == "solid":
            image[y0:y1, x0:x1] = 0
        elif mode == "pixel":
            image[y0:y1, x0:x1] = pixelate(image[y0:y1, x0:x1], blocks)
        else:
            raise ValueError(f"unknown mode {mode!r}")
        if alpha is not None:
            alpha[y0:y1, x0:x1] = 255
    return image
