"""Object-kind icons and the application icon, drawn in theme colors."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QIconEngine, QImage, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

from manim_studio.model.types import ObjectKind

ICON_SIZE = 48


def _accent() -> tuple[QColor, QColor, QColor]:
    from manim_studio.ui.theme import current_palette

    palette = current_palette()
    stroke = QColor(palette.accent)
    fill = QColor(palette.accent)
    fill.setAlphaF(0.22)
    return stroke, fill, QColor(palette.text_muted)


def _arrow(painter: QPainter, start: QPointF, end: QPointF, color: QColor) -> None:
    painter.drawLine(start, end)
    angle = math.atan2(end.y() - start.y(), end.x() - start.x())
    tip = 8.0
    left = QPointF(end.x() - tip * math.cos(angle - 0.5), end.y() - tip * math.sin(angle - 0.5))
    right = QPointF(end.x() - tip * math.cos(angle + 0.5), end.y() - tip * math.sin(angle + 0.5))
    painter.save()
    painter.setBrush(color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawPolygon(QPolygonF([end, left, right]))
    painter.restore()


def _text(painter: QPainter, rect: QRectF, text: str, color: QColor, italic: bool = False, size: float = 0.44) -> None:
    font = QFont("Serif" if italic else "Sans")
    font.setItalic(italic)
    font.setBold(not italic)
    font.setPixelSize(max(1, round(rect.height() * size)))
    painter.setFont(font)
    painter.setPen(color)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)


def _sine(m: float, s: float, amplitude: float) -> QPainterPath:
    path = QPainterPath(QPointF(m, s / 2))
    for index in range(41):
        x = m + (s - 2 * m) * index / 40
        path.lineTo(QPointF(x, s / 2 - amplitude * math.sin(index / 40 * 2 * math.pi)))
    return path


def draw_kind(painter: QPainter, kind: ObjectKind, size: float) -> None:
    """Draw the symbol of an object kind into a square of ``size`` pixels."""
    stroke, fill, neutral = _accent()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    width = max(1.4, size / 20)
    painter.setPen(QPen(stroke, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(QBrush(fill))
    s, m = float(size), size * 0.16
    box = QRectF(m, m, s - 2 * m, s - 2 * m)
    if kind == ObjectKind.CIRCLE:
        painter.drawEllipse(box)
    elif kind == ObjectKind.SQUARE:
        painter.drawRoundedRect(box, 2, 2)
    elif kind == ObjectKind.RECTANGLE:
        painter.drawRoundedRect(QRectF(m * 0.5, s * 0.3, s - m, s * 0.4), 2, 2)
    elif kind == ObjectKind.TRIANGLE:
        painter.drawPolygon(QPolygonF([QPointF(s / 2, m), QPointF(s - m, s - m), QPointF(m, s - m)]))
    elif kind == ObjectKind.ELLIPSE:
        painter.drawEllipse(QRectF(m * 0.5, s * 0.28, s - m, s * 0.44))
    elif kind == ObjectKind.LINE:
        painter.drawLine(QPointF(m, s - m), QPointF(s - m, m))
    elif kind == ObjectKind.ARROW:
        _arrow(painter, QPointF(m, s - m), QPointF(s - m, m), stroke)
    elif kind == ObjectKind.DOT:
        painter.setBrush(stroke)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(s / 2, s / 2), s * 0.12, s * 0.12)
    elif kind == ObjectKind.TEXT:
        _text(painter, QRectF(0, 0, s, s), "Aa", stroke, size=0.5)
    elif kind == ObjectKind.MATH_TEX:
        _text(painter, QRectF(0, 0, s, s), "∑x²", stroke, italic=True, size=0.42)
    elif kind == ObjectKind.AXES:
        painter.setPen(QPen(neutral, width))
        _arrow(painter, QPointF(m, s / 2), QPointF(s - m, s / 2), neutral)
        _arrow(painter, QPointF(s / 2, s - m), QPointF(s / 2, m), neutral)
    elif kind == ObjectKind.NUMBER_PLANE:
        painter.setPen(QPen(stroke, width * 0.6))
        for index in range(5):
            offset = m + (s - 2 * m) * index / 4
            painter.drawLine(QPointF(offset, m), QPointF(offset, s - m))
            painter.drawLine(QPointF(m, offset), QPointF(s - m, offset))
        painter.setPen(QPen(neutral, width))
        painter.drawLine(QPointF(s / 2, m), QPointF(s / 2, s - m))
        painter.drawLine(QPointF(m, s / 2), QPointF(s - m, s / 2))
    elif kind == ObjectKind.FUNCTION_GRAPH:
        painter.setPen(QPen(neutral, width * 0.7))
        painter.drawLine(QPointF(m, s / 2), QPointF(s - m, s / 2))
        painter.setPen(QPen(stroke, width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(_sine(m, s, (s / 2 - m) * 0.8))
    else:
        painter.setPen(QPen(neutral, width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(m, m + s * 0.06, s - 2 * m, s - 2 * m - s * 0.12), 3, 3)
        painter.setBrush(fill)
        painter.setPen(QPen(stroke, width))
        painter.drawPolygon(QPolygonF([QPointF(m + 3, s - m - 6), QPointF(s / 2 - 2, s / 2), QPointF(s - m - 3, s - m - 6)]))


class _KindIconEngine(QIconEngine):
    def __init__(self, kind: ObjectKind) -> None:
        super().__init__()
        self.kind = kind

    def paint(self, painter: QPainter, rect, mode: QIcon.Mode, state: QIcon.State) -> None:
        painter.save()
        painter.translate(rect.x(), rect.y())
        side = min(rect.width(), rect.height())
        if mode == QIcon.Mode.Disabled:
            painter.setOpacity(0.35)
        draw_kind(painter, self.kind, side)
        painter.restore()

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        self.paint(painter, image.rect(), mode, state)
        painter.end()
        return QPixmap.fromImage(image)

    def clone(self) -> "_KindIconEngine":
        return _KindIconEngine(self.kind)


def kind_icon(kind: ObjectKind, size: int = ICON_SIZE) -> QIcon:
    """Return the icon of an object kind (``size`` is kept for compatibility)."""
    return QIcon(_KindIconEngine(kind))


def kind_pixmap(kind: ObjectKind, size: int) -> QPixmap:
    """Return the icon of an object kind as pixmap (used while dragging)."""
    return kind_icon(kind).pixmap(QSize(size, size))


def app_icon() -> QIcon:
    """Return the application icon."""
    size = 128
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(QColor("#15161B"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRectF(4, 4, size - 8, size - 8), 26, 26)
    painter.setPen(QPen(QColor("#58C4DD"), 9))
    painter.setBrush(QColor(88, 196, 221, 70))
    painter.drawEllipse(QPointF(50, 72), 27, 27)
    painter.setPen(QPen(QColor("#FC6255"), 9))
    painter.setBrush(QColor(252, 98, 85, 70))
    painter.drawRoundedRect(QRectF(62, 26, 42, 42), 4, 4)
    painter.end()
    return QIcon(pixmap)
