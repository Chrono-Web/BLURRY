"""Preferences: level, mode, padding and language. Nothing else, ever.

No paths, no recent files, no output folder, no window geometry (R2). The
macOS app shares this store (com.chronocol.blurry) and adds one more key,
"onboarded" (a boolean: the first-run guide was seen), which is kept here too
so that this app does not delete it.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QSettings

from blurry_opsec import i18n, levels

ORG_DOMAIN = "chronocol.com"
APP_NAME = "blurry"  # -> com.chronocol.blurry on macOS
ALLOWED_KEYS = ("level", "mode", "padding", "language", "onboarded")


def _settings() -> QSettings:
    # Tests point this at an INI file; the app uses the platform's native store.
    ini = os.environ.get("BLURRY_PREFS_INI")
    if ini:
        return QSettings(ini, QSettings.Format.IniFormat)
    return QSettings(QSettings.Format.NativeFormat, QSettings.Scope.UserScope, ORG_DOMAIN, APP_NAME)


class Prefs:
    def __init__(self) -> None:
        self._s = _settings()
        # Drop anything that is not an allowed key (e.g. written by an old build).
        for key in self._s.allKeys():
            if key not in ALLOWED_KEYS:
                self._s.remove(key)

    @property
    def level(self) -> str:
        v = str(self._s.value("level", levels.DEFAULT_LEVEL))
        return v if v in levels.LEVELS else levels.DEFAULT_LEVEL

    @level.setter
    def level(self, v: str) -> None:
        if v in levels.LEVELS:
            self._s.setValue("level", v)

    @property
    def mode(self) -> str:
        v = str(self._s.value("mode", levels.DEFAULT_MODE))
        return v if v in levels.MODES else levels.DEFAULT_MODE

    @mode.setter
    def mode(self, v: str) -> None:
        if v in levels.MODES:
            self._s.setValue("mode", v)

    @property
    def padding(self) -> float:
        try:
            v = float(self._s.value("padding", levels.DEFAULT_PADDING))
        except (TypeError, ValueError):
            return levels.DEFAULT_PADDING
        return v if 0.0 <= v <= 1.0 else levels.DEFAULT_PADDING

    @padding.setter
    def padding(self, v: float) -> None:
        if 0.0 <= v <= 1.0:
            self._s.setValue("padding", round(float(v), 2))

    @property
    def language(self) -> str | None:
        v = self._s.value("language")
        return str(v) if v in i18n.LANGUAGES else None

    @language.setter
    def language(self, v: str) -> None:
        if v in i18n.LANGUAGES:
            self._s.setValue("language", v)

    def sync(self) -> None:
        self._s.sync()
