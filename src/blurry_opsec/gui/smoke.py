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
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QApplication, QMessageBox

from blurry_opsec import i18n
from blurry_opsec.gui.app import _contain_qt_settings
from blurry_opsec.gui.main_window import MainWindow
from blurry_opsec.gui.preferences import Group
from blurry_opsec.gui.prefs import ALLOWED_KEYS, Prefs


def main(fixture: str) -> int:
    with tempfile.TemporaryDirectory(prefix="blurry-smoke-è-日本-") as folder:
        root = Path(folder)
        os.environ["BLURRY_PREFS_INI"] = str(root / "preferences.ini")
        _contain_qt_settings()
        app = QApplication([])
        window = MainWindow(Prefs())
        window.show()
        store = window.store

        def wait(predicate):
            end = time.monotonic() + 120
            while time.monotonic() < end:
                app.processEvents()
                if predicate():
                    return
                time.sleep(0.02)
            raise RuntimeError("GUI smoke timeout")

        def export(item, output: Path) -> None:
            store.open(item.id)
            store.start_editing()
            store.add_box(QRectF(10, 10, 30, 30))
            store.end_editing(True)
            store.export(output)
            wait(lambda: item.status in ("exported", "error"))
            if item.status != "exported" or not output.is_file():
                raise RuntimeError(f"Frozen worker failed to export: {item.error}")

        try:
            if window.prefs.onboarded:
                raise RuntimeError("First run preferences are not empty")
            wait(lambda: window.welcome is not None and window.welcome.isVisible())
            for _ in range(3):
                window.welcome.next_btn.click()
            if not Prefs().onboarded:
                raise RuntimeError("Onboarding did not persist")
            for language in ("it", "en"):
                window.set_language(language)
                message = QMessageBox(window)
                message.setStandardButtons(QMessageBox.StandardButton.Yes)
                yes = message.button(QMessageBox.StandardButton.Yes).text().replace("&", "")
                if yes != ("Sì" if language == "it" else "Yes"):
                    raise RuntimeError("Qt standard button translation missing")
                window.open_preferences()
                app.processEvents()
                if len(window.preferences_dialog.findChildren(Group)) < 6:
                    raise RuntimeError("Missing settings sections")
                window.preferences_dialog.close()
            source = root / "original è 日本.jpg"
            shutil.copyfile(fixture, source)
            before = hashlib.sha256(source.read_bytes()).digest()
            window.add_paths([source])
            item = store.items[0]
            wait(lambda: item.status not in ("waiting", "analyzing"))
            if item.plan is None:
                raise RuntimeError("Frozen worker failed to analyse image")
            export(item, root / "original è 日本_blurry.jpg")
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
            clip = store.items[-1]
            wait(lambda: clip.status not in ("waiting", "analyzing"))
            if clip.plan is None:
                raise RuntimeError("Frozen video analysis failed")
            cleaned_path = root / "clip_blurry.mp4"
            export(clip, cleaned_path)
            with av.open(str(cleaned_path)) as cleaned:
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
