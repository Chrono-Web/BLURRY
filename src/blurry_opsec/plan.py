"""Coverage plan: what will be covered, produced by analyze and applied by render.

A plan lives in memory only. It is never written to disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Box:
    """A rectangle in display-oriented image coordinates (before padding)."""

    x: int
    y: int
    w: int
    h: int
    score: float | None = None
    source: str = "auto"  # "auto" (detector) or "manual" (user)

    @property
    def long_side(self) -> int:
        return max(self.w, self.h)

    def iou(self, other: Box) -> float:
        ix = max(0, min(self.x + self.w, other.x + other.w) - max(self.x, other.x))
        iy = max(0, min(self.y + self.h, other.y + other.h) - max(self.y, other.y))
        inter = ix * iy
        union = self.w * self.h + other.w * other.h - inter
        return inter / union if union > 0 else 0.0

    def union(self, other: Box) -> Box:
        x0, y0 = min(self.x, other.x), min(self.y, other.y)
        x1 = max(self.x + self.w, other.x + other.w)
        y1 = max(self.y + self.h, other.y + other.h)
        return Box(x0, y0, x1 - x0, y1 - y0, None, self.source)

    def to_dict(self) -> dict:
        d = {"x": self.x, "y": self.y, "w": self.w, "h": self.h, "source": self.source}
        if self.score is not None:
            d["score"] = round(self.score, 3)
        return d


# Review flag kinds.
NO_FACES = "no_faces"
NEAR_THRESHOLD = "near_threshold"
SMALL_FACE = "small_face"
TRACK_GAP = "track_gap"


@dataclass(frozen=True)
class Flag:
    kind: str
    frame: int | None = None
    track: int | None = None
    box: int | None = None

    def to_dict(self) -> dict:
        d: dict = {"kind": self.kind}
        for key in ("frame", "track", "box"):
            value = getattr(self, key)
            if value is not None:
                d[key] = value
        return d


@dataclass
class ImagePlan:
    width: int
    height: int
    boxes: list[Box] = field(default_factory=list)
    flags: list[Flag] = field(default_factory=list)
    faces_expected: bool = True

    def add_box(self, box: Box) -> None:
        self.boxes.append(Box(box.x, box.y, box.w, box.h, None, "manual"))

    def remove_box(self, index: int) -> None:
        del self.boxes[index]


@dataclass
class Track:
    id: int
    detections: dict[int, Box] = field(default_factory=dict)
    enabled: bool = True

    @property
    def first(self) -> int:
        return min(self.detections)

    @property
    def last(self) -> int:
        return max(self.detections)

    @property
    def last_box(self) -> Box:
        return self.detections[self.last]


@dataclass(frozen=True)
class ManualRange:
    start: int  # first frame, inclusive
    end: int  # last frame, inclusive
    box: Box


@dataclass
class VideoPlan:
    width: int
    height: int
    frame_count: int
    fps: float
    extend_frames: int
    tracks: list[Track] = field(default_factory=list)
    flags: list[Flag] = field(default_factory=list)
    manual: list[ManualRange] = field(default_factory=list)
    faces_expected: bool = True
    max_simultaneous: int = 0
    _coverage: dict[int, list[Box]] | None = field(default=None, repr=False)

    def boxes_for(self, frame: int) -> list[Box]:
        if self._coverage is None:
            self._coverage = self._build_coverage()
        return self._coverage.get(frame, [])

    def set_track_enabled(self, track_id: int, enabled: bool) -> None:
        for track in self.tracks:
            if track.id == track_id:
                track.enabled = enabled
                self._coverage = None
                return
        raise KeyError(track_id)

    def add_manual(self, start: int, end: int, box: Box) -> None:
        start, end = max(0, start), min(self.frame_count - 1, end)
        if end < start:
            raise ValueError("empty frame range")
        self.manual.append(ManualRange(start, end, Box(box.x, box.y, box.w, box.h, None, "manual")))
        self._coverage = None

    def update_manual(self, index: int, start: int, end: int, box: Box) -> None:
        start, end = max(0, start), min(self.frame_count - 1, end)
        if end < start:
            start, end = end, start
        self.manual[index] = ManualRange(
            start, end, Box(box.x, box.y, box.w, box.h, None, "manual")
        )
        self._coverage = None

    def remove_manual(self, index: int) -> None:
        del self.manual[index]
        self._coverage = None

    def _build_coverage(self) -> dict[int, list[Box]]:
        from blurry_opsec.tracking import track_coverage

        cov: dict[int, list[Box]] = {}
        for track in self.tracks:
            if not track.enabled:
                continue
            for frame, box in track_coverage(track, self.extend_frames, self.frame_count).items():
                cov.setdefault(frame, []).append(box)
        for rng in self.manual:
            for frame in range(rng.start, rng.end + 1):
                cov.setdefault(frame, []).append(rng.box)
        return cov


# --- Serialization -----------------------------------------------------------
# Plans travel between the app and its worker process as JSON over pipes. They
# are never written to disk.


def box_from_dict(d: dict) -> Box:
    return Box(int(d["x"]), int(d["y"]), int(d["w"]), int(d["h"]), d.get("score"),
               d.get("source", "auto"))  # fmt: skip


def flag_from_dict(d: dict) -> Flag:
    return Flag(d["kind"], d.get("frame"), d.get("track"), d.get("box"))


def image_plan_to_dict(p: ImagePlan) -> dict:
    return {
        "type": "image",
        "width": p.width,
        "height": p.height,
        "boxes": [b.to_dict() for b in p.boxes],
        "flags": [f.to_dict() for f in p.flags],
        "faces_expected": p.faces_expected,
    }


def image_plan_from_dict(d: dict) -> ImagePlan:
    return ImagePlan(
        d["width"],
        d["height"],
        [box_from_dict(b) for b in d["boxes"]],
        [flag_from_dict(f) for f in d.get("flags", [])],
        d.get("faces_expected", True),
    )


def video_plan_to_dict(p: VideoPlan) -> dict:
    return {
        "type": "video",
        "width": p.width,
        "height": p.height,
        "frame_count": p.frame_count,
        "fps": p.fps,
        "extend_frames": p.extend_frames,
        "tracks": [
            {
                "id": t.id,
                "enabled": t.enabled,
                "detections": [[f, b.to_dict()] for f, b in sorted(t.detections.items())],
            }
            for t in p.tracks
        ],
        "flags": [f.to_dict() for f in p.flags],
        "manual": [{"start": m.start, "end": m.end, "box": m.box.to_dict()} for m in p.manual],
        "faces_expected": p.faces_expected,
        "max_simultaneous": p.max_simultaneous,
    }


def video_plan_from_dict(d: dict) -> VideoPlan:
    return VideoPlan(
        width=d["width"],
        height=d["height"],
        frame_count=d["frame_count"],
        fps=d["fps"],
        extend_frames=d["extend_frames"],
        tracks=[
            Track(
                t["id"],
                {int(f): box_from_dict(b) for f, b in t["detections"]},
                t.get("enabled", True),
            )
            for t in d["tracks"]
        ],
        flags=[flag_from_dict(f) for f in d.get("flags", [])],
        manual=[
            ManualRange(m["start"], m["end"], box_from_dict(m["box"])) for m in d.get("manual", [])
        ],
        faces_expected=d.get("faces_expected", True),
        max_simultaneous=d.get("max_simultaneous", 0),
    )


def plan_to_dict(p: ImagePlan | VideoPlan) -> dict:
    return image_plan_to_dict(p) if isinstance(p, ImagePlan) else video_plan_to_dict(p)


def plan_from_dict(d: dict) -> ImagePlan | VideoPlan:
    return image_plan_from_dict(d) if d["type"] == "image" else video_plan_from_dict(d)
