"""Bundled YuNet face detection model (MIT, Shiqi Yu, OpenCV Zoo).

The SHA-256 is pinned here and checked on every start. There is no fallback
detector: if the model is missing or altered, Blurry refuses to run.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

MODEL_FILENAME = "face_detection_yunet_2023mar.onnx"
MODEL_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
MODEL_PATH = Path(__file__).with_name(MODEL_FILENAME)


class ModelIntegrityError(RuntimeError):
    pass


def load_verified(path: Path = MODEL_PATH) -> bytes:
    """Return the model bytes, or raise if missing or not the expected file.

    The detector is built from these exact bytes, so the file cannot be swapped
    between the check and its use.
    """
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ModelIntegrityError(
            "the face detection model is missing; reinstall Blurry"
        ) from exc
    digest = hashlib.sha256(data).hexdigest()
    if digest != MODEL_SHA256:
        raise ModelIntegrityError(
            "the face detection model does not match the expected SHA-256; "
            "reinstall Blurry from a verified download"
        )
    return data
