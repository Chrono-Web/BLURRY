# Blurry

**Cover faces and strip metadata from photos and videos — on your own computer, with no network.**

[Italiano](README.it.md) · [Threat model](THREAT_MODEL.md) · [Security](SECURITY.md) · License: [MIT](LICENSE)

Blurry finds faces, covers them with a solid black box (or pixelation), and writes a new file with
no metadata: no GPS position, no camera model, no dates, no hidden thumbnail of the original. It
runs entirely offline. It has no server, no account, no telemetry and no update check, and it
refuses to open network connections even if something tries.

> **Version 0.1 is a command-line tool.** A desktop app for people who do not use the terminal
> comes with version 1.0.

## What it does

- **Covers faces** in photos and videos, using the YuNet face detector (bundled; its SHA-256 is
  checked on every start, and Blurry refuses to run if it does not match).
- **Removes all metadata**:
  - photos: EXIF (including the embedded thumbnail), GPS, XMP, IPTC, colour profiles and comments;
  - videos: container and track tags (QuickTime location, device, dates), chapters, subtitles,
    data tracks (such as GoPro and drone GPS) and cover art.
- **Applies the rotation** of phone photos and videos to the pixels first, so sideways faces are
  not missed, and the output looks the same as before without carrying rotation metadata.
- **Drops audio by default**, because voices can identify people. Keep it with `--keep-audio`.
- **Never overwrites anything**: the original stays untouched, and if the output name is taken a
  numbered name is used.
- **Never stays silent when no face is found**: it warns, and with `--strict` it writes nothing
  and exits with code 2.

## What it does not do

Read the [threat model](THREAT_MODEL.md) before relying on Blurry. In short, it does **not** hide
bodies, clothes, tattoos, voices, places, reflections, or the camera sensor's fingerprint; it
cannot cover a face the detector does not find; it does not delete your original, which may also
be synced to iCloud or Google Photos.

**The detector can miss faces**, especially faces in profile, in the dark, very small, or turned
sideways. Always look at the result before sharing it. Files with uncertain detections are listed
under `flags` in the `--json` report.

## Install

You need Python 3.12. The simplest way is [pipx](https://pipx.pypa.io/) (or `uv tool`):

```bash
pipx install blurry-opsec
```

```bash
uv tool install blurry-opsec
```

The command is called `blurry`. Ready-made apps for macOS, Windows and Linux come with v1.0.

## Use

```bash
blurry photo.jpg
```

writes `photo.blurry.jpg` next to the original.

```bash
blurry IMG_0001.HEIC clip.mov -o ~/Desktop/clean
```

writes `IMG_0001.blurry.jpg` and `clip.blurry.mp4` in `~/Desktop/clean`.

```
blurry INPUT... [-o FOLDER] [--level base|medium|high] [--mode solid|pixel]
    [--padding 0.25] [--keep-audio] [--no-faces] [--watermark TEXT]
    [--strict] [--json] [--debug]
```

| Option | Meaning | Default |
|---|---|---|
| `-o FOLDER` | Where to write the outputs | next to each original |
| `--level` | Detection sensitivity: `base` (clear frontal faces only), `medium`, `high` (also small or partly hidden faces) | `high` |
| `--mode` | `solid` black box or `pixel` (pixelation) | `solid` |
| `--padding` | Margin around each face, as a fraction of its long side, on every side | `0.25` |
| `--keep-audio` | Keep the audio track (re-encoded to AAC) | audio removed |
| `--no-faces` | Only remove metadata, cover nothing | |
| `--watermark TEXT` | Add a text watermark | off |
| `--strict` | If a file has no faces, write nothing for it and exit with code 2 | |
| `--json` | Print one JSON report per file on stdout | |
| `--debug` | Debug output on stderr | off |

**Accepted files.** Photos: JPEG, PNG, WebP (still), HEIC/HEIF. Videos: MP4, MOV, M4V, MKV, WebM,
AVI. GIFs and animated images are refused. Photos come out as JPEG (PNG stays PNG); videos come
out as MP4 (H.264).

**Exit codes.** `0` all good · `1` an error · `2` no face found with `--strict`.

Progress is printed on stderr as `__PROGRESS__ {json}` lines, for scripts and integrations.

## Verify what you download

Every release on GitHub comes with a `SHA256SUMS` file, a CycloneDX SBOM, and a GitHub
build-provenance attestation for each file, which proves it was built by this repository's
release workflow.

- macOS / Linux, in the folder with the downloads:

  ```bash
  shasum -a 256 -c SHA256SUMS
  ```

- Windows (compare the result with the line in `SHA256SUMS`):

  ```
  CertUtil -hashfile <file> SHA256
  ```

- Provenance, with the [GitHub CLI](https://cli.github.com/):

  ```bash
  gh attestation verify <file> --repo Chrono-Web/BLURRY
  ```

The PyPI package is published from the same workflow with Trusted Publishing (no tokens), and
PyPI shows its provenance on the project page.

## Known limits

- Faces in profile, in the dark, very small or turned sideways can be missed (see above).
- HDR videos from phones (10-bit HEVC) come out as 8-bit SDR H.264: colours can look flatter.
- On macOS, processing a video prints a harmless `objc ... implemented in both` warning, because
  OpenCV and PyAV each bundle their own FFmpeg.

## Licence

Blurry is MIT-licensed. The PyPI package contains only Blurry's code, the YuNet model (MIT) and the
Geist font (OFL). The ready-made apps (from v1.0) also contain FFmpeg with **x264 and x265, which
are GPL-2.0-or-later**: see [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) for every licence
and the exact sources.
