"""Worker process for the desktop app.

The app starts the same executable with the hidden `__worker` argument and
talks to it over pipes, one JSON object per line. Plans and pixels travel only
through the pipes; nothing is written to disk except the outputs the user
exports.

Requests (app -> worker):
  {"id": 1, "cmd": "analyze", "path": "...", "settings": {"level": "high", "faces": true}}
  {"id": 2, "cmd": "frame", "path": "...", "index": 120, "max_side": 1600}
  {"id": 3, "cmd": "render", "path": "...", "plan": {...}, "settings": {...}, "out_dir": null}
  {"cmd": "cancel"}   cancels the request being processed
  {"cmd": "quit"}

Events (worker -> app), all carrying the request id:
  progress {stage, done, total} | result {...} | error {message} | cancelled
"""

from __future__ import annotations

import base64
import json
import os
import queue
import sys
import threading
from pathlib import Path

import cv2
import numpy as np

from blurry_opsec import engine, image_io, levels, video_io
from blurry_opsec.detect import FaceDetector
from blurry_opsec.files import InputError
from blurry_opsec.model import load_verified
from blurry_opsec.plan import ImagePlan, VideoPlan, plan_from_dict, plan_to_dict

PREVIEW_MAX_SIDE = 2400


class Cancelled(Exception):
    pass


def encode_preview(bgr: np.ndarray, max_side: int) -> tuple[str, float]:
    """JPEG in memory, downscaled for display. Returns (base64, scale)."""
    h, w = bgr.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale < 1.0:
        bgr = cv2.resize(bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise RuntimeError("could not encode preview")
    return base64.b64encode(buf.tobytes()).decode("ascii"), scale


def settings_from(d: dict) -> engine.Settings:
    s = engine.Settings(
        level=d.get("level", levels.DEFAULT_LEVEL),
        mode=d.get("mode", levels.DEFAULT_MODE),
        padding=float(d.get("padding", levels.DEFAULT_PADDING)),
        keep_audio=bool(d.get("keep_audio", False)),
        faces=bool(d.get("faces", True)),
        watermark=d.get("watermark") or None,
    )
    s.validate()
    return s


class Worker:
    def __init__(self, out) -> None:
        self.out = out
        self.cancel = threading.Event()
        self.requests: queue.Queue = queue.Queue()
        self.model = load_verified()
        self.detectors: dict[str, FaceDetector] = {}
        self.pts: dict[str, list] = {}  # video path -> frame timestamps, in memory only

    # -- I/O -------------------------------------------------------------------
    def send(self, msg: dict) -> None:
        self.out.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.out.flush()

    def read_stdin(self) -> None:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("cmd") == "cancel":
                self.cancel.set()
            elif msg.get("cmd") == "quit":
                break
            else:
                self.requests.put(msg)
        self.cancel.set()
        self.requests.put(None)

    def progress(self, rid):
        def report(stage: str, done: int, total: int) -> None:
            if self.cancel.is_set():
                raise Cancelled
            self.send(
                {"id": rid, "event": "progress", "stage": stage, "done": done, "total": total}
            )

        return report

    def detector(self, level: str) -> FaceDetector:
        if level not in self.detectors:
            self.detectors[level] = FaceDetector(level, self.model)
        return self.detectors[level]

    # -- Commands ----------------------------------------------------------------
    def analyze(self, rid, msg) -> dict:
        path = Path(msg["path"])
        settings = settings_from(msg.get("settings", {}))
        det = self.detector(settings.level) if settings.faces else None
        kind = engine.kind_of(path)
        if kind == "image":
            job = engine.analyze_image(path, settings, det)
            preview, scale = encode_preview(
                cv2.cvtColor(job.loaded.rgb, cv2.COLOR_RGB2BGR),
                msg.get("max_side", PREVIEW_MAX_SIDE),
            )
            return {
                "kind": "image",
                "plan": plan_to_dict(job.plan),
                "metadata_found": job.loaded.metadata_found,
                "preview": preview,
                "scale": scale,
            }
        job = engine.analyze_video(path, settings, det, self.progress(rid))
        self.pts[str(path)] = job.pts
        return {
            "kind": "video",
            "plan": plan_to_dict(job.plan),
            "metadata_found": job.info.metadata_found,
            "has_audio": job.info.has_audio,
        }

    def frame(self, rid, msg) -> dict:
        path = Path(msg["path"])
        index = int(msg["index"])
        bgr = video_io.read_frame(path, index, self.pts.get(str(path)))
        preview, scale = encode_preview(bgr, int(msg.get("max_side", 1600)))
        return {"index": index, "preview": preview, "scale": scale}

    def render(self, rid, msg) -> dict:
        path = Path(msg["path"])
        settings = settings_from(msg.get("settings", {}))
        plan = plan_from_dict(msg["plan"])
        out_dir = Path(msg["out_dir"]) if msg.get("out_dir") else None
        if isinstance(plan, ImagePlan):
            loaded = image_io.load(path)
            if (loaded.rgb.shape[1], loaded.rgb.shape[0]) != (plan.width, plan.height):
                raise InputError("the file changed since it was analysed")
            result = engine.render_image(engine.ImageJob(path, loaded, plan), settings, out_dir)
        elif isinstance(plan, VideoPlan):
            info = video_io.probe(path)
            job = engine.VideoJob(path, info, plan, self.pts.get(str(path), []))
            result = engine.render_video(job, settings, out_dir, self.progress(rid))
        else:
            raise ValueError("unknown plan type")
        return {
            "output": str(result.output),
            "output_name": result.output.name,
            "metadata_removed": result.metadata_removed,
            "audio": result.audio,
        }

    def run(self) -> int:
        threading.Thread(target=self.read_stdin, daemon=True).start()
        self.send({"event": "ready"})
        handlers = {"analyze": self.analyze, "frame": self.frame, "render": self.render}
        while True:
            msg = self.requests.get()
            if msg is None:
                return 0
            rid = msg.get("id")
            self.cancel.clear()
            handler = handlers.get(msg.get("cmd"))
            if handler is None:
                self.send({"id": rid, "event": "error", "message": "unknown command"})
                continue
            try:
                result = handler(rid, msg)
            except Cancelled:
                self.send({"id": rid, "event": "cancelled"})
            except (InputError, ValueError, OSError) as exc:
                self.send({"id": rid, "event": "error", "message": str(exc)})
            except Exception as exc:  # decoder errors and the like
                self.send({"id": rid, "event": "error", "message": type(exc).__name__})
            else:
                self.send({"id": rid, "event": "result", **result})


def main() -> int:
    # The protocol owns the original stdout. Anything a library prints (Python
    # or native code writing to fd 1) goes to stderr instead.
    out = os.fdopen(os.dup(1), "w", encoding="utf-8")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    return Worker(out).run()
