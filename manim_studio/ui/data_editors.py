"""Inspector editors for structured parameters: fonts, points, tables, word colors."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QCompleter,
    QHBoxLayout,
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from manim_studio.i18n import tr
from manim_studio.model.expression import evaluate_number
from manim_studio.ui.icon_set import icon
from manim_studio.ui.theme import px
from manim_studio.ui.widgets import ColorButton

MAX_TABLE_ROWS = 6


class FontPicker(QComboBox):
    """Editable list of installed font families; empty means Manim's default font."""

    committed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(8)
        self.addItem(tr("widget.font_default"), "")
        for family in QFontDatabase.families():
            if not QFontDatabase.isPrivateFamily(family):
                self.addItem(family, family)
        completer = QCompleter([self.itemText(i) for i in range(self.count())], self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.setCompleter(completer)
        self.setMaxVisibleItems(18)
        self.activated.connect(lambda _index: self._commit())
        self.lineEdit().editingFinished.connect(self._commit)
        self._value = ""

    def _commit(self) -> None:
        text = self.currentText().strip()
        value = "" if text in ("", tr("widget.font_default")) else text
        if value != self._value:
            self._value = value
            self.committed.emit(value)

    def set_value(self, value: Any) -> None:
        """Show a font without emitting :attr:`committed`."""
        self._value = str(value or "")
        self.blockSignals(True)
        index = self.findData(self._value)
        if index >= 0:
            self.setCurrentIndex(index)
        else:
            self.setEditText(self._value)
        if self._value:
            font = QFont(self.font())
            font.setFamily(self._value)
            self.lineEdit().setFont(font)
        self.blockSignals(False)


class _GridEditor(QWidget):
    """Base class: a compact table with add/remove buttons below it."""

    committed = Signal(object)

    def __init__(self, columns: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.table = QTableWidget(0, len(columns))
        self.table.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.table.setMinimumWidth(px(120))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.verticalHeader().setDefaultSectionSize(px(26))
        self.table.verticalHeader().setMinimumWidth(px(22))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.table.itemChanged.connect(self._on_item_changed)
        self.buttons = QHBoxLayout()
        self.buttons.setContentsMargins(0, 0, 0, 0)
        self.buttons.setSpacing(px(2))
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(px(3))
        column.addWidget(self.table)
        column.addLayout(self.buttons)
        self._loading = False

    def add_button(self, icon_name: str, tooltip: str, slot) -> QToolButton:
        button = QToolButton()
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setIcon(icon(icon_name))
        button.setIconSize(QSize(px(14), px(14)))
        button.setToolTip(tooltip)
        button.clicked.connect(slot)
        self.buttons.addWidget(button)
        return button

    def finish_buttons(self) -> None:
        self.buttons.addStretch(1)

    def _fit_height(self) -> None:
        rows = min(self.table.rowCount(), MAX_TABLE_ROWS)
        header = self.table.horizontalHeader().height() if self.table.horizontalHeader().isVisible() else 0
        self.table.setFixedHeight(header + rows * self.table.verticalHeader().defaultSectionSize() + px(6))

    def _cell(self, row: int, column: int) -> str:
        item = self.table.item(row, column)
        return item.text() if item is not None else ""

    def _set_cell(self, row: int, column: int, text: str) -> None:
        item = self.table.item(row, column)
        if item is None:
            self.table.setItem(row, column, QTableWidgetItem(text))
        elif item.text() != text:
            item.setText(text)

    def _on_item_changed(self, _item: QTableWidgetItem) -> None:
        if not self._loading:
            self.committed.emit(self.value())

    def _current_row(self) -> int:
        row = self.table.currentRow()
        return row if row >= 0 else self.table.rowCount() - 1

    def value(self) -> Any:  # pragma: no cover - overridden
        raise NotImplementedError


class PointsEditor(_GridEditor):
    """Vertices of a polygon as an x/y table (terms like ``sqrt(2)`` are allowed)."""

    MIN_POINTS = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(["x", "y"], parent)
        self.add_button("plus", tr("widget.add_point"), self._add)
        self.remove_button = self.add_button("minus", tr("widget.remove_point"), self._remove)
        self.finish_buttons()
        self._points: list[list[float]] = []

    def set_value(self, value: Any) -> None:
        points = [[float(x), float(y)] for x, y in (value or [])]
        if self.table.state() == QAbstractItemView.State.EditingState and len(points) == len(self._points):
            return
        self._points = points
        self._loading = True
        self.table.setRowCount(len(points))
        for row, (x, y) in enumerate(points):
            self._set_cell(row, 0, f"{x:g}")
            self._set_cell(row, 1, f"{y:g}")
        self._loading = False
        self.remove_button.setEnabled(len(points) > self.MIN_POINTS)
        self._fit_height()

    def value(self) -> list[list[float]]:
        result = []
        for row in range(self.table.rowCount()):
            fallback = self._points[row] if row < len(self._points) else [0.0, 0.0]
            x = evaluate_number(self._cell(row, 0))
            y = evaluate_number(self._cell(row, 1))
            result.append([round(x if x is not None else fallback[0], 4), round(y if y is not None else fallback[1], 4)])
        return result

    def _add(self) -> None:
        points = self.value()
        row = self._current_row()
        if points:
            first = points[row]
            second = points[(row + 1) % len(points)]
            new = [round((first[0] + second[0]) / 2, 4), round((first[1] + second[1]) / 2, 4)]
        else:
            new = [0.0, 0.0]
        points.insert(row + 1, new)
        self.committed.emit(points)

    def _remove(self) -> None:
        points = self.value()
        if len(points) > self.MIN_POINTS:
            points.pop(self._current_row())
            self.committed.emit(points)


class TableEditor(_GridEditor):
    """Cell texts of a table or matrix."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__([], parent)
        self.table.horizontalHeader().setVisible(False)
        self.add_button("row_add", tr("widget.add_row"), self._add_row)
        self.add_button("row_remove", tr("widget.remove_row"), self._remove_row)
        self.add_button("column_add", tr("widget.add_column"), self._add_column)
        self.add_button("column_remove", tr("widget.remove_column"), self._remove_column)
        self.finish_buttons()

    def set_value(self, value: Any) -> None:
        rows = [[str(cell) for cell in row] for row in (value or []) if isinstance(row, list)]
        width = max((len(row) for row in rows), default=0)
        if self.table.state() == QAbstractItemView.State.EditingState and (len(rows), width) == (
            self.table.rowCount(),
            self.table.columnCount(),
        ):
            return
        self._loading = True
        self.table.setRowCount(len(rows))
        self.table.setColumnCount(width)
        for r, row in enumerate(rows):
            for c in range(width):
                self._set_cell(r, c, row[c] if c < len(row) else "")
        self._loading = False
        self._fit_height()

    def value(self) -> list[list[str]]:
        return [[self._cell(r, c) for c in range(self.table.columnCount())] for r in range(self.table.rowCount())]

    def _add_row(self) -> None:
        rows = self.value()
        rows.insert(self._current_row() + 1, [""] * max(1, self.table.columnCount()))
        self.committed.emit(rows)

    def _remove_row(self) -> None:
        rows = self.value()
        if len(rows) > 1:
            rows.pop(self._current_row())
            self.committed.emit(rows)

    def _add_column(self) -> None:
        column = self.table.currentColumn()
        index = column + 1 if column >= 0 else self.table.columnCount()
        rows = [row[:index] + [""] + row[index:] for row in self.value()] or [[""]]
        self.committed.emit(rows)

    def _remove_column(self) -> None:
        if self.table.columnCount() <= 1:
            return
        column = self.table.currentColumn()
        index = column if column >= 0 else self.table.columnCount() - 1
        self.committed.emit([row[:index] + row[index + 1:] for row in self.value()])


class WordColorsEditor(_GridEditor):
    """Words of a text that get their own color (Manim's ``t2c``)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__([tr("widget.word"), tr("widget.color")], parent)
        self.add_button("plus", tr("widget.add_word"), self._add)
        self.remove_button = self.add_button("minus", tr("widget.remove_word"), self._remove)
        self.finish_buttons()
        self._colors: list[str] = []

    def set_value(self, value: Any) -> None:
        pairs = [(str(word), str(color)) for word, color in (value or [])]
        if self.table.state() == QAbstractItemView.State.EditingState and len(pairs) == self.table.rowCount():
            return
        self._loading = True
        self.table.setRowCount(len(pairs))
        self._colors = [color for _word, color in pairs]
        for row, (word, color) in enumerate(pairs):
            self._set_cell(row, 0, word)
            button = self.table.cellWidget(row, 1)
            if not isinstance(button, ColorButton):
                button = ColorButton(color)
                button.colorChosen.connect(lambda chosen, b=button: self._on_color(b, chosen))
                self.table.setCellWidget(row, 1, button)
            button.set_color(color)
        self._loading = False
        self.remove_button.setEnabled(bool(pairs))
        self._fit_height()

    def _on_color(self, button: ColorButton, color: str) -> None:
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, 1) is button:
                self._colors[row] = color
        self.committed.emit(self.value())

    def value(self) -> list[list[str]]:
        return [[self._cell(row, 0), self._colors[row] if row < len(self._colors) else "#FFFF00"] for row in range(self.table.rowCount())]

    def _add(self) -> None:
        self.committed.emit(self.value() + [[tr("widget.word_placeholder"), "#FFFF00"]])

    def _remove(self) -> None:
        pairs = self.value()
        if pairs:
            pairs.pop(self._current_row())
            self.committed.emit(pairs)


class PiecesEditor(_GridEditor):
    """Parts of a piecewise function: term, from, to (``from <= x < to``)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__([tr("widget.term"), tr("widget.from"), tr("widget.to")], parent)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.table.horizontalHeader().resizeSection(column, px(52))
        self.add_button("plus", tr("widget.add_piece"), self._add)
        self.remove_button = self.add_button("minus", tr("widget.remove_piece"), self._remove)
        self.finish_buttons()

    def set_value(self, value: Any) -> None:
        rows = [[str(cell) for cell in (list(row) + ["", "", ""])[:3]] for row in (value or []) if isinstance(row, (list, tuple))]
        if self.table.state() == QAbstractItemView.State.EditingState and len(rows) == self.table.rowCount():
            return
        self._loading = True
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c in range(3):
                self._set_cell(r, c, row[c])
        self._loading = False
        self.remove_button.setEnabled(len(rows) > 1)
        self._fit_height()

    def value(self) -> list[list[str]]:
        return [[self._cell(r, c).strip() for c in range(3)] for r in range(self.table.rowCount())]

    def _add(self) -> None:
        rows = self.value()
        last_end = rows[-1][2] if rows else "0"
        rows.append(["x", last_end, ""])
        self.committed.emit(rows)

    def _remove(self) -> None:
        rows = self.value()
        if len(rows) > 1:
            rows.pop(self._current_row())
            self.committed.emit(rows)
