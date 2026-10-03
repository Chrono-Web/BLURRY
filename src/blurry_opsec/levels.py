"""Single source of truth for detection levels.

The numbers come from the original OPSEC engine, where they were measured on
98 real images: up to a confidence of 0.7 only redundant detections are lost,
from 0.8 up whole images (real faces) disappear. Lower threshold = more
sensitive: covering something extra is better than missing a face.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Level:
    name: str
    confidence: float
    # Pixelation strength as the number of blocks on the long side of the face.
    # Fewer blocks = more anonymous, independently of the face size.
    blocks: int
    label: dict[str, str]
    description: dict[str, str]


LEVELS: dict[str, Level] = {
    "base": Level(
        "base",
        0.7,
        8,
        {"it": "Leggero", "en": "Light"},
        {"it": "Solo volti evidenti e frontali", "en": "Only clear, frontal faces"},
    ),
    "medium": Level(
        "medium",
        0.6,
        6,
        {"it": "Standard", "en": "Standard"},
        {
            "it": "Bilanciato per la maggior parte dei casi",
            "en": "Balanced for most cases",
        },
    ),
    "high": Level(
        "high",
        0.5,
        4,
        {"it": "Aggressivo", "en": "Aggressive"},
        {
            "it": "Cattura anche volti piccoli o parzialmente nascosti",
            "en": "Also catches small or partly hidden faces",
        },
    ),
}

YUNET_NMS = 0.3
YUNET_TOPK = 5000

DEFAULT_LEVEL = "high"
DEFAULT_MODE = "solid"
DEFAULT_PADDING = 0.25
MODES = ("solid", "pixel")

# Review flags.
NEAR_THRESHOLD_MARGIN = 0.1
SMALL_FACE_PX = 32


def get(name: str) -> Level:
    try:
        return LEVELS[name]
    except KeyError:
        raise ValueError(f"unknown level {name!r}; choose one of {', '.join(LEVELS)}") from None
