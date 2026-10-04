# Changelog

All notable changes are listed here. Versions follow [Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-10-04

First public release: the desktop app and the `blurry` command.

- Native macOS app (SwiftUI, Apple Silicon, macOS 14+) distributed as `Blurry.dmg`,
  with the frozen Python engine, image/video review and a first-run guide.

- Desktop app (PySide6, optional `gui` extra): drag and drop queue, image editor with detected and
  manual boxes, video review with timeline, review flags, track on/off and manual boxes over a
  span of time, result preview, explicit confirmation for files with no faces, Italian and
  English. Processing runs in a separate, cancellable worker process. Preferences limited to
  sensitivity, cover, margin and language; a custom file picker that remembers nothing.

- Face covering with YuNet (solid black box by default, or pixelation), three detection levels,
  adjustable padding; tracks held half a second before and after in videos.
- Metadata removal for JPEG, PNG, WebP, HEIC/HEIF photos and MP4, MOV, M4V, MKV, WebM, AVI videos;
  output as JPEG/PNG and H.264 MP4. Rotation applied to the pixels.
- Offline by construction: network sockets blocked in-process, FFmpeg restricted to local files and
  whitelisted demuxers.
- Nothing written besides the chosen output; originals never overwritten.
- Review flags (no faces, near-threshold detections, small faces, track gaps), `--strict`,
  `--json` reports and `__PROGRESS__` lines.
