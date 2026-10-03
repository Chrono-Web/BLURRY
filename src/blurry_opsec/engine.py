"""The two phases, shared by the command and the app.

analyze -> a coverage plan in memory (boxes, tracks, review flags)
render  -> apply the plan and write the clean file

The command runs both back to back; the app stops in between so the user can
correct the plan.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import cv2

from blurry_opsec import files, image_io, levels, redact, tracking, video_io
from blurry_opsec.detect import FaceDetector
from blurry_opsec.plan import NEAR_THRESHOLD, NO_FACES, SMALL_FACE, Flag, ImagePlan, VideoPlan
from blurry_opsec.watermark import Watermark

# stage, done, total
ProgressFn = Callable[[str, int, int], None]


@dataclass
class Settings:
    level: str = levels.DEFAULT_LEVEL
    mode: str = levels.DEFAULT_MODE
    padding: float = levels.DEFAULT_PADDING
    keep_audio: bool = False
    faces: bool = True  # False = metadata cleanup only (--no-faces)
    watermark: str | None = None

    def validate(self) -> None:
        levels.get(self.level)
        if self.mode not in levels.MODES:
            raise ValueError(f"unknown mode {self.mode!r}")
        if not 0.0 <= self.padding <= 2.0:
            raise ValueError("padding must be between 0 and 2")


def kind_of(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in image_io.IMAGE_EXTENSIONS:
        return "image"
    if ext in video_io.VIDEO_EXTENSIONS:
        return "video"
    raise files.InputError(
        "unsupported file type (images: JPEG, PNG, WebP, HEIC; "
        "videos: MP4, MOV, M4V, MKV, WebM, AVI)"
    )


@dataclass
class ImageJob:
    source: Path
    loaded: image_io.LoadedImage
    plan: ImagePlan


@dataclass
class VideoJob:
    source: Path
    info: video_io.VideoInfo
    plan: VideoPlan


@dataclass
class Result:
    output: Path
    audio: str = "none"  # none | removed | kept
    metadata_removed: list[str] = field(default_factory=list)


def image_flags(plan: ImagePlan, confidence: float) -> list[Flag]:
    flags = []
    for i, box in enumerate(plan.boxes):
        if box.score is not None and box.score < confidence + levels.NEAR_THRESHOLD_MARGIN:
            flags.append(Flag(NEAR_THRESHOLD, box=i))
        if box.long_side < levels.SMALL_FACE_PX:
            flags.append(Flag(SMALL_FACE, box=i))
    if plan.faces_expected and not plan.boxes:
        flags.append(Flag(NO_FACES))
    return flags


def analyze_image(path: Path, settings: Settings, detector: FaceDetector | None) -> ImageJob:
    loaded = image_io.load(path)
    h, w = loaded.rgb.shape[:2]
    plan = ImagePlan(w, h, faces_expected=settings.faces)
    if settings.faces:
        if detector is None:
            raise ValueError("a detector is required to cover faces")
        plan.boxes = detector.detect(cv2.cvtColor(loaded.rgb, cv2.COLOR_RGB2BGR))
        plan.flags = image_flags(plan, detector.confidence)
    return ImageJob(path, loaded, plan)


def render_image(job: ImageJob, settings: Settings, out_dir: Path | None) -> Result:
    rgb = job.loaded.rgb.copy()
    alpha = None if job.loaded.alpha is None else job.loaded.alpha.copy()
    blocks = levels.get(settings.level).blocks
    redact.apply(rgb, job.plan.boxes, settings.mode, settings.padding, blocks, alpha)
    if settings.watermark:
        Watermark(settings.watermark).apply(rgb)
    data = image_io.encode(rgb, alpha, job.loaded.out_format)
    final = files.output_path(job.source, out_dir, job.loaded.out_ext)
    with files.partial_output(final) as partial, open(partial, "wb") as fh:
        fh.write(data)
    return Result(final, "none", job.loaded.metadata_found)


def analyze_video(
    path: Path,
    settings: Settings,
    detector: FaceDetector | None,
    progress: ProgressFn | None = None,
) -> VideoJob:
    info = video_io.probe(path)
    detections = []
    count = 0
    report = (lambda d, t: progress("analyzing", d, t)) if progress else None
    for frame in video_io.iter_frames(path, report, info.estimated_frames):
        count += 1
        detections.append(detector.detect(frame) if settings.faces and detector else [])
    if count == 0:
        raise files.InputError("the video has no decodable frames")
    fps = info.fps
    plan = VideoPlan(
        width=info.width,
        height=info.height,
        frame_count=count,
        fps=fps,
        extend_frames=max(1, int(round(fps * 0.5))),
        faces_expected=settings.faces,
    )
    if settings.faces and detector is not None:
        plan.tracks = tracking.build_tracks(detections, max_gap=max(1, int(round(fps))))
        plan.flags = tracking.track_flags(plan.tracks, detector.confidence)
        plan.max_simultaneous = tracking.max_simultaneous(detections)
        if not plan.tracks:
            plan.flags.append(Flag(NO_FACES))
    return VideoJob(path, info, plan)


def render_video(
    job: VideoJob,
    settings: Settings,
    out_dir: Path | None,
    progress: ProgressFn | None = None,
) -> Result:
    blocks = levels.get(settings.level).blocks
    mark = Watermark(settings.watermark) if settings.watermark else None
    plan = job.plan

    def process(index, frame):
        redact.apply(frame, plan.boxes_for(index), settings.mode, settings.padding, blocks)
        if mark:
            mark.apply(frame)
        return frame

    final = files.output_path(job.source, out_dir, "mp4")
    report = (lambda d, t: progress("rendering", d, t)) if progress else None
    with files.partial_output(final) as partial:
        wrote_audio = video_io.render(
            job.source, partial, plan.frame_count, process, settings.keep_audio, report
        )
    removed = list(job.info.metadata_found)
    if job.info.has_audio:
        audio = "kept" if wrote_audio else "removed"
        if not wrote_audio:
            removed.append("audio")
    else:
        audio = "none"
    return Result(final, audio, sorted(set(removed)))
