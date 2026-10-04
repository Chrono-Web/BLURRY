"""Lifecycle invariants and Linux installer in a disposable user home."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtWidgets")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QTabWidget  # noqa: E402

from blurry_opsec.gui import lifecycle  # noqa: E402
from blurry_opsec.gui.main_window import MainWindow  # noqa: E402
from blurry_opsec.gui.prefs import ALLOWED_KEYS, Prefs  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_onboarding_settings_reset_no_history(tmp_path, monkeypatch):
    path = tmp_path / "prefs.ini"
    monkeypatch.setenv("BLURRY_PREFS_INI", str(path))
    qa = QApplication.instance() or QApplication([])
    prefs = Prefs()
    assert not prefs.onboarded
    window = MainWindow(prefs)
    try:
        window.show_guide(first=True)
        window.guide_dialog.reject()
        assert not Prefs().onboarded
        window.show_guide(first=True)
        window.guide_dialog.accept()
        assert Prefs().onboarded
        for language in ("it", "en"):
            window._on_language(language)
            message = QMessageBox(window)
            message.setStandardButtons(QMessageBox.StandardButton.Yes)
            yes = message.button(QMessageBox.StandardButton.Yes).text().replace("&", "")
            assert yes == ("Sì" if language == "it" else "Yes")
            dialog = lifecycle.preferences(window)
            assert dialog.findChild(QTabWidget).count() == 3
            window.mode_seg.set_value("pixel")
            window._on_mode()
            window.padding_slider.setValue(40)
            reset = next(
                b
                for b in dialog.findChildren(QPushButton)
                if b.text() in ("Ripristina valori consigliati", "Restore recommended values")
            )
            reset.click()
            assert window.mode == "solid" and window.padding == 0.25
            dialog.close()
        prefs.sync()
        assert set(QSettings(str(path), QSettings.Format.IniFormat).allKeys()) <= set(ALLOWED_KEYS)
        prefs.clear()
        assert not Prefs().onboarded
        assert not Prefs()._s.allKeys()
    finally:
        window.close()
        qa.processEvents()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX installer")
def test_linux_install_upgrade_remove_reinstall(tmp_path):
    home = tmp_path / "home with space"
    home.mkdir()
    stage = tmp_path / "stage"
    (stage / "Blurry").mkdir(parents=True)
    for name in ("Blurry", "blurry-engine"):
        (stage / "Blurry" / name).write_text("#!/bin/sh\nexit 0\n")
    for name in ("install.sh", "uninstall.sh"):
        (stage / name).write_bytes((ROOT / "packaging/linux" / name).read_bytes())
    env = {**os.environ, "HOME": str(home), "XDG_CONFIG_HOME": str(home / "settings")}
    config = home / "settings/chronocol.com/blurry.conf"
    config.parent.mkdir(parents=True)
    config.write_text("[General]\nonboarded=true\n")
    original = home / "original.jpg"
    original.write_bytes(b"original remains")
    subprocess.run(["sh", str(stage / "install.sh")], env=env, check=True)
    subprocess.run(["sh", str(stage / "install.sh")], env=env, check=True)
    assert config.exists()  # upgrade preserves preferences
    installed = home / ".local/opt/blurry"
    subprocess.run(["sh", str(installed / "uninstall.sh")], env=env, check=True)
    assert not installed.exists() and not config.exists()
    assert not (home / ".local/share/applications/blurry.desktop").exists()
    assert original.read_bytes() == b"original remains"
    subprocess.run(["sh", str(stage / "install.sh")], env=env, check=True)
    assert installed.exists() and not config.exists()
