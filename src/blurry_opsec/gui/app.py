"""Start the desktop app."""

from __future__ import annotations

import platform
import sys

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from blurry_opsec import tempfiles
from blurry_opsec.gui import style
from blurry_opsec.gui.main_window import MainWindow
from blurry_opsec.gui.prefs import APP_NAME, ORG_DOMAIN, Prefs


def _contain_qt_settings() -> None:
    """Belt and braces: any QSettings created without an explicit format (by Qt
    itself or a dependency) goes to an INI file in a private temporary folder,
    removed at exit. Blurry's preferences ask for the native format explicitly.
    Qt's file dialog is not used at all (see picker.py)."""
    private = str(tempfiles.make_private_dir())
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    for scope in (QSettings.Scope.UserScope, QSettings.Scope.SystemScope):
        QSettings.setPath(QSettings.Format.IniFormat, scope, private)


def run(argv: list[str] | None = None) -> int:
    _contain_qt_settings()
    app = QApplication(sys.argv[:1] if argv is None else argv)
    app.setOrganizationDomain(ORG_DOMAIN)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName("Blurry")
    app.setStyle("Fusion")
    QFontDatabase.addApplicationFont(str(style.MONO_FILE))
    glass = sys.platform == "darwin" and platform.machine() == "arm64"
    app.setStyleSheet(style.qss(glass))
    window = MainWindow(Prefs(), glass=glass)
    window.show()
    return app.exec()
