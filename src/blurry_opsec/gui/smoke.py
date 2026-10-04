"""Exercise the installed GUI and its real frozen workers with disposable data."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import time
from pathlib import Path

import av
import numpy as np
from PIL import Image
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QPushButton

from blurry_opsec import i18n
from blurry_opsec.gui.app import _contain_qt_settings
from blurry_opsec.gui.lifecycle import preferences
from blurry_opsec.gui.main_window import MainWindow
from blurry_opsec.gui.prefs import ALLOWED_KEYS, Prefs
from blurry_opsec.plan import Box


def main(fixture: str) -> int:
    with tempfile.TemporaryDirectory(prefix="blurry-smoke-è-日本-") as folder:
        root = Path(folder)
        os.environ["BLURRY_PREFS_INI"] = str(root / "preferences.ini")
        _contain_qt_settings()
        app = QApplication([])
        window = MainWindow(Prefs())
        window.show()

        def wait(predicate):
            end = time.monotonic() + 120
            while time.monotonic() < end:
                app.processEvents()
                if predicate():
                    return
                time.sleep(0.02)
            raise RuntimeError("GUI smoke timeout")

        try:
            if window.prefs.onboarded:
                raise RuntimeError("First run preferences are not empty")
            window.show_guide(first=True)
            app.processEvents()
            window.guide_dialog.findChild(QDialogButtonBox).accepted.emit()
            if not Prefs().onboarded:
                raise RuntimeError("Onboarding did not persist")
            window.show_guide()
            window.guide_dialog.accept()
            for language in ("it", "en"):
                window._on_language(language)
                dialog = preferences(window)
                app.processEvents()
                if len(dialog.findChildren(QPushButton)) < 5:
                    raise RuntimeError("Missing lifecycle controls")
                dialog.close()
            source = root / "original è 日本.jpg"
            shutil.copyfile(fixture, source)
            before = hashlib.sha256(source.read_bytes()).digest()
            window.add_paths([source])
            wait(lambda: window.items[0].status not in ("waiting", "analyzing"))
            item = window.items[0]
            if item.plan is None:
                raise RuntimeError("Frozen worker failed to analyse image")
            window.queue.topLevelItem(0).setSelected(True)
            window.open_review()
            window.review.canvas.box_added.emit(Box(100, 100, 100, 100))
            if not item.edited:
                raise RuntimeError("Manual review failed")
            window.close_review()
            window.export(selected_only=False)
            wait(lambda: item.status in ("exported", "error"))
            if item.status != "exported" or not (root / item.output_name).is_file():
                raise RuntimeError("Frozen worker failed to export")
            if hashlib.sha256(source.read_bytes()).digest() != before:
                raise RuntimeError("Original changed")
            # Exercise bundled video decoders/encoders and manual video coverage.
            video = root / "clip.mp4"
            pixels = np.asarray(Image.open(source).convert("RGB").resize((320, 240)))
            with av.open(str(video), "w") as container:
                stream = container.add_stream("libx264", rate=5)
                stream.width, stream.height, stream.pix_fmt = 320, 240, "yuv420p"
                container.metadata["location"] = "private-test-location"
                for _ in range(5):
                    for packet in stream.encode(av.VideoFrame.from_ndarray(pixels, format="rgb24")):
                        container.mux(packet)
                for packet in stream.encode():
                    container.mux(packet)
            video_before = hashlib.sha256(video.read_bytes()).digest()
            window.add_paths([video])
            wait(lambda: window.items[-1].status not in ("waiting", "analyzing"))
            clip = window.items[-1]
            if clip.plan is None:
                raise RuntimeError("Frozen video analysis failed")
            clip.plan.add_manual(0, 4, Box(10, 10, 30, 30))
            clip.edited = True
            clip.settle()
            window.export(selected_only=False)
            wait(lambda: clip.status in ("exported", "error"))
            if clip.status != "exported":
                raise RuntimeError("Frozen video export failed")
            with av.open(str(root / clip.output_name)) as cleaned:
                if "location" in cleaned.metadata or cleaned.streams.audio:
                    raise RuntimeError("Video metadata or audio survived")
            if hashlib.sha256(video.read_bytes()).digest() != video_before:
                raise RuntimeError("Original video changed")
            window.prefs.sync()
            if set(window.prefs._s.allKeys()) - set(ALLOWED_KEYS):
                raise RuntimeError("Unexpected preferences")
            if str(source) in (root / "preferences.ini").read_text():
                raise RuntimeError("File history persisted")
            window.prefs.clear()
            if Prefs().onboarded:
                raise RuntimeError("Onboarding survived complete preference removal")
        finally:
            window.close()
            i18n.set_language("en")
    print("GUI smoke: startup, onboarding, settings IT/EN, worker, manual review, export, reset OK")
    return 0
