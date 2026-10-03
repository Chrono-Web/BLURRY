"""Baseline: Blurry must find the same faces as the original OPSEC engine.

Needs the original script and a virtualenv built from its requirements, both
outside this repository. Skipped unless configured:

    BLURRY_BASELINE_PYTHON=/path/to/venv/bin/python
    BLURRY_BASELINE_SCRIPT=/path/to/BACKEND/scripts/media_processor.py
"""

import json
import os
import subprocess
from pathlib import Path

import pytest
from corpus import FIXTURES, detect_file

from blurry_opsec.detect import FaceDetector
from blurry_opsec.model import MODEL_PATH
from blurry_opsec.plan import Box

PY = os.environ.get("BLURRY_BASELINE_PYTHON")
SCRIPT = os.environ.get("BLURRY_BASELINE_SCRIPT")

pytestmark = pytest.mark.skipif(not (PY and SCRIPT), reason="baseline not configured")


def corpus_images() -> list[Path]:
    images = []
    for kind in ("public", "private"):
        images += sorted(
            p for p in (FIXTURES / kind).iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png")
        )
    return images


def test_same_faces_as_original_engine(tmp_path):
    # The original read files with cv2.imread, which ignores colour profiles;
    # Blurry converts to sRGB (R3). Both engines get the same decoded pixels,
    # as lossless PNG, so the comparison is about detection only.
    from PIL import Image

    from blurry_opsec import image_io

    images = corpus_images()
    decoded = []
    for p in images:
        out = tmp_path / (p.stem + ".png")
        Image.fromarray(image_io.load(p).rgb).save(out)
        decoded.append(out)
    raw = subprocess.run(
        [PY, str(Path(__file__).with_name("baseline_dump.py")), SCRIPT, str(MODEL_PATH), "medium"]
        + [str(p) for p in decoded],
        check=True,
        capture_output=True,
        text=True,
        timeout=600,
    ).stdout
    original = json.loads(raw.strip().splitlines()[-1])
    detector = FaceDetector("medium")
    problems = []
    for path in images:
        theirs = [Box(*b) for b in original[path.stem + ".png"]]
        ours, _ = detect_file(path, detector)
        if len(ours) != len(theirs):
            problems.append(f"{path.name}: {len(ours)} faces vs {len(theirs)} in the original")
            continue
        for t in theirs:
            best = max((t.iou(o) for o in ours), default=0.0)
            if best < 0.9:
                problems.append(f"{path.name}: box {t} best IoU {best:.2f}")
    assert not problems, "\n".join(problems)
