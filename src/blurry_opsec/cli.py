"""The `blurry` command: analyze and render each input back to back."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from blurry_opsec import __version__, engine, levels
from blurry_opsec.detect import FaceDetector
from blurry_opsec.files import InputError
from blurry_opsec.model import ModelIntegrityError, load_verified

EXIT_OK, EXIT_ERROR, EXIT_NO_FACES = 0, 1, 2


def _padding(value: str) -> float:
    try:
        v = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a number, e.g. 0.25") from None
    if not 0.0 <= v <= 2.0:
        raise argparse.ArgumentTypeError("must be between 0 and 2")
    return v


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="blurry",
        description="Cover faces and strip metadata from photos and videos, offline.",
    )
    p.add_argument("inputs", nargs="+", metavar="INPUT", type=Path)
    p.add_argument("-o", "--output", type=Path, metavar="FOLDER",
                   help="output folder (default: next to each original)")
    p.add_argument("--level", choices=list(levels.LEVELS), default=levels.DEFAULT_LEVEL,
                   help=f"detection sensitivity (default: {levels.DEFAULT_LEVEL})")
    p.add_argument("--mode", choices=levels.MODES, default=levels.DEFAULT_MODE,
                   help="solid black box or pixelation (default: solid)")
    p.add_argument("--padding", type=_padding, default=levels.DEFAULT_PADDING,
                   help="margin around each face, as a fraction of its long side (default: 0.25)")
    p.add_argument("--keep-audio", action="store_true",
                   help="keep the audio track (voices can identify people)")
    p.add_argument("--no-faces", action="store_true",
                   help="only strip metadata, do not cover anything")
    p.add_argument("--watermark", metavar="TEXT", help="add a text watermark (off by default)")
    p.add_argument("--strict", action="store_true",
                   help="exit with code 2 (and write nothing for that file) when no face is found")
    p.add_argument("--json", action="store_true", help="print one JSON report per file on stdout")
    p.add_argument("--debug", action="store_true", help="debug output on stderr")
    p.add_argument("-V", "--version", action="version", version=f"blurry {__version__}")
    return p


def _progress_printer(enabled: bool):
    state = {"last": (None, -1)}

    def emit(stage: str, done: int, total: int) -> None:
        if not enabled:
            return
        percent = int(min(100 if stage == "completed" else 99, done * 100 / total)) if total else 0
        if state["last"] == (stage, percent) and done != total:
            return
        state["last"] = (stage, percent)
        payload = {"stage": stage, "percent": percent, "framesProcessed": done, "totalFrames": total}
        print(f"__PROGRESS__ {json.dumps(payload)}", file=sys.stderr, flush=True)

    return emit


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    settings = engine.Settings(
        level=args.level,
        mode=args.mode,
        padding=args.padding,
        keep_audio=args.keep_audio,
        faces=not args.no_faces,
        watermark=args.watermark,
    )
    settings.validate()

    def debug(msg: str) -> None:
        if args.debug:
            print(f"[blurry] {msg}", file=sys.stderr)

    try:
        model_bytes = load_verified()
    except ModelIntegrityError as exc:
        print(f"blurry: {exc}", file=sys.stderr)
        return EXIT_ERROR
    detector = FaceDetector(settings.level, model_bytes) if settings.faces else None

    if args.output is not None and not args.output.is_dir():
        print("blurry: the output folder does not exist", file=sys.stderr)
        return EXIT_ERROR

    progress = _progress_printer(True)
    exit_code = EXIT_OK
    for n, src in enumerate(args.inputs, 1):
        report: dict = {
            "input": src.name,
            "level": settings.level,
            "mode": settings.mode,
            "padding": settings.padding,
        }
        label = f"file {n}/{len(args.inputs)}"
        try:
            kind = engine.kind_of(src)
            report["kind"] = kind
            if kind == "image":
                job = engine.analyze_image(src, settings, detector)
                plan = job.plan
                report["faces"] = len(plan.boxes)
            else:
                job = engine.analyze_video(src, settings, detector, progress)
                plan = job.plan
                report["faces"] = len(plan.tracks)
                report["max_simultaneous"] = plan.max_simultaneous
                report["frames"] = plan.frame_count
            report["flags"] = [f.to_dict() for f in plan.flags]
            no_faces = settings.faces and any(f.kind == "no_faces" for f in plan.flags)

            if no_faces:
                print(f"blurry: warning: no face found in {label}"
                      + (" (not written: --strict)" if args.strict else ""), file=sys.stderr)
                if args.strict:
                    report["status"] = "no_faces"
                    exit_code = max(exit_code, EXIT_NO_FACES)
                    _print_report(args, report)
                    continue

            if kind == "image":
                result = engine.render_image(job, settings, args.output)
            else:
                result = engine.render_video(job, settings, args.output, progress)
            progress("completed", 1, 1)
            report.update(
                status="ok",
                output=result.output.name,
                metadata_removed=result.metadata_removed,
                audio=result.audio,
            )
            debug(f"{label}: {report.get('faces', 0)} faces, flags={len(report['flags'])}")
        except (InputError, ValueError, OSError) as exc:
            report.update(status="error", error=str(exc))
            print(f"blurry: error in {label}: {exc}", file=sys.stderr)
            if args.debug:
                traceback.print_exc()
            exit_code = EXIT_ERROR if exit_code != EXIT_NO_FACES else exit_code
        except Exception as exc:  # FFmpeg and decoder errors
            report.update(status="error", error=type(exc).__name__)
            print(f"blurry: error in {label}: {type(exc).__name__}", file=sys.stderr)
            if args.debug:
                traceback.print_exc()
            exit_code = EXIT_ERROR if exit_code != EXIT_NO_FACES else exit_code
        _print_report(args, report)
    return exit_code


def _print_report(args, report: dict) -> None:
    if args.json:
        print(json.dumps(report, ensure_ascii=False), flush=True)
        return
    if report.get("status") == "ok":
        flags = len(report.get("flags", []))
        extra = f", {flags} to review" if flags else ""
        faces = "" if report.get("faces") is None else f"{report['faces']} face(s) covered{extra}, "
        print(f"{report['input']} -> {report['output']}: {faces}metadata removed")
