"""Compatibility contract for headless process integrations (including the GUI extra)."""

import hashlib
import json
import os
import subprocess
import sys

import numpy as np
import pytest
from conftest import PUBLIC
from media import write_video
from PIL import Image


def invoke(*args):
    env = {**os.environ, "QT_QPA_PLATFORM": "deliberately-invalid", "DISPLAY": ""}
    return subprocess.run(
        [sys.executable, "-m", "blurry_opsec", *map(str, args)],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )


def reports(result):
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    assert all(isinstance(row, dict) for row in rows)
    return rows


def progress(result):
    events = [
        json.loads(line.removeprefix("__PROGRESS__ "))
        for line in result.stderr.splitlines()
        if line.startswith("__PROGRESS__ ")
    ]
    for event in events:
        assert set(event) == {"stage", "percent", "framesProcessed", "totalFrames"}
        assert isinstance(event["stage"], str)
        assert all(type(event[k]) is int for k in ("percent", "framesProcessed", "totalFrames"))
        assert 0 <= event["percent"] <= 100
        assert 0 <= event["framesProcessed"] <= event["totalFrames"]
    return events


def test_success_json_no_gui_with_arguments(tmp_path):
    source = PUBLIC / "dental_squadron.jpg"
    before = hashlib.sha256(source.read_bytes()).digest()
    result = invoke(source, "-o", tmp_path, "--json", "--strict")
    assert result.returncode == 0, result.stderr
    (row,) = reports(result)
    assert set(row) == {
        "input",
        "level",
        "mode",
        "padding",
        "kind",
        "faces",
        "flags",
        "status",
        "output",
        "metadata_removed",
        "audio",
    }
    assert row["input"] == source.name and row["output"] == "dental_squadron.blurry.jpg"
    assert row["level"] == "high" and row["mode"] == "solid" and row["padding"] == 0.25
    assert row["status"] == "ok" and row["kind"] == "image" and row["faces"] == 1
    assert isinstance(row["metadata_removed"], list)
    assert hashlib.sha256(source.read_bytes()).digest() == before
    assert progress(result)[-1] == {
        "stage": "completed",
        "percent": 100,
        "framesProcessed": 1,
        "totalFrames": 1,
    }


def test_strict_error_batch_precedence_and_order(tmp_path):
    blank = tmp_path / "blank.png"
    Image.new("RGB", (100, 100)).save(blank)
    missing = tmp_path / "missing.jpg"
    for inputs in ((blank, missing), (missing, blank)):
        result = invoke(*inputs, "--json", "--strict")
        assert result.returncode == 2  # existing contract: strict no-face dominates errors
        rows = reports(result)
        assert [row["input"] for row in rows] == [p.name for p in inputs]
        assert {row["status"] for row in rows} == {"no_faces", "error"}
        assert not progress(result)
    assert not (tmp_path / "blank.blurry.png").exists()
    result = invoke(missing, "--json")
    assert result.returncode == 1 and reports(result)[0]["status"] == "error"


def test_video_progress_and_report(tmp_path):
    video = tmp_path / "clip.mp4"
    write_video(video, [np.full((96, 128, 3), 120, dtype=np.uint8)] * 3, fps=3)
    result = invoke(video, "--json", "--no-faces")
    assert result.returncode == 0, result.stderr
    (row,) = reports(result)
    assert row["kind"] == "video" and row["frames"] == 3 and row["max_simultaneous"] == 0
    assert row["status"] == "ok" and row["output"] == "clip.blurry.mp4"
    assert row["audio"] == "removed"
    events = progress(result)
    assert events[-1]["stage"] == "completed" and events[-1]["percent"] == 100
    assert any(event["totalFrames"] == 3 for event in events)


@pytest.mark.parametrize(
    "args,code", [(["--help"], 0), (["--version"], 0), (["--unknown-option"], 2)]
)
def test_terminal_control_arguments_do_not_open_gui(args, code):
    result = invoke(*args)
    assert result.returncode == code
    assert "qt.qpa" not in result.stderr


def test_gui_script_with_arguments_is_also_headless():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from blurry_opsec.__main__ import gui_main; gui_main(['--version'])",
        ],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "QT_QPA_PLATFORM": "deliberately-invalid"},
    )
    assert result.returncode == 0
    assert result.stdout.startswith("blurry ") and "qt.qpa" not in result.stderr


def test_json_reports_are_utf8_with_legacy_windows_encoding(tmp_path):
    source = tmp_path / "foto è 日本.png"
    Image.new("RGB", (100, 100)).save(source)
    result = subprocess.run(
        [sys.executable, "-m", "blurry_opsec", "--json", "--no-faces", str(source)],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
    )
    assert result.returncode == 0, result.stderr
    assert reports(result)[0]["output"] == "foto è 日本.blurry.png"
