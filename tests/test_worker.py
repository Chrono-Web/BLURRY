"""The app's worker process: JSON over pipes, plans edited by the user, cancel."""

import json
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
    def __init__(self):
        self.p = subprocess.Popen(
            [sys.executable, "-m", "blurry_opsec", "__worker"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
        )  # fmt: skip
        assert json.loads(self.p.stdout.readline())["event"] == "ready"
        self.n = 0

    def send(self, msg):
        self.p.stdin.write(json.dumps(msg) + "\n")
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
