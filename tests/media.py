"""Generate test videos from public fixtures and inject metadata with ffmpeg.

ffmpeg/ffprobe/exiftool are test tools only; Blurry never calls them.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from corpus import FIXTURES
from PIL import Image

TOOLS = {name: shutil.which(name) for name in ("ffmpeg", "ffprobe", "exiftool")}
LOCATION = "+45.4642+009.1900+120.000/"


def frames_from(image: str, width: int, height: int, count: int) -> list[np.ndarray]:
    """Slow pan over a fixture: same faces, moving a little every frame."""
    im = Image.open(FIXTURES / "public" / image).convert("RGB")
    scale = max(width / im.width, height / im.height) * 1.15
    big = np.asarray(im.resize((int(im.width * scale), int(im.height * scale))))
    max_dx, max_dy = big.shape[1] - width, big.shape[0] - height
    out = []
    for i in range(count):
        t = i / max(1, count - 1)
        x, y = int(max_dx * t * 0.5), int(max_dy * 0.5)
        out.append(np.ascontiguousarray(big[y : y + height, x : x + width]))
    return out


def write_video(path: Path, frames: list[np.ndarray], fps: int = 15, audio: bool = True) -> None:
    """RGB frames -> H.264 MP4 (+ 440 Hz AAC tone)."""
    h, w = frames[0].shape[:2]
    with av.open(str(path), "w") as out:
        vs = out.add_stream("libx264", rate=fps)
        vs.width, vs.height, vs.pix_fmt = w, h, "yuv420p"
        as_ = out.add_stream("aac", rate=44100) if audio else None
        for i, arr in enumerate(frames):
            frame = av.VideoFrame.from_ndarray(arr, format="rgb24")
            frame.pts, frame.time_base = i, Fraction(1, fps)
            for p in vs.encode(frame):
                out.mux(p)
        for p in vs.encode():
            out.mux(p)
        if as_ is not None:
            n = int(44100 * len(frames) / fps)
            t = np.arange(n) / 44100
            tone = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)[None, :]
            for start in range(0, n, 1024):
                af = av.AudioFrame.from_ndarray(
                    tone[:, start : start + 1024], format="flt", layout="mono"
                )
                af.sample_rate, af.pts = 44100, start
                for p in as_.encode(af):
                    out.mux(p)
            for p in as_.encode():
                out.mux(p)


def inject_metadata(src: Path, dst: Path, rotation: int = 0) -> None:
    """Add location, tags, chapters, a subtitle track, a timecode data track
    and cover art; optionally a display rotation."""
    work = dst.parent
    (work / "subs.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nsecret subtitle\n")
    (work / "chapters.txt").write_text(
        ";FFMETADATA1\ntitle=secret title\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=500\n"
        "title=secret chapter\n"
    )
    Image.open(FIXTURES / "public" / "dental_squadron.jpg").convert("RGB").resize((160, 107)).save(
        work / "cover.jpg"
    )
    cmd = [TOOLS["ffmpeg"], "-v", "error", "-y"]
    if rotation:
        cmd += ["-display_rotation", str(rotation)]
    cmd += [
        "-i", str(src), "-i", str(work / "subs.srt"), "-i", str(work / "chapters.txt"),
        "-i", str(work / "cover.jpg"),
        "-map", "0", "-map", "1", "-map", "3", "-map_metadata", "2", "-map_chapters", "2",
        "-c", "copy", "-c:s", "mov_text", "-c:v:1", "mjpeg", "-disposition:v:1", "attached_pic",
        "-timecode", "01:00:00:00",
        "-metadata", f"location={LOCATION}",
        "-metadata", f"com.apple.quicktime.location.ISO6709={LOCATION}",
        "-metadata", "com.apple.quicktime.make=Apple",
        "-metadata", "com.apple.quicktime.model=iPhone 15",
        "-metadata", "creation_time=2026-01-02T03:04:05Z",
        "-metadata:s:v:0", "title=secret track",
        "-movflags", "use_metadata_tags",
        str(dst),
    ]  # fmt: skip
    subprocess.run(cmd, check=True)


def ffprobe(path: Path) -> dict:
    raw = subprocess.run(
        [TOOLS["ffprobe"], "-v", "error", "-show_format", "-show_streams", "-show_chapters",
         "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout  # fmt: skip
    return json.loads(raw)


def exiftool(path: Path) -> dict:
    raw = subprocess.run(
        [TOOLS["exiftool"], "-j", "-a", "-G1", "-ee", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout  # fmt: skip
    return json.loads(raw)[0]


def write_hlg_video(path: Path, frames: list[np.ndarray], fps: int = 15) -> None:
    """RGB (sRGB) frames -> HEVC 10 bit HLG BT.2020, as a phone records HDR:
    sRGB -> linear, BT.709 -> BT.2020 primaries, SDR white at HLG 75 %
    (BT.2408), HLG OETF, BT.2020 matrix, limited range."""
    a = 0.17883277
    b, c = 1 - 4 * a, 0.5 - a * np.log(4 * a)

    def scene(v):
        return np.where(v <= 0.5, v * v / 3, (np.exp((v - c) / a) + b) / 12)

    white = float(scene(np.float64(0.75)))
    m = np.array([[0.6274, 0.3293, 0.0433], [0.0691, 0.9195, 0.0114], [0.0164, 0.0880, 0.8956]])
    h, w = frames[0].shape[:2]
    with av.open(str(path), "w") as out:
        vs = out.add_stream("libx265", rate=fps)
        vs.width, vs.height, vs.pix_fmt = w, h, "yuv420p10le"
        vs.codec_tag = "hvc1"  # as the iPhone writes it; AVFoundation does not read "hev1"
        vs.options = {
            "x265-params": "log-level=error:colorprim=bt2020:transfer=arib-std-b67"
            ":colormatrix=bt2020nc"
        }
        cc = vs.codec_context
        cc.color_primaries, cc.color_trc, cc.colorspace, cc.color_range = 9, 18, 9, 1
        for i, arr in enumerate(frames):
            x = arr.astype(np.float64) / 255
            lin = np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4) @ m.T
            e = lin * white
            hlg = np.where(
                e <= 1 / 12,
                np.sqrt(3 * np.maximum(e, 0)),
                a * np.log(np.maximum(12 * e - b, 1e-9)) + c,
            )
            r, g, bl = hlg[..., 0], hlg[..., 1], hlg[..., 2]
            y = 0.2627 * r + 0.6780 * g + 0.0593 * bl
            cb, cr = (bl - y) / 1.8814, (r - y) / 1.4746
            sub = lambda p: p.reshape(h // 2, 2, w // 2, 2).mean(axis=(1, 3))  # noqa: E731
            frame = av.VideoFrame(w, h, "yuv420p10le")
            for plane, data in zip(
                frame.planes,
                (64 + 876 * y, 512 + 896 * sub(cb), 512 + 896 * sub(cr)),
                strict=True,
            ):
                q = np.clip(np.round(data), 0, 1023).astype("<u2")
                buf = np.frombuffer(memoryview(plane), dtype="<u2").reshape(
                    -1, plane.line_size // 2
                )
                buf[: q.shape[0], : q.shape[1]] = q
            frame.color_primaries, frame.color_trc, frame.colorspace, frame.color_range = (
                9,
                18,
                9,
                1,
            )
            frame.pts, frame.time_base = i, Fraction(1, fps)
            for p in vs.encode(frame):
                out.mux(p)
        for p in vs.encode():
            out.mux(p)
