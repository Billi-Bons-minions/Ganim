"""Rulers along the stage showing Manim units."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from manim_studio.ui.stage.drawing import PX
from manim_studio.ui.stage.view import StageView
from manim_studio.ui.theme import color as theme_color
from manim_studio.ui.theme import px

RULER_SIZE = 20
#: Candidate label spacings in Manim units; the smallest one that leaves enough room is used.
SPACINGS = (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0)
MIN_LABEL_DISTANCE = 46


class Ruler(QWidget):
    """Horizontal or vertical ruler synchronized with a :class:`StageView`."""

    def __init__(self, view: StageView, orientation: Qt.Orientation, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view = view
        self.orientation = orientation
        self._marker: float | None = None
        self._selection: tuple[float, float] | None = None
        if orientation == Qt.Orientation.Horizontal:
            self.setFixedHeight(px(RULER_SIZE))
        else:
            self.setFixedWidth(px(RULER_SIZE))
        view.viewChanged.connect(self.update)
        view.cursorMoved.connect(self._on_cursor)

    def _on_cursor(self, x: float, y: float) -> None:
        self._marker = x if self.orientation == Qt.Orientation.Horizontal else y
        self.update()

    def set_selection_range(self, low: float | None, high: float | None) -> None:
        """Highlight the extent of the selection (Manim units)."""
        self._selection = (low, high) if low is not None and high is not None else None
        self.update()

    def _to_widget(self, value: float) -> float:
        """Map a Manim coordinate to a pixel position along the ruler."""
        horizontal = self.orientation == Qt.Orientation.Horizontal
        scene_point = QPointF(value * PX, 0.0) if horizontal else QPointF(0.0, -value * PX)
        view_point = self.view.mapFromScene(scene_point)
        local = self.mapFromGlobal(self.view.viewport().mapToGlobal(view_point))
        return float(local.x() if horizontal else local.y())

    def _visible_range(self) -> tuple[float, float]:
        rect = self.view.mapToScene(self.view.viewport().rect()).boundingRect()
        if self.orientation == Qt.Orientation.Horizontal:
            return rect.left() / PX, rect.right() / PX
        return -rect.bottom() / PX, -rect.top() / PX

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.fillRect(self.rect(), theme_color("panel"))
        horizontal = self.orientation == Qt.Orientation.Horizontal
        low, high = self._visible_range()
        pixels_per_unit = abs(self._to_widget(1.0) - self._to_widget(0.0)) or 1.0
        spacing = next((s for s in SPACINGS if s * pixels_per_unit >= px(MIN_LABEL_DISTANCE)), SPACINGS[-1])
        minor = spacing / 5 if spacing * pixels_per_unit >= px(30) else spacing / 2
        size = self.height() if horizontal else self.width()
        if self._selection is not None:
            start, end = sorted((self._to_widget(self._selection[0]), self._to_widget(self._selection[1])))
            band = QColor(theme_color("accent"))
            band.setAlpha(60)
            rect = QRectF(start, 0, end - start, size) if horizontal else QRectF(0, start, size, end - start)
            painter.fillRect(rect, band)
        tick_pen = QPen(theme_color("text_faint"), 1.0)
        painter.setPen(tick_pen)
        font = QFont(self.font())
        font.setPixelSize(px(9))
        painter.setFont(font)
        first = math.floor(low / minor) * minor
        count = int((high - first) / minor) + 2
        for index in range(count):
            value = first + index * minor
            position = self._to_widget(value)
            major = abs(value / spacing - round(value / spacing)) < 1e-6
            length = size * (0.55 if major else 0.25)
            if horizontal:
                painter.drawLine(QPointF(position, size - length), QPointF(position, size))
            else:
                painter.drawLine(QPointF(size - length, position), QPointF(size, position))
            if major:
                label = f"{round(value, 2):g}"
                painter.setPen(theme_color("text_muted"))
                if horizontal:
                    painter.drawText(QPointF(position + px(3), px(10)), label)
                else:
                    painter.save()
                    painter.translate(px(10), position - px(3))
                    painter.rotate(-90)
                    painter.drawText(QPointF(0, 0), label)
                    painter.restore()
                painter.setPen(tick_pen)
        if self._marker is not None:
            position = self._to_widget(self._marker)
            painter.setPen(QPen(theme_color("accent"), 1.5))
            if horizontal:
                painter.drawLine(QPointF(position, 0), QPointF(position, size))
            else:
                painter.drawLine(QPointF(0, position), QPointF(size, position))
        painter.setPen(QPen(theme_color("border"), 1.0))
        if horizontal:
            painter.drawLine(QPointF(0, size - 0.5), QPointF(self.width(), size - 0.5))
        else:
            painter.drawLine(QPointF(size - 0.5, 0), QPointF(size - 0.5, self.height()))
        painter.end()


class RulerCorner(QWidget):
    """The small square where both rulers meet."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(px(RULER_SIZE), px(RULER_SIZE))

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.fillRect(self.rect(), theme_color("panel"))
        painter.end()
