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


def _regular(cx: float, cy: float, radius: float, corners: int, start: float = -90.0) -> QPolygonF:
    return QPolygonF(
        [
            QPointF(cx + radius * math.cos(math.radians(start + 360 * k / corners)), cy + radius * math.sin(math.radians(start + 360 * k / corners)))
            for k in range(corners)
        ]
    )


def _number_line(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    p.setPen(QPen(neutral, w))
    p.drawLine(QPointF(m * 0.6, s * 0.45), QPointF(s - m * 0.6, s * 0.45))
    for index in range(5):
        x = m + (s - 2 * m) * index / 4
        p.drawLine(QPointF(x, s * 0.36), QPointF(x, s * 0.54))
    _text(p, QRectF(0, s * 0.52, s, s * 0.4), "0  1  2", stroke, size=0.55)


def _vector(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    p.setPen(QPen(neutral, w))
    p.drawEllipse(QPointF(m, s - m), w * 1.2, w * 1.2)
    p.setPen(QPen(stroke, w * 1.2))
    _arrow(p, QPointF(m, s - m), QPointF(s - m, m * 1.5), stroke)


def _double_arrow(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    _arrow(p, QPointF(s / 2, s / 2), QPointF(s - m, s / 2), stroke)
    _arrow(p, QPointF(s / 2, s / 2), QPointF(m, s / 2), stroke)


def _dashed_line(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    pen = QPen(stroke, w, Qt.PenStyle.DashLine, Qt.PenCapStyle.FlatCap)
    p.setPen(pen)
    p.drawLine(QPointF(m, s - m), QPointF(s - m, m))


def _brace(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath(QPointF(m, s * 0.35))
    path.quadTo(QPointF(m, s * 0.5), QPointF(s * 0.3, s * 0.5))
    path.lineTo(QPointF(s * 0.42, s * 0.5))
    path.quadTo(QPointF(s * 0.5, s * 0.5), QPointF(s * 0.5, s * 0.64))
    path.quadTo(QPointF(s * 0.5, s * 0.5), QPointF(s * 0.58, s * 0.5))
    path.lineTo(QPointF(s * 0.7, s * 0.5))
    path.quadTo(QPointF(s - m, s * 0.5), QPointF(s - m, s * 0.35))
    p.drawPath(path)


def _highlight(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    p.setPen(QPen(neutral, w))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawText(QRectF(m, m, s - 2 * m, s - 2 * m), Qt.AlignmentFlag.AlignCenter, "x²")
    pen = QPen(QColor("#F7D96F"), w)
    p.setPen(pen)
    p.drawRoundedRect(QRectF(m * 0.6, s * 0.22, s - 1.2 * m, s * 0.56), s * 0.08, s * 0.08)


def _angle(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    p.setPen(QPen(neutral, w))
    p.setBrush(Qt.BrushStyle.NoBrush)
    corner = QPointF(m, s - m)
    p.drawLine(corner, QPointF(s - m, s - m))
    p.drawLine(corner, QPointF(s * 0.72, s * 0.28))
    p.setPen(QPen(QColor("#F7D96F"), w))
    radius = s * 0.36
    p.drawArc(QRectF(corner.x() - radius, corner.y() - radius, 2 * radius, 2 * radius), 0, 46 * 16)


def _trace(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    path = QPainterPath(QPointF(m, s - m))
    path.cubicTo(QPointF(s * 0.3, s * 0.2), QPointF(s * 0.6, s * 0.9), QPointF(s * 0.78, s * 0.3))
    pen = QPen(QColor("#F7D96F"), w)
    pen.setStyle(Qt.PenStyle.DashLine)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    p.setPen(QPen(neutral, w))
    p.setBrush(neutral)
    p.drawEllipse(QPointF(s * 0.78, s * 0.3), s * 0.09, s * 0.09)


def _polygon(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    p.drawPolygon(QPolygonF([QPointF(m, s * 0.7), QPointF(s * 0.32, m), QPointF(s - m, s * 0.35), QPointF(s * 0.7, s - m)]))


def _regular_polygon(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    p.drawPolygon(_regular(s / 2, s / 2, s / 2 - m, 6, 0.0))


def _star(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    outer, inner = s / 2 - m * 0.7, (s / 2 - m * 0.7) * 0.45
    points = []
    for k in range(10):
        radius = outer if k % 2 == 0 else inner
        angle = math.radians(-90 + 36 * k)
        points.append(QPointF(s / 2 + radius * math.cos(angle), s * 0.53 + radius * math.sin(angle)))
    p.drawPolygon(QPolygonF(points))


def _arc_icon(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(m, m, s - 2 * m, s - 2 * m), 0, 200 * 16)


def _sector(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    p.drawPie(QRectF(m, m, s - 2 * m, s - 2 * m), 20 * 16, 110 * 16)


def _annulus(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    ring = QPainterPath()
    ring.addEllipse(QRectF(m, m, s - 2 * m, s - 2 * m))
    inner = s * 0.2
    ring.addEllipse(QRectF(s / 2 - inner, s / 2 - inner, 2 * inner, 2 * inner))
    p.drawPath(ring)


def _decimal(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    _text(p, QRectF(0, 0, s, s), "3.14", stroke, size=0.36)


def _cells(p: QPainter, s: float, m: float, w: float, stroke: QColor, neutral: QColor, rows: int, columns: int) -> QRectF:
    box = QRectF(m, s * 0.24, s - 2 * m, s * 0.52)
    p.setPen(QPen(neutral, w * 0.7))
    p.setBrush(Qt.BrushStyle.NoBrush)
    for row in range(rows):
        for column in range(columns):
            cell = QRectF(box.x() + box.width() * column / columns, box.y() + box.height() * row / rows, box.width() / columns, box.height() / rows)
            p.drawRect(cell)
    return box


def _table(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    box = _cells(p, s, m, w, stroke, neutral, 2, 3)
    p.fillRect(QRectF(box.x(), box.y(), box.width(), box.height() / 2), fill)


def _matrix(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    p.setBrush(Qt.BrushStyle.NoBrush)
    for left in (True, False):
        x = m if left else s - m
        inward = s * 0.08 * (1 if left else -1)
        p.drawPolyline(QPolygonF([QPointF(x + inward, m), QPointF(x, m), QPointF(x, s - m), QPointF(x + inward, s - m)]))
    _text(p, QRectF(0, s * 0.18, s, s * 0.32), "1  0", stroke, size=0.62)
    _text(p, QRectF(0, s * 0.5, s, s * 0.32), "0  1", stroke, size=0.62)


def _code(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    p.setPen(QPen(neutral, w * 0.8))
    p.drawRoundedRect(QRectF(m * 0.6, m, s - 1.2 * m, s - 2 * m), 3, 3)
    p.setPen(QPen(stroke, w))
    for index, length in enumerate((0.5, 0.35, 0.42)):
        y = s * (0.38 + index * 0.13)
        indent = s * (0.24 if index == 1 else 0.18)
        p.drawLine(QPointF(indent, y), QPointF(indent + s * length, y))


def _tex(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    _text(p, QRectF(0, 0, s, s), "TeX", stroke, italic=True, size=0.38)


def _markup(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    font = QFont("Sans")
    font.setPixelSize(max(1, round(s * 0.44)))
    font.setBold(True)
    p.setFont(font)
    p.setPen(stroke)
    p.drawText(QRectF(0, 0, s * 0.55, s), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "A")
    font.setBold(False)
    font.setItalic(True)
    p.setFont(font)
    p.setPen(neutral)
    p.drawText(QRectF(s * 0.52, 0, s * 0.48, s), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "a")


def _group(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    p.drawEllipse(QRectF(m * 1.4, s * 0.38, s * 0.36, s * 0.36))
    p.drawRoundedRect(QRectF(s * 0.46, m * 1.4, s * 0.34, s * 0.34), 2, 2)
    dashed = QPen(neutral, w * 0.7, Qt.PenStyle.DashLine)
    p.setPen(dashed)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(QRectF(m * 0.6, m * 0.6, s - 1.2 * m, s - 1.2 * m))


def _axes_hint(p: QPainter, s: float, m: float, w: float, neutral: QColor) -> None:
    p.save()
    p.setPen(QPen(neutral, w * 0.7))
    p.drawLine(QPointF(m * 0.6, s - m * 1.2), QPointF(s - m * 0.6, s - m * 1.2))
    p.drawLine(QPointF(m * 1.2, m * 0.6), QPointF(m * 1.2, s - m * 0.6))
    p.restore()


def _parabola(s: float, m: float) -> QPainterPath:
    path = QPainterPath(QPointF(m * 1.4, m))
    path.quadTo(QPointF(s * 0.5, s * 1.25), QPointF(s - m * 0.8, m))
    return path


def _area(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    _axes_hint(p, s, m, w, neutral)
    region = QPainterPath(QPointF(s * 0.35, s - m * 1.2))
    region.lineTo(QPointF(s * 0.35, s * 0.55))
    region.quadTo(QPointF(s * 0.55, s * 0.2), QPointF(s * 0.8, s * 0.35))
    region.lineTo(QPointF(s * 0.8, s - m * 1.2))
    region.closeSubpath()
    p.setPen(Qt.PenStyle.NoPen)
    solid = QColor(stroke)
    solid.setAlphaF(0.55)
    p.setBrush(solid)
    p.drawPath(region)
    p.setPen(QPen(stroke, w))
    p.setBrush(Qt.BrushStyle.NoBrush)
    curve = QPainterPath(QPointF(m * 1.2, s * 0.75))
    curve.quadTo(QPointF(s * 0.55, s * 0.05), QPointF(s - m * 0.6, s * 0.4))
    p.drawPath(curve)


def _riemann(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    _axes_hint(p, s, m, w, neutral)
    base = s - m * 1.2
    for index, height in enumerate((0.25, 0.4, 0.52, 0.6)):
        x = s * 0.28 + index * s * 0.15
        p.drawRect(QRectF(x, base - s * height, s * 0.15, s * height))


def _tangent(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(neutral, w))
    p.drawPath(_parabola(s, m))
    p.setPen(QPen(stroke, w * 1.1))
    p.drawLine(QPointF(m * 0.4, s * 0.88), QPointF(s - m * 0.4, s * 0.36))
    p.setBrush(stroke)
    p.drawEllipse(QPointF(s * 0.62, s * 0.62), w * 1.6, w * 1.6)


def _graph_point(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    _axes_hint(p, s, m, w, neutral)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(neutral, w * 0.8))
    p.drawPath(_parabola(s, m))
    dashed = QPen(stroke, w * 0.7, Qt.PenStyle.DashLine)
    p.setPen(dashed)
    p.drawLine(QPointF(s * 0.7, s * 0.45), QPointF(s * 0.7, s - m * 1.2))
    p.drawLine(QPointF(s * 0.7, s * 0.45), QPointF(m * 1.2, s * 0.45))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(stroke)
    p.drawEllipse(QPointF(s * 0.7, s * 0.45), w * 2, w * 2)


def _markers(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    p.setPen(QPen(neutral, w * 0.7))
    p.drawLine(QPointF(m * 0.5, s * 0.55), QPointF(s - m * 0.5, s * 0.55))
    p.setPen(QPen(stroke, w))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(_sine(m, s, s * 0.28).translated(0, s * 0.05))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#FC6255"))
    for x in (m, s / 2, s - m):
        p.drawEllipse(QPointF(x, s * 0.55), w * 1.8, w * 1.8)


def _graph_label(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    p.setPen(QPen(neutral, w))
    p.setBrush(Qt.BrushStyle.NoBrush)
    curve = QPainterPath(QPointF(m, s - m))
    curve.quadTo(QPointF(s * 0.45, s - m), QPointF(s * 0.6, s * 0.45))
    p.drawPath(curve)
    _text(p, QRectF(s * 0.4, 0, s * 0.6, s * 0.5), "f", stroke, italic=True, size=0.8)


def _parameter(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    p.setPen(QPen(neutral, w))
    p.drawLine(QPointF(m, s * 0.68), QPointF(s - m, s * 0.68))
    p.setPen(QPen(stroke, w))
    p.setBrush(stroke)
    p.drawEllipse(QPointF(s * 0.6, s * 0.68), s * 0.09, s * 0.09)
    _text(p, QRectF(0, 0, s, s * 0.55), "a", stroke, italic=True, size=0.75)


def _data_plot(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    _axes_hint(p, s, m, w, neutral)
    p.setPen(QPen(QColor("#F7D96F"), w))
    p.drawLine(QPointF(m * 1.6, s * 0.72), QPointF(s - m, s * 0.25))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(stroke)
    for x, y in ((0.3, 0.62), (0.42, 0.68), (0.55, 0.45), (0.68, 0.5), (0.8, 0.3)):
        p.drawEllipse(QPointF(s * x, s * y), w * 1.5, w * 1.5)


def _bar_chart(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    _axes_hint(p, s, m, w, neutral)
    base = s - m * 1.2
    colors = ("#58508D", "#BC5090", "#FF6361", "#FFA600")
    for index, (height, color) in enumerate(zip((0.35, 0.6, 0.45, 0.7), colors)):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        p.drawRect(QRectF(s * 0.27 + index * s * 0.17, base - s * height, s * 0.12, s * height))


def _camera_kind(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    body = QRectF(m * 0.8, s * 0.32, s * 0.58, s * 0.42)
    p.drawRoundedRect(body, 3, 3)
    p.drawPolygon(QPolygonF([QPointF(body.right(), s * 0.45), QPointF(s - m * 0.6, s * 0.34), QPointF(s - m * 0.6, s * 0.72), QPointF(body.right(), s * 0.61)]))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(body.center().x(), body.center().y()), s * 0.1, s * 0.1)


def _axes_3d(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    origin = QPointF(s * 0.45, s * 0.6)
    p.setPen(QPen(neutral, w))
    for end in (QPointF(s - m * 0.6, s * 0.72), QPointF(s * 0.45, m * 0.6), QPointF(m * 0.6, s - m * 0.6)):
        _arrow(p, origin, end, neutral)


def _surface(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    path = QPainterPath(QPointF(m, s * 0.55))
    path.cubicTo(QPointF(s * 0.3, s * 0.25), QPointF(s * 0.45, s * 0.75), QPointF(s * 0.62, s * 0.4))
    path.lineTo(QPointF(s - m, s * 0.3))
    path.cubicTo(QPointF(s * 0.75, s * 0.55), QPointF(s * 0.6, s * 0.95), QPointF(s * 0.38, s * 0.72))
    path.closeSubpath()
    p.drawPath(path)
    p.setPen(QPen(stroke, w * 0.5))
    p.drawLine(QPointF(s * 0.3, s * 0.42), QPointF(s * 0.5, s * 0.82))
    p.drawLine(QPointF(s * 0.5, s * 0.5), QPointF(s * 0.68, s * 0.72))


def _curve_3d(p: QPainter, s: float, m: float, w: float, stroke: QColor, fill: QColor, neutral: QColor) -> None:
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath(QPointF(s / 2 + s * 0.3, s - m))
    for index in range(1, 81):
        t = index / 80 * 4 * math.pi
        path.lineTo(QPointF(s / 2 + s * 0.3 * math.cos(t), s - m - (s - 2 * m) * index / 80 + s * 0.08 * math.sin(t)))
    p.drawPath(path)


_EXTRA_DRAWERS = {
    ObjectKind.NUMBER_LINE: _number_line,
    ObjectKind.VECTOR: _vector,
    ObjectKind.DOUBLE_ARROW: _double_arrow,
    ObjectKind.DASHED_LINE: _dashed_line,
    ObjectKind.BRACE: _brace,
    ObjectKind.HIGHLIGHT: _highlight,
    ObjectKind.ANGLE: _angle,
    ObjectKind.TRACE: _trace,
    ObjectKind.POLYGON: _polygon,
    ObjectKind.REGULAR_POLYGON: _regular_polygon,
    ObjectKind.STAR: _star,
    ObjectKind.ARC: _arc_icon,
    ObjectKind.SECTOR: _sector,
    ObjectKind.ANNULUS: _annulus,
    ObjectKind.DECIMAL_NUMBER: _decimal,
    ObjectKind.TABLE: _table,
    ObjectKind.MATRIX: _matrix,
    ObjectKind.CODE: _code,
    ObjectKind.TEX: _tex,
    ObjectKind.MARKUP_TEXT: _markup,
    ObjectKind.GROUP: _group,
    ObjectKind.GRAPH_AREA: _area,
    ObjectKind.RIEMANN: _riemann,
    ObjectKind.TANGENT: _tangent,
    ObjectKind.GRAPH_POINT: _graph_point,
    ObjectKind.GRAPH_MARKERS: _markers,
    ObjectKind.GRAPH_LABEL: _graph_label,
    ObjectKind.PARAMETER: _parameter,
    ObjectKind.DATA_PLOT: _data_plot,
    ObjectKind.BAR_CHART: _bar_chart,
    ObjectKind.CAMERA: _camera_kind,
    ObjectKind.AXES_3D: _axes_3d,
    ObjectKind.SURFACE: _surface,
    ObjectKind.CURVE_3D: _curve_3d,
}


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
    elif kind in _EXTRA_DRAWERS:
        _EXTRA_DRAWERS[kind](painter, s, m, width, stroke, fill, neutral)
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

    def clone(self) -> _KindIconEngine:
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


class _RateIconEngine(QIconEngine):
    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name

    def paint(self, painter: QPainter, rect, mode: QIcon.Mode, state: QIcon.State) -> None:
        from manim_studio.model.rate_functions import rate
        from manim_studio.ui.theme import current_palette

        palette = current_palette()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        box = QRectF(rect).adjusted(2, 4, -2, -4)
        painter.setPen(QPen(QColor(palette.border_strong), 1))
        painter.drawLine(box.bottomLeft(), box.bottomRight())
        values = [rate(self.name, index / 40) for index in range(41)]
        low, high = min(min(values), 0.0), max(max(values), 1.0)
        path = QPainterPath()
        for index, value in enumerate(values):
            point = QPointF(box.left() + box.width() * index / 40, box.bottom() - (value - low) / (high - low) * box.height())
            if index == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        painter.setPen(QPen(QColor(palette.accent), 1.6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.restore()

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        self.paint(painter, image.rect(), mode, state)
        painter.end()
        return QPixmap.fromImage(image)

    def clone(self) -> _RateIconEngine:
        return _RateIconEngine(self.name)


def rate_icon(name: str) -> QIcon:
    """Return a small plot of a rate function."""
    return QIcon(_RateIconEngine(name))
