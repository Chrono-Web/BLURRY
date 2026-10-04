"""The interface language, Italian or English. No i18n library.

The strings themselves are in gui/strings.py, the same table as the Mac app's
Strings.swift.
"""

from __future__ import annotations

LANGUAGES = {"it": "Italiano", "en": "English"}
_current = "en"


def set_language(lang: str) -> None:
    global _current
    _current = lang if lang in LANGUAGES else "en"


def language() -> str:
    return _current
