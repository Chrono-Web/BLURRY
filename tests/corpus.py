"""Recall measurement on annotated fixtures (shared by tests and local tools)."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from blurry_opsec import image_io, redact
from blurry_opsec.detect import FaceDetector
from blurry_opsec.plan import Box

FIXTURES = Path(__file__).parent / "fixtures"
MATCH_IOU = 0.4  # hand boxes are looser than YuNet's tight boxes
COVERED_FRACTION = 0.9


def annotations(kind: str = "public") -> dict[str, list[Box]]:
    path = FIXTURES / kind / "annotations.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {
        name: [Box(*b) for b in boxes]
        for name, boxes in raw.items()
        if not name.startswith("_") and (FIXTURES / kind / name).exists()
    }


def detect_file(path: Path, detector: FaceDetector) -> tuple[list[Box], tuple[int, int]]:
    loaded = image_io.load(path)
    h, w = loaded.rgb.shape[:2]
    return detector.detect(cv2.cvtColor(loaded.rgb, cv2.COLOR_RGB2BGR)), (w, h)


def covered(gt: Box, boxes: list[Box], padding: float, size: tuple[int, int]) -> bool:
    w, h = size
    mask = np.zeros((h, w), dtype=bool)
    for b in boxes:
        x0, y0, x1, y1 = redact.padded_rect(b, padding, w, h)
        mask[y0:y1, x0:x1] = True
    region = mask[gt.y : gt.y + gt.h, gt.x : gt.x + gt.w]
    return region.size > 0 and region.mean() >= COVERED_FRACTION


def measure(level: str, padding: float, kind: str = "public") -> dict:
    detector = FaceDetector(level)
    total = found = cov = 0
    per_file = {}
    for name, gts in annotations(kind).items():
        boxes, size = detect_file(FIXTURES / kind / name, detector)
        f = sum(1 for g in gts if any(g.iou(b) >= MATCH_IOU for b in boxes))
        c = sum(1 for g in gts if covered(g, boxes, padding, size))
        per_file[name] = {"faces": len(gts), "found": f, "covered": c, "detections": len(boxes)}
        total, found, cov = total + len(gts), found + f, cov + c
    return {
        "faces": total,
        "recall": found / total if total else 0.0,
        "coverage": cov / total if total else 0.0,
        "files": per_file,
    }
