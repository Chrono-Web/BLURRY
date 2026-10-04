"""Translate Qt's standard buttons along with Blurry's own UI strings."""

from PySide6.QtCore import QLibraryInfo, QTranslator
from PySide6.QtWidgets import QApplication


def set_language(code: str) -> None:
    app = QApplication.instance()
    if app is None:
        return
    previous = getattr(app, "_blurry_translator", None)
    if previous is not None:
        app.removeTranslator(previous)
        previous.deleteLater()
    app._blurry_translator = None
    if code == "it":
        translator = QTranslator(app)
        directory = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        if translator.load("qtbase_it", directory):
            app.installTranslator(translator)
            app._blurry_translator = translator
