"""The app's state: the files of this session, the guide, the engine.

Port of macos/Sources/Blurry/Store.swift, so that the two apps behave the
same. Everything lives in memory; only the four allowed settings and the
guide flag reach the preferences (prefs.py).
"""

from __future__ import annotations

import base64
import itertools
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, QRectF, Signal
from PySide6.QtGui import QImage

from blurry_opsec import image_io, levels, video_io
from blurry_opsec.gui import edits as E
from blurry_opsec.gui import strings as L
from blurry_opsec.gui.edits import EditBox, Edits
from blurry_opsec.gui.prefs import Prefs
from blurry_opsec.gui.worker_client import WorkerClient

# Item states
WAITING = "waiting"
ANALYZING = "analyzing"
READY = "ready"
REVIEW = "review"
NO_FACES = "no_faces"
EXPORTING = "exporting"
EXPORTED = "exported"
ERROR = "error"
CANCELLED = "cancelled"

ANALYSED = (READY, REVIEW, NO_FACES, EXPORTED)

# The guide's steps, one at a time.
STEPS = ("sensitivity", "cover", "margin", "audio", "result")

_ids = itertools.count(1)


def decode(b64: str) -> QImage:
    return QImage.fromData(base64.b64decode(b64))


@dataclass(eq=False)
class Item:
    """One file. Lives in memory only."""

    path: Path
    kind: str  # "image" or "video"
    id: int = field(default_factory=lambda: next(_ids))
    status: str = WAITING
    progress: int = 0
    plans: dict = field(default_factory=dict)  # one per level, from a single analysis
    plan: dict | None = None  # the one for the chosen level, corrected
    edits: Edits = field(default_factory=Edits)  # corrections by hand
    pts: list | None = None  # video frame timestamps from the analysis, for fast seeking
    out_ext: str = ""  # what the export will be: jpg, png… or mp4
    has_audio: bool | None = None  # video: read before the analysis; None until known
    faces: int | None = None
    thumb: QImage | None = None  # the original: the image, or a video frame
    preview_index: int | None = None  # video: the frame on screen
    error: str = ""
    output: Path | None = None

    def __post_init__(self) -> None:
        if not self.out_ext:
            self.out_ext = "mp4" if self.kind == "video" else self.path.suffix.lower().lstrip(".")

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def analysed(self) -> bool:
        return self.status in ANALYSED

    @property
    def busy(self) -> bool:
        return self.status in (ANALYZING, EXPORTING)

    @property
    def frame_count(self) -> int:
        return int((self.plan or {}).get("frame_count", 0))

    @property
    def fps(self) -> float:
        return float((self.plan or {}).get("fps", 30) or 30)

    @property
    def covered_ranges(self) -> list[tuple[int, int]]:
        """Video: the stretches of time where something is covered, for the timeline."""
        if not self.plan:
            return []
        ranges = []
        for track in self.plan.get("tracks", []):
            if track.get("enabled", True):
                frames = [f for f, _ in track.get("detections", [])]
                if frames:
                    ranges.append((min(frames), max(frames)))
        for m in self.plan.get("manual", []):
            if m["start"] <= m["end"]:
                ranges.append((m["start"], m["end"]))
        out: list[tuple[int, int]] = []
        for lo, hi in sorted(ranges):
            if out and lo <= out[-1][1] + 1:
                out[-1] = (out[-1][0], max(out[-1][1], hi))
            else:
                out.append((lo, hi))
        return out


class Store(QObject):
    changed = Signal()  # anything the views show
    picture = Signal()  # only the picture and the playhead (video playback)

    def __init__(self, prefs: Prefs, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.prefs = prefs
        self.items: list[Item] = []
        self.notice: str | None = None

        # The guide: which file, which step, what the floating picture shows.
        self.current_id: int | None = None
        self.step = "sensitivity"
        self.preview: QImage | None = None
        # The picture on screen is not yet the one for the current step and
        # settings (a preview is on its way): the view dims it.
        self.preview_stale = False
        self.playing = False
        # The file opened straight on the result, with the previous file's settings.
        self.using_previous = False

        # Correcting boxes by hand: the picture uncovered, the boxes on it, the one selected.
        self.editing = False
        self.edit_boxes: list[EditBox] = []
        self.selection: str | None = None
        self._edit_snapshot: Edits | None = None

        self.jobs = WorkerClient(self)  # analysis and export
        self.view = WorkerClient(self)  # previews and playback
        self.jobs.crashed.connect(self._jobs_crashed)
        self.view.crashed.connect(self._view_crashed)

        # Settings. Level, mode and padding are kept between sessions (R2 allows
        # exactly these); audio is off at every start.
        self.level = prefs.level
        self.mode = prefs.mode
        self.padding = prefs.padding
        self.keep_audio = False

        # First-run guide: a few tips during the first file, ending on the queue.
        seen = prefs.onboarded
        self.onboarded = seen
        self.show_welcome = not seen
        self.guiding = not seen
        self.tip_stage = 0  # 0 steps, 1 correct, 2 waiting for the first export, then queue

        self._skipped: set[int] = set()
        self._confirmed_once = False  # a file has been exported this session
        self._play_token = 0
        self._preview_in_flight = False
        self._preview_again = False
        self._export_queue: list[tuple[int, Path]] = []

    # -- settings ---------------------------------------------------------------
    def set_level(self, level: str) -> None:
        if level == self.level or level not in levels.LEVELS:
            return
        self.level = level
        self.prefs.level = level
        self._apply_level()
        self.changed.emit()

    def set_mode(self, mode: str) -> None:
        if mode == self.mode or mode not in levels.MODES:
            return
        self.mode = mode
        self.prefs.mode = mode
        self._settings_changed()
        self.changed.emit()

    def set_padding(self, padding: float) -> None:
        if abs(padding - self.padding) < 1e-9 or not 0.0 <= padding <= 1.0:
            return
        self.padding = padding
        self.prefs.padding = padding
        self._settings_changed()
        self.changed.emit()

    def set_keep_audio(self, keep: bool) -> None:
        if keep == self.keep_audio:
            return
        self.keep_audio = keep
        self._settings_changed()
        self.changed.emit()

    def restore_defaults(self) -> None:
        self.set_level(levels.DEFAULT_LEVEL)
        self.set_mode(levels.DEFAULT_MODE)
        self.set_padding(levels.DEFAULT_PADDING)
        self.set_keep_audio(False)

    def _settings(self) -> dict:
        return {
            "level": self.level,
            "mode": self.mode,
            "padding": self.padding,
            "keep_audio": self.keep_audio,
            "faces": True,
        }

    # -- first-run guide ----------------------------------------------------------
    @property
    def tip(self) -> str | None:
        """The tip to show now, if any: "steps", "correct" or "queue"."""
        item = self.current
        if not self.guiding or self.show_welcome or item is None or self.editing:
            return None
        if item.status == EXPORTED:
            return "queue"
        if self.tip_stage == 0:
            return "steps"
        if self.tip_stage == 1:
            return "correct" if item.analysed else None
        return None

    def next_tip(self) -> None:
        self.tip_stage += 1
        self.changed.emit()

    def _set_onboarded(self, value: bool) -> None:
        self.onboarded = value
        self.prefs.onboarded = value

    def begin_guided_session(self) -> None:
        """The introduction is complete; contextual tips continue for this session."""
        self._set_onboarded(True)
        self.show_welcome = False
        self.changed.emit()

    def finish_onboarding(self) -> None:
        self.show_welcome = False
        self.guiding = False
        self._set_onboarded(True)
        self.tip_stage = 0
        self.changed.emit()

    def restart_onboarding(self) -> None:
        """Help ▸ Show the Guide Again."""
        self._set_onboarded(False)
        self.show_welcome = True
        self.guiding = True
        self.tip_stage = 0
        self.changed.emit()

    # -- where we are ---------------------------------------------------------------
    @property
    def engine_missing(self) -> bool:
        return self.jobs.unavailable

    @property
    def current(self) -> Item | None:
        return next((it for it in self.items if it.id == self.current_id), None)

    @property
    def steps(self) -> tuple[str, ...]:
        """Fixed from the start: audio is there for every video (and says so when
        the video has none), never for photos."""
        cur = self.current
        return tuple(s for s in STEPS if s != "audio") if cur and cur.kind == "image" else STEPS

    @property
    def busy(self) -> bool:
        return any(it.busy for it in self.items)

    def _todo(self) -> list[Item]:
        """Files still to go through the guide, in order."""
        return [
            it
            for it in self.items
            if it.status not in (EXPORTED, ERROR) and it.id not in self._skipped
        ]

    @property
    def position(self) -> tuple[int, int]:
        open_ = [
            it
            for it in self.items
            if (it.status != EXPORTED and it.id not in self._skipped) or it.id == self.current_id
        ]
        i = next((n for n, it in enumerate(open_) if it.id == self.current_id), 0)
        return i + 1, len(open_)

    @property
    def has_next(self) -> bool:
        return any(it.id != self.current_id for it in self._todo())

    def set_step(self, step: str) -> None:
        if step == self.step:
            return
        self.step = step
        if step != "result":
            self.using_previous = False
        self.stop_playing()
        self.refresh_preview()
        self.changed.emit()

    def move(self, delta: int) -> None:
        steps = self.steps
        if self.step in steps:
            i = steps.index(self.step)
            self.set_step(steps[max(0, min(len(steps) - 1, i + delta))])

    def _set_current(self, item_id: int | None) -> None:
        if item_id == self.current_id:
            return
        self.current_id = item_id
        self._enter_file()

    # -- adding, opening, removing ----------------------------------------------------
    def add(self, paths: list[Path]) -> None:
        expanded: list[Path] = []
        for p in paths:
            if p.is_dir():
                try:
                    expanded += sorted(
                        (c for c in p.iterdir() if c.is_file()), key=lambda c: c.name
                    )
                except OSError:
                    continue
            elif p.is_file():
                expanded.append(p)
        known = {it.path.resolve() for it in self.items}
        skipped = 0
        first: Item | None = None
        for p in expanded:
            if p.resolve() in known or p.name.startswith("."):
                continue
            ext = p.suffix.lower()
            if ext in image_io.IMAGE_EXTENSIONS:
                kind = "image"
            elif ext in video_io.VIDEO_EXTENSIONS:
                kind = "video"
            else:
                skipped += 1
                continue
            item = Item(p, kind)
            self.items.append(item)
            known.add(p.resolve())
            first = first or item
            if kind == "video":
                self._first_frame(item)
        self.notice = L.skipped(skipped) if skipped else None
        if self.current_id is None and first is not None:
            self._set_current(first.id)
        self._pump()
        self.changed.emit()

    def remove(self, ids: set[int]) -> None:
        if any(it.id in ids and it.busy for it in self.items):
            self.jobs.cancel()
        self._export_queue = [(i, p) for i, p in self._export_queue if i not in ids]
        if self.current_id in ids:
            self._set_current(None)
        self.items = [it for it in self.items if it.id not in ids]
        self.changed.emit()

    def next(self) -> None:
        """Next file in the guide, or back to the drop window."""
        nxt = next((it for it in self._todo() if it.id != self.current_id), None)
        self._set_current(nxt.id if nxt else None)
        self.changed.emit()

    def skip(self) -> None:
        """Leave this file for now: it stays in the queue, not exported."""
        if self.current_id is not None:
            self._skipped.add(self.current_id)
        self.next()

    def open(self, item_id: int) -> None:
        self._skipped.discard(item_id)
        self._set_current(item_id)
        self.changed.emit()

    def _enter_file(self) -> None:
        self.stop_playing()
        if self.editing:
            self.editing, self.edit_boxes, self.selection = False, [], None
            self._edit_snapshot = None
        # After a first export, the next files open on the result with the same settings.
        cur = self.current
        fresh = cur is not None and cur.status != EXPORTED
        self.using_previous = self._confirmed_once and fresh
        self.set_step("result" if self.using_previous else "sensitivity")
        self.preview = cur.thumb if cur else None
        self.refresh_preview()
        self._pump()

    def _item(self, item_id: int) -> Item | None:
        return next((it for it in self.items if it.id == item_id), None)

    def _set_notice(self, text: str | None) -> None:
        self.notice = text
        self.changed.emit()

    # -- analysis and export (jobs worker) -------------------------------------------
    def _pump(self) -> None:
        if self.jobs.busy:
            return
        while self._export_queue:
            item_id, path = self._export_queue.pop(0)
            item = self._item(item_id)
            if item is not None and item.plan is not None:
                return self._render(item, path)
        # The file on screen first, then the others in order.
        waiting = [it for it in self.items if it.status == WAITING]
        nxt = next((it for it in waiting if it.id == self.current_id), None) or next(
            iter(waiting), None
        )
        if nxt is not None:
            self._analyze(nxt)

    def _apply_level(self) -> None:
        """A new level is instant: every analysed file already has the plan for it.
        Files already exported keep their status, except the one on screen."""
        for it in self.items:
            if not it.plans or it.status == EXPORTING:
                continue
            if it.status == EXPORTED and it.id != self.current_id:
                continue
            self._rebuild(it)
        self.refresh_preview()

    def _rebuild(self, it: Item) -> None:
        """The plan for the chosen level with the corrections applied, and its status."""
        it.plan = it.edits.apply(it.plans.get(self.level))
        self._settle(it)

    def _settings_changed(self) -> None:
        """Mode, margin or audio changed: refresh, and the file on screen, if it was
        already exported, can be exported again with the new settings."""
        cur = self.current
        if cur is not None and cur.status == EXPORTED:
            self._settle(cur)
        self.refresh_preview()

    def retry(self) -> None:
        """After an error: analyse again, or allow the export again."""
        cur = self.current
        if cur is None:
            return
        cur.error = ""
        if not cur.plans:
            cur.status = WAITING
        else:
            self._settle(cur)
        self.refresh_preview()
        self._pump()
        self.changed.emit()

    def _alive(self, it: Item) -> bool:
        if it in self.items:
            return True
        self._pump()
        return False

    def _progress(self, it: Item) -> Callable[[str, int, int], None]:
        def report(_stage: str, done: int, total: int) -> None:
            if it in self.items:
                it.progress = min(99, done * 100 // total) if total else 0
                self.changed.emit()

        return report

    def _analyze(self, it: Item) -> None:
        it.status, it.progress = ANALYZING, 0
        payload = {
            "path": str(it.path),
            "settings": self._settings(),
            "max_side": 1600,
            "all_levels": True,
        }

        def result(msg: dict) -> None:
            if not self._alive(it):
                return
            it.plans = msg.get("plans") or {}
            if not it.plans and msg.get("plan"):
                it.plans = {self.level: msg["plan"]}
            it.plan = it.edits.apply(it.plans.get(self.level))
            it.pts = msg.get("pts")
            if isinstance(msg.get("has_audio"), bool):
                it.has_audio = msg["has_audio"]
            if msg.get("out_ext"):
                it.out_ext = msg["out_ext"].lstrip(".")
            if msg.get("preview"):
                it.thumb = decode(msg["preview"])
            self._settle(it)
            if it.id == self.current_id:
                self.refresh_preview()
            self._pump()
            self.changed.emit()

        def error(message: str) -> None:
            if self._alive(it):
                self._fail(it, message)
                self._pump()
                self.changed.emit()

        def cancelled() -> None:
            if self._alive(it):
                it.status = CANCELLED
                self._pump()
                self.changed.emit()

        self.jobs.request("analyze", payload, result, self._progress(it), error, cancelled)

    def export(self, output: Path) -> None:
        """Export the current file to a path chosen in the save dialog."""
        if self.current_id is None:
            return
        self._export_queue.append((self.current_id, output))
        self._pump()
        self.changed.emit()

    def cancel_export(self) -> None:
        self._export_queue.clear()
        cur = self.current
        if cur is not None and cur.status == EXPORTING:
            self.jobs.cancel()

    def _render(self, it: Item, output: Path) -> None:
        it.status, it.progress = EXPORTING, 0
        payload = {
            "path": str(it.path),
            "plan": it.plan,
            "settings": self._settings(),
            "output": str(output),
        }

        def result(msg: dict) -> None:
            if not self._alive(it):
                return
            it.status = EXPORTED
            it.output = Path(msg["output"]) if msg.get("output") else None
            self._confirmed_once = True
            self._pump()
            self.changed.emit()

        def error(message: str) -> None:
            if self._alive(it):
                self._fail(it, message)
                self._pump()
                self.changed.emit()

        def cancelled() -> None:
            if self._alive(it):
                self._settle(it)
                self._pump()
                self.changed.emit()

        self.jobs.request("render", payload, result, self._progress(it), error, cancelled)

    def _fail(self, it: Item, message: str) -> None:
        it.status = ERROR
        it.error = L.worker_crashed() if message == "worker" else message

    def _settle(self, it: Item) -> None:
        """Port of Store.settle: the status after analysis or a correction."""
        plan = it.plan or {}
        if plan.get("type") == "image":
            faces = len(plan.get("boxes", []))
        else:
            faces = sum(1 for t in plan.get("tracks", []) if t.get("enabled", True))
            faces += len(plan.get("manual", []))
        it.faces = faces
        flags = [f for f in plan.get("flags", []) if f.get("kind") != "no_faces"]
        if plan.get("faces_expected", True) and faces == 0:
            it.status = NO_FACES
        elif flags and it.edits.empty:
            it.status = REVIEW
        else:
            it.status = READY

    def _jobs_crashed(self) -> None:
        self._set_notice(L.worker_crashed())

    def _view_crashed(self) -> None:
        self._preview_in_flight = False
        self.playing = False
        self.changed.emit()

    # -- the floating picture (view worker) ------------------------------------------
    def _first_frame(self, it: Item) -> None:
        payload = {"path": str(it.path), "index": 0, "max_side": 1600, "probe": True}

        def result(r: dict) -> None:
            if it not in self.items or not r.get("preview"):
                return
            if isinstance(r.get("has_audio"), bool):
                it.has_audio = r["has_audio"]
            it.thumb = decode(r["preview"])
            if it.id == self.current_id and it.plan is None:
                self.preview = it.thumb
            self.changed.emit()

        self.view.request("frame", payload, result)

    def refresh_preview(self) -> None:
        """The picture for the current step: detected faces outlined while choosing
        the sensitivity, then covered exactly as the export will be. Requests are
        coalesced: while one is running, only the latest change is sent next."""
        item = self.current
        if item is None or item.plan is None:
            self.preview = item.thumb if item else None
            # Before the analysis the original is right for the sensitivity step only.
            self.preview_stale = (
                self.step != "sensitivity"
                and item is not None
                and not item.analysed
                and item.status != ERROR
            )
            return
        self.preview_stale = True
        if self._preview_in_flight:
            self._preview_again = True
            return
        self._preview_in_flight = True
        item_id = item.id
        edit = self.editing
        payload = {
            "path": str(item.path),
            "plan": item.plan,
            "settings": self._settings(),
            "max_side": 1600,
            "outline": self.step == "sensitivity" and not edit,
            "edit": edit,
        }
        if item.kind == "video":
            payload["index"] = item.preview_index
            payload["pts"] = item.pts

        def done(r: dict | None) -> None:
            self._preview_in_flight = False
            it = self._item(item_id)
            if r is not None and it is not None and item_id == self.current_id and not self.playing:
                if it.kind == "video" and it.preview_index is None:
                    it.preview_index = r.get("index")
                if r.get("preview"):
                    self.preview = decode(r["preview"])
                if edit and self.editing:
                    self.edit_boxes = self._parse_boxes(r.get("boxes", []), it)
            if self._preview_again:
                self._preview_again = False
                self.refresh_preview()
            else:
                self.preview_stale = False
            self.changed.emit()

        self.view.request("preview", payload, done, None, lambda _m: done(None), lambda: done(None))

    def play(self) -> None:
        """Video: play the covered result in real time, from where the playhead is
        (from the start if it is at the end). Stopping leaves the picture there."""
        it = self.current
        if it is None or it.kind != "video" or it.plan is None or self.playing:
            return
        last = it.frame_count - 1
        start = it.preview_index or 0
        if start >= last:
            start = 0
        self.playing = True
        self._play_token += 1
        token = self._play_token
        payload = {
            "path": str(it.path),
            "plan": it.plan,
            "settings": self._settings(),
            "start": start,
            "max_side": 1280,
            "pts": it.pts,
        }

        def frame(index: int, b64: str) -> None:
            if token != self._play_token or not self.playing or it not in self.items:
                return
            it.preview_index = index
            self.preview_stale = False
            self.preview = decode(b64)
            self.picture.emit()

        def end(*_args) -> None:
            if token == self._play_token:
                self.playing = False
                self.changed.emit()

        self.view.request("play", payload, end, None, end, end, frame)
        self.changed.emit()

    def stop_playing(self) -> None:
        if not self.playing:
            return
        self.playing = False
        self._play_token += 1
        self.view.cancel()
        self.changed.emit()

    def seek(self, frame: int) -> None:
        """Video: move the playhead and show that frame, covered."""
        it = self.current
        if it is None:
            return
        self.stop_playing()
        it.preview_index = max(0, min(frame, max(0, it.frame_count - 1)))
        self.refresh_preview()
        self.picture.emit()

    # -- correcting boxes by hand ----------------------------------------------------
    def start_editing(self) -> None:
        it = self.current
        if it is None or it.plan is None or it.busy:
            return
        self.stop_playing()
        self._edit_snapshot = it.edits.copy()
        self.selection = None
        self.edit_boxes = []
        self.editing = True
        self.refresh_preview()
        self.changed.emit()

    def end_editing(self, keep: bool) -> None:
        """Done keeps the corrections; Cancel puts back the ones from before."""
        it = self.current
        if not keep and self._edit_snapshot is not None and it is not None:
            it.edits = self._edit_snapshot
            self._rebuild(it)
        self._edit_snapshot = None
        self.editing = False
        self.selection = None
        self.edit_boxes = []
        self.refresh_preview()
        self.changed.emit()

    @property
    def selected_box(self) -> EditBox | None:
        return next((b for b in self.edit_boxes if b.id == self.selection), None)

    def select(self, box_id: str | None) -> None:
        self.selection = box_id
        self.changed.emit()

    def _parse_boxes(self, boxes: list[dict], it: Item) -> list[EditBox]:
        base_manual = len((it.plans.get(self.level) or {}).get("manual", []))
        found = sum(1 for b in boxes if "index" in b and b.get("source") != "manual")
        out = []
        for b in boxes:
            rect = QRectF(b.get("x", 0), b.get("y", 0), b.get("w", 0), b.get("h", 0))
            if "index" in b:
                if b.get("source") == "manual":
                    owner = ("drawn", b["index"] - found)
                else:
                    owner = ("found", E.key(b))
                box_id = f"b{b['index']}"
            elif "track" in b:
                owner, box_id = ("track", b["track"]), f"t{b['track']}"
            elif "manual" in b:
                if b["manual"] < base_manual:
                    continue
                j = b["manual"] - base_manual
                owner, box_id = ("manual", j), f"m{j}"
            else:
                continue
            out.append(
                EditBox(
                    box_id,
                    owner,
                    rect,
                    b.get("enabled", True),
                    b.get("uncertain", False),
                    b.get("start"),
                    b.get("end"),
                )
            )
        return out

    def _edit(self, change: Callable[[Item], None]) -> None:
        it = self.current
        if it is None:
            return
        change(it)
        self._rebuild(it)
        self.refresh_preview()
        self.changed.emit()

    def add_box(self, rect: QRectF) -> None:
        """A box drawn on the picture: on a photo it covers that area; on a video
        it covers it, still, for the whole video (the span can then be narrowed)."""
        it = self.current
        if it is None:
            return
        if it.kind == "image":
            self.selection = f"b{len((it.plan or {}).get('boxes', []))}"
            self.edit_boxes.append(EditBox(self.selection, ("drawn", len(it.edits.added)), rect))
            self._edit(lambda i: i.edits.added.append(E.box(rect)))
        else:
            last = max(0, it.frame_count - 1)
            self.selection = f"m{len(it.edits.manual)}"
            self.edit_boxes.append(
                EditBox(self.selection, ("manual", len(it.edits.manual)), rect, start=0, end=last)
            )
            self._edit(
                lambda i: i.edits.manual.append({"start": 0, "end": last, "box": E.box(rect)})
            )

    def move_box(self, box: EditBox, rect: QRectF) -> None:
        """A box moved or resized. A found box becomes one drawn by hand."""
        for b in self.edit_boxes:
            if b.id == box.id:
                b.rect = rect
        kind, ref = box.owner
        if kind == "found":
            count = len((self.current.plan or {}).get("boxes", [])) if self.current else 1
            self.selection = f"b{count - 1}"  # the found box goes, the drawn one is last

            def change(i: Item) -> None:
                i.edits.removed.add(ref)
                i.edits.added.append(E.box(rect))

            self._edit(change)
        elif kind == "drawn":
            self._edit(lambda i: _set_at(i.edits.added, ref, E.box(rect)))
        elif kind == "manual":
            self._edit(
                lambda i: _set_at(
                    i.edits.manual,
                    ref,
                    {**i.edits.manual[ref], "box": E.box(rect)}
                    if ref < len(i.edits.manual)
                    else None,
                )
            )

    def remove_box(self, box: EditBox) -> None:
        """Delete: a photo box goes away, a manual video box goes away, a track is
        switched off (or on again)."""
        self.selection = None
        kind, ref = box.owner
        if kind == "track":
            self.selection = box.id
            self.toggle_track(ref)
            return
        self.edit_boxes = [b for b in self.edit_boxes if b.id != box.id]
        if kind == "found":
            self._edit(lambda i: i.edits.removed.add(ref))
        elif kind == "drawn":
            self._edit(lambda i: _pop_at(i.edits.added, ref))
        elif kind == "manual":
            self._edit(lambda i: _pop_at(i.edits.manual, ref))

    def toggle_track(self, track_id: int) -> None:
        it = self.current
        base = it.plans.get(self.level) if it else None
        track = next((t for t in (base or {}).get("tracks", []) if t["id"] == track_id), None)
        if track is None:
            return
        keys = {E.detection_key(f, b) for f, b in track["detections"]}

        def change(i: Item) -> None:
            if keys & i.edits.disabled:
                i.edits.disabled -= keys
            else:
                i.edits.disabled |= keys

        self._edit(change)

    def set_range(self, j: int, start: bool) -> None:
        """Video: the selected manual box starts (or ends) at the playhead."""
        it = self.current
        if it is None or it.preview_index is None:
            return
        frame = it.preview_index

        def change(i: Item) -> None:
            if j >= len(i.edits.manual):
                return
            m = i.edits.manual[j]
            lo, hi = m.get("start", 0), m.get("end", frame)
            if start:
                lo = frame
            else:
                hi = frame
            i.edits.manual[j] = {**m, "start": min(lo, hi), "end": max(lo, hi)}

        self._edit(change)

    def shutdown(self) -> None:
        self.jobs.shutdown()
        self.view.shutdown()


def _set_at(items: list, i: int, value) -> None:
    if value is not None and 0 <= i < len(items):
        items[i] = value


def _pop_at(items: list, i: int) -> None:
    if 0 <= i < len(items):
        items.pop(i)
