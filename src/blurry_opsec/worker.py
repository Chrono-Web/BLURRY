"""Worker process for the desktop app.

The app starts the same executable with the hidden `__worker` argument and
talks to it over pipes, one JSON object per line. Plans and pixels travel only
through the pipes; nothing is written to disk except the outputs the user
exports.

Requests (app -> worker):
  {"id": 1, "cmd": "analyze", "path": "...", "settings": {"level": "high", "faces": true},
   "all_levels": false}   all_levels: detect once at the most sensitive level and also
                          return "plans", the plan for every level (levels.MOST_SENSITIVE)
  {"id": 2, "cmd": "frame", "path": "...", "index": 120, "max_side": 1600, "probe": false}
                          probe: also "has_audio", read from the container without decoding
  {"id": 3, "cmd": "render", "path": "...", "plan": {...}, "settings": {...}, "out_dir": null,
   "output": null}        output: exact path chosen in a save dialog (replaces an existing file)
  {"id": 4, "cmd": "preview", "path": "...", "plan": {...}, "settings": {...}, "index": null,
   "max_side": 1600, "outline": false}
                          the covered picture as the export will look (outline: detected
                          faces drawn instead of covered). Video: frame `index`, or the
                          frame with the most faces if null. With "edit": true the picture
                          is not covered and "boxes" lists what is there, for the editor.
                          Videos may carry "pts" (from
                          the analysis result) so that seeking is fast in another worker
  {"id": 5, "cmd": "play", "path": "...", "plan": {...}, "settings": {...}, "start": 0,
   "max_side": 640}       covered frames in real time, as "frame" events, until the end
                          or a cancel
  {"cmd": "cancel"}   cancels the request being processed
  {"cmd": "quit"}

Events (worker -> app), all carrying the request id:
  progress {stage, done, total} | frame {index, preview} | result {...} | error {message}
  | cancelled
"""

from __future__ import annotations

import base64
import json
import os
import queue
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from blurry_opsec import engine, image_io, levels, redact, tracking, video_io
from blurry_opsec.detect import FaceDetector
from blurry_opsec.files import InputError
from blurry_opsec.model import load_verified
from blurry_opsec.plan import Box, ImagePlan, VideoPlan, plan_from_dict, plan_to_dict

PREVIEW_MAX_SIDE = 2400
OUTLINE_BGR = (24, 220, 73)  # Chrono green, #49dc18


class Cancelled(Exception):
    pass


def downscale(bgr: np.ndarray, max_side: int) -> tuple[np.ndarray, float]:
    h, w = bgr.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale < 1.0:
        bgr = cv2.resize(bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return bgr, scale


def encode_jpeg(bgr: np.ndarray, quality: int = 90) -> str:
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("could not encode preview")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def encode_preview(bgr: np.ndarray, max_side: int) -> tuple[str, float]:
    """JPEG in memory, downscaled for display. Returns (base64, scale)."""
    small, scale = downscale(bgr, max_side)
    return encode_jpeg(small), scale


def edit_boxes(plan: ImagePlan | VideoPlan, index: int | None) -> list[dict]:
    """What the editor draws: every box on the picture (video: at frame `index`,
    as covered there, including switched-off tracks), with who owns it."""
    if isinstance(plan, ImagePlan):
        uncertain = {f.box for f in plan.flags if f.box is not None}
        return [{**b.to_dict(), "index": i, "enabled": True, "uncertain": i in uncertain}
                for i, b in enumerate(plan.boxes)]  # fmt: skip
    flagged = {f.track for f in plan.flags if f.track is not None}
    out = []
    for t in plan.tracks:
        box = tracking.track_coverage(t, plan.extend_frames, plan.frame_count).get(index)
        if box is not None:
            out.append({**box.to_dict(), "track": t.id, "enabled": t.enabled,
                        "uncertain": t.id in flagged})  # fmt: skip
    for i, m in enumerate(plan.manual):
        if m.start <= index <= m.end:
            out.append({**m.box.to_dict(), "manual": i, "enabled": True, "uncertain": False,
                        "start": m.start, "end": m.end})  # fmt: skip
    return out


def covered(bgr: np.ndarray, boxes: list[Box], settings: engine.Settings, max_side: int,
            outline: bool = False) -> np.ndarray:  # fmt: skip
    """A display copy with the boxes covered as the export will be, or outlined."""
    small, s = downscale(bgr, max_side)
    small = small.copy() if small is bgr else small
    scaled = [Box(int(b.x * s), int(b.y * s), max(1, round(b.w * s)), max(1, round(b.h * s)),
                  b.score, b.source) for b in boxes]  # fmt: skip
    if outline:
        for b in scaled:
            cv2.rectangle(small, (b.x, b.y), (b.x + b.w, b.y + b.h), OUTLINE_BGR, 2)
        return small
    blocks = levels.get(settings.level).blocks
    return redact.apply(small, scaled, settings.mode, settings.padding, blocks)


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
        self.image: tuple[str, np.ndarray] | None = None  # last image previewed (BGR)

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
        all_levels = bool(msg.get("all_levels")) and settings.faces
        det_level = levels.MOST_SENSITIVE if all_levels else settings.level
        det = self.detector(det_level) if settings.faces else None
        kind = engine.kind_of(path)
        if kind == "image":
            job = engine.analyze_image(path, settings, det)
            preview, scale = encode_preview(
                cv2.cvtColor(job.loaded.rgb, cv2.COLOR_RGB2BGR),
                msg.get("max_side", PREVIEW_MAX_SIDE),
            )
            plans = (
                {k: plan_to_dict(engine.image_plan_at(job.plan, lv.confidence))
                 for k, lv in levels.LEVELS.items()}
                if all_levels else {settings.level: plan_to_dict(job.plan)}
            )  # fmt: skip
            return {
                "kind": "image",
                "plan": plans[settings.level],
                "plans": plans,
                "metadata_found": job.loaded.metadata_found,
                "out_ext": job.loaded.out_ext,
                "preview": preview,
                "scale": scale,
            }
        job = engine.analyze_video(path, settings, det, self.progress(rid))
        self.pts[str(path)] = job.pts
        plans = (
            {k: plan_to_dict(engine.video_plan_from(job.detections, job.info, True, lv.confidence))
             for k, lv in levels.LEVELS.items()}
            if all_levels else {settings.level: plan_to_dict(job.plan)}
        )  # fmt: skip
        return {
            "kind": "video",
            "pts": job.pts,
            "plan": plans[settings.level],
            "plans": plans,
            "metadata_found": job.info.metadata_found,
            "has_audio": job.info.has_audio,
        }

    def frame(self, rid, msg) -> dict:
        path = Path(msg["path"])
        index = int(msg["index"])
        bgr = video_io.read_frame(path, index, self.pts.get(str(path)))
        preview, scale = encode_preview(bgr, int(msg.get("max_side", 1600)))
        out = {"index": index, "preview": preview, "scale": scale}
        if msg.get("probe"):
            out["has_audio"] = video_io.probe(path).has_audio
        return out

    def _pts(self, path: Path, msg: dict) -> list | None:
        """Frame timestamps: from this worker's own analysis, or sent by the app
        (which keeps them from the analysis worker), so seeking stays fast."""
        return self.pts.get(str(path)) or msg.get("pts")

    def _image_bgr(self, path: Path) -> np.ndarray:
        if self.image is None or self.image[0] != str(path):
            self.image = (str(path), cv2.cvtColor(image_io.load(path).rgb, cv2.COLOR_RGB2BGR))
        return self.image[1]

    def preview(self, rid, msg) -> dict:
        path = Path(msg["path"])
        settings = settings_from(msg.get("settings", {}))
        plan = plan_from_dict(msg["plan"])
        max_side = int(msg.get("max_side", 1600))
        if isinstance(plan, ImagePlan):
            index, bgr, boxes = None, self._image_bgr(path), plan.boxes
        else:
            index = msg.get("index")
            if index is None:
                index = max(range(plan.frame_count), key=lambda i: len(plan.boxes_for(i)))
            index = int(index)
            bgr = video_io.read_frame(path, index, self._pts(path, msg))
            boxes = plan.boxes_for(index)
        if msg.get("edit"):
            small, _ = downscale(bgr, max_side)
            return {"index": index, "faces": len(boxes), "preview": encode_jpeg(small),
                    "boxes": edit_boxes(plan, index)}  # fmt: skip
        out = covered(bgr, boxes, settings, max_side, bool(msg.get("outline")))
        return {"index": index, "faces": len(boxes), "preview": encode_jpeg(out)}

    def play(self, rid, msg) -> dict:
        path = Path(msg["path"])
        settings = settings_from(msg.get("settings", {}))
        plan = plan_from_dict(msg["plan"])
        if not isinstance(plan, VideoPlan):
            raise ValueError("play is for videos")
        max_side = int(msg.get("max_side", 640))
        start = max(0, min(int(msg.get("start", 0)), plan.frame_count - 1))
        step = 1.0 / plan.fps if plan.fps > 0 else 1.0 / 30
        t0 = time.monotonic()
        last = start
        for n, (index, bgr) in enumerate(video_io.iter_from(path, start, self._pts(path, msg))):
            if self.cancel.is_set():
                raise Cancelled
            if index >= plan.frame_count:
                break
            out = covered(bgr, plan.boxes_for(index), settings, max_side)
            delay = t0 + n * step - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            frame = encode_jpeg(out, 80)
            self.send({"id": rid, "event": "frame", "index": index, "preview": frame})
            last = index
        return {"end": last}

    def render(self, rid, msg) -> dict:
        path = Path(msg["path"])
        settings = settings_from(msg.get("settings", {}))
        plan = plan_from_dict(msg["plan"])
        out_dir = Path(msg["out_dir"]) if msg.get("out_dir") else None
        output = Path(msg["output"]) if msg.get("output") else None
        if isinstance(plan, ImagePlan):
            loaded = image_io.load(path)
            if (loaded.rgb.shape[1], loaded.rgb.shape[0]) != (plan.width, plan.height):
                raise InputError("the file changed since it was analysed")
            job = engine.ImageJob(path, loaded, plan)
            result = engine.render_image(job, settings, out_dir, output)
        elif isinstance(plan, VideoPlan):
            info = video_io.probe(path)
            job = engine.VideoJob(path, info, plan, self.pts.get(str(path), []))
            result = engine.render_video(job, settings, out_dir, self.progress(rid), output)
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
        handlers = {"analyze": self.analyze, "frame": self.frame, "render": self.render,
                    "preview": self.preview, "play": self.play}  # fmt: skip
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
