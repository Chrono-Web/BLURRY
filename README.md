<p align="center">
  <img src="docs/icona.png" width="128" height="128" alt="Blurry icon">
</p>

<h1 align="center">Blurry</h1>

<p align="center">
  Cover faces and strip metadata from photos and videos,<br>
  on your own computer, with no network.
</p>

<p align="center">
  <a href="https://github.com/Chrono-Web/BLURRY/releases/latest/download/Blurry.dmg"><b>⬇ Download for Mac</b></a>
  &nbsp;·&nbsp;
  <a href="#with-python-windows-linux-command-line"><b>Windows and Linux (with Python)</b></a>
  <br>
  <sub>Version 0.1.0 · Mac with Apple Silicon, macOS 14+ · free and open source (MIT)</sub>
  <br>
  <sub><a href="README.it.md">Italiano</a> · <a href="THREAT_MODEL.md">Threat model</a> · <a href="SECURITY.md">Security</a></sub>
</p>

Blurry finds faces, covers them with a solid black box (or pixelation), and writes a new file with
no metadata: no GPS position, no camera model, no dates, no hidden thumbnail of the original. It
runs entirely offline. It has no server, no account, no telemetry and no update check, and it
refuses to open network connections even if something tries.

> **Always check the result before you share it:** the detector can miss faces, and Blurry
> does not hide bodies, voices or places. See [What it does not do](#what-it-does-not-do).

## Install

### Mac

Apple Silicon (M1 or later), macOS 14 or later.

1. Download [`Blurry.dmg`](https://github.com/Chrono-Web/BLURRY/releases/latest/download/Blurry.dmg)
   from the [Releases](https://github.com/Chrono-Web/BLURRY/releases) page.
2. Open it and drag Blurry onto the Applications folder.
3. The first time, macOS warns that it cannot verify the developer: Blurry is not signed by Apple.
   Open System Settings › Privacy & Security, scroll down and click **Open Anyway** next to
   Blurry. You only do this once.

### With Python (Windows, Linux, command line)

You need Python 3.12. The simplest way is [pipx](https://pipx.pypa.io/) (or `uv tool`). With the
desktop app:

```bash
pipx install "blurry-opsec[gui]"
```

Command line only:

```bash
pipx install blurry-opsec
```

## The app

**On a Mac** (`Blurry.dmg`):

1. **Drop** photos and videos on the window, or use *Choose Files…* (⌘O).
2. A **guide** takes one file at a time: the file in the middle, and below it one choice at a
   time (sensitivity, cover, margin, and the sound for videos). From the cover step on, the
   picture shows exactly what will be exported; on a video you can play the covered result.
3. **Correct the boxes** by hand if needed: draw, move, resize or remove boxes on photos; in
   videos switch off a track that is not a face, or draw a still box over a span of time.
4. **Export…** opens the save panel on the original's folder, with `<name>_blurry`. The original
   is never touched. If no face was found, Blurry asks first.

Every file of the session is in View › Queue (⌘L). A short guide accompanies the first file
(Help › Show the Guide Again).

**On Windows and Linux**, run `blurry` with no arguments (or `blurry-app`) to open the app
installed with Python:

1. **Drop** photos and videos on the window, or use *Choose files…*. Each file is analysed in a
   separate process; nothing leaves your computer.
2. **Review** any file. Boxes found by the detector are yellow, boxes you add are teal. Drag on an
   empty area to add a box, drag a box to move it, drag its corners to resize it, press Delete to
   remove it. *Preview result* shows exactly what will be exported.
   In videos, scrub the timeline (uncertain moments are marked in red), turn off a track that is
   not a face, or draw a box that covers an area for a span of time.
3. **Export.** If a file has no face and you added none, Blurry asks before exporting it.

Both apps remember only a few settings (sensitivity, cover, margin, language, and on the Mac
whether the guide was seen): never file names, folders or recent files. The Qt app uses its own
file picker, because Qt's dialogs keep a list of recent folders; the Mac app uses the system's
panels and removes what they record as soon as they close.

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

## Uninstall

**Mac:** drag Blurry from Applications to the Bin. Blurry keeps no data: its only preferences
(sensitivity, cover, margin, and whether the guide was seen) live in
`~/Library/Preferences/com.chronocol.blurry.plist`, which you can delete.

**With Python:** `pipx uninstall blurry-opsec`.

## Report a problem

Something does not work, or a face is not covered? Open an
[issue](https://github.com/Chrono-Web/BLURRY/issues/new): say what you did and what happened,
**without attaching photos or videos of real people**. Security vulnerabilities do not go in
public issues: follow [SECURITY.md](SECURITY.md).

## From the command line

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
Geist font (OFL). The Mac app (`Blurry.dmg`) also contains FFmpeg with **x264 and x265, which
are GPL-2.0-or-later**, and the PyInstaller bootloader (GPL-2.0 with an exception for the
programs it runs): see [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) for every licence
and the exact sources.
