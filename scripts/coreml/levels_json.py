"""Write ios/BlurryKit's levels.json from blurry_opsec.levels, the single source.

    uv run python scripts/coreml/levels_json.py

tests/test_ios_kit.py fails if the committed file differs from what this writes.
"""

import json
from pathlib import Path

from blurry_opsec import levels

OUT = Path(__file__).resolve().parents[2] / "ios/BlurryKit/Sources/BlurryKit/Resources/levels.json"


def levels_json() -> str:
    data = {
        "_generated": "scripts/coreml/levels_json.py from src/blurry_opsec/levels.py: do not edit",
        "levels": [
            {
                "name": lv.name,
                "confidence": lv.confidence,
                "blocks": lv.blocks,
                "label": lv.label,
                "description": lv.description,
            }
            for lv in levels.LEVELS.values()
        ],
        "default_level": levels.DEFAULT_LEVEL,
        "most_sensitive": levels.MOST_SENSITIVE,
        "default_mode": levels.DEFAULT_MODE,
        "default_padding": levels.DEFAULT_PADDING,
        "modes": list(levels.MODES),
        "yunet_nms": levels.YUNET_NMS,
        "yunet_topk": levels.YUNET_TOPK,
        "near_threshold_margin": levels.NEAR_THRESHOLD_MARGIN,
        "small_face_px": levels.SMALL_FACE_PX,
    }
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(levels_json(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(OUT.parents[5])}")
