"""The Qt app, driven offscreen: the guide one file at a time, corrections by
hand, export, the queue, preferences (R2)."""

import os
import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("PySide6.QtWidgets")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from conftest import PUBLIC  # noqa: E402
from PySide6.QtCore import QPoint, QRectF, QSettings, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


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

    prefs = Prefs()
    prefs.onboarded = True  # the introduction has its own test
    prefs.language = "en"
    w = MainWindow(prefs)
    w.show()
    yield w
    w.close()


def test_guided_flow(qapp, window, tmp_path):
    from blurry_opsec.gui.prefs import ALLOWED_KEYS

    qa, prefs = qapp
    w, s = window, window.store
    assert w.stack.currentWidget() is w.landing
    src = tmp_path / "in"
    src.mkdir()
    for name in ("dental_squadron.jpg", "challenger_51l_crew.jpg"):
        (src / name).write_bytes((PUBLIC / name).read_bytes())
    Image.new("RGB", (300, 200), (90, 90, 90)).save(src / "wall.png")
    (src / "notes.txt").write_text("not a picture")
    w.add_paths([src])
    assert w.windowTitle() == "Blurry"
    assert s.notice and "1" in s.notice  # the text file was skipped
    assert w.stack.currentWidget() is w.guide
    assert s.current.name == "challenger_51l_crew.jpg" and s.step == "sensitivity"
    assert wait(qa, lambda: all(it.analysed for it in s.items))
    by_name = {it.name: it for it in s.items}
    assert by_name["challenger_51l_crew.jpg"].faces == 7
    assert by_name["wall.png"].status == "no_faces"
    assert s.steps == ("sensitivity", "cover", "margin", "result")  # no audio for photos

    # A new sensitivity is instant: the plans for every level are already there.
    s.set_level("base")
    assert not s.jobs.busy and s.current.plan is not None
    s.set_level("high")
    assert s.current.faces == 7

    # The step bar and the buttons move through the steps; the picture follows.
    w.guide.step_bar.buttons["margin"].click()
    assert s.step == "margin"
    w.guide.back_btn.click()
    assert s.step == "cover"
    assert wait(qa, lambda: not s.preview_stale)

    # Corrections by hand on the dental photo: drag on an empty area draws a box.
    s.open(by_name["dental_squadron.jpg"].id)
    before = by_name["dental_squadron.jpg"].faces
    w.guide.picture.correct_btn.click()
    assert s.editing and w.guide.bottom.currentWidget() is w.guide.edit_panel
    assert wait(qa, lambda: s.edit_boxes and not s.preview_stale)
    pic = w.guide.picture
    r = pic.image_rect()
    width = pic.plan_size()[0]
    a = QPoint(int(r.left() + r.width() * 100 / width), int(r.top() + r.width() * 900 / width))
    b = QPoint(int(r.left() + r.width() * 300 / width), int(r.top() + r.width() * 1100 / width))
    QTest.mousePress(pic, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, a)
    QTest.mouseMove(pic, QPoint((a.x() + b.x()) // 2, (a.y() + b.y()) // 2))
    QTest.mouseMove(pic, b)
    QTest.mouseRelease(pic, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, b)
    assert by_name["dental_squadron.jpg"].faces == before + 1
    assert s.selected_box is not None and s.selected_box.owner[0] == "drawn"
    # Cancel puts back the corrections from before; Done keeps them.
    w.guide.edit_panel.cancel_btn.click()
    assert by_name["dental_squadron.jpg"].faces == before and not s.editing
    s.start_editing()
    s.add_box(QRectF(100, 900, 200, 200))
    w.guide.edit_panel.done_btn.click()
    assert by_name["dental_squadron.jpg"].faces == before + 1
    # The corrections survive a change of sensitivity.
    s.set_level("base")
    s.set_level("high")
    assert by_name["dental_squadron.jpg"].faces == before + 1

    # Export to the path chosen in the save picker.
    s.set_step("result")
    out = tmp_path / "out"
    out.mkdir()
    s.export(out / "dental_squadron_blurry.jpg")
    assert wait(qa, lambda: s.current.status == "exported")
    arr = np.array(Image.open(out / "dental_squadron_blurry.jpg"))
    assert arr[930:1070, 130:270].max() < 10
    assert not [p for p in src.iterdir() if "blurry" in p.name]
    assert w.guide.primary_btn.text() == "Next file" and w.guide.saved.isVisible()

    # The next file opens on the result, with the same settings.
    w.guide.primary_btn.click()
    assert s.current.name == "challenger_51l_crew.jpg"
    assert s.step == "result" and s.using_previous
    assert w.guide.previous_row.isVisible()

    # The queue lists every file of the session; double-click opens one.
    w.open_queue()
    q = w.queue_window
    assert q.list.count() == 3
    assert {r.status.text() for r in q._rows.values()} >= {"Exported", "No face"}
    wall = by_name["wall.png"]
    q.open_item.emit(wall.id)
    assert s.current is wall

    # Preferences hold only the allowed keys, and no paths.
    prefs_text = prefs.read_text()
    assert str(tmp_path) not in prefs_text
    keys = set(QSettings(str(prefs), QSettings.Format.IniFormat).allKeys())
    assert keys <= set(ALLOWED_KEYS)


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
    # Saving starts in the original's folder, with <name>_blurry.<ext>.
    save = picker.SavePicker(window, tmp_path, "a_blurry.jpg", ".jpg")
    assert save.current == tmp_path and save.target() == tmp_path / "a_blurry.jpg"
    save.name.setText("other")
    assert save.target() == tmp_path / "other.jpg"
    save.deleteLater()


def test_language_switch(qapp, window):
    window.set_language("it")
    assert window.landing.title.text() == "Trascina qui foto e video"
    assert window.prefs.language == "it"
    window.set_language("en")
    assert window.landing.title.text() == "Drop photos and videos here"
