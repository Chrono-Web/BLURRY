# Changelog

## [Unreleased]

- Windows and Linux: the Qt app now works like the Mac app. Only the drop window at first;
  then a guide takes one file at a time (sensitivity, cover, margin, sound, result) with the
  real preview from the engine, instant sensitivity, corrections by hand on the picture, and
  playback of the covered video. Export asks where to save, starting in the original's folder,
  with `<name>_blurry`. View › Queue, grouped Settings, a three-page introduction and three
  tips on the first file, as on the Mac. The old dashboard and review screens are gone.

## [0.1.2b1] — 2026-10-04 (beta)

- Add Qt onboarding, replayable guide, settings, manual updates and uninstall controls.
- Prepare per-user Windows x64 and Ubuntu 24.04 x86-64 native installer builds,
  installed-package smoke tests, CI/release artifacts, GUI SBOMs and provenance.
- Preserve PyPI engine/CLI and optional Qt; document and test headless CLI contracts.
- Add a separate-process backend example and record Chrono integration differences.
- Native Windows/Linux builds and installed-package CI tests pass; interactive
  real-desktop validation remains outstanding. See `docs/DISTRIBUZIONE.md`.
- Blurry becomes a small animated character in onboarding (Qt guide and macOS
  welcome): the icon's mosaic blinks, follows the pointer and greets. Cells are
  recomputed only while it moves; Reduce Motion keeps it still on macOS.
- Onboarding is centred and goes one step at a time on every system (the Qt
  guide gains Back/Next/Skip); Blurry stays in place above the changing text.
- The app icon's mosaic moves from 7 × 7 to 9 × 9 blocks, the same grid as the
  character. `scripts/icona.sh` now regenerates `docs/icona.png` too.


All notable changes are listed here. Versions follow [Semantic Versioning](https://semver.org/).

## [0.1.1] — 2026-10-04

- macOS: first-launch introduction with contextual tips, replayable from Help and Settings.
- Native grouped Settings window for sensitivity, cover, margin, manual updates and uninstall.
- Uninstallation moves the app to the Trash and removes preferences; reinstalling starts
  onboarding from scratch. Originals and exports are preserved; failed removal keeps preferences.
- Dismissing a contextual tip no longer advances onboarding or opens the queue.

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
