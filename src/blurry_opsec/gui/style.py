"""Look: Chrono's design language on top of the system's window material.

Black, glass panels with 1 px hairlines, white and grey text, one green
accent, monospace labels in capitals. On macOS the window background is the
system's own blurred material (see native.py); elsewhere it is plain black.
"""

from __future__ import annotations

from pathlib import Path

# Tokens (from Chrono's design system: --sfondo-primario, --bordo-base,
# --testo-secondario, --verde-500/600, --arancione-600, --rosso-600).
BG = "#000000"
TEXT = "#ffffff"
MUTED = "#888888"
DIM = "#525252"
LINE = "rgba(255, 255, 255, 0.10)"
LINE_HOVER = "rgba(255, 255, 255, 0.30)"
GLASS = "rgba(255, 255, 255, 0.035)"
GLASS_HOVER = "rgba(255, 255, 255, 0.07)"
GLASS_ACTIVE = "rgba(255, 255, 255, 0.12)"
ACCENT = "#49dc18"  # text and hairlines
ACCENT_FILL = "#6bf93d"  # small fills, dots
WARN = "#fb923c"
DANGER = "#ef4444"

# Boxes on the canvas
AUTO = ACCENT  # found by the detector
MANUAL = TEXT  # added by hand
OFF = DIM  # a track turned off
SURFACE = "#0a0a0a"  # canvas and timeline ground

FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"
MONO_FILE = FONT_DIR / "GeistMono-Medium.otf"
MONO = "Geist Mono"


def qss(glass_window: bool) -> str:
    """Stylesheet. With the native glass the root is a dark tint over it."""
    root = "rgba(0, 0, 0, 0.62)" if glass_window else BG
    return f"""
* {{ color: {TEXT}; font-size: 13px; }}
QWidget#root {{ background: {root}; }}
QStackedWidget, QWidget#page {{ background: transparent; }}
QToolTip {{ background: #111111; color: {TEXT}; border: 1px solid {LINE}; padding: 4px 6px; }}

/* Typography */
QLabel#wordmark {{ font-family: "{MONO}"; font-size: 13px; letter-spacing: 5px; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#hint {{ color: {MUTED}; font-size: 12px; }}
QLabel#label {{ font-family: "{MONO}"; color: {MUTED}; font-size: 10px; letter-spacing: 1.5px; }}
QLabel#value {{ font-family: "{MONO}"; color: {TEXT}; font-size: 10px; letter-spacing: 1px; }}
QLabel#chip {{ font-family: "{MONO}"; color: {ACCENT}; font-size: 10px; letter-spacing: 2px;
  border: 1px solid rgba(73, 220, 24, 0.45); border-radius: 3px; padding: 2px 7px; }}
QLabel#warning {{ color: {WARN}; font-size: 12px; }}
QLabel#banner, QLabel#bannerInfo {{ border-radius: 8px; padding: 9px 12px; font-size: 12px; }}
QLabel#banner {{ background: rgba(239, 68, 68, 0.10); border: 1px solid rgba(239, 68, 68, 0.55); }}
QLabel#bannerInfo {{ background: rgba(251, 146, 60, 0.08); border: 1px solid rgba(251, 146, 60, 0.45); }}

/* Glass panels */
QFrame#glass {{ background: {GLASS}; border: 1px solid {LINE}; border-radius: 10px; }}
QFrame#drop {{ background: {GLASS}; border: 1px dashed rgba(255, 255, 255, 0.18);
  border-radius: 10px; }}
QFrame#drop[active="true"] {{ background: rgba(73, 220, 24, 0.06);
  border: 1px solid rgba(73, 220, 24, 0.7); }}
QLabel#dropTitle {{ font-size: 17px; font-weight: 500; }}
QLabel#dropFormats {{ font-family: "{MONO}"; color: {MUTED}; font-size: 10px; letter-spacing: 1.5px; }}

/* Buttons */
QPushButton {{ background: {GLASS}; border: 1px solid {LINE}; border-radius: 6px; padding: 6px 13px; }}
QPushButton:hover {{ background: {GLASS_HOVER}; border-color: {LINE_HOVER}; }}
QPushButton:pressed {{ background: {GLASS_ACTIVE}; }}
QPushButton:disabled {{ color: {DIM}; border-color: rgba(255, 255, 255, 0.05); background: transparent; }}
QPushButton#primary {{ background: {TEXT}; color: {BG}; border-color: {TEXT}; font-weight: 600; }}
QPushButton#primary:hover {{ background: #e6e6e6; }}
QPushButton#primary:disabled {{ background: rgba(255, 255, 255, 0.12); color: {DIM};
  border-color: transparent; }}
QPushButton#link {{ background: transparent; border: none; color: {MUTED}; padding: 2px 4px; }}
QPushButton#link:hover {{ color: {TEXT}; }}
QPushButton#seg {{ font-family: "{MONO}"; font-size: 10px; letter-spacing: 1.2px; color: {MUTED};
  background: transparent; border: none; border-radius: 5px; padding: 6px 8px; }}
QPushButton#seg:hover {{ color: {TEXT}; }}
QPushButton#seg:checked {{ color: {TEXT}; background: {GLASS_ACTIVE}; }}
QFrame#segmented {{ background: rgba(255, 255, 255, 0.03); border: 1px solid {LINE};
  border-radius: 7px; }}

/* Lists */
QTreeWidget, QListWidget {{ background: transparent; border: none; outline: none; }}
QTreeWidget::item, QListWidget::item {{ padding: 6px 4px; border-bottom: 1px solid rgba(255, 255, 255, 0.05); }}
QTreeWidget::item:hover, QListWidget::item:hover {{ background: rgba(255, 255, 255, 0.04); }}
QTreeWidget::item:selected, QListWidget::item:selected {{ background: rgba(255, 255, 255, 0.09);
  color: {TEXT}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{ background: transparent; color: {MUTED}; border: none;
  border-bottom: 1px solid {LINE}; padding: 6px 4px; font-family: "{MONO}"; font-size: 10px;
  letter-spacing: 1.5px; }}
QListWidget::indicator, QTreeWidget::indicator {{ width: 12px; height: 12px; border-radius: 3px;
  border: 1px solid {MUTED}; background: transparent; }}
QListWidget::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

/* Inputs */
QDoubleSpinBox, QSpinBox {{ background: {GLASS}; border: 1px solid {LINE}; border-radius: 6px;
  padding: 4px 6px; font-family: "{MONO}"; font-size: 11px; }}
QSlider::groove:horizontal {{ height: 1px; background: rgba(255, 255, 255, 0.18); }}
QSlider::sub-page:horizontal {{ background: {TEXT}; }}
QSlider {{ min-height: 16px; }}
QSlider::handle:horizontal {{ background: {TEXT}; border: none; width: 12px; height: 12px;
  margin: -6px 0; border-radius: 6px; }}

/* Canvas */
QGraphicsView {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 10px; }}
QScrollBar:vertical {{ background: transparent; width: 6px; }}
QScrollBar::handle:vertical {{ background: rgba(255, 255, 255, 0.18); border-radius: 3px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QStatusBar {{ background: transparent; color: {MUTED}; }}
/* Lifecycle panels use explicit dark surfaces instead of the system palette. */
QWidget#lifecyclePage, QTabWidget::pane {{ background: {SURFACE}; }}
QTabWidget::pane {{ border: 1px solid {LINE}; border-radius: 6px; }}
QTabBar::tab {{ background: {SURFACE}; color: {MUTED}; padding: 9px 14px;
  border: 1px solid {LINE}; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; }}
QComboBox {{ background: {SURFACE}; color: {TEXT}; padding: 7px 10px;
  border: 1px solid {LINE_HOVER}; border-radius: 5px; }}
QComboBox QAbstractItemView {{ background: {SURFACE}; color: {TEXT};
  selection-background-color: #333333; }}
QLabel#body {{ color: {TEXT}; font-size: 13px; }}
QLabel#guideHeading {{ color: {TEXT}; font-size: 17px; font-weight: 600; }}
QDialog {{ background: #0b0b0b; }}
QMessageBox {{ background: #0b0b0b; }}
"""
