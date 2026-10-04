"""Look: the Mac app's, on Windows and Linux.

A dark window, the system font, white and grey text, one green accent, a few
monospace capitals for labels, hairlines instead of boxes. The primary action
is a white button with black text. On macOS (development only) the window
background is the system's own blurred material (see native.py).
"""

from __future__ import annotations

from pathlib import Path

BG = "#1e1e1e"  # the Mac's dark window material, without the blur
TEXT = "#ffffff"
SECONDARY = "#9b9b9f"
TERTIARY = "#5f5f63"
HAIRLINE = "rgba(255, 255, 255, 0.10)"
ACCENT = "#49dc18"
ORANGE = "#ff9f0a"
RED = "#ff453a"
POPOVER = "#2b2b2d"

FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"
MONO_FILE = FONT_DIR / "GeistMono-Medium.otf"
MONO = "Geist Mono"


def qss(glass_window: bool) -> str:
    """Stylesheet. With the native glass the root is a dark tint over it."""
    root = "rgba(30, 30, 30, 0.55)" if glass_window else BG
    main = "transparent" if glass_window else BG
    return f"""
* {{ color: {TEXT}; font-size: 13px; }}
QMainWindow {{ background: {main}; }}
QDialog, QWidget#queueWindow {{ background: {BG}; }}
QWidget#root {{ background: {root}; }}
QWidget#page, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}
QToolTip {{ background: {POPOVER}; color: {TEXT}; border: 1px solid {HAIRLINE}; padding: 4px 6px; }}

/* Type, as SwiftUI names it */
QLabel#title2 {{ font-size: 21px; font-weight: 600; }}
QLabel#title3 {{ font-size: 16px; font-weight: 500; }}
QLabel#subtitle {{ font-size: 16px; }}
QLabel#secondary {{ color: {SECONDARY}; }}
QLabel#callout {{ font-size: 12px; }}
QLabel#calloutSecondary {{ font-size: 12px; color: {SECONDARY}; }}
QLabel#caption {{ font-size: 11px; color: {SECONDARY}; }}
QLabel#captionOrange {{ font-size: 11px; color: {ORANGE}; }}
QLabel#captionRed {{ font-size: 12px; color: {RED}; }}
QLabel#accent {{ color: {ACCENT}; }}
QLabel#mono {{ font-family: "{MONO}"; font-size: 12px; }}
QLabel#monoSmall {{ font-family: "{MONO}"; font-size: 11px; color: {SECONDARY}; }}
QLabel#section {{ font-family: "{MONO}"; font-size: 10px; letter-spacing: 1.5px; color: {SECONDARY}; }}
QLabel#formHeader {{ font-size: 12px; font-weight: 600; color: {SECONDARY}; }}

/* Buttons: system grey; the one primary action white */
QPushButton {{ background: rgba(255, 255, 255, 0.11); border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 6px; padding: 4px 12px; }}
QPushButton:hover {{ background: rgba(255, 255, 255, 0.15); }}
QPushButton:pressed {{ background: rgba(255, 255, 255, 0.22); }}
QPushButton:disabled {{ color: {TERTIARY}; background: rgba(255, 255, 255, 0.05); }}
QPushButton:focus {{ border-color: rgba(73, 220, 24, 0.6); }}
QPushButton#large {{ padding: 8px 18px; border-radius: 8px; }}
QPushButton#small {{ padding: 2px 10px; font-size: 12px; }}
QPushButton#primary {{ background: {TEXT}; color: #000000; font-weight: 600; border: none;
  border-radius: 8px; padding: 9px 18px; }}
QPushButton#primary:hover {{ background: #ececec; }}
QPushButton#primary:pressed {{ background: #cfcfcf; }}
QPushButton#primary:disabled {{ background: rgba(255, 255, 255, 0.08); color: rgba(255, 255, 255, 0.35); }}
QPushButton#primary:focus {{ border: 2px solid rgba(73, 220, 24, 0.7); padding: 7px 16px; }}
QPushButton#link {{ background: transparent; border: none; color: {ACCENT}; padding: 2px 0; }}
QPushButton#link:hover {{ color: #7af04f; }}
QPushButton#quiet {{ background: transparent; border: none; color: {SECONDARY}; padding: 2px 0;
  font-size: 12px; }}
QPushButton#quiet:hover {{ color: {TEXT}; }}
QPushButton#destructive {{ color: {RED}; }}
QPushButton#capsule {{ background: rgba(40, 40, 42, 0.92); border: 1px solid {HAIRLINE};
  border-radius: 13px; padding: 5px 11px; font-size: 12px; font-weight: 500; }}
QPushButton#capsule:hover {{ background: rgba(60, 60, 62, 0.95); }}
QPushButton#capsule[warn="true"] {{ color: {ORANGE}; }}
QPushButton#play {{ background: rgba(255, 255, 255, 0.08); border: none; border-radius: 14px;
  padding: 0; min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px; }}
QPushButton#play:hover {{ background: rgba(255, 255, 255, 0.14); }}
QFrame#badge {{ background: rgba(40, 40, 42, 0.92); border: 1px solid {HAIRLINE}; border-radius: 13px; }}
QFrame#badge QLabel {{ font-size: 12px; font-weight: 500; background: transparent; }}

/* Controls */
QSlider {{ min-height: 20px; }}
QSlider::groove:horizontal {{ height: 4px; border-radius: 2px; background: rgba(255, 255, 255, 0.16); }}
QSlider::sub-page:horizontal {{ height: 4px; border-radius: 2px; background: {ACCENT}; }}
QSlider::handle:horizontal {{ background: {TEXT}; border: none; width: 16px; height: 16px;
  margin: -6px 0; border-radius: 8px; }}
QSlider::handle:horizontal:disabled {{ background: {TERTIARY}; }}
QComboBox {{ background: rgba(255, 255, 255, 0.11); border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 6px; padding: 4px 10px; min-width: 130px; }}
QComboBox:hover {{ background: rgba(255, 255, 255, 0.15); }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: none; width: 0; height: 0; }}
QComboBox QAbstractItemView {{ background: {POPOVER}; border: 1px solid {HAIRLINE};
  selection-background-color: rgba(73, 220, 24, 0.35); outline: none; padding: 4px; }}
QLineEdit {{ background: rgba(255, 255, 255, 0.07); border: 1px solid {HAIRLINE}; border-radius: 6px;
  padding: 5px 8px; selection-background-color: rgba(73, 220, 24, 0.45); }}
QLineEdit:focus {{ border-color: rgba(73, 220, 24, 0.7); }}
QProgressBar {{ background: rgba(255, 255, 255, 0.14); border: none; border-radius: 2px;
  max-height: 4px; min-height: 4px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 2px; }}

/* Grouped settings */
QFrame#group {{ background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 9px; }}
QFrame#group QLabel, QFrame#group QWidget#row {{ background: transparent; }}
QFrame#separator {{ background: rgba(255, 255, 255, 0.07); border: none; max-height: 1px; min-height: 1px; }}

/* Lists */
QListWidget, QTreeView {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ border-radius: 6px; margin: 1px 6px; }}
QListWidget::item:hover {{ background: rgba(255, 255, 255, 0.04); }}
QListWidget::item:selected {{ background: rgba(73, 220, 24, 0.22); }}
QTreeView::item {{ padding: 4px 2px; }}
QTreeView::item:selected {{ background: rgba(73, 220, 24, 0.28); color: {TEXT}; }}
QHeaderView::section {{ background: transparent; color: {SECONDARY}; border: none;
  border-bottom: 1px solid {HAIRLINE}; padding: 4px; font-size: 11px; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: rgba(255, 255, 255, 0.20); border-radius: 4px; min-height: 24px; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; }}
QScrollBar::handle:horizontal {{ background: rgba(255, 255, 255, 0.20); border-radius: 4px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}

/* Menus and message boxes */
QMenuBar {{ background: transparent; padding: 2px 4px; }}
QMenuBar::item {{ background: transparent; padding: 4px 9px; border-radius: 5px; }}
QMenuBar::item:selected {{ background: rgba(255, 255, 255, 0.10); }}
QMenu {{ background: {POPOVER}; border: 1px solid {HAIRLINE}; border-radius: 8px; padding: 5px; }}
QMenu::item {{ padding: 5px 22px 5px 12px; border-radius: 5px; }}
QMenu::item:selected {{ background: rgba(73, 220, 24, 0.35); }}
QMenu::item:disabled {{ color: {TERTIARY}; }}
QMenu::separator {{ height: 1px; background: {HAIRLINE}; margin: 5px 8px; }}
QMessageBox {{ background: {POPOVER}; }}
QMessageBox QLabel {{ background: transparent; }}
QWidget#tip QLabel {{ background: transparent; }}
"""
