import hashlib

import pytest

from blurry_opsec import __version__
from blurry_opsec.__main__ import main
from blurry_opsec.model import MODEL_PATH, MODEL_SHA256


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"blurry {__version__}"


def test_bundled_model_hash():
    assert hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest() == MODEL_SHA256


def test_engine_dependencies_import_together():
    # cv2 and av each bundle their own FFmpeg; on macOS this only prints an
    # objc duplicate-class warning (checked in phase 0), it must not crash.
    import av
    import cv2

    assert hasattr(cv2, "FaceDetectorYN")
    assert "libx264" in av.codecs_available


def test_version_matches_pyproject():
    import tomllib
    from pathlib import Path

    meta = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    assert meta["project"]["version"] == __version__
