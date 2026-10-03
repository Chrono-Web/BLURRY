# Changelog

All notable changes are listed here. Versions follow [Semantic Versioning](https://semver.org/).

## [0.1.0] — unreleased

First public release: the `blurry` command.

- Face covering with YuNet (solid black box by default, or pixelation), three detection levels,
  adjustable padding; tracks held half a second before and after in videos.
- Metadata removal for JPEG, PNG, WebP, HEIC/HEIF photos and MP4, MOV, M4V, MKV, WebM, AVI videos;
  output as JPEG/PNG and H.264 MP4. Rotation applied to the pixels.
- Offline by construction: network sockets blocked in-process, FFmpeg restricted to local files and
  whitelisted demuxers.
- Nothing written besides the chosen output; originals never overwritten.
- Review flags (no faces, near-threshold detections, small faces, track gaps), `--strict`,
  `--json` reports and `__PROGRESS__` lines.
