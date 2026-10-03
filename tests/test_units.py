"""Plan, tracking, coverage and model integrity."""

import numpy as np
import pytest

from blurry_opsec import model, redact, tracking
from blurry_opsec.plan import NEAR_THRESHOLD, SMALL_FACE, TRACK_GAP, Box, VideoPlan


def test_model_hash_is_enforced(tmp_path):
    good = model.load_verified()
    assert len(good) == 232589
    bad = tmp_path / model.MODEL_FILENAME
    bad.write_bytes(good[:-1] + b"\x00")
    with pytest.raises(model.ModelIntegrityError):
        model.load_verified(bad)
    with pytest.raises(model.ModelIntegrityError):
        model.load_verified(tmp_path / "missing.onnx")


def test_padding_is_25_percent_of_long_side_per_side():
    assert redact.padded_rect(Box(100, 100, 40, 80), 0.25, 1000, 1000) == (80, 80, 160, 200)
    assert redact.padded_rect(Box(0, 0, 40, 80), 0.25, 50, 50) == (0, 0, 50, 50)


def test_solid_and_pixel_modes():
    img = np.random.default_rng(0).integers(0, 255, (100, 100, 3), dtype=np.uint8)
    solid = redact.apply(img.copy(), [Box(10, 10, 40, 40)], "solid", 0.0, 4)
    assert (solid[10:50, 10:50] == 0).all()
    assert (solid[60:, 60:] == img[60:, 60:]).all()
    pix = redact.apply(img.copy(), [Box(10, 10, 40, 40)], "pixel", 0.0, 4)
    region = pix[10:50, 10:50]
    assert len(np.unique(region.reshape(-1, 3), axis=0)) <= 16  # 4x4 blocks


def test_alpha_becomes_opaque_under_cover():
    img = np.zeros((20, 20, 3), np.uint8)
    alpha = np.zeros((20, 20), np.uint8)
    redact.apply(img, [Box(5, 5, 5, 5)], "solid", 0.0, 4, alpha)
    assert (alpha[5:10, 5:10] == 255).all() and alpha[0, 0] == 0


def test_tracks_bridge_gaps_and_extend_half_a_second():
    fps = 10
    dets = [[] for _ in range(40)]
    for f in list(range(10, 15)) + list(range(20, 25)):  # gap of 5 frames
        dets[f] = [Box(100 + f, 100, 50, 50, score=0.9)]
    tracks = tracking.build_tracks(dets, max_gap=fps)
    assert len(tracks) == 1
    plan = VideoPlan(640, 480, 40, fps, extend_frames=5, tracks=tracks)
    covered = [f for f in range(40) if plan.boxes_for(f)]
    assert covered == list(range(5, 30))
    gap_box = plan.boxes_for(17)[0]
    assert gap_box.x <= 114 and gap_box.x + gap_box.w >= 120 + 50  # frames 14 and 20
    flags = tracking.track_flags(tracks, confidence=0.5)
    assert any(f.kind == TRACK_GAP and f.frame == 20 for f in flags)


def test_far_apart_detections_are_separate_tracks():
    dets = [[Box(0, 0, 30, 30, score=0.9)], [Box(500, 300, 30, 30, score=0.9)]]
    assert len(tracking.build_tracks(dets, max_gap=5)) == 2


def test_review_flags():
    dets = [[Box(0, 0, 20, 20, score=0.55)]]
    flags = {f.kind for f in tracking.track_flags(tracking.build_tracks(dets, 5), 0.5)}
    assert flags == {NEAR_THRESHOLD, SMALL_FACE}


def test_disabled_track_and_manual_range():
    dets = [[Box(0, 0, 50, 50, score=0.9)] for _ in range(10)]
    plan = VideoPlan(640, 480, 10, 10.0, 2, tracks=tracking.build_tracks(dets, 5))
    assert plan.boxes_for(3)
    plan.set_track_enabled(0, False)
    assert not plan.boxes_for(3)
    plan.add_manual(2, 4, Box(10, 10, 10, 10))
    assert [f for f in range(10) if plan.boxes_for(f)] == [2, 3, 4]
    assert plan.boxes_for(3)[0].source == "manual"
