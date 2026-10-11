"""Color themes, fonts and the application style sheet."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from manim_studio.ui.icon_set import icon_image

DARK_THEME = "dark"
LIGHT_THEME = "light"
THEMES = (DARK_THEME, LIGHT_THEME)
BASE_FONT_POINTS = 10.0
SCALES = (0.85, 1.0, 1.15, 1.3, 1.5)


@dataclass(frozen=True)
class Palette:
    """All colors used by the interface."""

    name: str
    window: str
    panel: str
    field: str
    raised: str
    hover: str
    border: str
    border_strong: str
    text: str
    text_muted: str
    text_faint: str
    accent: str
    accent_hover: str
    accent_text: str
    accent_soft: str
    danger: str
    warning: str
    success: str
    record: str
    stage_outside: str
    shadow: str


DARK = Palette(
    name=DARK_THEME,
    window="#111216",
    panel="#18191E",
    field="#101115",
    raised="#22242B",
    hover="#2B2D35",
    border="#272930",
    border_strong="#3A3C46",
    text="#E9EAEE",
    text_muted="#A2A5B0",
    text_faint="#666A76",
    accent="#58C4DD",
    accent_hover="#7DD3E7",
    accent_text="#06161B",
    accent_soft="#1C3A44",
    danger="#FC6255",
    warning="#F0AC5F",
    success="#83C167",
    record="#FF5C5C",
    stage_outside="#0B0C0F",
    shadow="#000000",
)

LIGHT = Palette(
    name=LIGHT_THEME,
    window="#ECEEF2",
    panel="#F7F8FA",
    field="#FFFFFF",
    raised="#FFFFFF",
    hover="#E4E7EC",
    border="#DADDE3",
    border_strong="#C3C7D0",
    text="#1B1D22",
    text_muted="#5C616C",
    text_faint="#9A9EA8",
    accent="#1690BD",
    accent_hover="#127BA2",
    accent_text="#FFFFFF",
    accent_soft="#D6EEF6",
    danger="#D9473A",
    warning="#C27616",
    success="#4C9A3A",
    record="#E5484D",
    stage_outside="#C9CDD4",
    shadow="#7A808C",
)

_PALETTES = {DARK_THEME: DARK, LIGHT_THEME: LIGHT}
_current = DARK
_scale = 1.0


def current_palette() -> Palette:
    """Return the active palette."""
    return _current


def ui_scale() -> float:
    """Return the active interface scale factor."""
    return _scale


def px(value: float) -> int:
    """Scale a pixel size by the interface scale."""
    return max(1, round(value * _scale))


def color(name: str) -> QColor:
    """Return a palette color as ``QColor``."""
    return QColor(getattr(_current, name))


def _qpalette(palette: Palette) -> QPalette:
    qp = QPalette()
    roles = {
        QPalette.ColorRole.Window: palette.window,
        QPalette.ColorRole.WindowText: palette.text,
        QPalette.ColorRole.Base: palette.field,
        QPalette.ColorRole.AlternateBase: palette.panel,
        QPalette.ColorRole.ToolTipBase: palette.raised,
        QPalette.ColorRole.ToolTipText: palette.text,
        QPalette.ColorRole.PlaceholderText: palette.text_faint,
        QPalette.ColorRole.Text: palette.text,
        QPalette.ColorRole.Button: palette.raised,
        QPalette.ColorRole.ButtonText: palette.text,
        QPalette.ColorRole.BrightText: palette.danger,
        QPalette.ColorRole.Highlight: palette.accent,
        QPalette.ColorRole.HighlightedText: palette.accent_text,
        QPalette.ColorRole.Link: palette.accent,
        QPalette.ColorRole.Mid: palette.border_strong,
        QPalette.ColorRole.Midlight: palette.hover,
        QPalette.ColorRole.Dark: palette.window,
        QPalette.ColorRole.Shadow: palette.shadow,
    }
    for role, value in roles.items():
        qp.setColor(role, QColor(value))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        qp.setColor(QPalette.ColorGroup.Disabled, role, QColor(palette.text_faint))
    return qp


def _style_images(palette: Palette, folder: Path) -> dict[str, str]:
    folder.mkdir(parents=True, exist_ok=True)
    images = {
        "down": ("chevron_down", palette.text_muted),
        "up": ("chevron_up", palette.text_muted),
        "check": ("check", palette.accent_text),
        "right": ("chevron_right", palette.text_muted),
    }
    paths: dict[str, str] = {}
    for key, (name, tint) in images.items():
        path = folder / f"{palette.name}_{key}.png"
        icon_image(name, tint, 32).save(str(path))
        paths[key] = path.as_posix()
    return paths


def style_sheet(palette: Palette, images: dict[str, str]) -> str:
    """Return the complete Qt style sheet for a palette."""
    p = palette
    r = px(7)
    return f"""
* {{ outline: 0; }}
QMainWindow, QDialog {{ background: {p.window}; }}
QWidget#Panel, QWidget#Inspector, QScrollArea#Inspector > QWidget > QWidget {{ background: {p.panel}; }}
QFrame#HeaderBar {{ background: {p.window}; border-bottom: 1px solid {p.border}; }}
QFrame#PanelHeader {{ background: {p.panel}; border-bottom: 1px solid {p.border}; }}
QFrame#Separator {{ background: {p.border}; max-height: 1px; min-height: 1px; border: none; }}
QSplitter::handle {{ background: {p.window}; }}
QSplitter::handle:horizontal {{ width: {px(3)}px; }}
QSplitter::handle:vertical {{ height: {px(3)}px; }}
QSplitter::handle:hover {{ background: {p.accent_soft}; }}
QToolTip {{ background: {p.raised}; color: {p.text}; border: 1px solid {p.border_strong}; border-radius: {px(6)}px; padding: {px(5)}px {px(8)}px; }}
QMenuBar {{ background: {p.window}; padding: {px(2)}px {px(4)}px; }}
QMenuBar::item {{ padding: {px(4)}px {px(9)}px; border-radius: {px(6)}px; background: transparent; color: {p.text_muted}; }}
QMenuBar::item:selected {{ background: {p.hover}; color: {p.text}; }}
QMenu {{ background: {p.raised}; border: 1px solid {p.border_strong}; border-radius: {px(9)}px; padding: {px(5)}px; }}
QMenu::item {{ padding: {px(6)}px {px(26)}px {px(6)}px {px(10)}px; border-radius: {px(6)}px; color: {p.text}; }}
QMenu::item:selected {{ background: {p.accent_soft}; }}
QMenu::item:disabled {{ color: {p.text_faint}; }}
QMenu::separator {{ height: 1px; background: {p.border}; margin: {px(5)}px {px(6)}px; }}
QMenu::icon {{ padding-left: {px(8)}px; }}
QMenu::right-arrow {{ image: url({images['right']}); width: {px(12)}px; height: {px(12)}px; }}
QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: {r}px; padding: {px(4)}px {px(7)}px; color: {p.text}; }}
QToolButton:hover {{ background: {p.hover}; }}
QToolButton:pressed {{ background: {p.border_strong}; }}
QToolButton:checked {{ background: {p.accent_soft}; color: {p.accent}; }}
QToolButton:disabled {{ color: {p.text_faint}; }}
QToolButton::menu-indicator {{ image: url({images['down']}); width: {px(10)}px; height: {px(10)}px; subcontrol-position: right center; right: {px(3)}px; }}
QToolButton[popupMode="2"] {{ padding-right: {px(16)}px; }}
QToolButton[variant="segment"] {{ border-radius: {px(6)}px; padding: {px(4)}px {px(12)}px; color: {p.text_muted}; }}
QToolButton[variant="segment"]:checked {{ background: {p.raised}; color: {p.text}; border: 1px solid {p.border_strong}; }}
QPushButton, QToolButton[variant="button"] {{ background: {p.raised}; border: 1px solid {p.border_strong}; border-radius: {px(8)}px; padding: {px(5)}px {px(13)}px; color: {p.text}; }}
QPushButton:hover, QToolButton[variant="button"]:hover {{ background: {p.hover}; }}
QPushButton:pressed {{ background: {p.border}; }}
QPushButton:disabled, QToolButton[variant="button"]:disabled {{ color: {p.text_faint}; background: {p.panel}; }}
QPushButton[variant="primary"], QToolButton[variant="primary"] {{ background: {p.accent}; color: {p.accent_text}; border: 1px solid {p.accent}; font-weight: 600; }}
QPushButton[variant="primary"]:hover, QToolButton[variant="primary"]:hover {{ background: {p.accent_hover}; border-color: {p.accent_hover}; }}
QPushButton[variant="primary"]:disabled, QToolButton[variant="primary"]:disabled {{ background: {p.accent_soft}; color: {p.text_faint}; border-color: {p.accent_soft}; }}
QPushButton[variant="danger"] {{ color: {p.danger}; }}
QPushButton[variant="tile"], QToolButton[variant="tile"] {{ background: {p.raised}; border: 1px solid {p.border}; border-radius: {px(9)}px; padding: {px(6)}px; color: {p.text}; text-align: left; }}
QPushButton[variant="tile"]:hover, QToolButton[variant="tile"]:hover {{ border-color: {p.accent}; background: {p.hover}; }}
QPushButton[variant="link"] {{ background: transparent; border: none; color: {p.accent}; padding: 0; }}
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {p.field}; border: 1px solid {p.border_strong}; border-radius: {r}px;
    padding: {px(3)}px {px(7)}px; color: {p.text};
    selection-background-color: {p.accent}; selection-color: {p.accent_text};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {p.accent}; }}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{ color: {p.text_faint}; background: {p.panel}; }}
QLineEdit[invalid="true"] {{ border-color: {p.danger}; }}
QComboBox::drop-down {{ border: none; width: {px(20)}px; }}
QComboBox::down-arrow {{ image: url({images['down']}); width: {px(12)}px; height: {px(12)}px; }}
QComboBox QAbstractItemView {{ background: {p.raised}; border: 1px solid {p.border_strong}; border-radius: {px(6)}px; selection-background-color: {p.accent_soft}; selection-color: {p.text}; padding: {px(3)}px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::down-button {{ border: none; width: {px(16)}px; background: transparent; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url({images['up']}); width: {px(10)}px; height: {px(10)}px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url({images['down']}); width: {px(10)}px; height: {px(10)}px; }}
QCheckBox {{ spacing: {px(7)}px; color: {p.text}; }}
QCheckBox::indicator {{ width: {px(15)}px; height: {px(15)}px; border-radius: {px(4)}px; border: 1px solid {p.border_strong}; background: {p.field}; }}
QCheckBox::indicator:hover {{ border-color: {p.accent}; }}
QCheckBox::indicator:checked {{ background: {p.accent}; border-color: {p.accent}; image: url({images['check']}); }}
QRadioButton::indicator {{ width: {px(14)}px; height: {px(14)}px; border-radius: {px(7)}px; border: 1px solid {p.border_strong}; background: {p.field}; }}
QRadioButton::indicator:checked {{ background: {p.accent}; border: {px(4)}px solid {p.field}; }}
QScrollBar:vertical {{ background: transparent; width: {px(10)}px; margin: {px(2)}px; }}
QScrollBar:horizontal {{ background: transparent; height: {px(10)}px; margin: {px(2)}px; }}
QScrollBar::handle {{ background: {p.border_strong}; border-radius: {px(3)}px; }}
QScrollBar::handle:vertical {{ min-height: {px(28)}px; }}
QScrollBar::handle:horizontal {{ min-width: {px(28)}px; }}
QScrollBar::handle:hover {{ background: {p.text_faint}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QTabWidget::pane {{ border: none; }}
QTabBar {{ qproperty-drawBase: 0; }}
QTabBar::tab {{ background: transparent; color: {p.text_muted}; padding: {px(5)}px {px(12)}px; border-radius: {px(7)}px; margin: {px(3)}px {px(2)}px; }}
QTabBar::tab:selected {{ background: {p.raised}; color: {p.text}; }}
QTabBar::tab:hover:!selected {{ background: {p.hover}; color: {p.text}; }}
QTabBar::close-button {{ subcontrol-position: right; }}
QListWidget, QListView, QTreeView, QTableWidget, QTableView {{ background: {p.panel}; border: none; color: {p.text}; }}
QListWidget::item, QTreeView::item {{ padding: {px(3)}px {px(4)}px; border-radius: {px(6)}px; }}
QListWidget::item:selected, QTreeView::item:selected {{ background: {p.accent_soft}; color: {p.text}; }}
QListWidget::item:hover:!selected, QTreeView::item:hover:!selected {{ background: {p.hover}; }}
QTreeView#LayerTree::item {{ border-radius: 0px; padding: {px(3)}px {px(2)}px; }}
QListView#History {{ padding: {px(6)}px; }}
QListView#History::item {{ padding: {px(4)}px {px(8)}px; border-radius: {px(6)}px; }}
QListView#History::item:selected {{ background: {p.accent_soft}; color: {p.text}; }}
QListView#History::item:hover:!selected {{ background: {p.hover}; }}
QTreeView#LayerTree::branch:selected {{ background: {p.accent_soft}; }}
QTreeView#LayerTree::branch:hover:!selected {{ background: {p.hover}; }}
QTableWidget {{ gridline-color: {p.border}; background: {p.field}; border: 1px solid {p.border_strong}; border-radius: {r}px; }}
QHeaderView::section {{ background: {p.raised}; color: {p.text_muted}; border: none; border-bottom: 1px solid {p.border}; padding: {px(4)}px; }}
QStatusBar {{ background: {p.window}; color: {p.text_muted}; border-top: 1px solid {p.border}; }}
QStatusBar::item {{ border: none; }}
QProgressBar {{ background: {p.field}; border: 1px solid {p.border}; border-radius: {px(5)}px; max-height: {px(10)}px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {p.accent}; border-radius: {px(4)}px; }}
QSlider::groove:horizontal {{ height: {px(4)}px; background: {p.border_strong}; border-radius: {px(2)}px; }}
QSlider::sub-page:horizontal {{ background: {p.accent}; border-radius: {px(2)}px; }}
QSlider::handle:horizontal {{ background: {p.text}; width: {px(12)}px; height: {px(12)}px; margin: -{px(4)}px 0; border-radius: {px(6)}px; }}
QLabel {{ color: {p.text}; background: transparent; }}
QLabel[role="muted"] {{ color: {p.text_muted}; }}
QLabel[role="faint"] {{ color: {p.text_faint}; }}
QLabel[role="section"] {{ color: {p.text_muted}; font-weight: 600; }}
QLabel[role="title"] {{ font-weight: 600; }}
QLabel[role="hint"] {{ color: {p.text_muted}; padding: {px(6)}px {px(8)}px; background: {p.raised}; border: 1px solid {p.border}; border-radius: {px(7)}px; }}
QLabel[role="warning"] {{ color: {p.warning}; }}
QLabel[role="error"] {{ color: {p.danger}; }}
QLabel[role="pill"] {{ color: {p.text_muted}; background: {p.raised}; border: 1px solid {p.border}; border-radius: {px(9)}px; padding: {px(2)}px {px(9)}px; }}
QFrame[role="card"] {{ background: {p.raised}; border: 1px solid {p.border}; border-radius: {px(10)}px; }}
QGraphicsView {{ border: none; background: {p.stage_outside}; }}
QScrollArea {{ border: none; background: transparent; }}
QGroupBox {{ border: 1px solid {p.border}; border-radius: {px(8)}px; margin-top: {px(14)}px; padding-top: {px(6)}px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: {px(10)}px; padding: 0 {px(4)}px; color: {p.text_muted}; }}
QDialogButtonBox QPushButton {{ min-width: {px(84)}px; }}
"""


def choose_font(scale: float) -> QFont:
    """Return the interface font (Inter when installed, otherwise the system font)."""
    font = QFont()
    families = set(QFontDatabase.families())
    for preferred in ("Inter", "Inter Variable", "Segoe UI Variable Text", "SF Pro Text", "Cantarell", "Noto Sans"):
        if preferred in families:
            font = QFont(preferred)
            break
    font.setPointSizeF(BASE_FONT_POINTS * scale)
    return font


def apply_theme(app: QApplication, name: str, scale: float, image_dir: Path) -> Palette:
    """Activate a theme and interface scale for the whole application."""
    global _current, _scale
    _current = _PALETTES.get(name, DARK)
    _scale = scale if scale in SCALES else 1.0
    app.setStyle("Fusion")
    app.setPalette(_qpalette(_current))
    app.setFont(choose_font(_scale))
    app.setStyleSheet(style_sheet(_current, _style_images(_current, image_dir)))
    return _current
