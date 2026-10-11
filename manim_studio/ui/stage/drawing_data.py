"""Stage drawings of data plots and bar charts."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QBrush, QFont, QFontMetricsF, QPainterPath

from manim_studio.model import graphs
from manim_studio.model.data import bar_colors, bar_range, bar_values, color_gradient, data_points
from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.geometry import axes_to_scene, param_float
from manim_studio.model.state import ObjectState
from manim_studio.ui.stage.drawing import (
    PX,
    TEXT_CAP_HEIGHT_PER_POINT,
    Primitive,
    _color,
    _pen,
    pt,
)

DATA_LABEL_SIZE = 24.0
NUMBER_SIZE = 36.0
LABEL_BUFF = 0.25
TICK = 0.1


def _font(points: float) -> QFont:
    font = QFont()
    font.setPixelSize(max(1, round(TEXT_CAP_HEIGHT_PER_POINT * points * PX / 0.7)))
    return font


def data_primitives(scene: Scene, obj: SceneObject, state: ObjectState) -> tuple[list[Primitive], bool]:
    """Dots, connecting line and regression curve on a coordinate system."""
    axes = graphs.data_axes(scene, obj)
    points = data_points(obj)
    if axes is None or not points:
        path = QPainterPath()
        path.addRect(QRectF(-0.3 * PX, -0.3 * PX, 0.6 * PX, 0.6 * PX))
        return [Primitive(path=path, pen=_pen(state.stroke_color, 2.0, 0.6, 1.0))], True
    ox, oy = graphs.bound_anchor(scene, obj)

    def local(x: float, y: float) -> QPointF:
        sx, sy = axes_to_scene(axes, x, y)
        return pt(sx - ox, sy - oy)

    primitives = []
    style = obj.params.get("display", "dots")
    pen = _pen(state.stroke_color, obj.stroke_width, obj.stroke_opacity, state.scale)
    if style in ("line", "both") and len(points) > 1:
        line = QPainterPath(local(*points[0]))
        for point in points[1:]:
            line.lineTo(local(*point))
        primitives.append(Primitive(path=line, pen=pen))
    curve = graphs.regression_points(obj)
    if len(curve) > 1:
        path = QPainterPath(local(*curve[0]))
        for point in curve[1:]:
            path.lineTo(local(*point))
        primitives.append(Primitive(path=path, pen=pen))
    if style in ("dots", "both"):
        radius = param_float(obj.params, "radius", 0.08) * PX
        dots = QPainterPath()
        for point in points:
            dots.addEllipse(local(*point), radius, radius)
        primitives.append(Primitive(path=dots, brush=QBrush(_color(state.fill_color, obj.fill_opacity))))
    return primitives, False


def _number_text(value: float) -> str:
    return str(int(round(value))) if abs(value - round(value)) < 1e-9 else f"{value:g}"


def bar_chart_primitives(obj: SceneObject, state: ObjectState) -> tuple[list[Primitive], bool]:
    """A ``BarChart`` (axes, bars, names, numbers), centered later like ``move_to``."""
    bars = bar_values(obj)
    count = max(1, len(bars))
    x_length = param_float(obj.params, "x_length", 6.0)
    y_length = param_float(obj.params, "y_length", 4.0)
    y_min, y_max, y_step = bar_range(obj)

    def to_local(x: float, y: float) -> QPointF:
        lx = (x / count - 0.5) * x_length
        ly = ((y - y_min) / (y_max - y_min) - 0.5) * y_length
        return pt(lx, ly)

    axis_y = min(max(0.0, y_min), y_max)
    axes = QPainterPath(to_local(0, axis_y))
    axes.lineTo(to_local(count, axis_y))
    axes.moveTo(to_local(0, y_min))
    axes.lineTo(to_local(0, y_max))
    for index in range(count + 1):
        point = to_local(index, axis_y)
        axes.moveTo(QPointF(point.x(), point.y() - TICK * PX))
        axes.lineTo(QPointF(point.x(), point.y() + TICK * PX))
    labels = QPainterPath()
    number_font = _font(NUMBER_SIZE)
    number_metrics = QFontMetricsF(number_font)
    steps = int(round((y_max - y_min) / y_step)) if y_step > 0 else 0
    for index in range(steps + 1):
        value = y_min + index * y_step
        point = to_local(0, value)
        axes.moveTo(QPointF(point.x() - TICK * PX, point.y()))
        axes.lineTo(QPointF(point.x() + TICK * PX, point.y()))
        if abs(value) < 1e-9 or steps > 60:
            continue
        text = _number_text(value)
        labels.addText(
            QPointF(point.x() - LABEL_BUFF * PX - number_metrics.horizontalAdvance(text), point.y() + number_metrics.capHeight() / 2),
            number_font,
            text,
        )
    primitives = [Primitive(path=axes, pen=_pen("#FFFFFF", 2.0, 1.0, state.scale))]
    colors = color_gradient(bar_colors(obj), len(bars))
    width = param_float(obj.params, "bar_width", 0.6)
    name_font = _font(DATA_LABEL_SIZE)
    name_metrics = QFontMetricsF(name_font)
    for index, ((name, value), color) in enumerate(zip(bars, colors)):
        top_left = to_local(index + 0.5 - width / 2, max(value, 0.0))
        bottom_right = to_local(index + 0.5 + width / 2, min(value, 0.0))
        path = QPainterPath()
        path.addRect(QRectF(top_left, bottom_right))
        pen = _pen(color, obj.stroke_width, 1.0, state.scale) if obj.stroke_width > 0 else None
        primitives.append(Primitive(path=path, brush=QBrush(_color(color, obj.fill_opacity)), pen=pen))
        anchor = to_local(index + 0.5, axis_y)
        below = value >= 0
        y = anchor.y() + LABEL_BUFF * PX + name_metrics.capHeight() if below else anchor.y() - LABEL_BUFF * PX
        labels.addText(QPointF(anchor.x() - name_metrics.horizontalAdvance(name) / 2, y), name_font, name)
        if obj.params.get("show_values"):
            text = _number_text(value)
            tip = to_local(index + 0.5, value)
            y = tip.y() - LABEL_BUFF * PX if value >= 0 else tip.y() + LABEL_BUFF * PX + name_metrics.capHeight()
            value_path = QPainterPath()
            value_path.addText(QPointF(tip.x() - name_metrics.horizontalAdvance(text) / 2, y), name_font, text)
            primitives.append(Primitive(path=value_path, brush=QBrush(_color(color))))
    primitives.append(Primitive(path=labels, brush=QBrush(_color("#FFFFFF"))))
    return primitives, True
