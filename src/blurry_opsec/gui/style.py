"""Sober dark style: thin lines, muted surfaces, one accent per meaning."""

BG = "#0e1014"
SURFACE = "#161a20"
SURFACE_2 = "#1d222a"
BORDER = "#2b313b"
TEXT = "#e7e9ec"
MUTED = "#8b94a3"
AUTO = "#f5b83d"  # boxes found by the detector
MANUAL = "#4fd1c5"  # boxes added by hand
DANGER = "#ff6b6b"
OK = "#5ccf8f"

QSS = f"""
* {{ color: {TEXT}; font-size: 13px; }}
QMainWindow, QWidget#root {{ background: {BG}; }}
QWidget#panel {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px; }}
QLabel#wordmark {{ font-size: 15px; font-weight: 700; letter-spacing: 4px; }}
QLabel#muted, QLabel#hint {{ color: {MUTED}; }}
QLabel#hint {{ font-size: 12px; }}
QLabel#section {{ color: {MUTED}; font-size: 11px; font-weight: 600; letter-spacing: 1.5px; }}
QLabel#chip {{ color: {OK}; border: 1px solid {OK}; border-radius: 3px; padding: 1px 6px;
  font-size: 10px; font-weight: 700; letter-spacing: 1.5px; }}
QLabel#warning {{ color: {DANGER}; font-size: 12px; }}
QLabel#banner {{ background: #3a1d1f; color: #ffd9d9; border: 1px solid {DANGER};
  border-radius: 4px; padding: 8px 10px; }}
QLabel#bannerInfo {{ background: #3a2f17; color: #ffe9bf; border: 1px solid {AUTO};
  border-radius: 4px; padding: 8px 10px; }}
QFrame#drop {{ border: 1px dashed {BORDER}; border-radius: 8px; background: {SURFACE}; }}
QFrame#drop[active="true"] {{ border: 1px solid {MANUAL}; background: #13232a; }}
QLabel#dropTitle {{ font-size: 18px; font-weight: 600; }}
QPushButton {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 4px;
  padding: 6px 12px; }}
QPushButton:hover {{ border-color: {MUTED}; }}
QPushButton:disabled {{ color: #59606c; border-color: #23282f; }}
QPushButton#primary {{ background: {TEXT}; color: {BG}; border-color: {TEXT}; font-weight: 600; }}
QPushButton#primary:disabled {{ background: #3a3f47; color: #6c727c; border-color: #3a3f47; }}
QPushButton#link {{ background: transparent; border: none; color: {MUTED}; padding: 2px 4px; }}
QPushButton#link:hover {{ color: {TEXT}; }}
QTreeWidget, QListWidget {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px;
  alternate-background-color: #181c23; outline: none; }}
QTreeWidget::item, QListWidget::item {{ padding: 4px 2px; }}
QTreeWidget::item:selected, QListWidget::item:selected {{ background: #26303c; color: {TEXT}; }}
QHeaderView::section {{ background: {SURFACE}; color: {MUTED}; border: none;
  border-bottom: 1px solid {BORDER}; padding: 5px 6px; font-size: 11px; }}
QComboBox, QSpinBox, QDoubleSpinBox {{ background: {SURFACE_2}; border: 1px solid {BORDER};
  border-radius: 4px; padding: 4px 8px; }}
QComboBox QAbstractItemView {{ background: {SURFACE_2}; border: 1px solid {BORDER};
  selection-background-color: #26303c; }}
QSlider::groove:horizontal {{ height: 2px; background: {BORDER}; }}
QSlider::handle:horizontal {{ background: {TEXT}; width: 10px; height: 10px; margin: -4px 0;
  border-radius: 5px; }}
QSlider::sub-page:horizontal {{ background: {MUTED}; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 12px; height: 12px;
  border: 1px solid {MUTED}; background: {SURFACE_2}; }}
QRadioButton::indicator {{ border-radius: 7px; }}
QCheckBox::indicator {{ border-radius: 3px; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{ background: {TEXT};
  border-color: {TEXT}; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {TEXT}; }}
QProgressBar {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 3px;
  height: 6px; text-align: center; font-size: 1px; }}
QProgressBar::chunk {{ background: {TEXT}; }}
QGraphicsView {{ background: #08090b; border: 1px solid {BORDER}; border-radius: 6px; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QToolTip {{ background: {SURFACE_2}; color: {TEXT}; border: 1px solid {BORDER}; }}
"""
