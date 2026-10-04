"""Blurry's animated face: the mosaic math, the animator and the Qt view."""

import os

import pytest

from blurry_opsec.gui import mascot_face as face


def grid(values):
    return dict(zip(face.cells(), values, strict=True))


def eye_cells(g, threshold=0.75):
    return {cell for cell, v in g.items() if v > threshold}


def test_shape_is_the_icon_mosaic():
    assert len(face.cells()) == 61
    assert not face.inside(0, 0) and not face.inside(8, 8)
    assert face.inside(4, 0) and face.inside(0, 4)


def test_greys_stay_in_range_and_are_deterministic():
    for pose in (face.Pose(), face.Pose(smile=1), face.Pose(open=0), face.Pose(0.45, -0.3)):
        v = face.values(pose)
        assert len(v) == 61
        assert all(0 <= x <= 1 for x in v)
        assert v == face.values(pose)


# Shared with macos/Tests/MascotFaceTests.swift: both sides must draw the same face.
GOLDEN = {
    "rest": (face.Pose(), {(2, 3): 0.799, (4, 3): 0.347, (6, 4): 0.767, (4, 0): 0.358}),
    "smile": (face.Pose(smile=1), {(2, 2): 0.808, (1, 3): 0.903, (3, 3): 0.877, (2, 4): 0.356}),
    "blink": (face.Pose(open=0), {(2, 3): 0.497, (6, 4): 0.436}),
    "right": (face.Pose(gaze_x=0.4), {(4, 3): 1.0, (7, 3): 1.0, (2, 3): 0.346}),
}


@pytest.mark.parametrize("name", GOLDEN)
def test_golden_values(name):
    pose, expected = GOLDEN[name]
    g = grid(face.values(pose))
    for cell, v in expected.items():
        assert g[cell] == pytest.approx(v, abs=0.002), (name, cell, g[cell])


def test_eyes_open_blink_and_greet():
    rest = grid(face.values(face.Pose()))
    eyes = eye_cells(rest)
    assert eyes == {(c, r) for c in (2, 3, 5, 6) for r in (3, 4)}
    shut = grid(face.values(face.Pose(open=0)))
    assert not eye_cells(shut)
    # Greeting: each eye is an arc (^): its middle reaches one row higher than its ends.
    smile = grid(face.values(face.Pose(smile=1)))
    for middle in (2, 6):
        assert smile[(middle, 2)] > 0.75
        for end in (middle - 1, middle + 1):
            assert smile[(end, 3)] > 0.75
            assert smile[(end, 2)] < smile[(middle, 2)] - 0.1


def test_gaze_moves_the_eyes():
    right = eye_cells(grid(face.values(face.Pose(gaze_x=0.4))))
    left = eye_cells(grid(face.values(face.Pose(gaze_x=-0.4))))
    assert sum(c for c, _ in right) / len(right) > 4.5 > sum(c for c, _ in left) / len(left)


def test_blink_timing():
    assert face.eye_open(0, False) == 1
    assert face.eye_open(face.BLINK / 2, False) == pytest.approx(0)
    assert face.eye_open(face.BLINK, False) == 1
    assert face.eye_open(face.DOUBLE_BLINK_GAP + face.BLINK / 2, True) == pytest.approx(0)
    assert face.eye_open(face.DOUBLE_BLINK_GAP + face.BLINK / 2, False) == 1


def test_animator_sleeps_when_still():
    a = face.Animator()
    _, moving = a.frame(0.0)
    assert not moving
    a.blink(1.0)
    assert a.frame(1.05)[1]
    t = 1.05
    while a.frame(t)[1]:
        t += 1 / 30
        assert t < 3
    # A pointer that barely moves does not wake it.
    a.look(t, (0.2, 0.0))
    until = a.active_until
    a.look(t + 0.1, (0.205, 0.0))
    assert a.active_until == until


def test_animator_greets_and_looks_at_viewer():
    a = face.Animator()
    a.look(0.0, (0.4, 0.0))
    a.set_smiling(0.0, True)
    t = 0.0
    for _ in range(40):
        t += 1 / 30
        a.frame(t)
    pose = a.pose(t)
    assert pose.smile == pytest.approx(1)
    assert abs(pose.gaze_x) < 0.01
    a.reduce_motion = True
    assert a.pose(t + 1) == face.Pose(smile=1)


def test_guide_shows_the_mascot(tmp_path, monkeypatch):
    pytest.importorskip("PySide6.QtWidgets")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("BLURRY_PREFS_INI", str(tmp_path / "prefs.ini"))
    from PySide6.QtWidgets import QApplication

    from blurry_opsec.gui.main_window import MainWindow
    from blurry_opsec.gui.mascot import Mascot
    from blurry_opsec.gui.prefs import Prefs

    qa = QApplication.instance() or QApplication([])
    window = MainWindow(Prefs())
    try:
        window.show_guide(first=True)
        qa.processEvents()
        m = window.guide_dialog.findChild(Mascot)
        assert m is not None and m.isVisible()
        assert m.anim.smiling and m.frame.isActive()
        image = m.grab().toImage()
        assert image.width() == 72
        window.guide_dialog.reject()
        qa.processEvents()
        assert not m.frame.isActive() and not m.pointer.isActive() and not m.blinker.isActive()
    finally:
        window.close()
