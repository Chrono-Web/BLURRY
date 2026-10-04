"""Local lifecycle: showing a file in its folder, the releases page, uninstalling.
No network requests: the releases page opens in the user's browser."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from blurry_opsec.gui import strings as L

RELEASES_URL = "https://github.com/Chrono-Web/BLURRY/releases"


def clean_env() -> dict:
    """The environment for programs outside Blurry: the packaged app's library
    path would make them load Blurry's own libraries."""
    env = os.environ.copy()
    if "LD_LIBRARY_PATH_ORIG" in env:
        env["LD_LIBRARY_PATH"] = env.pop("LD_LIBRARY_PATH_ORIG")
    else:
        env.pop("LD_LIBRARY_PATH", None)
    return env


def reveal(path: Path) -> None:
    """Show the file in the system's file manager (its folder, on Linux)."""
    try:
        if sys.platform == "win32":
            subprocess.Popen(f'explorer /select,"{path}"')  # noqa: S603
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])  # noqa: S603, S607
        else:
            folder = path if path.is_dir() else path.parent
            command = ["xdg-open", str(folder)]
            subprocess.Popen(command, env=clean_env(), start_new_session=True)  # noqa: S603
    except OSError:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))


def open_releases() -> None:
    QDesktopServices.openUrl(QUrl(RELEASES_URL))


def uninstall_command() -> list[str] | None:
    if not getattr(sys, "frozen", False):
        return None
    root = Path(sys.executable).resolve().parent
    if sys.platform == "win32" and (root / "unins000.exe").is_file():
        return [str(root / "unins000.exe")]
    expected = Path.home() / ".local/opt/blurry"
    if sys.platform == "linux" and root == expected and (root / "uninstall.sh").is_file():
        return ["/bin/sh", str(root / "uninstall.sh")]
    return None


def remove(window) -> None:
    """Settings ▸ Uninstall: ask, then hand over to the installer's uninstaller,
    which removes the app and this user's preferences, and quit."""
    if window.store.busy or window.store.jobs.busy:
        QMessageBox.information(window, "Blurry", L.uninstall_busy())
        return
    command = uninstall_command()
    if command is None:
        # Installed with Python: the package manager removes the app; Blurry can
        # still remove its own preferences.
        box = QMessageBox(window)
        box.setText(L.uninstall_not_packaged())
        clear = box.addButton(L.clear_and_quit(), QMessageBox.ButtonRole.DestructiveRole)
        box.setDefaultButton(box.addButton(L.cancel(), QMessageBox.ButtonRole.RejectRole))
        box.exec()
        if box.clickedButton() is clear:
            window.prefs.clear()
            window.close()
        return
    box = QMessageBox(window)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setText(L.uninstall_question())
    box.setInformativeText(L.uninstall_description())
    go = box.addButton(L.uninstall().rstrip("…"), QMessageBox.ButtonRole.DestructiveRole)
    cancel = box.addButton(L.cancel(), QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel)
    box.exec()
    if box.clickedButton() is not go:
        return
    try:
        # The Linux helper waits for this process to exit before removing files.
        if sys.platform == "linux":
            command.append(str(os.getpid()))
        subprocess.Popen(command, env=clean_env(), start_new_session=True)  # noqa: S603
    except OSError:
        QMessageBox.warning(window, "Blurry", L.uninstall_error())
        return
    window.close()
