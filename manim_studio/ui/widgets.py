"""Small reusable input widgets."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFocusEvent, QIcon, QPainter, QPixmap, QValidator
from PySide6.QtWidgets import (
    QColorDialog,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QToolButton,
    QWidget,
)

from manim_studio.i18n import tr
from manim_studio.model.expression import evaluate_number
from manim_studio.model.types import MANIM_COLORS

DEBOUNCE_MS = 450


def color_icon(color: str, size: int = 16) -> QIcon:
    """Return a square icon filled with ``color``."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setPen(QColor("#777777"))
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(1, 1, size - 2, size - 2, 3, 3)
    painter.end()
    return QIcon(pixmap)


class ColorButton(QToolButton):
    """Shows a color; offers Manim's palette and a free color dialog."""

    colorChosen = Signal(str)

    def __init__(self, color: str = "#FFFFFF", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setIconSize(QSize(18, 18))
        menu = QMenu(self)
        for name, value in MANIM_COLORS.items():
            action = menu.addAction(color_icon(value), tr(f"color.{name}"))
            action.triggered.connect(lambda _checked=False, v=value: self._choose(v))
        menu.addSeparator()
        custom = QAction(tr("widget.color_more"), menu)
        custom.triggered.connect(self._open_dialog)
        menu.addAction(custom)
        self.setMenu(menu)
        self._refresh()

    def color(self) -> str:
        """Return the current color as ``#RRGGBB``."""
        return self._color

    def set_color(self, color: str) -> None:
        """Show ``color`` without emitting :attr:`colorChosen`."""
        self._color = color
        self._refresh()

    def _refresh(self) -> None:
        self.setIcon(color_icon(self._color, 18))
        names = [name for name, value in MANIM_COLORS.items() if value.upper() == self._color.upper()]
        self.setText(tr(f"color.{names[0]}") if names else self._color.upper())

    def _choose(self, color: str) -> None:
        self._color = color.upper()
        self._refresh()
        self.colorChosen.emit(self._color)

    def _open_dialog(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._color), self, tr("widget.color_title"))
        if chosen.isValid():
            self._choose(chosen.name().upper())


class DebouncedLineEdit(QLineEdit):
    """Line edit that emits :attr:`committed` shortly after typing stops."""

    committed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self, singleShot=True, interval=DEBOUNCE_MS)
        self._timer.timeout.connect(lambda: self.committed.emit(self.text()))
        self.textEdited.connect(lambda _text: self._timer.start())
        self.editingFinished.connect(self._flush)

    def _flush(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
            self.committed.emit(self.text())


class DebouncedTextEdit(QPlainTextEdit):
    """Multi-line editor that commits after a pause or when focus leaves."""

    committed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self, singleShot=True, interval=DEBOUNCE_MS)
        self._timer.timeout.connect(lambda: self.committed.emit(self.toPlainText()))
        self.textChanged.connect(self._on_changed)
        self._silent = False
        self.setTabChangesFocus(True)

    def set_text_silently(self, text: str) -> None:
        """Replace the text without emitting :attr:`committed`."""
        if text == self.toPlainText():
            return
        self._silent = True
        self.setPlainText(text)
        self._silent = False

    def _on_changed(self) -> None:
        if not self._silent:
            self._timer.start()

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802 - Qt API
        if self._timer.isActive():
            self._timer.stop()
            self.committed.emit(self.toPlainText())
        super().focusOutEvent(event)


class SpinBox(QDoubleSpinBox):
    """Double spin box that only commits on Enter, focus loss or arrow clicks.

    Besides plain numbers it accepts small terms such as ``pi/2`` or ``3*1.5``.
    """

    def __init__(self, minimum: float, maximum: float, step: float, decimals: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setRange(minimum, maximum)
        self.setSingleStep(step)
        self.setDecimals(decimals)
        self.setKeyboardTracking(False)
        self.setAccelerated(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()

    def validate(self, text: str, position: int) -> object:
        value = evaluate_number(text)
        if value is not None and self.minimum() <= value <= self.maximum():
            return QValidator.State.Acceptable, text, position
        return QValidator.State.Intermediate, text, position

    def valueFromText(self, text: str) -> float:  # noqa: N802 - Qt API
        value = evaluate_number(text)
        return self.value() if value is None else max(self.minimum(), min(self.maximum(), value))

    def fixup(self, text: str) -> str:
        value = evaluate_number(text)
        return self.textFromValue(self.value() if value is None else value)


class FileField(QWidget):
    """Path line edit with a browse button."""

    committed = Signal(str)

    def __init__(self, file_filter: str, start_dir: Callable[[], str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._filter = file_filter
        self._start_dir = start_dir
        self.edit = QLineEdit()
        self.edit.editingFinished.connect(lambda: self.committed.emit(self.edit.text()))
        button = QToolButton()
        button.setText("…")
        button.setToolTip(tr("widget.browse"))
        button.clicked.connect(self._browse)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit, 1)
        layout.addWidget(button)

    def set_path(self, path: str) -> None:
        """Show ``path`` without emitting :attr:`committed`."""
        if not self.edit.hasFocus():
            self.edit.setText(path)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("widget.choose_file"), self._start_dir(), self._filter)
        if path:
            self.edit.setText(path)
            self.committed.emit(path)
