"""Building blocks for the window chrome: panel frames, segmented controls, banners."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from manim_studio.ui.icon_set import icon
from manim_studio.ui.theme import current_palette, px


def tool_button(icon_name: str, tooltip: str, slot=None, text: str = "", checkable: bool = False) -> QToolButton:
    """Return a flat icon button (optionally with text)."""
    button = QToolButton()
    button.setIcon(icon(icon_name))
    button.setIconSize(QSize(px(18), px(18)))
    button.setToolTip(tooltip)
    button.setCheckable(checkable)
    if text:
        button.setText(text)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    if slot is not None:
        button.clicked.connect(slot)
    return button


def action_button(action: QAction, show_text: bool = False, variant: str = "") -> QToolButton:
    """Return a tool button bound to an action."""
    button = QToolButton()
    button.setDefaultAction(action)
    button.setIconSize(QSize(px(18), px(18)))
    if show_text:
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    else:
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    if variant:
        button.setProperty("variant", variant)
    return button


def separator(vertical: bool = False) -> QFrame:
    """Return a thin separator line."""
    line = QFrame()
    line.setObjectName("Separator")
    if vertical:
        line.setFixedWidth(1)
        line.setMinimumHeight(px(18))
        line.setStyleSheet(f"background: {current_palette().border}; max-height: none;")
    return line


class PanelFrame(QWidget):
    """A side panel with a title row and optional header buttons."""

    def __init__(self, title: str, content: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        header = QFrame()
        header.setObjectName("PanelHeader")
        self.header_layout = QHBoxLayout(header)
        self.header_layout.setContentsMargins(px(12), px(6), px(6), px(6))
        self.title = QLabel(title)
        self.title.setProperty("role", "title")
        self.header_layout.addWidget(self.title)
        self.header_layout.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(content, 1)

    def add_header_widget(self, widget: QWidget) -> None:
        """Put a small widget (e.g. a button) at the right of the title."""
        self.header_layout.addWidget(widget)


class SegmentedControl(QWidget):
    """A row of mutually exclusive buttons (like a tab switch)."""

    changed = Signal(int)

    def __init__(self, labels: list[tuple[str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(px(2), px(2), px(2), px(2))
        layout.setSpacing(px(2))
        self.setStyleSheet(
            f"SegmentedControl {{ background: {current_palette().field}; border: 1px solid {current_palette().border};"
            f" border-radius: {px(8)}px; }}"
        )
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        for index, (icon_name, text) in enumerate(labels):
            button = QToolButton()
            button.setCheckable(True)
            button.setProperty("variant", "segment")
            button.setText(text)
            if icon_name:
                button.setIcon(icon(icon_name))
                button.setIconSize(QSize(px(16), px(16)))
                button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            self.group.addButton(button, index)
            layout.addWidget(button)
        self.group.button(0).setChecked(True)
        self.group.idToggled.connect(lambda index, checked: checked and self.changed.emit(index))

    def set_current(self, index: int) -> None:
        """Select a segment without emitting :attr:`changed`."""
        button = self.group.button(index)
        if button is not None and not button.isChecked():
            self.group.blockSignals(True)
            button.setChecked(True)
            self.group.blockSignals(False)

    def current(self) -> int:
        """Return the selected segment index."""
        return self.group.checkedId()


class StageBanner(QLabel):
    """Pill on top of the stage telling the user what editing does right now."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

    def show_message(self, html: str, recording: bool) -> None:
        """Display a message; ``recording`` uses the red record style."""
        palette = current_palette()
        border = palette.record if recording else palette.border_strong
        self.setStyleSheet(
            f"QLabel {{ background: {palette.raised}; color: {palette.text}; border: 1px solid {border};"
            f" border-radius: {px(13)}px; padding: {px(4)}px {px(12)}px; }}"
        )
        self.setText(html)
        self.adjustSize()
