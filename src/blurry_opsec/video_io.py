"""Video decoding and clean encoding with PyAV.

FFmpeg can reach the network on its own (TLS is built into the PyAV wheels), so
every input is opened as a Python file object, with `protocol_whitelist=file`
and a `format_whitelist` limited to the accepted demuxers. A playlist hidden
in an .avi cannot pull in a remote segment.

The output has one H.264 video track and, if requested, one AAC audio track:
no container or track metadata, chapters, subtitles, data tracks or cover art.
Frames are rotated to their display orientation before detection, and the
original timestamps are kept so audio stays in sync.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

import numpy as np

from blurry_opsec.files import InputError, check_regular_file

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}
FORMAT_WHITELIST = "mov,mp4,matroska,webm,avi"
_ALLOWED_DEMUXERS = set(FORMAT_WHITELIST.split(","))
MAX_FILE_BYTES = 20 * 1024**3
MAX_DURATION_S = 3 * 3600
MAX_FRAME_PIXELS = 8192 * 4352

# Container/track tags that describe the file format itself, not the recording.
_TECHNICAL_TAGS = {
    "major_brand",
    "minor_version",
    "compatible_brands",
    "handler_name",
    "vendor_id",
    "language",
    "duration",
    "encoder",
}

ProgressFn = Callable[[int, int], None]


def _av():
    import av  # imported lazily: only video work loads FFmpeg

    return av


@dataclass
class VideoInfo:
    width: int  # display orientation
    height: int
    fps: float
    estimated_frames: int
    has_audio: bool
    metadata_found: list[str] = field(default_factory=list)


@contextlib.contextmanager
def open_input(path: Path) -> Iterator:
    if path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise InputError("unsupported video type (accepted: MP4, MOV, M4V, MKV, WebM, AVI)")
    check_regular_file(path, MAX_FILE_BYTES)
    av = _av()
    fh = open(path, "rb")  # noqa: SIM115 - closed below
    try:
        try:
            container = av.open(
                fh,
                "r",
                container_options={
                    "protocol_whitelist": "file",
                    "format_whitelist": FORMAT_WHITELIST,
                },
            )
        except av.FFmpegError as exc:
            raise InputError(
                "not a readable video, or a container type that is not accepted"
            ) from exc
        try:
            if not set(container.format.name.split(",")) & _ALLOWED_DEMUXERS:
                raise InputError("container type not accepted")
            if not _video_streams(container):
                raise InputError("no video track")
            if container.duration and container.duration / 1_000_000 > MAX_DURATION_S:
                raise InputError(f"video too long (limit {MAX_DURATION_S // 3600} h)")
            yield container
        finally:
            container.close()
    finally:
        fh.close()


def _video_streams(container) -> list:
    av = _av()
    return [
        s
        for s in container.streams.video
        if not (s.disposition & av.stream.Disposition.attached_pic)
    ]


def _main_streams(container, keep_audio: bool):
    video = _video_streams(container)[0]
    audio = container.streams.audio[0] if keep_audio and container.streams.audio else None
    return video, audio


def _fps(stream) -> float:
    rate = stream.average_rate or stream.guessed_rate or stream.base_rate
    return float(rate) if rate else 30.0


def _metadata_found(container, video) -> list[str]:
    av = _av()
    found: set[str] = set()
    if set(container.metadata) - _TECHNICAL_TAGS:
        found.add("container_tags")
    for key in container.metadata:
        k = key.lower()
        if "location" in k or k in ("com.apple.quicktime.location.iso6709", "gps"):
            found.add("location")
        if "creation_time" in k or k == "date":
            found.add("creation_time")
        if k.startswith("com.apple.quicktime.") and ("make" in k or "model" in k):
            found.add("device")
    for s in container.streams:
        if set(s.metadata) - _TECHNICAL_TAGS:
            found.add("track_tags")
        if s.type in ("data", "subtitle", "attachment"):
            found.add(f"{s.type}_track")
        if s.type == "video" and s.disposition & av.stream.Disposition.attached_pic:
            found.add("cover_art")
    with contextlib.suppress(Exception):
        if container.chapters():
            found.add("chapters")
    if len(container.streams.video) > 1 + ("cover_art" in found):
        found.add("extra_video_track")
    if len(container.streams.audio) > 1:
        found.add("extra_audio_track")
    return sorted(found)


def _rotate(frame) -> np.ndarray:
    """BGR array in display orientation. PyAV reports the display matrix angle
    counter-clockwise, which is also np.rot90's direction."""
    arr = frame.to_ndarray(format="bgr24")
    k = int(round((frame.rotation or 0) / 90)) % 4
    return np.ascontiguousarray(np.rot90(arr, k)) if k else arr


def probe(path: Path) -> VideoInfo:
    with open_input(path) as container:
        video, _ = _main_streams(container, keep_audio=False)
        found = _metadata_found(container, video)
        fps = _fps(video)
        frames = video.frames
        if not frames and container.duration:
            frames = int(container.duration / 1_000_000 * fps)
        w, h = video.codec_context.width, video.codec_context.height
        if w * h > MAX_FRAME_PIXELS:
            raise InputError("video resolution too large")
        rotation = 0
        for frame in container.decode(video):
            rotation = frame.rotation or 0
            w, h = frame.width, frame.height
            break
        if int(round(rotation / 90)) % 2:
            w, h = h, w
            found = sorted(set(found) | {"rotation"})
        elif rotation:
            found = sorted(set(found) | {"rotation"})
        return VideoInfo(w, h, fps, int(frames or 0), bool(container.streams.audio), found)


def iter_frames(
    path: Path,
    progress: ProgressFn | None = None,
    total: int = 0,
    pts_out: list | None = None,
) -> Iterator[np.ndarray]:
    """Decode every frame of the main video track, in display orientation (BGR).
    If `pts_out` is given, each frame's timestamp is appended to it, so that a
    frame can later be found again by seeking (see read_frame)."""
    with open_input(path) as container:
        video, _ = _main_streams(container, keep_audio=False)
        video.thread_type = "AUTO"
        for index, frame in enumerate(container.decode(video)):
            if pts_out is not None:
                pts_out.append(frame.pts)
            yield _rotate(frame)
            if progress:
                progress(index + 1, total)


def frame_at(path: Path, index: int) -> np.ndarray:
    for i, arr in enumerate(iter_frames(path)):
        if i == index:
            return arr
    raise IndexError(index)


def read_frame(path: Path, index: int, pts: list | None = None) -> np.ndarray:
    """One display-oriented BGR frame, by index. With the timestamps recorded
    during analysis it seeks to the nearest keyframe instead of decoding the
    whole video from the start."""
    target = pts[index] if pts and 0 <= index < len(pts) else None
    if target is None:
        return frame_at(path, index)
    with open_input(path) as container:
        video, _ = _main_streams(container, keep_audio=False)
        container.seek(target, stream=video, backward=True, any_frame=False)
        for frame in container.decode(video):
            if frame.pts is None:
                break
            if frame.pts >= target:
                return _rotate(frame)
    return frame_at(path, index)


def render(
    path: Path,
    out_path: Path,
    frame_count: int,
    process: Callable[[int, np.ndarray], np.ndarray],
    keep_audio: bool,
    progress: ProgressFn | None = None,
) -> bool:
    """Re-encode `path` into `out_path` (MP4), passing every display-oriented BGR
    frame through `process(index, frame)`. Returns whether audio was written.

    The frame sequence must match the analysis exactly: a frame beyond the
    analysed count is an error, never an uncovered frame.
    """
    av = _av()
    with open_input(path) as src:
        video, audio = _main_streams(src, keep_audio)
        video.thread_type = "AUTO"
        out = av.open(
            str(out_path),
            "w",
            format="mp4",
            container_options={"movflags": "+faststart", "fflags": "+bitexact"},
        )
        try:
            rate = video.average_rate or video.guessed_rate or Fraction(30, 1)
            vout = None
            aout = None
            if audio is not None:
                aout = out.add_stream("aac", rate=audio.codec_context.sample_rate or 48000)
                layout = audio.codec_context.layout
                if layout is not None and layout.nb_channels <= 8:
                    aout.codec_context.layout = layout
            last_pts = None
            index = 0

            def encode_video(frame) -> None:
                nonlocal vout, last_pts, index
                if index >= frame_count:
                    raise RuntimeError("decoded more frames than were analysed")
                arr = process(index, _rotate(frame))
                h, w = arr.shape[:2]
                w2, h2 = w - (w % 2), h - (h % 2)  # yuv420p needs even sizes
                if (w2, h2) != (w, h):
                    arr = np.ascontiguousarray(arr[:h2, :w2])
                if vout is None:
                    vout = out.add_stream("libx264", rate=rate)
                    vout.width, vout.height = w2, h2
                    vout.pix_fmt = "yuv420p"
                    vout.codec_context.time_base = video.time_base
                    vout.time_base = video.time_base
                    vout.options = {"crf": "18", "preset": "medium"}
                    out.start_encoding()
                new = av.VideoFrame.from_ndarray(arr, format="bgr24")
                pts = frame.pts
                if pts is None or (last_pts is not None and pts <= last_pts):
                    pts = 0 if last_pts is None else last_pts + 1
                new.pts, new.time_base = pts, video.time_base
                last_pts = pts
                for packet in vout.encode(new):
                    out.mux(packet)
                index += 1
                if progress:
                    progress(index, frame_count)

            streams = [video] + ([audio] if audio is not None else [])
            pending_audio = []
            for packet in src.demux(*streams):
                if packet.stream is video:
                    for frame in packet.decode():
                        encode_video(frame)
                    if vout is not None and pending_audio:
                        for af in pending_audio:
                            for p in aout.encode(af):
                                out.mux(p)
                        pending_audio.clear()
                elif aout is not None:
                    for frame in packet.decode():
                        if vout is None:
                            pending_audio.append(frame)  # wait until the video stream exists
                        else:
                            for p in aout.encode(frame):
                                out.mux(p)
            if vout is None:
                raise RuntimeError("the video has no decodable frames")
            if index != frame_count:
                raise RuntimeError("decoded fewer frames than were analysed")
            for p in vout.encode(None):
                out.mux(p)
            if aout is not None:
                for af in pending_audio:
                    for p in aout.encode(af):
                        out.mux(p)
                for p in aout.encode(None):
                    out.mux(p)
        finally:
            out.close()
        return aout is not None
