"""Optional watermark: off by default, never a brand by default.

The text is set in Geist SemiBold (SIL OFL 1.1), white at 40% opacity,
centred, and one third of the image width.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = Path(__file__).parent / "fonts" / "Geist-SemiBold.otf"
OPACITY = 0.4
WIDTH_RATIO = 1 / 3


class Watermark:
    def __init__(self, text: str) -> None:
        text = text.strip()
        if not text:
            raise ValueError("watermark text is empty")
        self.text = text
        self._masks: dict[tuple[int, int], np.ndarray] = {}

    def _mask(self, width: int, height: int) -> np.ndarray:
        key = (width, height)
        if key not in self._masks:
            target = width * WIDTH_RATIO
            probe = ImageFont.truetype(str(FONT_PATH), 100)
            x0, _, x1, _ = probe.getbbox(self.text)
            size = max(8, int(round(100 * target / max(1, x1 - x0))))
            size = min(size, max(8, height // 2))
            font = ImageFont.truetype(str(FONT_PATH), size)
            left, top, right, bottom = font.getbbox(self.text)
            layer = Image.new("L", (width, height), 0)
            ImageDraw.Draw(layer).text(
                ((width - (right - left)) // 2 - left, (height - (bottom - top)) // 2 - top),
                self.text,
                font=font,
                fill=255,
            )
            self._masks[key] = (np.asarray(layer, dtype=np.float32) / 255.0 * OPACITY)[..., None]
        return self._masks[key]

    def apply(self, image: np.ndarray) -> np.ndarray:
        """Blend white text into an HxWx3 uint8 image (RGB or BGR), in place."""
        mask = self._mask(image.shape[1], image.shape[0])
        blended = image.astype(np.float32) * (1.0 - mask) + 255.0 * mask
        image[...] = np.clip(blended + 0.5, 0, 255).astype(np.uint8)
        return image
