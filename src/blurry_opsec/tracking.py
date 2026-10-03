"""Link per-frame detections into tracks and extend coverage in time.

Every detected box is held half a second before and after it was seen, and a
gap inside a track is covered by the union of the boxes on either side. A
detector that blinks for a few frames must not leave a face uncovered.
"""

from __future__ import annotations

from blurry_opsec import levels
from blurry_opsec.plan import NEAR_THRESHOLD, SMALL_FACE, TRACK_GAP, Box, Flag, Track

MATCH_IOU = 0.2
# A gap of this many missing frames (or more) inside a track is flagged for review.
GAP_FLAG_FRAMES = 3


def build_tracks(detections: list[list[Box]], max_gap: int) -> list[Track]:
    """Greedy IoU matching against the last box of each recently seen track."""
    tracks: list[Track] = []
    for frame, boxes in enumerate(detections):
        active = [t for t in tracks if frame - t.last <= max_gap + 1]
        pairs = sorted(
            (
                (box.iou(t.last_box), bi, ti)
                for bi, box in enumerate(boxes)
                for ti, t in enumerate(active)
            ),
            reverse=True,
        )
        used_boxes: set[int] = set()
        used_tracks: set[int] = set()
        for iou, bi, ti in pairs:
            if iou < MATCH_IOU:
                break
            if bi in used_boxes or ti in used_tracks:
                continue
            active[ti].detections[frame] = boxes[bi]
            used_boxes.add(bi)
            used_tracks.add(ti)
        for bi, box in enumerate(boxes):
            if bi not in used_boxes:
                tracks.append(Track(id=len(tracks), detections={frame: box}))
    return tracks


def track_coverage(track: Track, extend: int, frame_count: int) -> dict[int, Box]:
    frames = sorted(track.detections)
    cov: dict[int, Box] = {}

    def put(frame: int, box: Box) -> None:
        if 0 <= frame < frame_count:
            cov[frame] = cov[frame].union(box) if frame in cov else box

    for a, b in zip(frames, frames[1:], strict=False):
        box_a, box_b = track.detections[a], track.detections[b]
        bridge = box_a.union(box_b)
        put(a, box_a)
        for f in range(a + 1, b):
            put(f, bridge)
    put(frames[-1], track.detections[frames[-1]])
    # Hold every detection for `extend` frames before and after.
    for f in frames:
        box = track.detections[f]
        for g in range(f - extend, f + extend + 1):
            put(g, box)
    return cov


def track_flags(tracks: list[Track], confidence: float) -> list[Flag]:
    flags: list[Flag] = []
    for track in tracks:
        frames = sorted(track.detections)
        for a, b in zip(frames, frames[1:], strict=False):
            if b - a - 1 >= GAP_FLAG_FRAMES:
                flags.append(Flag(TRACK_GAP, frame=b, track=track.id))
        scores = [d.score for d in track.detections.values() if d.score is not None]
        if scores and max(scores) < confidence + levels.NEAR_THRESHOLD_MARGIN:
            flags.append(Flag(NEAR_THRESHOLD, frame=track.first, track=track.id))
        sides = sorted(d.long_side for d in track.detections.values())
        if sides[len(sides) // 2] < levels.SMALL_FACE_PX:
            flags.append(Flag(SMALL_FACE, frame=track.first, track=track.id))
    return flags


def max_simultaneous(detections: list[list[Box]]) -> int:
    return max((len(b) for b in detections), default=0)
