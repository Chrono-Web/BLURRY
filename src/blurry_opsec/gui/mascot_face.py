"""Blurry's face: a 9 x 9 mosaic whose cells are recomputed while it moves.

Every cell is the average of a few samples of a small sphere with two eyes, so
gaze, blinks and the greeting show up as cells fading between greys. Pure math,
no Qt: the macOS app ports the same functions (MascotFace.swift) and the tests
on both sides check the same values.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

GRID = 9
SAMPLES = 5

# Sphere and eyes, angles in radians. The axis leans towards the viewer.
TILT = 0.32
EYE_LON = 0.38
EYE_LAT = 0.08 + TILT
HALF_WIDTH = 0.115 * 1.25
HALF_STRAIGHT = 0.19 * 1.25
MIN_OPEN = 0.12  # a closed eye is still a thin slit

# Greeting: eyes shut into wide arcs (^ ^), a little further apart.
SMILE_WIDTH = 2.5
SMILE_SPREAD = 0.14
SMILE_ARCH = 0.042 * 6
SMILE_SLIT = 0.35

GLOW = 0.45
BODY = 0.7  # body greys relative to the app icon's
TURN = 0.3  # how much the shading follows the gaze

# Timing.
BLINK = 0.18
DOUBLE_BLINK_GAP = 0.28
BLINK_EVERY = 4.0
SMILE_DURATION = 0.5
GAZE_RATE = 9.0
FADE_RATE = 31.0
GAZE_WAKE = 0.012


@dataclass(frozen=True)
class Pose:
    gaze_x: float = 0.0  # head turned right (radians)
    gaze_y: float = 0.0  # head turned up (radians)
    open: float = 1.0  # 1 open, 0 shut by a blink
    smile: float = 0.0  # 0 normal eyes, 1 greeting arcs


def inside(col: int, row: int, n: int = GRID) -> bool:
    """Whether a cell belongs to the round face (the corners stay empty)."""
    x = col + 0.5 - n / 2
    y = row + 0.5 - n / 2
    return math.hypot(x, y) <= n / 2 - 0.2


def cells(n: int = GRID) -> list[tuple[int, int]]:
    """The face's cells as (col, row), row by row from the top left."""
    return [(c, r) for r in range(n) for c in range(n) if inside(c, r, n)]


def noise(col: int, row: int) -> float:
    """Fixed per-cell variation in -0.5...0.5, as in the app icon."""
    v = math.sin(col * 129898 + row * 78233) * 43758.5453
    return v - math.floor(v) - 0.5


def _eye_centres(pose: Pose) -> list[tuple[float, float]]:
    out = []
    for side in (-1.0, 1.0):
        vx = math.cos(EYE_LAT) * math.sin(side * EYE_LON)
        vy = math.sin(EYE_LAT)
        vz = math.cos(EYE_LAT) * math.cos(side * EYE_LON)
        x = vx * math.cos(pose.gaze_x) + vz * math.sin(pose.gaze_x)
        z = -vx * math.sin(pose.gaze_x) + vz * math.cos(pose.gaze_x)
        pitch = TILT - pose.gaze_y
        y = vy * math.cos(pitch) - z * math.sin(pitch)
        out.append((x + side * SMILE_SPREAD * pose.smile, y))
    return out


def _body(x: float, y: float, pose: Pose, nz: float) -> float:
    k = TURN * 1.6
    g = min(2.0, max(0.0, ((x - pose.gaze_x * k) - (y - pose.gaze_y * k)) / 2 + 1)) / 2
    return max(0.2, 0.66 - 0.54 * g + nz * 0.08) * BODY


@lru_cache(maxsize=4)
def _grid(n: int, samples: int):
    """Sample points of every cell, and each cell's fixed variation."""
    side = 2 / n
    face = cells(n)
    offs = (np.arange(samples) + 0.5) / samples * side
    xs, ys, cx, cy, nz = [], [], [], [], []
    for col, row in face:
        x0 = -1 + col * side
        y0 = 1 - row * side
        gx, gy = np.meshgrid(x0 + offs, y0 - offs)
        xs.append(gx.ravel())
        ys.append(gy.ravel())
        cx.append(x0 + side / 2)
        cy.append(y0 - side / 2)
        nz.append(noise(col, row))
    return np.array(xs), np.array(ys), np.array(cx), np.array(cy), np.array(nz)


def values(pose: Pose, n: int = GRID, samples: int = SAMPLES) -> list[float]:
    """Grey (0 black ... 1 white) of every cell, in the order of `cells(n)`."""
    s = pose.smile
    opened = pose.open * (1 - s)
    w = HALF_WIDTH * max(1 + (SMILE_WIDTH - 1) * s, 0.5)
    squash = max(opened, MIN_OPEN + (SMILE_SLIT - MIN_OPEN) * s)
    h = (HALF_STRAIGHT + HALF_WIDTH) * squash
    arch = SMILE_ARCH * s
    rc = min(w, h)
    x, y, cx, cy, nz = _grid(n, samples)

    k = TURN * 1.6
    g = np.clip(((cx - pose.gaze_x * k) - (cy - pose.gaze_y * k)) / 2 + 1, 0, 2) / 2
    body = (np.maximum(0.2, 0.66 - 0.54 * g + nz * 0.08) * BODY)[:, None]

    fill = np.zeros_like(x)
    glow = np.zeros_like(x)
    for ex, ey in _eye_centres(pose):
        u = x - ex
        un = np.clip(u / w, -1, 1)
        dl = y - ey - arch * (1 - un * un)
        qx = np.abs(u) - (w - rc)
        qy = np.abs(dl) - (h - rc)
        sd = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - rc
        fill = np.maximum(fill, sd <= 0)
        glow = np.maximum(glow, np.exp(-((np.maximum(sd, 0) / 0.13) ** 2)))
    on_sphere = x * x + y * y < 1
    fill = np.where(on_sphere, fill, 0)
    glow = np.where(on_sphere, glow, 0)
    v = body * (1 - fill) + fill
    v = v + (1 - v) * GLOW * 0.6 * glow * (1 - fill)
    return v.mean(axis=1).tolist()


def eye_open(elapsed: float, double: bool) -> float:
    """How open the eyes are `elapsed` seconds after a blink starts."""

    def one(start: float) -> float:
        d = elapsed - start
        if 0 <= d < BLINK:
            return abs(d - BLINK / 2) / (BLINK / 2)
        return 1.0

    return min(one(0.0), one(DOUBLE_BLINK_GAP) if double else 1.0)


def gaze_goal(
    dx: float, dy: float, falloff: float = 500, reach: float = 0.45
) -> tuple[float, float]:
    """Head turn towards a point `dx`, `dy` pixels away (y grows downwards)."""
    dist = max(math.hypot(dx, dy), 1.0)
    a = min(dist / falloff, 1.0) * reach
    return dx / dist * a, -dy / dist * a * 0.7


class Animator:
    """Blinks, greeting and a damped gaze, driven by the caller's clock.

    It only says what to draw at time `t` and how long drawing must go on
    (`active_until`); the view decides when to repaint, and stops when idle.
    """

    def __init__(self, n: int = GRID):
        self.n = n
        self.blink_start = -1e9
        self.double = False
        self.blinks = 0
        self.smile_from = 0.0
        self.smile_to = 0.0
        self.smile_start = -1e9
        self.smiling = False
        self.gaze = (0.0, 0.0)
        self.goal = (0.0, 0.0)
        self.last_goal: tuple[float, float] | None = None
        self.last_t: float | None = None
        self.shown: list[float] | None = None
        self.active_until = 0.0
        self.reduce_motion = False

    def wake(self, t: float, duration: float) -> None:
        self.active_until = max(self.active_until, t + duration)

    def blink(self, t: float, double: bool = False) -> None:
        if self.reduce_motion:
            return
        self.blink_start = t
        self.double = double
        self.wake(t, 0.5 if double else 0.25)

    def tick_blink(self, t: float) -> None:
        """The regular blink: every third one is double."""
        self.blinks += 1
        self.blink(t, self.blinks % 3 == 0)

    def smile_amount(self, t: float) -> float:
        u = min(1.0, max(0.0, (t - self.smile_start) / SMILE_DURATION))
        return self.smile_from + (self.smile_to - self.smile_from) * u * u * (3 - 2 * u)

    def set_smiling(self, t: float, on: bool) -> None:
        self.smile_from = self.smile_amount(t)
        self.smile_to = 1.0 if on else 0.0
        self.smile_start = t
        self.smiling = on
        self.wake(t, SMILE_DURATION + 0.15)

    def look(self, t: float, goal: tuple[float, float]) -> None:
        """New gaze target; wakes the view only if the change is visible."""
        self.goal = goal
        last = self.last_goal
        if last is not None and math.hypot(goal[0] - last[0], goal[1] - last[1]) < GAZE_WAKE:
            return
        self.last_goal = goal
        self.wake(t, 0.8)

    def pose(self, t: float) -> Pose:
        dt = min(t - (self.last_t if self.last_t is not None else t), 0.1)
        self.last_t = t
        if self.reduce_motion:
            return Pose(smile=1.0 if self.smiling else 0.0)
        smile = self.smile_amount(t)
        goal = (0.0, 0.0) if smile > 0.12 else self.goal
        k = min(1.0, dt * GAZE_RATE)
        gx, gy = self.gaze
        self.gaze = (gx + (goal[0] - gx) * k, gy + (goal[1] - gy) * k)
        return Pose(self.gaze[0], self.gaze[1], eye_open(t - self.blink_start, self.double), smile)

    def frame(self, t: float) -> tuple[list[float], bool]:
        """Greys to draw now, and whether anything is still moving."""
        dt = min(t - (self.last_t if self.last_t is not None else t), 0.1)
        target = values(self.pose(t), self.n)
        if self.shown is None or self.reduce_motion:
            self.shown = target
            return target, t < self.active_until
        a = min(1.0, dt * FADE_RATE)
        settling = False
        shown = []
        for old, new in zip(self.shown, target, strict=True):
            v = old + (new - old) * a
            if abs(new - v) > 0.003:
                settling = True
            else:
                v = new
            shown.append(v)
        self.shown = shown
        return shown, settling or t < self.active_until
