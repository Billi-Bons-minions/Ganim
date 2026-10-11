"""Programmatically drawn icons (no image files needed)."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)

from manim_studio.model.types import ObjectKind

ICON_SIZE = 48
_STROKE = QColor("#2E9CC0")
_FILL = QColor(88, 196, 221, 70)
_NEUTRAL = QColor("#8A8A92")


def _canvas(size: int) -> tuple[QPixmap, QPainter]:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(_STROKE, 2.4))
    painter.setBrush(QBrush(_FILL))
    return pixmap, painter


def _text(painter: QPainter, rect: QRectF, text: str, italic: bool = False, size: float = 0.42) -> None:
    font = QFont("Serif" if italic else "Sans")
    font.setItalic(italic)
    font.setPixelSize(round(rect.height() * size))
    painter.setFont(font)
    painter.setPen(_STROKE)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)


def _arrow(painter: QPainter, start: QPointF, end: QPointF) -> None:
    painter.drawLine(start, end)
    angle = math.atan2(end.y() - start.y(), end.x() - start.x())
    tip = 9.0
    left = QPointF(end.x() - tip * math.cos(angle - 0.5), end.y() - tip * math.sin(angle - 0.5))
    right = QPointF(end.x() - tip * math.cos(angle + 0.5), end.y() - tip * math.sin(angle + 0.5))
    painter.setBrush(_STROKE)
    painter.drawPolygon(QPolygonF([end, left, right]))


def _draw_axes(painter: QPainter, m: float, s: float) -> None:
    painter.setPen(QPen(_NEUTRAL, 2))
    _arrow(painter, QPointF(m, s / 2), QPointF(s - m, s / 2))
    _arrow(painter, QPointF(s / 2, s - m), QPointF(s / 2, m))


def _draw_graph(painter: QPainter, m: float, s: float) -> None:
    painter.setPen(QPen(_NEUTRAL, 1.5))
    painter.drawLine(QPointF(m, s / 2), QPointF(s - m, s / 2))
    path = QPainterPath(QPointF(m, s / 2))
    for index in range(41):
        x = m + (s - 2 * m) * index / 40
        path.lineTo(QPointF(x, s / 2 - (s / 2 - m) * 0.8 * math.sin(index / 40 * 2 * math.pi)))
    painter.setPen(QPen(QColor("#E0A800"), 2.4))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)


def _draw_plane(painter: QPainter, m: float, s: float) -> None:
    painter.setPen(QPen(QColor("#29ABCA"), 1.2))
    for index in range(5):
        offset = m + (s - 2 * m) * index / 4
        painter.drawLine(QPointF(offset, m), QPointF(offset, s - m))
        painter.drawLine(QPointF(m, offset), QPointF(s - m, offset))
    painter.setPen(QPen(_NEUTRAL, 2))
    painter.drawLine(QPointF(s / 2, m), QPointF(s / 2, s - m))
    painter.drawLine(QPointF(m, s / 2), QPointF(s - m, s / 2))


def _draw_image(painter: QPainter, m: float, s: float) -> None:
    painter.setPen(QPen(_NEUTRAL, 2))
    painter.setBrush(QColor(128, 128, 128, 30))
    painter.drawRoundedRect(QRectF(m, m + 4, s - 2 * m, s - 2 * m - 8), 4, 4)
    painter.setBrush(QColor("#83C167"))
    painter.drawPolygon(QPolygonF([QPointF(m + 4, s - m - 8), QPointF(s / 2 - 2, s / 2), QPointF(s - m - 4, s - m - 8)]))
    painter.setBrush(QColor("#F7D96F"))
    painter.drawEllipse(QPointF(s - m - 10, m + 13), 4, 4)


def kind_icon(kind: ObjectKind, size: int = ICON_SIZE) -> QIcon:
    """Return the library icon of an object kind."""
    pixmap, painter = _canvas(size)
    s, m = float(size), size * 0.16
    box = QRectF(m, m, s - 2 * m, s - 2 * m)
    if kind == ObjectKind.CIRCLE:
        painter.drawEllipse(box)
    elif kind == ObjectKind.SQUARE:
        painter.drawRect(box)
    elif kind == ObjectKind.RECTANGLE:
        painter.drawRect(QRectF(m * 0.6, s * 0.3, s - 1.2 * m, s * 0.4))
    elif kind == ObjectKind.TRIANGLE:
        painter.drawPolygon(QPolygonF([QPointF(s / 2, m), QPointF(s - m, s - m), QPointF(m, s - m)]))
    elif kind == ObjectKind.ELLIPSE:
        painter.drawEllipse(QRectF(m * 0.6, s * 0.3, s - 1.2 * m, s * 0.4))
    elif kind == ObjectKind.LINE:
        painter.drawLine(QPointF(m, s - m), QPointF(s - m, m))
    elif kind == ObjectKind.ARROW:
        _arrow(painter, QPointF(m, s - m), QPointF(s - m, m))
    elif kind == ObjectKind.DOT:
        painter.setBrush(_STROKE)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(s / 2, s / 2), s * 0.12, s * 0.12)
    elif kind == ObjectKind.TEXT:
        _text(painter, box, "Aa")
    elif kind == ObjectKind.MATH_TEX:
        _text(painter, box, "∑x²", italic=True, size=0.38)
    elif kind == ObjectKind.AXES:
        _draw_axes(painter, m, s)
    elif kind == ObjectKind.NUMBER_PLANE:
        _draw_plane(painter, m, s)
    elif kind == ObjectKind.FUNCTION_GRAPH:
        _draw_graph(painter, m, s)
    else:
        _draw_image(painter, m, s)
    painter.end()
    return QIcon(pixmap)


def app_icon() -> QIcon:
    """Return the application icon."""
    size = 128
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(QColor("#1C1C24"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRectF(4, 4, size - 8, size - 8), 24, 24)
    painter.setPen(QPen(QColor("#58C4DD"), 9))
    painter.setBrush(QColor(88, 196, 221, 70))
    painter.drawEllipse(QPointF(50, 70), 28, 28)
    painter.setPen(QPen(QColor("#FC6255"), 9))
    painter.setBrush(QColor(252, 98, 85, 70))
    painter.drawRect(QRectF(62, 26, 44, 44))
    painter.end()
    return QIcon(pixmap)
