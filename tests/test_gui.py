"""The desktop app, driven offscreen: queue, review, export, preferences (R2)."""

import os
import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("PySide6.QtWidgets")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from conftest import PUBLIC  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from blurry_opsec.plan import Box  # noqa: E402


@pytest.fixture(scope="module")
def qapp(tmp_path_factory):
    prefs = tmp_path_factory.mktemp("prefs") / "prefs.ini"
    os.environ["BLURRY_PREFS_INI"] = str(prefs)
    from blurry_opsec.gui import app as gapp

    gapp._contain_qt_settings()
    qa = QApplication.instance() or QApplication([])
    qa.setStyleSheet(gapp.style.qss(False))
    yield qa, prefs


def wait(qa, cond, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        qa.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def window(qapp):
    from blurry_opsec.gui.main_window import MainWindow
    from blurry_opsec.gui.prefs import Prefs

    w = MainWindow(Prefs())
    w.show()
    yield w
    w.close()


def test_full_flow(qapp, window, tmp_path):
    qa, prefs = qapp
    w = window
    src = tmp_path / "in"
    src.mkdir()
    for name in ("dental_squadron.jpg", "challenger_51l_crew.jpg"):
        (src / name).write_bytes((PUBLIC / name).read_bytes())
    blank = src / "wall.png"
    Image.new("RGB", (300, 200), (90, 90, 90)).save(blank)
    w.add_paths([src])
    assert w.windowTitle() == "Blurry"
    assert wait(qa, lambda: all(it.status not in ("waiting", "analyzing") for it in w.items))
    by_name = {it.name: it for it in w.items}
    assert by_name["challenger_51l_crew.jpg"].faces == 7
    assert by_name["wall.png"].status == "no_faces" and by_name["wall.png"].uncovered_risk

    # Review: the user adds a box by hand on the dental photo.
    w.queue.clearSelection()
    row = [it.name for it in w.items].index("dental_squadron.jpg")
    w.queue.topLevelItem(row).setSelected(True)
    w.open_review()
    assert w.review is not None
    w.review.canvas.box_added.emit(Box(100, 900, 200, 200))
    assert len(by_name["dental_squadron.jpg"].plan.boxes) == 2
    assert by_name["dental_squadron.jpg"].edited
    w.review.preview_box.setChecked(True)
    w.close_review()

    # Export to a chosen folder; the no-faces file is left out (not risky-exported).
    out = tmp_path / "out"
    out.mkdir()
    w.out_dir = out
    w.export_queue += [it for it in w.items if not it.uncovered_risk]
    w.pump()
    assert wait(qa, lambda: all(it.status in ("exported", "no_faces") for it in w.items))
    assert sorted(p.name for p in out.iterdir()) == [
        "challenger_51l_crew.blurry.jpg", "dental_squadron.blurry.jpg"]  # fmt: skip
    arr = np.array(Image.open(out / "dental_squadron.blurry.jpg"))
    assert arr[930:1070, 130:270].max() < 10
    assert list(src.iterdir()) and not [p for p in src.iterdir() if ".blurry" in p.name]

    # Preferences hold only the four allowed keys, and no paths.
    w.prefs.padding = 0.3
    w.prefs.sync()
    text = prefs.read_text()
    assert str(tmp_path) not in text and "out" not in text.lower().split("=")[0]
    keys = set(QSettings(str(prefs), QSettings.Format.IniFormat).allKeys())
    assert keys <= {"level", "mode", "padding", "language"}


def test_no_qt_file_dialog_and_picker_remembers_nothing(qapp, window, tmp_path):
    import inspect

    from blurry_opsec.gui import main_window, picker

    # Qt's QFileDialog saves "lastVisited" and a history in the QtProject
    # preferences even when non-native: the app must never create one.
    for mod in (main_window, picker):
        assert "QFileDialog" not in inspect.getsource(mod)
    (tmp_path / "a.jpg").write_bytes((PUBLIC / "dental_squadron.jpg").read_bytes())
    dlg = picker.Picker(window, "x", False, [".jpg"])
    assert dlg.current == Path.home()
    dlg.go(tmp_path)
    dlg.deleteLater()
    again = picker.Picker(window, "x", False, [".jpg"])
    assert again.current == Path.home()  # nothing remembered
    again.deleteLater()


def test_language_switch(qapp, window):
    window.lang_seg._buttons["it"].click()
    assert window.export_all_btn.text() == "Esporta tutti"
    assert window.prefs.language == "it"
    window.lang_seg._buttons["en"].click()
    assert window.export_all_btn.text() == "Export all"
