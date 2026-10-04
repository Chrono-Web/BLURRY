"""The app's worker process: JSON over pipes, plans edited by the user, cancel."""

import json
import os
import subprocess
import sys
import threading
import time

import numpy as np
import pytest
from conftest import PUBLIC
from media import frames_from, write_video
from PIL import Image

from blurry_opsec.plan import Box, plan_from_dict, plan_to_dict


class Worker:
    def __init__(self, env=None):
        self.p = subprocess.Popen(
            [sys.executable, "-m", "blurry_opsec", "__worker"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8",
            bufsize=1, env=env,
        )  # fmt: skip
        assert json.loads(self.p.stdout.readline())["event"] == "ready"
        self.n = 0

    def send(self, msg):
        self.p.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.p.stdin.flush()

    def call(self, cmd, on_progress=None, **payload):
        self.n += 1
        self.send({"id": self.n, "cmd": cmd, **payload})
        while True:
            msg = json.loads(self.p.stdout.readline())
            assert msg["id"] == self.n
            if msg["event"] == "progress":
                if on_progress:
                    on_progress(msg)
                continue
            return msg

    def close(self):
        self.send({"cmd": "quit"})
        self.p.stdin.close()
        assert self.p.wait(timeout=20) == 0


@pytest.fixture
def worker():
    w = Worker()
    yield w
    w.close()


def test_image_roundtrip_with_manual_box(worker, tmp_path):
    res = worker.call("analyze", path=str(PUBLIC / "dental_squadron.jpg"), settings={})
    assert res["event"] == "result" and res["kind"] == "image" and res["preview"]
    plan = plan_from_dict(res["plan"])
    assert len(plan.boxes) == 1
    plan.add_box(Box(100, 900, 200, 200))  # the user covers something else too
    res = worker.call(
        "render",
        path=str(PUBLIC / "dental_squadron.jpg"),
        plan=plan_to_dict(plan),
        settings={"mode": "solid", "padding": 0.0},
        out_dir=str(tmp_path),
    )
    assert res["event"] == "result", res
    out = np.array(Image.open(tmp_path / res["output_name"]))
    assert out[920:1080, 120:280].max() < 10
    assert "exif" in res["metadata_removed"]


def test_errors_are_reported_without_paths(worker, tmp_path):
    missing = tmp_path / "secret-name.jpg"
    res = worker.call("analyze", path=str(missing), settings={})
    assert res["event"] == "error" and "secret-name" not in res["message"]


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    d = tmp_path_factory.mktemp("clip")
    path = d / "clip.mp4"
    write_video(path, frames_from("challenger_51l_crew.jpg", 640, 480, 90), fps=30)
    return path


def test_video_frames_and_disabled_track(worker, clip, tmp_path):
    res = worker.call("analyze", path=str(clip), settings={"level": "high"})
    plan = plan_from_dict(res["plan"])
    assert plan.frame_count == 90 and len(plan.tracks) >= 7
    frame = worker.call("frame", path=str(clip), index=60, max_side=320)
    assert frame["event"] == "result" and frame["index"] == 60 and frame["scale"] == 0.5
    plan.set_track_enabled(plan.tracks[0].id, False)
    plan.add_manual(10, 20, Box(0, 0, 50, 50))
    res = worker.call("render", path=str(clip), plan=plan_to_dict(plan), settings={},
                      out_dir=str(tmp_path))  # fmt: skip
    assert res["event"] == "result" and res["output_name"] == "clip.blurry.mp4"


def test_cancel_removes_partial_output(worker, tmp_path):
    long_clip = tmp_path / "long.mp4"
    write_video(long_clip, frames_from("sts125_crew.jpg", 1280, 720, 240), fps=30, audio=False)
    out = tmp_path / "out"
    out.mkdir()
    plan = worker.call("analyze", path=str(long_clip), settings={})["plan"]
    seen = threading.Event()

    def on_progress(msg):
        if msg["done"] > 5 and not seen.is_set():
            seen.set()
            worker.send({"cmd": "cancel"})

    res = worker.call("render", on_progress, path=str(long_clip), plan=plan, settings={},
                      out_dir=str(out))  # fmt: skip
    assert res["event"] == "cancelled"
    time.sleep(0.2)
    assert not list(out.iterdir())


def _decode(b64):
    import base64
    import io

    return np.array(Image.open(io.BytesIO(base64.b64decode(b64))))


def test_preview_covers_like_the_export_and_outlines(worker):
    src = str(PUBLIC / "dental_squadron.jpg")
    res = worker.call("analyze", path=src, settings={})
    assert res["out_ext"] == "jpg"
    plan = res["plan"]
    box = plan["boxes"][0]
    settings = {"mode": "solid", "padding": 0.0}
    res = worker.call("preview", path=src, plan=plan, settings=settings, max_side=800)
    assert res["event"] == "result" and res["faces"] == 1 and res["index"] is None
    img = _decode(res["preview"])
    s = 800 / max(plan["width"], plan["height"])
    cx, cy = int((box["x"] + box["w"] / 2) * s), int((box["y"] + box["h"] / 2) * s)
    assert max(img.shape[:2]) == 800 and img[cy - 3 : cy + 3, cx - 3 : cx + 3].max() < 20
    res = worker.call("preview", path=src, plan=plan, settings=settings, max_side=800,
                      outline=True)  # fmt: skip
    assert _decode(res["preview"])[cy, cx].max() > 20  # outlined, not covered


def test_preview_and_play_video(worker, clip):
    res = worker.call("analyze", path=str(clip), settings={})
    plan = res["plan"]
    res = worker.call("preview", path=str(clip), plan=plan, settings={}, max_side=320)
    assert res["event"] == "result" and res["faces"] >= 7 and 0 <= res["index"] < 90
    worker.n += 1
    worker.send({"id": worker.n, "cmd": "play", "path": str(clip), "plan": plan,
                 "settings": {}, "start": 80, "max_side": 160})  # fmt: skip
    t0, frames = time.monotonic(), []
    while True:
        msg = json.loads(worker.p.stdout.readline())
        if msg["event"] != "frame":
            break
        frames.append(msg["index"])
    assert msg["event"] == "result" and frames == list(range(80, 90))
    assert time.monotonic() - t0 >= 9 / 30 * 0.8  # paced to the video's fps


def test_play_can_be_cancelled(worker, clip):
    plan = worker.call("analyze", path=str(clip), settings={})["plan"]
    worker.n += 1
    worker.send({"id": worker.n, "cmd": "play", "path": str(clip), "plan": plan, "settings": {}})
    assert json.loads(worker.p.stdout.readline())["event"] == "frame"
    worker.send({"cmd": "cancel"})
    while (msg := json.loads(worker.p.stdout.readline()))["event"] == "frame":
        pass
    assert msg["event"] == "cancelled"


def test_render_to_a_chosen_path_replaces_only_there(worker, tmp_path):
    src = PUBLIC / "dental_squadron.jpg"
    plan = worker.call("analyze", path=str(src), settings={})["plan"]
    target = tmp_path / "scelto_blurry.jpg"
    target.write_bytes(b"old")  # the save dialog asked before replacing it
    res = worker.call("render", path=str(src), plan=plan, settings={}, output=str(target))
    assert res["event"] == "result" and res["output_name"] == "scelto_blurry.jpg"
    assert target.read_bytes()[:2] == b"\xff\xd8"
    res = worker.call("render", path=str(src), plan=plan, settings={}, output=str(src))
    assert res["event"] == "error" and "overwrite the input" in res["message"]


def test_one_analysis_gives_every_level_exactly(worker, clip):
    """Detecting once at the most sensitive level and filtering by score gives
    the same plan as analysing at each level (levels.MOST_SENSITIVE)."""
    sources = [PUBLIC / n for n in ("challenger_51l_crew.jpg", "cabinet_room_1968.jpg",
                                    "marines_crop.jpg", "air_force_ball.jpg")] + [clip]  # fmt: skip
    for src in sources:
        both = worker.call("analyze", path=str(src), settings={}, all_levels=True)
        assert set(both["plans"]) == {"base", "medium", "high"}
        for level in ("base", "medium", "high"):
            alone = worker.call("analyze", path=str(src), settings={"level": level})
            assert both["plans"][level] == alone["plan"], (src.name, level)


def test_frame_probe_tells_if_a_video_has_audio(worker, tmp_path):
    silent = tmp_path / "silent.mp4"
    write_video(silent, frames_from("sts125_crew.jpg", 320, 240, 10), audio=False)
    for path, audio in ((silent, False), (None, True)):
        if path is None:
            path = tmp_path / "loud.mp4"
            write_video(path, frames_from("sts125_crew.jpg", 320, 240, 10), audio=True)
        res = worker.call("frame", path=str(path), index=0, max_side=160, probe=True)
        assert res["event"] == "result" and res["has_audio"] is audio


def test_edit_preview_lists_boxes_with_owners(worker, clip):
    src = str(PUBLIC / "dental_squadron.jpg")
    plan = worker.call("analyze", path=src, settings={})["plan"]
    plan["boxes"].append({"x": 10, "y": 10, "w": 40, "h": 40, "source": "manual"})
    res = worker.call("preview", path=src, plan=plan, settings={"mode": "solid"}, edit=True)
    boxes = res["boxes"]
    assert [b["index"] for b in boxes] == [0, 1] and boxes[1]["source"] == "manual"
    img = _decode(res["preview"])
    s = img.shape[1] / plan["width"]
    assert img[int(30 * s), int(30 * s)].max() > 20  # not covered in edit mode

    vplan = plan_from_dict(worker.call("analyze", path=str(clip), settings={})["plan"])
    off = vplan.tracks[0].id
    vplan.set_track_enabled(off, False)
    vplan.add_manual(5, 15, Box(0, 0, 50, 50))
    res = worker.call("preview", path=str(clip), plan=plan_to_dict(vplan), settings={}, index=10,
                      edit=True)  # fmt: skip
    tracks = {b["track"]: b["enabled"] for b in res["boxes"] if "track" in b}
    assert tracks[off] is False and sum(tracks.values()) == len(tracks) - 1
    manual = [b for b in res["boxes"] if "manual" in b]
    assert manual == [{"x": 0, "y": 0, "w": 50, "h": 50, "source": "manual", "manual": 0,
                       "enabled": True, "uncertain": False, "start": 5, "end": 15}]  # fmt: skip
    res = worker.call("preview", path=str(clip), plan=plan_to_dict(vplan), settings={}, index=40,
                      edit=True)  # fmt: skip
    assert not [b for b in res["boxes"] if "manual" in b]


def test_utf8_wire_protocol_with_legacy_windows_encoding(tmp_path):
    source = tmp_path / "foto è 日本.jpg"
    source.write_bytes((PUBLIC / "dental_squadron.jpg").read_bytes())
    w = Worker(env={**os.environ, "PYTHONIOENCODING": "cp1252"})
    try:
        result = w.call("analyze", path=str(source), settings={})
        assert result["event"] == "result" and result["kind"] == "image"
        result = w.call(
            "render", path=str(source), plan=result["plan"], settings={}, out_dir=str(tmp_path)
        )
        assert result["event"] == "result"
        assert result["output_name"] == "foto è 日本.blurry.jpg"
    finally:
        w.close()
