"""Videos: R3 metadata and rotation, R4 coverage in time, audio, timestamps."""

import json

import av
import numpy as np
import pytest
from conftest import need, run_blurry
from media import exiftool, ffprobe, frames_from, inject_metadata, write_hlg_video, write_video

from blurry_opsec.detect import FaceDetector

TECHNICAL = {"major_brand", "minor_version", "compatible_brands"}


@pytest.fixture(scope="module")
def phone_video(tmp_path_factory):
    """Vertical-style recording: frames stored sideways with a 90° display
    matrix, plus location, device, dates, chapters, subtitles, data tracks."""
    need("ffmpeg")
    work = tmp_path_factory.mktemp("video")
    upright = frames_from("challenger_51l_crew.jpg", 640, 480, 30)
    write_video(work / "plain.mp4", [np.ascontiguousarray(np.rot90(f, -1)) for f in upright])
    inject_metadata(work / "plain.mp4", work / "phone.mov", rotation=90)
    return work / "phone.mov", upright


def report(res):
    return json.loads(res.stdout.strip().splitlines()[-1])


def decode(path):
    with av.open(str(path)) as c:
        return [f.to_ndarray(format="rgb24") for f in c.decode(video=0)]


def test_input_really_is_poisoned(phone_video):
    need("ffprobe")
    info = ffprobe(phone_video[0])
    assert "location" in info["format"]["tags"] and info["chapters"]
    assert {s["codec_type"] for s in info["streams"]} >= {"video", "audio", "subtitle", "data"}


def test_video_metadata_removed(phone_video, outdir):
    need("ffprobe")
    need("exiftool")
    res = run_blurry(phone_video[0], "-o", outdir, "--json")
    assert res.returncode == 0, res.stderr
    rep = report(res)
    assert {"location", "chapters", "subtitle_track", "data_track", "device", "rotation",
            "audio"} <= set(rep["metadata_removed"])  # fmt: skip
    out = outdir / rep["output"]
    info = ffprobe(out)
    assert set(info["format"].get("tags", {})) <= TECHNICAL
    assert not info["chapters"]
    assert [s["codec_type"] for s in info["streams"]] == ["video"]
    v = info["streams"][0]
    assert v["codec_name"] == "h264" and v["pix_fmt"] == "yuv420p"
    assert (v["width"], v["height"]) == (640, 480)  # upright, no display matrix
    assert not v.get("side_data_list")
    tags = exiftool(out)
    bad = [k for k in tags if any(w in k.lower() for w in ("gps", "location", "make", "model"))]
    assert not bad, bad


def test_faces_covered_in_every_frame(phone_video, outdir):
    src, upright = phone_video
    rep = report(run_blurry(src, "-o", outdir, "--json"))
    assert rep["faces"] >= 7 and rep["frames"] == 30
    out = decode(outdir / rep["output"])
    assert len(out) == 30
    detector = FaceDetector("high")
    for i in (0, 10, 20, 29):
        before = detector.detect(np.ascontiguousarray(upright[i][..., ::-1]))
        after = detector.detect(np.ascontiguousarray(out[i][..., ::-1]))
        assert len(before) >= 7
        assert not any(a.iou(b) > 0.3 for a in after for b in before), f"frame {i}"


def test_keep_audio_and_timestamps(phone_video, outdir):
    need("ffprobe")
    res = run_blurry(phone_video[0], "-o", outdir, "--keep-audio", "--json")
    rep = report(res)
    assert rep["audio"] == "kept"
    info = ffprobe(outdir / rep["output"])
    streams = {s["codec_type"]: s for s in info["streams"]}
    assert set(streams) == {"video", "audio"} and streams["audio"]["codec_name"] == "aac"
    v, a = float(streams["video"]["duration"]), float(streams["audio"]["duration"])
    assert abs(v - 2.0) < 0.15 and abs(a - v) < 0.15


def test_pixel_mode_and_progress_lines(phone_video, outdir):
    res = run_blurry(phone_video[0], "-o", outdir, "--mode", "pixel", "--level", "medium")
    assert res.returncode == 0
    progress = [json.loads(line.split(" ", 1)[1]) for line in res.stderr.splitlines()
                if line.startswith("__PROGRESS__ ")]  # fmt: skip
    assert {p["stage"] for p in progress} == {"analyzing", "rendering", "completed"}
    assert progress[-1]["percent"] == 100


def test_odd_size_avi_and_mkv(tmp_path, outdir):
    frames = frames_from("sts125_crew.jpg", 321, 241, 8)
    for ext, codec, pix in ((".avi", "mpeg4", "yuv420p"), (".mkv", "libx264", "yuv444p")):
        src = tmp_path / f"clip{ext}"
        with av.open(str(src), "w") as c:
            s = c.add_stream(codec, rate=8)
            s.width, s.height, s.pix_fmt = 321, 241, pix
            for f in frames:
                for p in s.encode(av.VideoFrame.from_ndarray(f, format="rgb24")):
                    c.mux(p)
            for p in s.encode():
                c.mux(p)
        res = run_blurry(src, "-o", outdir, "--json")
        assert res.returncode == 0, res.stderr
        assert report(res)["frames"] == 8


def test_hlg_video_as_apple_shows_it(tmp_path):
    """HDR as phones record it (HEVC 10 bit, HLG, BT.2020) comes out in SDR as
    Apple's own conversion shows it. Field tests of the iOS app, 2026-10-08:
    read as plain 8-bit video it was washed out; with HLG 75 % as white
    (BT.2408) real iPhone videos were blown out."""
    from blurry_opsec import video_io

    # A grey ramp of HLG values, and what AVFoundation makes of it in BT.709
    # (measured on macOS 26 with AVAssetReader, 2026-10-08).
    apple = {0.25: 55, 0.5: 98, 0.75: 155, 0.94: 226}
    ramp = np.tile(np.linspace(0, 1, 1024)[None, :, None], (64, 1, 3))
    path = tmp_path / "ramp.mp4"
    write_hlg_video(path, [ramp], signal=True)
    grey = next(video_io.iter_frames(path))[32]
    for v, expected in apple.items():
        assert abs(int(grey[round(v * 1023)].mean()) - expected) <= 5, v

    # Colour survives: each patch keeps its purity ((max - min) / max), which
    # the plain reading loses (a green turns olive).
    def purity(px):
        px = px.astype(float)
        return (px.max() - px.min()) / px.max()

    colours = [(200, 30, 30), (30, 160, 40), (40, 60, 200), (220, 180, 40)]
    frame = np.concatenate([np.full((128, 128, 3), c, np.uint8) for c in colours], axis=1)
    path = tmp_path / "patches.mp4"
    write_hlg_video(path, [frame] * 3)
    got = next(video_io.iter_frames(path))[..., ::-1]
    with av.open(str(path)) as c:
        plain = next(c.decode(video=0)).to_ndarray(format="rgb24")
    for k, colour in enumerate(colours):
        x = k * 128 + 64
        assert purity(got[64, x]) >= 0.85 * purity(np.array(colour)), colour
        assert purity(got[64, x]) > purity(plain[64, x]), colour
