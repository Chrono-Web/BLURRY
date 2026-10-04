"""Corrections made by hand, kept apart from the analysis so that they survive
a change of sensitivity: every level's plan comes from the same detections, so
a found box or a track is recognised by its coordinates at any level.

Port of macos/Sources/Blurry/Edits.swift. Plans are the dictionaries of the
worker protocol (plan.plan_to_dict).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QRectF


def key(b: dict) -> str:
    return ",".join(str(int(b.get(k, 0))) for k in ("x", "y", "w", "h"))


def detection_key(frame: int, b: dict) -> str:
    return f"{frame}:{key(b)}"


def box(r: QRectF) -> dict:
    return {
        "x": int(r.x()),
        "y": int(r.y()),
        "w": max(1, int(r.width())),
        "h": max(1, int(r.height())),
        "source": "manual",
    }


@dataclass
class Edits:
    removed: set[str] = field(default_factory=set)  # photo: found boxes taken away (by key)
    added: list[dict] = field(default_factory=list)  # photo: boxes drawn by hand
    disabled: set[str] = field(default_factory=set)  # video: detections of switched-off tracks
    manual: list[dict] = field(default_factory=list)  # video: {start, end, box}, still boxes

    @property
    def empty(self) -> bool:
        return not (self.removed or self.added or self.disabled or self.manual)

    def copy(self) -> Edits:
        return Edits(
            set(self.removed),
            [dict(b) for b in self.added],
            set(self.disabled),
            [dict(m) for m in self.manual],
        )

    def apply(self, base: dict | None) -> dict | None:
        """The plan the export uses: the analysis for the chosen level, corrected."""
        if base is None:
            return None
        plan = dict(base)
        if plan.get("type") == "image":
            kept, moved = [], {}
            for i, b in enumerate(plan.get("boxes", [])):
                if key(b) not in self.removed:
                    moved[i] = len(kept)
                    kept.append(b)
            boxes = kept + [dict(b) for b in self.added]
            plan["boxes"] = boxes
            # Flags point at boxes by position: follow them, drop those of removed boxes.
            flags = []
            for flag in plan.get("flags", []):
                if flag.get("kind") == "no_faces":
                    if not boxes:
                        flags.append(flag)
                elif flag.get("box") is None:
                    flags.append(flag)
                elif flag["box"] in moved:
                    flags.append({**flag, "box": moved[flag["box"]]})
            plan["flags"] = flags
        else:
            tracks = []
            for track in plan.get("tracks", []):
                off = any(detection_key(f, b) in self.disabled for f, b in track["detections"])
                tracks.append({**track, "enabled": not off})
            plan["tracks"] = tracks
            plan["manual"] = list(plan.get("manual", [])) + [
                {**m, "box": dict(m["box"])} for m in self.manual
            ]
        return plan


@dataclass
class EditBox:
    """One box as the editor draws it, in the picture's own pixels.

    owner: ("found", key) photo, found by the analysis; ("drawn", i) photo,
    index in Edits.added; ("track", id) video, follows the face; ("manual", i)
    video, index in Edits.manual.
    """

    id: str
    owner: tuple
    rect: QRectF
    enabled: bool = True
    uncertain: bool = False
    start: int | None = None
    end: int | None = None

    @property
    def movable(self) -> bool:
        """A track follows the face, so it can only be switched off."""
        return self.owner[0] != "track"
