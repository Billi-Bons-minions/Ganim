"""Building blocks for the window chrome: panel frames, segmented controls, banners."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer, Signal
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


class Collapsible(QWidget):
    """Shows ``full`` when there is room for it, otherwise the smaller ``compact`` version.

    Used for tool bars so that the window still fits on small screens.
    """

    def __init__(self, full: QWidget, compact: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.full = full
        self.compact = compact
        for widget in (full, compact):
            widget.setParent(self)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._apply(True)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        full, compact = self.full.sizeHint(), self.compact.sizeHint()
        return QSize(full.width(), max(full.height(), compact.height()))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt API
        full, compact = self.full.sizeHint(), self.compact.sizeHint()
        return QSize(compact.width(), max(full.height(), compact.height()))

    def is_compact(self) -> bool:
        """Return ``True`` while the compact version is shown."""
        return self.compact.isVisibleTo(self)

    def _apply(self, use_full: bool) -> None:
        self.full.setVisible(use_full)
        self.compact.setVisible(not use_full)
        shown = self.full if use_full else self.compact
        width = self.width() if use_full else shown.sizeHint().width()
        shown.setGeometry(0, max(0, (self.height() - shown.sizeHint().height()) // 2), width, shown.sizeHint().height())

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._apply(self.width() >= self.full.sizeHint().width())


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


class ChoiceTile(QFrame):
    """Clickable card with icon, bold title and a wrapped description."""

    clicked = Signal()

    def __init__(self, icon_value, title: str, text: str, primary: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        palette = current_palette()
        background = palette.accent if primary else palette.raised
        foreground = palette.accent_text if primary else palette.text
        muted = palette.accent_text if primary else palette.text_muted
        hover = palette.accent_hover if primary else palette.hover
        self.setObjectName("ChoiceTile")
        self.setStyleSheet(
            f"QFrame#ChoiceTile {{ background: {background}; border: 1px solid {palette.border if not primary else background};"
            f" border-radius: {px(10)}px; }} QFrame#ChoiceTile:hover {{ background: {hover}; border-color: {palette.accent}; }}"
            f" QFrame#ChoiceTile:disabled {{ background: {palette.panel}; }}"
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(px(210), px(70))
        picture = QLabel()
        picture.setPixmap(icon_value.pixmap(QSize(px(26), px(26))))
        picture.setFixedWidth(px(30))
        title_label = QLabel(title)
        font = title_label.font()
        font.setBold(True)
        title_label.setFont(font)
        title_label.setStyleSheet(f"color: {foreground};")
        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setStyleSheet(f"color: {muted};")
        texts = QVBoxLayout()
        texts.setSpacing(px(2))
        texts.addWidget(title_label)
        texts.addWidget(text_label)
        row = QHBoxLayout(self)
        row.setContentsMargins(px(12), px(10), px(12), px(10))
        row.setSpacing(px(10))
        row.addWidget(picture, 0, Qt.AlignmentFlag.AlignTop)
        row.addLayout(texts, 1)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled() and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class Toast(QLabel):
    """Short notification that fades out by itself (placed by its parent)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWordWrap(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setMaximumWidth(px(520))
        self._timer = QTimer(self, singleShot=True, interval=3200)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def show_message(self, text: str) -> None:
        """Show ``text`` for a few seconds."""
        palette = current_palette()
        self.setStyleSheet(
            f"QLabel {{ background: {palette.accent}; color: {palette.accent_text}; border-radius: {px(9)}px;"
            f" padding: {px(7)}px {px(14)}px; font-weight: 600; }}"
        )
        self.setText(text)
        self.adjustSize()
        self.show()
        self.raise_()
        self._timer.start()


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
