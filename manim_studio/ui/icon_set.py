"""Vector icons drawn with QPainter (24×24 grid, outlined style).

Icons are rendered by :class:`PaintedIconEngine`, so they stay sharp at any
size and automatically use the theme's text, muted or accent color.
"""

from __future__ import annotations

import math
from typing import Callable

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QIconEngine, QImage, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

Drawer = Callable[[QPainter], None]

STROKE = 1.8


def _line(p: QPainter, x1: float, y1: float, x2: float, y2: float) -> None:
    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))


def _poly(p: QPainter, points: list[tuple[float, float]], closed: bool = False, fill: bool = False) -> None:
    polygon = QPolygonF([QPointF(x, y) for x, y in points])
    if fill:
        p.save()
        p.setBrush(p.pen().color())
        p.drawPolygon(polygon)
        p.restore()
    elif closed:
        p.drawPolygon(polygon)
    else:
        p.drawPolyline(polygon)


def _rect(p: QPainter, x: float, y: float, w: float, h: float, r: float = 2.0, fill: bool = False) -> None:
    if fill:
        p.save()
        p.setBrush(p.pen().color())
        p.drawRoundedRect(QRectF(x, y, w, h), r, r)
        p.restore()
    else:
        p.drawRoundedRect(QRectF(x, y, w, h), r, r)


def _circle(p: QPainter, cx: float, cy: float, r: float, fill: bool = False) -> None:
    if fill:
        p.save()
        p.setBrush(p.pen().color())
        p.drawEllipse(QPointF(cx, cy), r, r)
        p.restore()
    else:
        p.drawEllipse(QPointF(cx, cy), r, r)


def _arc(p: QPainter, cx: float, cy: float, r: float, start: float, span: float) -> None:
    p.drawArc(QRectF(cx - r, cy - r, 2 * r, 2 * r), round(start * 16), round(span * 16))


def _text(p: QPainter, text: str, size: float = 14, bold: bool = True, rect: QRectF | None = None) -> None:
    font = QFont()
    font.setPixelSize(round(size))
    font.setBold(bold)
    p.setFont(font)
    p.drawText(rect or QRectF(0, 0, 24, 24), Qt.AlignmentFlag.AlignCenter, text)


def _arrow_head(p: QPainter, x: float, y: float, angle: float, size: float = 4.0) -> None:
    left = (x - size * math.cos(angle - 0.6), y - size * math.sin(angle - 0.6))
    right = (x - size * math.cos(angle + 0.6), y - size * math.sin(angle + 0.6))
    _poly(p, [left, (x, y), right])


# --- file and edit ----------------------------------------------------------------


def _new(p: QPainter) -> None:
    _poly(p, [(14, 3), (6, 3), (6, 21), (18, 21), (18, 7), (14, 3), (14, 7), (18, 7)])
    _line(p, 12, 11, 12, 17)
    _line(p, 9, 14, 15, 14)


def _open(p: QPainter) -> None:
    _poly(p, [(3, 19), (3, 6), (9, 6), (11, 8), (19, 8), (19, 11)])
    _poly(p, [(3, 19), (6, 11), (22, 11), (19, 19), (3, 19)])


def _save(p: QPainter) -> None:
    _poly(p, [(5, 4), (16, 4), (20, 8), (20, 20), (4, 20), (4, 4), (5, 4)])
    _rect(p, 8, 4, 7, 5, 1)
    _rect(p, 7, 13, 10, 7, 1)


def _undo(p: QPainter) -> None:
    path = QPainterPath(QPointF(5, 10))
    path.lineTo(15, 10)
    path.cubicTo(22, 10, 22, 20, 15, 20)
    path.lineTo(10, 20)
    p.drawPath(path)
    _poly(p, [(9, 6), (5, 10), (9, 14)])


def _redo(p: QPainter) -> None:
    p.save()
    p.translate(24, 0)
    p.scale(-1, 1)
    _undo(p)
    p.restore()


def _cut(p: QPainter) -> None:
    _circle(p, 7, 17, 3)
    _circle(p, 17, 17, 3)
    _line(p, 9, 15, 18, 4)
    _line(p, 15, 15, 6, 4)


def _copy(p: QPainter) -> None:
    _rect(p, 9, 9, 11, 11)
    _poly(p, [(15, 9), (15, 4), (4, 4), (4, 15), (9, 15)])


def _paste(p: QPainter) -> None:
    _rect(p, 5, 5, 14, 16)
    _rect(p, 9, 3, 6, 4, 1)


def _duplicate(p: QPainter) -> None:
    _copy(p)
    _line(p, 14.5, 12, 14.5, 17)
    _line(p, 12, 14.5, 17, 14.5)


def _trash(p: QPainter) -> None:
    _line(p, 4, 6, 20, 6)
    _poly(p, [(9, 6), (9, 3.5), (15, 3.5), (15, 6)])
    _poly(p, [(6, 6), (7, 21), (17, 21), (18, 6)])
    _line(p, 10, 10, 10, 17)
    _line(p, 14, 10, 14, 17)


# --- playback ---------------------------------------------------------------------


def _play(p: QPainter) -> None:
    _poly(p, [(7, 4), (20, 12), (7, 20)], fill=True)


def _pause(p: QPainter) -> None:
    _rect(p, 6, 4, 4, 16, 1, fill=True)
    _rect(p, 14, 4, 4, 16, 1, fill=True)


def _stop(p: QPainter) -> None:
    _rect(p, 5, 5, 14, 14, 2, fill=True)


def _skip_back(p: QPainter) -> None:
    _line(p, 5, 5, 5, 19)
    _poly(p, [(19, 5), (8, 12), (19, 19)], fill=True)


def _skip_forward(p: QPainter) -> None:
    _line(p, 19, 5, 19, 19)
    _poly(p, [(5, 5), (16, 12), (5, 19)], fill=True)


def _record(p: QPainter) -> None:
    _circle(p, 12, 12, 6, fill=True)


def _render(p: QPainter) -> None:
    _rect(p, 3, 5, 18, 14)
    for x in (6, 10, 14, 18):
        _line(p, x, 5, x, 7.5)
        _line(p, x, 16.5, x, 19)
    _poly(p, [(10, 9.5), (14.5, 12), (10, 14.5)], fill=True)


def _export(p: QPainter) -> None:
    _poly(p, [(4, 14), (4, 20), (20, 20), (20, 14)])
    _line(p, 12, 3, 12, 15)
    _poly(p, [(7, 8), (12, 3), (17, 8)])


def _clock(p: QPainter) -> None:
    _circle(p, 12, 12, 9)
    _poly(p, [(12, 7), (12, 12), (15.5, 14)])


# --- view ---------------------------------------------------------------------------


def _grid(p: QPainter) -> None:
    _rect(p, 4, 4, 16, 16)
    for value in (9.33, 14.66):
        _line(p, value, 4, value, 20)
        _line(p, 4, value, 20, value)


def _magnet(p: QPainter) -> None:
    path = QPainterPath(QPointF(5, 4))
    path.lineTo(5, 12)
    path.cubicTo(5, 21, 19, 21, 19, 12)
    path.lineTo(19, 4)
    p.drawPath(path)
    _line(p, 5, 8, 9, 8)
    _line(p, 15, 8, 19, 8)
    _line(p, 9, 4, 9, 12)
    _line(p, 15, 4, 15, 12)
    path = QPainterPath(QPointF(9, 12))
    path.cubicTo(9, 16, 15, 16, 15, 12)
    p.drawPath(path)


def _fit(p: QPainter) -> None:
    _poly(p, [(4, 9), (4, 4), (9, 4)])
    _poly(p, [(15, 4), (20, 4), (20, 9)])
    _poly(p, [(20, 15), (20, 20), (15, 20)])
    _poly(p, [(9, 20), (4, 20), (4, 15)])


def _magnifier(p: QPainter) -> None:
    _circle(p, 10.5, 10.5, 6.5)
    _line(p, 15.5, 15.5, 20.5, 20.5)


def _zoom_in(p: QPainter) -> None:
    _magnifier(p)
    _line(p, 10.5, 7.5, 10.5, 13.5)
    _line(p, 7.5, 10.5, 13.5, 10.5)


def _zoom_out(p: QPainter) -> None:
    _magnifier(p)
    _line(p, 7.5, 10.5, 13.5, 10.5)


def _eye(p: QPainter) -> None:
    path = QPainterPath(QPointF(2.5, 12))
    path.cubicTo(6, 5, 18, 5, 21.5, 12)
    path.cubicTo(18, 19, 6, 19, 2.5, 12)
    p.drawPath(path)
    _circle(p, 12, 12, 3)


def _eye_off(p: QPainter) -> None:
    _eye(p)
    _line(p, 4, 4, 20, 20)


def _lock(p: QPainter) -> None:
    _rect(p, 5, 11, 14, 10)
    path = QPainterPath(QPointF(8, 11))
    path.lineTo(8, 8)
    path.cubicTo(8, 2.5, 16, 2.5, 16, 8)
    path.lineTo(16, 11)
    p.drawPath(path)


def _unlock(p: QPainter) -> None:
    _rect(p, 5, 11, 14, 10)
    path = QPainterPath(QPointF(8, 11))
    path.lineTo(8, 8)
    path.cubicTo(8, 2.5, 16, 2.5, 16, 7)
    p.drawPath(path)


def _layers(p: QPainter) -> None:
    _poly(p, [(12, 3), (21, 8), (12, 13), (3, 8)], closed=True)
    _poly(p, [(3, 12), (12, 17), (21, 12)])
    _poly(p, [(3, 16), (12, 21), (21, 16)])


# --- generic ---------------------------------------------------------------------------


def _plus(p: QPainter) -> None:
    _line(p, 12, 5, 12, 19)
    _line(p, 5, 12, 19, 12)


def _minus(p: QPainter) -> None:
    _line(p, 5, 12, 19, 12)


def _close(p: QPainter) -> None:
    _line(p, 6, 6, 18, 18)
    _line(p, 18, 6, 6, 18)


def _check(p: QPainter) -> None:
    _poly(p, [(5, 12.5), (10, 17.5), (19, 7)])


def _chevron_down(p: QPainter) -> None:
    _poly(p, [(6, 9), (12, 15), (18, 9)])


def _chevron_up(p: QPainter) -> None:
    _poly(p, [(6, 15), (12, 9), (18, 15)])


def _chevron_right(p: QPainter) -> None:
    _poly(p, [(9, 6), (15, 12), (9, 18)])


def _chevron_left(p: QPainter) -> None:
    _poly(p, [(15, 6), (9, 12), (15, 18)])


def _menu(p: QPainter) -> None:
    for y in (6, 12, 18):
        _line(p, 4, y, 20, y)


def _search(p: QPainter) -> None:
    _magnifier(p)


def _settings(p: QPainter) -> None:
    _circle(p, 12, 12, 3)
    _circle(p, 12, 12, 6.5)
    for index in range(8):
        angle = index * math.pi / 4
        _line(p, 12 + 6.5 * math.cos(angle), 12 + 6.5 * math.sin(angle), 12 + 9.5 * math.cos(angle), 12 + 9.5 * math.sin(angle))


def _help(p: QPainter) -> None:
    _circle(p, 12, 12, 9)
    _text(p, "?", 13)


def _info(p: QPainter) -> None:
    _circle(p, 12, 12, 9)
    _line(p, 12, 11, 12, 17)
    _circle(p, 12, 7.5, 0.6, fill=True)


def _warning(p: QPainter) -> None:
    _poly(p, [(12, 3), (22, 20), (2, 20)], closed=True)
    _line(p, 12, 9, 12, 14)
    _circle(p, 12, 17, 0.6, fill=True)


def _sparkle(p: QPainter) -> None:
    path = QPainterPath(QPointF(10, 3))
    path.cubicTo(10, 9, 11, 10, 17, 10)
    path.cubicTo(11, 10, 10, 11, 10, 17)
    path.cubicTo(10, 11, 9, 10, 3, 10)
    path.cubicTo(9, 10, 10, 9, 10, 3)
    p.drawPath(path)
    _line(p, 18, 15, 18, 21)
    _line(p, 15, 18, 21, 18)


def _wand(p: QPainter) -> None:
    _line(p, 4, 20, 15, 9)
    _line(p, 17, 3, 17, 7)
    _line(p, 15, 5, 19, 5)
    _line(p, 20, 10, 20, 13)
    _line(p, 18.5, 11.5, 21.5, 11.5)


def _lightbulb(p: QPainter) -> None:
    path = QPainterPath(QPointF(9, 16))
    path.cubicTo(9, 13, 6, 12, 6, 9)
    path.cubicTo(6, 2, 18, 2, 18, 9)
    path.cubicTo(18, 12, 15, 13, 15, 16)
    path.lineTo(9, 16)
    p.drawPath(path)
    _line(p, 9.5, 19, 14.5, 19)
    _line(p, 10.5, 21.5, 13.5, 21.5)


def _template(p: QPainter) -> None:
    _rect(p, 3, 3, 18, 18)
    _line(p, 3, 9, 21, 9)
    _line(p, 10, 9, 10, 21)


def _image(p: QPainter) -> None:
    _rect(p, 3, 4, 18, 16)
    _circle(p, 8.5, 9, 1.8)
    _poly(p, [(3, 18), (9, 12.5), (13, 16), (16, 13), (21, 17)])


def _text_icon(p: QPainter) -> None:
    _line(p, 5, 5, 19, 5)
    _line(p, 12, 5, 12, 20)
    _line(p, 9, 20, 15, 20)


def _graph(p: QPainter) -> None:
    _line(p, 3, 20, 21, 20)
    _line(p, 4, 3, 4, 21)
    path = QPainterPath(QPointF(5, 17))
    path.cubicTo(9, 2, 12, 22, 20, 5)
    p.drawPath(path)


def _camera(p: QPainter) -> None:
    _rect(p, 3, 7, 13, 11)
    _poly(p, [(16, 10), (21, 7), (21, 18), (16, 15)], closed=True)


def _group(p: QPainter) -> None:
    p.save()
    pen = p.pen()
    pen.setStyle(Qt.PenStyle.DashLine)
    p.setPen(pen)
    _rect(p, 2.5, 2.5, 19, 19, 3)
    p.restore()
    _rect(p, 6, 6, 7, 7, 1)
    _circle(p, 15, 15, 3.5)


def _ungroup(p: QPainter) -> None:
    _rect(p, 3, 3, 9, 9, 1)
    _circle(p, 16.5, 16.5, 4.5)


def _move(p: QPainter) -> None:
    _line(p, 12, 3, 12, 21)
    _line(p, 3, 12, 21, 12)
    _poly(p, [(9, 6), (12, 3), (15, 6)])
    _poly(p, [(9, 18), (12, 21), (15, 18)])
    _poly(p, [(6, 9), (3, 12), (6, 15)])
    _poly(p, [(18, 9), (21, 12), (18, 15)])


def _rotate(p: QPainter) -> None:
    _arc(p, 12, 12, 8, 30, 280)
    _poly(p, [(19, 3.5), (19, 8), (14.5, 8)])


def _scale(p: QPainter) -> None:
    _rect(p, 3, 11, 10, 10, 1)
    _poly(p, [(14, 4), (20, 4), (20, 10)])
    _line(p, 20, 4, 12, 12)


def _music(p: QPainter) -> None:
    _poly(p, [(9, 18), (9, 5), (20, 3), (20, 16)])
    _circle(p, 6.5, 18, 2.5)
    _circle(p, 17.5, 16, 2.5)


def _package(p: QPainter) -> None:
    _poly(p, [(12, 2.5), (21, 7), (21, 17), (12, 21.5), (3, 17), (3, 7)], closed=True)
    _poly(p, [(3, 7), (12, 11.5), (21, 7)])
    _line(p, 12, 11.5, 12, 21.5)


def _scene(p: QPainter) -> None:
    _rect(p, 3, 8, 18, 13)
    _poly(p, [(3, 8), (5, 3), (21, 3), (21, 8)])
    _line(p, 9, 3, 7, 8)
    _line(p, 15, 3, 13, 8)


def _dot(p: QPainter) -> None:
    _circle(p, 12, 12, 3.5, fill=True)


def _align(direction: str) -> Drawer:
    def draw(p: QPainter) -> None:
        if direction in ("left", "center_h", "right"):
            x = {"left": 4, "center_h": 12, "right": 20}[direction]
            _line(p, x, 3, x, 21)
            widths = (12, 7)
            for index, width in enumerate(widths):
                y = 6 + index * 7
                left = {"left": 6, "center_h": 12 - width / 2, "right": 18 - width}[direction]
                _rect(p, left, y, width, 5, 1)
        else:
            y = {"top": 4, "center_v": 12, "bottom": 20}[direction]
            _line(p, 3, y, 21, y)
            heights = (12, 7)
            for index, height in enumerate(heights):
                x = 6 + index * 7
                top = {"top": 6, "center_v": 12 - height / 2, "bottom": 18 - height}[direction]
                _rect(p, x, top, 5, height, 1)

    return draw


def _distribute(horizontal: bool) -> Drawer:
    def draw(p: QPainter) -> None:
        for index in range(3):
            offset = 3 + index * 7
            if horizontal:
                _rect(p, offset, 7, 4, 10, 1)
            else:
                _rect(p, 7, offset, 10, 4, 1)

    return draw


def _table_edit(row: bool, add: bool) -> Drawer:
    def draw(p: QPainter) -> None:
        _rect(p, 3, 3, 13, 13, 1.5)
        if row:
            _line(p, 3, 9.5, 16, 9.5)
        else:
            _line(p, 9.5, 3, 9.5, 16)
        _line(p, 15, 19, 22, 19)
        if add:
            _line(p, 18.5, 15.5, 18.5, 22.5)

    return draw


def _ruler(p: QPainter) -> None:
    _poly(p, [(3, 9), (21, 9), (21, 16), (3, 16)], closed=True)
    for x in (6, 9, 12, 15, 18):
        _line(p, x, 9, x, 12 if x % 2 else 13.5)


def _zoom_selection(p: QPainter) -> None:
    _magnifier(p)
    _rect(p, 7, 7, 6, 6, 1)


def _vertex(p: QPainter) -> None:
    _poly(p, [(4, 19), (10, 5), (20, 10), (17, 20)], closed=True)
    for x, y in ((4, 19), (10, 5), (20, 10), (17, 20)):
        _rect(p, x - 2, y - 2, 4, 4, 0.5, fill=True)


def _a_spin_in(p: QPainter) -> None:
    _rect(p, 9, 9, 6, 6, 1)
    _arc(p, 12, 12, 8.5, 20, 140)
    _arc(p, 12, 12, 8.5, 200, 140)
    _arrow_head(p, 4.5, 8.2, math.radians(250), 3.5)
    _arrow_head(p, 19.5, 15.8, math.radians(70), 3.5)


def _a_add_letters(p: QPainter) -> None:
    _text(p, "A", size=11, rect=QRectF(1, 4, 8, 14))
    _text(p, "B", size=11, rect=QRectF(8, 4, 8, 14))
    p.save()
    pen = p.pen()
    pen.setStyle(Qt.PenStyle.DotLine)
    p.setPen(pen)
    _line(p, 17, 7, 17, 17)
    p.restore()
    _line(p, 3, 20, 21, 20)


def _a_grow_arrow(p: QPainter) -> None:
    _line(p, 3, 18, 15, 6)
    _poly(p, [(9, 5), (16, 5), (16, 12)])
    p.save()
    pen = p.pen()
    pen.setStyle(Qt.PenStyle.DotLine)
    p.setPen(pen)
    _line(p, 16, 5, 21, 0)
    p.restore()


def _a_shrink(p: QPainter) -> None:
    _rect(p, 10, 10, 4, 4, 1)
    for x1, y1, x2, y2 in ((3, 3, 7.5, 7.5), (21, 3, 16.5, 7.5), (3, 21, 7.5, 16.5), (21, 21, 16.5, 16.5)):
        _line(p, x1, y1, x2, y2)
    _poly(p, [(7.5, 4), (7.5, 7.5), (4, 7.5)])
    _poly(p, [(16.5, 4), (16.5, 7.5), (20, 7.5)])
    _poly(p, [(4, 16.5), (7.5, 16.5), (7.5, 20)])
    _poly(p, [(20, 16.5), (16.5, 16.5), (16.5, 20)])


def _a_flash(p: QPainter) -> None:
    _circle(p, 12, 12, 2.5, fill=True)
    for k in range(8):
        angle = math.radians(45 * k)
        _line(p, 12 + 5 * math.cos(angle), 12 + 5 * math.sin(angle), 12 + 9.5 * math.cos(angle), 12 + 9.5 * math.sin(angle))


def _a_wiggle(p: QPainter) -> None:
    p.save()
    p.translate(12, 12)
    p.rotate(-12)
    _rect(p, -5, -5, 10, 10, 1.5)
    p.restore()
    _arc(p, 12, 12, 9.5, 120, 40)
    _arc(p, 12, 12, 9.5, 300, 40)


def _a_wave(p: QPainter) -> None:
    path = QPainterPath(QPointF(2, 12))
    for index in range(1, 41):
        x = 2 + 20 * index / 40
        path.lineTo(QPointF(x, 12 - 5 * math.sin(index / 40 * math.pi) * math.sin(index / 40 * 4 * math.pi)))
    p.drawPath(path)
    _line(p, 2, 19, 22, 19)


def _a_focus(p: QPainter) -> None:
    _circle(p, 12, 12, 9)
    _circle(p, 12, 12, 4.5)
    _circle(p, 12, 12, 1.2, fill=True)


def _a_fade_transform(p: QPainter) -> None:
    p.save()
    pen = p.pen()
    pen.setStyle(Qt.PenStyle.DotLine)
    p.setPen(pen)
    _circle(p, 6.5, 12, 4)
    p.restore()
    _rect(p, 14, 8, 8, 8, 1)
    _line(p, 9.5, 5, 15, 5)
    _poly(p, [(13, 3), (15, 5), (13, 7)])


def _a_matching(p: QPainter) -> None:
    _text(p, "ab", size=9, rect=QRectF(0, 2, 11, 10))
    _text(p, "ba", size=9, rect=QRectF(13, 12, 11, 10))
    _line(p, 6, 13, 16, 13)
    _poly(p, [(14, 11), (16, 13), (14, 15)])


def _a_path(p: QPainter) -> None:
    path = QPainterPath(QPointF(3, 19))
    path.cubicTo(6, 4, 14, 22, 20, 6)
    p.save()
    pen = p.pen()
    pen.setStyle(Qt.PenStyle.DashLine)
    p.setPen(pen)
    p.drawPath(path)
    p.restore()
    _circle(p, 20, 6, 2.6, fill=True)


def _a_swap(p: QPainter) -> None:
    _circle(p, 5, 15, 3)
    _rect(p, 16, 12, 6, 6, 1)
    _arc(p, 12, 13, 7, 30, 120)
    _arrow_head(p, 18.1, 9.5, math.radians(60), 3)
    _arc(p, 12, 14, 7, 210, 120)
    _arrow_head(p, 5.9, 17.5, math.radians(240), 3)


def _a_orbit(p: QPainter) -> None:
    p.save()
    pen = p.pen()
    pen.setStyle(Qt.PenStyle.DashLine)
    p.setPen(pen)
    p.drawEllipse(QRectF(2, 8, 20, 9))
    p.restore()
    _rect(p, 8, 2, 8, 6, 1)
    _arrow_head(p, 20.5, 14.5, math.radians(110), 3)


def _a_value(p: QPainter) -> None:
    _line(p, 3, 17, 21, 17)
    _circle(p, 15, 17, 2.6, fill=True)
    _text(p, "1.5", size=9, rect=QRectF(2, 2, 20, 11))


# --- animation kinds ---------------------------------------------------------------------


def _a_create(p: QPainter) -> None:
    _arc(p, 12, 12, 8, 90, 270)
    _circle(p, 12, 4, 1.6, fill=True)


def _a_write(p: QPainter) -> None:
    _poly(p, [(14, 4), (19, 9), (9, 19), (4, 20), (5, 15), (14, 4)])
    _line(p, 12, 6, 17, 11)


def _a_draw_fill(p: QPainter) -> None:
    _rect(p, 4, 4, 16, 16)
    p.save()
    p.setBrush(p.pen().color())
    p.drawPolygon(QPolygonF([QPointF(4, 20), QPointF(20, 4), QPointF(20, 20)]))
    p.restore()


def _a_fade_in(p: QPainter) -> None:
    p.save()
    pen = p.pen()
    pen.setStyle(Qt.PenStyle.DotLine)
    p.setPen(pen)
    _circle(p, 12, 12, 9)
    p.restore()
    _circle(p, 12, 12, 4.5, fill=True)


def _a_grow(p: QPainter) -> None:
    _rect(p, 9, 9, 6, 6, 1)
    for x1, y1, x2, y2 in ((7, 7, 3, 3), (17, 7, 21, 3), (7, 17, 3, 21), (17, 17, 21, 21)):
        _line(p, x1, y1, x2, y2)
    _poly(p, [(3, 6.5), (3, 3), (6.5, 3)])
    _poly(p, [(17.5, 3), (21, 3), (21, 6.5)])
    _poly(p, [(3, 17.5), (3, 21), (6.5, 21)])
    _poly(p, [(21, 17.5), (21, 21), (17.5, 21)])


def _a_grow_edge(p: QPainter) -> None:
    _line(p, 3, 21, 21, 21)
    _rect(p, 8, 11, 8, 10, 1)
    _line(p, 12, 9, 12, 3)
    _poly(p, [(9.5, 5.5), (12, 3), (14.5, 5.5)])


def _a_type_cursor(p: QPainter) -> None:
    _text(p, "Ab", size=11, rect=QRectF(1, 4, 15, 14))
    _rect(p, 17, 5, 2.4, 14, 0.5, fill=True)


def _a_unwrite(p: QPainter) -> None:
    _text(p, "A", size=12, rect=QRectF(1, 3, 11, 14))
    p.save()
    pen = p.pen()
    pen.setStyle(Qt.PenStyle.DotLine)
    p.setPen(pen)
    _line(p, 13, 15, 21, 15)
    p.restore()
    _line(p, 21, 19, 13, 19)
    _poly(p, [(15, 17), (13, 19), (15, 21)])


def _a_from_copy(p: QPainter) -> None:
    _circle(p, 6, 7, 3.5)
    p.save()
    pen = p.pen()
    pen.setStyle(Qt.PenStyle.DotLine)
    p.setPen(pen)
    _circle(p, 6, 17, 3.5)
    p.restore()
    _rect(p, 15, 13, 7, 7, 1)
    _line(p, 10, 17, 14, 17)
    _poly(p, [(12.5, 15.5), (14, 17), (12.5, 18.5)])


def _a_passing_flash(p: QPainter) -> None:
    p.save()
    pen = p.pen()
    pen.setStyle(Qt.PenStyle.DotLine)
    p.setPen(pen)
    _rect(p, 4, 4, 16, 16, 3)
    p.restore()
    p.save()
    pen = p.pen()
    pen.setWidthF(pen.widthF() * 2.2)
    p.setPen(pen)
    _line(p, 7, 4, 15, 4)
    p.restore()


def _a_broadcast(p: QPainter) -> None:
    _circle(p, 12, 12, 2, fill=True)
    _circle(p, 12, 12, 5.5)
    p.save()
    pen = p.pen()
    pen.setStyle(Qt.PenStyle.DotLine)
    p.setPen(pen)
    _circle(p, 12, 12, 9)
    p.restore()


def _a_apply_matrix(p: QPainter) -> None:
    # a square grid sheared into a parallelogram grid
    p.save()
    p.setOpacity(0.45)
    _rect(p, 3, 7, 12, 12, 0)
    p.restore()
    for offset in (0.0, 6.0, 12.0):
        _line(p, 3 + offset + 6, 7, 3 + offset, 19)
    _line(p, 9, 7, 21, 7)
    _line(p, 6, 13, 18, 13)
    _line(p, 3, 19, 15, 19)


def _a_apply_complex(p: QPainter) -> None:
    # the grid lines x = ±1 bent into two parabolas by z -> z^2, and the real axis
    for sign in (1, -1):
        path = QPainterPath()
        for index in range(17):
            v = -1 + index / 8
            point = QPointF(12 + sign * (7 * (1 - v * v) - 3), 12 - 8 * v)
            if index == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        p.drawPath(path)
    _line(p, 3, 12, 21, 12)


def _a_apply_pointwise(p: QPainter) -> None:
    # two wavy lines in each direction (x + sin y, y + sin x)
    for k in (8, 16):
        vertical, horizontal = QPainterPath(QPointF(k, 3)), QPainterPath(QPointF(3, k))
        for index in range(1, 19):
            t = 3 + index
            vertical.lineTo(QPointF(k + 1.4 * math.sin(t / 2.2), t))
            horizontal.lineTo(QPointF(t, k + 1.4 * math.sin(t / 2.2)))
        p.drawPath(vertical)
        p.drawPath(horizontal)


def _a_network_parts(p: QPainter) -> None:
    points = ((5, 18), (12, 5), (19, 18))
    _line(p, *points[0], *points[2])
    p.save()
    pen = p.pen()
    pen.setWidthF(pen.widthF() * 1.8)
    p.setPen(pen)
    _line(p, *points[0], *points[1])
    p.restore()
    _line(p, *points[1], *points[2])
    _circle(p, *points[0], 2.6, fill=True)
    _circle(p, *points[1], 2.6, fill=True)
    _circle(p, *points[2], 2.6)


def _a_one_by_one(p: QPainter) -> None:
    for row, alpha in enumerate((1.0, 0.65, 0.3)):
        p.save()
        p.setOpacity(alpha)
        y = 6 + row * 6
        _circle(p, 5, y, 1.3, fill=True)
        _line(p, 9, y, 20 - row * 2, y)
        p.restore()


def _a_transform(p: QPainter) -> None:
    _circle(p, 6.5, 12, 4)
    _rect(p, 14, 8, 8, 8, 1)
    _line(p, 9.5, 5, 15, 5)
    _poly(p, [(13, 3), (15, 5), (13, 7)])


def _a_replace(p: QPainter) -> None:
    _circle(p, 6.5, 12, 4)
    _rect(p, 14, 8, 8, 8, 1)
    _line(p, 9, 5, 15, 5)
    _poly(p, [(13, 3), (15, 5), (13, 7)])
    _line(p, 15, 19, 9, 19)
    _poly(p, [(11, 17), (9, 19), (11, 21)])


def _a_color(p: QPainter) -> None:
    path = QPainterPath(QPointF(12, 3))
    path.cubicTo(12, 3, 5, 11, 5, 15)
    path.cubicTo(5, 19, 8.5, 21, 12, 21)
    path.cubicTo(15.5, 21, 19, 19, 19, 15)
    path.cubicTo(19, 11, 12, 3, 12, 3)
    p.drawPath(path)


def _a_circumscribe(p: QPainter) -> None:
    p.save()
    pen = p.pen()
    pen.setStyle(Qt.PenStyle.DashLine)
    p.setPen(pen)
    _rect(p, 3, 6, 18, 12, 2)
    p.restore()
    _circle(p, 12, 12, 2.5, fill=True)


def _a_fade_out(p: QPainter) -> None:
    p.save()
    pen = p.pen()
    pen.setStyle(Qt.PenStyle.DotLine)
    p.setPen(pen)
    _circle(p, 10, 13, 6.5)
    p.restore()
    _line(p, 14, 9, 20, 3)
    _poly(p, [(15.5, 3), (20, 3), (20, 7.5)])


def _a_uncreate(p: QPainter) -> None:
    _arc(p, 12, 12, 8, 90, -150)
    p.save()
    pen = p.pen()
    pen.setStyle(Qt.PenStyle.DotLine)
    p.setPen(pen)
    _arc(p, 12, 12, 8, 300, -210)
    p.restore()


ICONS: dict[str, Drawer] = {
    "new": _new,
    "open": _open,
    "save": _save,
    "undo": _undo,
    "redo": _redo,
    "cut": _cut,
    "copy": _copy,
    "paste": _paste,
    "duplicate": _duplicate,
    "trash": _trash,
    "play": _play,
    "pause": _pause,
    "stop": _stop,
    "skip_back": _skip_back,
    "skip_forward": _skip_forward,
    "record": _record,
    "render": _render,
    "export": _export,
    "clock": _clock,
    "grid": _grid,
    "magnet": _magnet,
    "fit": _fit,
    "zoom_in": _zoom_in,
    "zoom_out": _zoom_out,
    "eye": _eye,
    "eye_off": _eye_off,
    "lock": _lock,
    "unlock": _unlock,
    "layers": _layers,
    "plus": _plus,
    "minus": _minus,
    "close": _close,
    "check": _check,
    "chevron_down": _chevron_down,
    "chevron_up": _chevron_up,
    "chevron_right": _chevron_right,
    "chevron_left": _chevron_left,
    "menu": _menu,
    "search": _search,
    "settings": _settings,
    "help": _help,
    "info": _info,
    "warning": _warning,
    "sparkle": _sparkle,
    "wand": _wand,
    "lightbulb": _lightbulb,
    "template": _template,
    "image": _image,
    "text": _text_icon,
    "graph": _graph,
    "camera": _camera,
    "group": _group,
    "ungroup": _ungroup,
    "move": _move,
    "rotate": _rotate,
    "scale": _scale,
    "music": _music,
    "package": _package,
    "scene": _scene,
    "dot": _dot,
    "align_left": _align("left"),
    "align_center_h": _align("center_h"),
    "align_right": _align("right"),
    "align_top": _align("top"),
    "align_center_v": _align("center_v"),
    "align_bottom": _align("bottom"),
    "distribute_h": _distribute(True),
    "distribute_v": _distribute(False),
    "row_add": _table_edit(True, True),
    "row_remove": _table_edit(True, False),
    "column_add": _table_edit(False, True),
    "column_remove": _table_edit(False, False),
    "zoom_selection": _zoom_selection,
    "ruler": _ruler,
    "vertex": _vertex,
    "a_create": _a_create,
    "a_write": _a_write,
    "a_draw_border_then_fill": _a_draw_fill,
    "a_fade_in": _a_fade_in,
    "a_grow_from_center": _a_grow,
    "a_transform": _a_transform,
    "a_replacement_transform": _a_replace,
    "a_move": _move,
    "a_scale": _scale,
    "a_rotate": _rotate,
    "a_change_color": _a_color,
    "a_set_value": _a_value,
    "a_spin_in": _a_spin_in,
    "a_grow_from_edge": _a_grow_edge,
    "a_type_with_cursor": _a_type_cursor,
    "a_unwrite": _a_unwrite,
    "a_transform_from_copy": _a_from_copy,
    "a_passing_flash": _a_passing_flash,
    "a_broadcast": _a_broadcast,
    "a_network_parts": _a_network_parts,
    "a_apply_matrix": _a_apply_matrix,
    "a_apply_complex": _a_apply_complex,
    "a_apply_pointwise": _a_apply_pointwise,
    "a_one_by_one": _a_one_by_one,
    "a_add_letters": _a_add_letters,
    "a_grow_arrow": _a_grow_arrow,
    "a_shrink_to_center": _a_shrink,
    "a_flash": _a_flash,
    "a_wiggle": _a_wiggle,
    "a_apply_wave": _a_wave,
    "a_focus_on": _a_focus,
    "a_fade_transform": _a_fade_transform,
    "a_transform_matching": _a_matching,
    "a_move_along_path": _a_path,
    "a_swap": _a_swap,
    "a_orbit": _a_orbit,
    "a_indicate": _sparkle,
    "a_circumscribe": _a_circumscribe,
    "a_fade_out": _a_fade_out,
    "a_uncreate": _a_uncreate,
}


def paint_icon(painter: QPainter, rect: QRect | QRectF, name: str, color: QColor) -> None:
    """Paint icon ``name`` into ``rect`` with ``color``."""
    drawer = ICONS.get(name)
    if drawer is None:
        return
    target = QRectF(rect)
    side = min(target.width(), target.height())
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.translate(target.center().x() - side / 2, target.center().y() - side / 2)
    painter.scale(side / 24.0, side / 24.0)
    pen = QPen(color, STROKE)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    drawer(painter)
    painter.restore()


class PaintedIconEngine(QIconEngine):
    """Icon engine that paints a named icon in theme-dependent colors."""

    def __init__(self, name: str, color: str | None = None) -> None:
        super().__init__()
        self.name = name
        self.color = color

    def _color(self, mode: QIcon.Mode, state: QIcon.State) -> QColor:
        from manim_studio.ui.theme import current_palette

        palette = current_palette()
        if mode == QIcon.Mode.Disabled:
            return QColor(palette.text_faint)
        if self.color is not None:
            return QColor(self.color)
        if state == QIcon.State.On or mode == QIcon.Mode.Selected:
            return QColor(palette.accent)
        return QColor(palette.text)

    def paint(self, painter: QPainter, rect: QRect, mode: QIcon.Mode, state: QIcon.State) -> None:
        paint_icon(painter, rect, self.name, self._color(mode, state))

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        self.paint(painter, QRect(0, 0, size.width(), size.height()), mode, state)
        painter.end()
        return QPixmap.fromImage(image)

    def clone(self) -> PaintedIconEngine:
        return PaintedIconEngine(self.name, self.color)


def icon(name: str, color: str | None = None) -> QIcon:
    """Return a themed icon by name (``color`` forces a fixed color)."""
    return QIcon(PaintedIconEngine(name, color))


def icon_image(name: str, color: str, size: int) -> QImage:
    """Render an icon into an image (used for style-sheet arrows)."""
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    paint_icon(painter, QRectF(0, 0, size, size), name, QColor(color))
    painter.end()
    return image
