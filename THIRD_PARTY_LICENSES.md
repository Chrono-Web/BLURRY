# Third-party licences

Blurry's own code is released under the [MIT licence](LICENSE).
Full licence texts are in [`licenses/`](licenses/).

## What ships where

| Distribution | Contains |
|---|---|
| **Python package on PyPI** (`blurry-opsec`) | Blurry's code (MIT), the YuNet model (MIT) and the Geist SemiBold and Geist Mono fonts (SIL OFL 1.1). Its dependencies are not included: pip installs them from PyPI, each under its own licence. |
| **Mac app** (`Blurry.dmg`) | All of the above **plus** the Python dependencies listed below (not PySide6/Qt: the Mac interface is SwiftUI), including **x264 and x265, which are GPL-2.0-or-later**, and the PyInstaller bootloader that starts the bundled engine. Those parts are distributed under their licences, with the source links given here. |

## Bundled with Blurry itself

| Component | Licence | Text | Source |
|---|---|---|---|
| YuNet face detector, `face_detection_yunet_2023mar.onnx` (Shiqi Yu, OpenCV Zoo) | MIT | [YuNet-MIT.txt](licenses/YuNet-MIT.txt) | <https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet> |
| Geist SemiBold (watermark) and Geist Mono Medium (app labels) fonts | SIL OFL 1.1 | [Geist-OFL-1.1.txt](licenses/Geist-OFL-1.1.txt) | <https://github.com/vercel/geist-font> |

## Python dependencies

| Component | Licence | Text |
|---|---|---|
| OpenCV (`opencv-python-headless`) | Apache-2.0 (OpenCV), MIT (packaging); bundles FFmpeg under LGPL-2.1 and other libraries | [OpenCV-Apache-2.0.txt](licenses/OpenCV-Apache-2.0.txt), [opencv-python-MIT.txt](licenses/opencv-python-MIT.txt), [OpenCV-third-party.txt](licenses/OpenCV-third-party.txt) |
| NumPy | BSD-3-Clause (and bundled 0BSD, MIT, Zlib, CC0 parts) | [NumPy-BSD-3-Clause.txt](licenses/NumPy-BSD-3-Clause.txt) |
| Pillow | MIT-CMU (and bundled library licences) | [Pillow-MIT-CMU.txt](licenses/Pillow-MIT-CMU.txt) |
| pi-heif | BSD-3-Clause; its wheels bundle **libheif** and **libde265** (LGPL-3.0), decoders only | [pi-heif-BSD-3-Clause.txt](licenses/pi-heif-BSD-3-Clause.txt), [LGPL-3.0.txt](licenses/LGPL-3.0.txt), [GPL-3.0.txt](licenses/GPL-3.0.txt) |
| PyAV (`av`) | BSD-3-Clause; its wheels bundle **FFmpeg** (LGPL-3.0-or-later), **x264** and **x265** (**GPL-2.0-or-later**) | [PyAV-BSD-3-Clause.txt](licenses/PyAV-BSD-3-Clause.txt), [LGPL-3.0.txt](licenses/LGPL-3.0.txt), [GPL-2.0.txt](licenses/GPL-2.0.txt) |
| PySide6-Essentials / Qt 6 (the Qt app for Windows and Linux only; not in the Mac `.dmg`) | LGPL-3.0 | [LGPL-3.0.txt](licenses/LGPL-3.0.txt), [GPL-3.0.txt](licenses/GPL-3.0.txt) |
| PyInstaller bootloader (Mac app only: it starts the frozen engine) | GPL-2.0-or-later with the PyInstaller bootloader exception, which allows bundling programs under any licence | [GPL-2.0.txt](licenses/GPL-2.0.txt); exception text: <https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt> |

## Exact sources of the copyleft libraries

For PyAV 19.0.1 (FFmpeg build `9.0.2-1` of
[PyAV-Org/pyav-ffmpeg](https://github.com/PyAV-Org/pyav-ffmpeg/releases/tag/9.0.2-1), checked on
2026-10-03) and pi-heif 1.4.0. The release process regenerates this table whenever these versions change.

| Library | Version | Source | SHA-256 of the source archive |
|---|---|---|---|
| FFmpeg | 9.0.2 | <https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz> | `8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e` |
| x264 | commit `b35605ace3ddf7c1a5d67a2eb553f034aef41d55` (core 165) | <https://code.videolan.org/videolan/x264/-/archive/b35605ace3ddf7c1a5d67a2eb553f034aef41d55/x264-b35605ace3ddf7c1a5d67a2eb553f034aef41d55.tar.bz2> | `6eeb82934e69fd51e043bd8c5b0d152839638d1ce7aa4eea65a3fedcf83ff224` |
| x265 | 4.3 | <https://github.com/Multicorewareinc/x265/releases/download/4.3/x265_4.3.tar.gz> | `83c53e4c8bbb8f1e33ed59e10a7d621d1d7801ca853910c3eb41f038b8ffb121` |
| libheif | 1.23.0 | <https://github.com/strukturag/libheif/tree/v1.23.0> | — |
| libde265 | 1.1.0 | <https://github.com/strukturag/libde265/tree/v1.1.0> | — |
| Qt for Python (PySide6) | as pinned in `uv.lock` | <https://download.qt.io/official_releases/QtForPython/> | — |

The FFmpeg build configuration (which libraries are enabled) is in
[`scripts/build-ffmpeg.py`](https://github.com/PyAV-Org/pyav-ffmpeg/blob/9.0.2-1/scripts/build-ffmpeg.py)
of that release. If you received a ready-made Blurry app and cannot reach these links, open an issue
and we will provide the corresponding source.
