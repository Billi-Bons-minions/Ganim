"""Stage drawings for the additional object kinds (approximations of Manim)."""

from __future__ import annotations

import math
import re
from html import escape

from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QTextDocument,
)

from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.extents import base_size, highlight_box, rotated_extent
from manim_studio.model.geometry import param_float
from manim_studio.model.groups import bounds_of, is_group, leaves
from manim_studio.model.state import ObjectState, initial_state
from manim_studio.model.types import ObjectKind
from manim_studio.ui.stage.drawing import (
    ARROW_TIP,
    PX,
    TEXT_CAP_HEIGHT_PER_POINT,
    Primitive,
    StageResources,
    _color,
    _pen,
    _polygon,
    _shape_primitive,
    _stroke_primitive,
    text_font,
)

NUMBER_LABEL_SIZE = 24.0
BRACE_THICKNESS = 0.27


def pt(x: float, y: float) -> QPointF:
    return QPointF(x * PX, -y * PX)


def _label_font(points: float) -> QFont:
    font = QFont()
    font.setPixelSize(max(1, round(TEXT_CAP_HEIGHT_PER_POINT * points * PX / 0.7)))
    return font


# --- lines -------------------------------------------------------------------------------


def _tip(x: float, direction: float, size: float) -> QPainterPath:
    return _polygon([(x, 0), (x - direction * size, size / 2), (x - direction * size, -size / 2)])


def vector_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    length = param_float(obj.params, "length", 2.0)
    tip = min(ARROW_TIP, 0.25 * length)
    shaft = QPainterPath(pt(0, 0))
    shaft.lineTo(pt(length - tip, 0))
    head = QBrush(_color(state.stroke_color, obj.stroke_opacity))
    return [_stroke_primitive(shaft, obj, state), Primitive(path=_tip(length, 1, tip), brush=head)]


def double_arrow_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    length = param_float(obj.params, "length", 3.0)
    tip = min(ARROW_TIP, 0.25 * length)
    shaft = QPainterPath(pt(-length / 2 + tip, 0))
    shaft.lineTo(pt(length / 2 - tip, 0))
    head = QBrush(_color(state.stroke_color, obj.stroke_opacity))
    return [
        _stroke_primitive(shaft, obj, state),
        Primitive(path=_tip(length / 2, 1, tip), brush=head),
        Primitive(path=_tip(-length / 2, -1, tip), brush=head),
    ]


def dashed_line_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    length = param_float(obj.params, "length", 3.0)
    dash = max(param_float(obj.params, "dash_length", 0.15), 0.01)
    ratio = max(0.05, min(0.95, param_float(obj.params, "dashed_ratio", 0.5)))
    count = max(2, math.ceil(length / dash * ratio))
    piece = length / count
    path = QPainterPath()
    for index in range(count):
        start = -length / 2 + index * piece
        path.moveTo(pt(start, 0))
        path.lineTo(pt(start + piece * ratio, 0))
    return [_stroke_primitive(path, obj, state)]


def number_line_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    params = obj.params
    low, high = param_float(params, "x_min", -5.0), param_float(params, "x_max", 5.0)
    step = max(param_float(params, "x_step", 1.0), 1e-6)
    length = param_float(params, "length", 10.0)
    span = (high - low) or 1.0
    to_x = lambda value: (value - (low + high) / 2) / span * length
    pen = _pen(state.stroke_color, obj.stroke_width, 1.0, state.scale)
    line = QPainterPath(pt(-length / 2, 0))
    tip = 0.35 if params.get("tips") else 0.0
    line.lineTo(pt(length / 2 - tip, 0))
    ticks = QPainterPath()
    labels = QPainterPath()
    font = _label_font(NUMBER_LABEL_SIZE)
    metrics = QFontMetricsF(font)
    count = int(round(span / step))
    for index in range(min(count, 400) + 1):
        value = low + index * step
        x = to_x(value)
        ticks.moveTo(pt(x, -0.1))
        ticks.lineTo(pt(x, 0.1))
        if params.get("show_numbers", True):
            text = str(int(round(value))) if abs(value - round(value)) < 1e-9 else f"{value:g}"
            anchor = pt(x, -0.25)
            labels.addText(QPointF(anchor.x() - metrics.horizontalAdvance(text) / 2, anchor.y() + metrics.capHeight()), font, text)
    primitives = [Primitive(path=line, pen=pen), Primitive(path=ticks, pen=pen)]
    if tip:
        primitives.append(Primitive(path=_tip(length / 2, 1, tip), brush=QBrush(_color(state.stroke_color))))
    if not labels.isEmpty():
        primitives.append(Primitive(path=labels, brush=QBrush(QColor("#FFFFFF"))))
    return primitives


def arc_points(radius: float, start: float, angle: float, samples: int = 64) -> list[tuple[float, float]]:
    """Points along an arc (degrees)."""
    return [
        (radius * math.cos(math.radians(start + angle * index / samples)), radius * math.sin(math.radians(start + angle * index / samples)))
        for index in range(samples + 1)
    ]


def arc_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    points = arc_points(param_float(obj.params, "radius", 1.5), param_float(obj.params, "start_angle", 0.0), param_float(obj.params, "angle", 120.0))
    path = QPainterPath(pt(*points[0]))
    for point in points[1:]:
        path.lineTo(pt(*point))
    return [_stroke_primitive(path, obj, state)]


def sector_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    points = arc_points(param_float(obj.params, "radius", 1.5), param_float(obj.params, "start_angle", 0.0), param_float(obj.params, "angle", 90.0))
    return [_shape_primitive(_polygon([(0.0, 0.0)] + points), obj, state)]


def annulus_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    outer, inner = param_float(obj.params, "outer_radius", 1.3), param_float(obj.params, "inner_radius", 0.7)
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.OddEvenFill)
    path.addEllipse(QPointF(0, 0), outer * PX, outer * PX)
    path.addEllipse(QPointF(0, 0), inner * PX, inner * PX)
    return [_shape_primitive(path, obj, state)]


def polygon_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    points = [(float(x), float(y)) for x, y in obj.params.get("points", [])] or [(0.0, 0.0)]
    return [_shape_primitive(_polygon(points), obj, state)]


def regular_polygon_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    n = max(3, int(obj.params.get("n", 6)))
    radius = param_float(obj.params, "radius", 1.0)
    start = 90.0 if n % 2 else 0.0
    points = [(radius * math.cos(math.radians(start + 360 * k / n)), radius * math.sin(math.radians(start + 360 * k / n))) for k in range(n)]
    return [_shape_primitive(_polygon(points), obj, state)]


def star_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    n = max(3, int(obj.params.get("n", 5)))
    outer, inner = param_float(obj.params, "outer_radius", 1.2), param_float(obj.params, "inner_radius", 0.5)
    points = []
    for k in range(n):
        for radius, offset in ((outer, 0.0), (inner, 180.0 / n)):
            angle = math.radians(90 + 360 * k / n + offset)
            points.append((radius * math.cos(angle), radius * math.sin(angle)))
    return [_shape_primitive(_polygon(points), obj, state)]


# --- brace -------------------------------------------------------------------------------


def _brace_path(width: float) -> QPainterPath:
    """A filled curly brace opening upwards, spanning ``width`` (centered at 0)."""
    w, t = width / 2, BRACE_THICKNESS
    upper = QPainterPath(pt(-w, t / 2))
    upper.cubicTo(pt(-w, 0), pt(-w + t * 0.4, -t * 0.05), pt(-w + t, -t * 0.05))
    upper.lineTo(pt(-t * 0.8, -t * 0.05))
    upper.cubicTo(pt(-t * 0.25, -t * 0.05), pt(-t * 0.05, -t * 0.25), pt(0, -t / 2))
    upper.cubicTo(pt(t * 0.05, -t * 0.25), pt(t * 0.25, -t * 0.05), pt(t * 0.8, -t * 0.05))
    upper.lineTo(pt(w - t, -t * 0.05))
    upper.cubicTo(pt(w - t * 0.4, -t * 0.05), pt(w, 0), pt(w, t / 2))
    upper.cubicTo(pt(w, t * 0.1), pt(w - t * 0.4, t * 0.15), pt(w - t, t * 0.15))
    upper.lineTo(pt(t * 0.8, t * 0.15))
    upper.cubicTo(pt(t * 0.3, t * 0.15), pt(t * 0.1, 0), pt(0, -t * 0.3))
    upper.cubicTo(pt(-t * 0.1, 0), pt(-t * 0.3, t * 0.15), pt(-t * 0.8, t * 0.15))
    upper.lineTo(pt(-w + t, t * 0.15))
    upper.cubicTo(pt(-w + t * 0.4, t * 0.15), pt(-w, t * 0.1), pt(-w, t / 2))
    upper.closeSubpath()
    return upper


def brace_span(scene: Scene, obj: SceneObject) -> float:
    """Length of a brace: the target's size along the brace, or the free width."""
    target = scene.object_by_id(obj.params.get("target"))
    horizontal = obj.params.get("direction", "down") in ("down", "up")
    if target is None or target.id == obj.id:
        return param_float(obj.params, "width", 3.0)
    if is_group(target):
        ids = leaves(scene, target.id)
        left, bottom, right, top = bounds_of(scene, ids, {leaf: initial_state(scene, scene.object_by_id(leaf)) for leaf in ids})
        return (right - left) if horizontal else (top - bottom)
    width, height = rotated_extent(*base_size(scene, target), target.rotation)
    return width if horizontal else height


def brace_primitives(scene: Scene, obj: SceneObject, state: ObjectState) -> tuple[list[Primitive], bool]:
    direction = obj.params.get("direction", "down")
    path = _brace_path(max(brace_span(scene, obj), 0.3))
    rotation = {"down": 0.0, "up": 180.0, "left": -90.0, "right": 90.0}.get(direction, 0.0)
    from PySide6.QtGui import QTransform

    path = QTransform().rotate(rotation).map(path)
    brush = QBrush(_color(state.fill_color, obj.fill_opacity))
    primitives = [Primitive(path=path, brush=brush)]
    label = str(obj.params.get("label", "")).strip()
    if label:
        font = text_font(obj, param_float(obj.params, "label_size", 36.0))
        text = QPainterPath()
        text.addText(QPointF(0, 0), font, label)
        bounds, gap = text.boundingRect(), (BRACE_THICKNESS / 2 + 0.15) * PX
        offsets = {
            "down": QPointF(-bounds.center().x(), gap - bounds.top()),
            "up": QPointF(-bounds.center().x(), -gap - bounds.bottom()),
            "left": QPointF(-gap - bounds.right(), -bounds.center().y()),
            "right": QPointF(gap - bounds.left(), -bounds.center().y()),
        }
        text.translate(offsets.get(direction, offsets["down"]))
        primitives.append(Primitive(path=text, brush=brush))
    attached = scene.object_by_id(obj.params.get("target")) is not None
    return primitives, not attached


def highlight_primitives(scene: Scene, obj: SceneObject, state: ObjectState) -> list[Primitive]:
    """Frame, background, underline or cross around the target (drawn around the target's center)."""
    box = highlight_box(scene, obj)
    if box is None:
        return []
    width, height = box
    buff = param_float(obj.params, "buff", 0.15)
    style = obj.params.get("style", "frame")
    w, h = (width + 2 * buff) * PX, (height + 2 * buff) * PX
    path = QPainterPath()
    if style == "underline":
        y = (height / 2 + buff) * PX
        path.moveTo(-width * PX / 2, y)
        path.lineTo(width * PX / 2, y)
        return [_stroke_primitive(path, obj, state)]
    if style == "cross":
        path.moveTo(-width * PX / 2, -height * PX / 2)
        path.lineTo(width * PX / 2, height * PX / 2)
        path.moveTo(-width * PX / 2, height * PX / 2)
        path.lineTo(width * PX / 2, -height * PX / 2)
        return [_stroke_primitive(path, obj, state)]
    if style == "background":
        path.addRect(QRectF(-w / 2, -h / 2, w, h))
        return [Primitive(path=path, brush=QBrush(_color(state.fill_color, param_float(obj.params, "opacity", 0.75))))]
    radius = min(param_float(obj.params, "corner_radius", 0.0) * PX, w / 2, h / 2)
    path.addRoundedRect(QRectF(-w / 2, -h / 2, w, h), radius, radius)
    return [_shape_primitive(path, obj, state)]


def field_primitives(scene: Scene, obj: SceneObject, state: ObjectState, resources: StageResources) -> list[Primitive]:
    """Arrows or stream lines of a vector field (relative to the object's position)."""
    from manim_studio.model.fields import field_arrows, magnitude_color, stream_lines

    ox, oy = obj.x, obj.y
    paths: dict[str, QPainterPath] = {}
    tips: dict[str, QPainterPath] = {}
    widths: dict[str, float] = {}

    def local(x: float, y: float) -> QPointF:
        return QPointF((x - ox) * PX, -(y - oy) * PX)

    if obj.params.get("display") == "stream":
        for line in stream_lines(scene, obj, resources.values):
            for (x1, y1, m1), (x2, y2, _m2) in zip(line, line[1:]):
                # colors are bucketed so that the stage needs only a few paths
                color = magnitude_color(obj, round(m1 * 8) / 8)
                path = paths.setdefault(color, QPainterPath())
                path.moveTo(local(x1, y1))
                path.lineTo(local(x2, y2))
                widths[color] = obj.stroke_width
    else:
        for arrow in field_arrows(scene, obj, resources.values):
            length = math.hypot(arrow.dx, arrow.dy)
            if length < 1e-6:
                continue
            tip = min(0.35, 0.25 * length)
            ux, uy = arrow.dx / length, arrow.dy / length
            end = (arrow.x + arrow.dx, arrow.y + arrow.dy)
            base = (end[0] - ux * tip, end[1] - uy * tip)
            path = paths.setdefault(arrow.color, QPainterPath())
            path.moveTo(local(arrow.x, arrow.y))
            path.lineTo(local(*base))
            head = tips.setdefault(arrow.color, QPainterPath())
            head.addPolygon(QPolygonF([local(*end), local(base[0] - uy * tip / 2, base[1] + ux * tip / 2), local(base[0] + uy * tip / 2, base[1] - ux * tip / 2)]))
            head.closeSubpath()
            widths[arrow.color] = min(6.0, 5.0 * length)
    primitives = [Primitive(path=path, pen=_pen(color, widths[color], obj.stroke_opacity, 1.0)) for color, path in paths.items()]
    primitives += [Primitive(path=path, brush=QBrush(_color(color, obj.stroke_opacity))) for color, path in tips.items()]
    return primitives


def trace_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    """The recorded positions of the traced object as a line."""
    values = state.geometry
    if len(values) < 4:
        return []
    path = QPainterPath(QPointF(values[0] * PX, -values[1] * PX))
    for index in range(2, len(values) - 1, 2):
        path.lineTo(values[index] * PX, -values[index + 1] * PX)
    return [_stroke_primitive(path, obj, state)]


def angle_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    """Arc (or right-angle corner) around the intersection plus the optional label."""
    if len(state.geometry) < 2:
        return []
    start, sweep = state.geometry[0], state.geometry[1]
    radius = param_float(obj.params, "radius", 0.6)
    r = radius * PX
    path = QPainterPath()
    if obj.params.get("right_angle"):
        a, b = math.radians(start), math.radians(start + sweep)
        first, second = (math.cos(a), math.sin(a)), (math.cos(b), math.sin(b))
        path.moveTo(first[0] * r, -first[1] * r)
        path.lineTo((first[0] + second[0]) * r, -(first[1] + second[1]) * r)
        path.lineTo(second[0] * r, -second[1] * r)
    else:
        rect = QRectF(-r, -r, 2 * r, 2 * r)
        path.arcMoveTo(rect, start)
        path.arcTo(rect, start, sweep)
    primitives = [_stroke_primitive(path, obj, state)]
    from manim_studio.model.angles import AngleGeometry, angle_label, label_position

    geometry = AngleGeometry(0.0, 0.0, start, sweep, (0.0, 0.0), (0.0, 0.0))
    label = angle_label(obj, geometry)
    if label:
        font = text_font(obj, param_float(obj.params, "label_size", 32.0))
        text = QPainterPath()
        text.addText(QPointF(0, 0), font, label)
        x, y = label_position(obj, geometry)
        bounds = text.boundingRect()
        text.translate(x * PX - bounds.center().x(), -y * PX - bounds.center().y())
        primitives.append(Primitive(path=text, brush=QBrush(_color(state.stroke_color, obj.stroke_opacity))))
    return primitives


# --- text-like -------------------------------------------------------------------------------


def decimal_text(obj: SceneObject, value: float | None = None) -> str:
    """Formatted value of a number object (as Manim shows it)."""
    value = param_float(obj.params, "value", 0.0) if value is None else value
    decimals = max(0, int(obj.params.get("decimals", 2)))
    text = f"{value:,.{decimals}f}"
    if obj.params.get("show_sign") and value >= 0:
        text = "+" + text
    return text + str(obj.params.get("unit", ""))


def decimal_primitives(scene: Scene, obj: SceneObject, state: ObjectState, resources: StageResources) -> list[Primitive]:
    value = state.value
    parameter = scene.object_by_id(obj.params.get("parameter_id"))
    if parameter is not None and parameter.kind == ObjectKind.PARAMETER:
        symbol = str(parameter.params.get("symbol", ""))
        values = resources.values or {}
        value = values.get(symbol, param_float(parameter.params, "value", 0.0))
    path = QPainterPath()
    path.addText(QPointF(0, 0), text_font(obj, param_float(obj.params, "font_size", 48.0)), decimal_text(obj, value))
    return [Primitive(path=path, brush=QBrush(_color(state.fill_color, obj.fill_opacity)))]


def _cells(obj: SceneObject) -> list[list[str]]:
    rows = [[str(cell) for cell in row] for row in obj.params.get("rows", []) if isinstance(row, list)]
    width = max((len(row) for row in rows), default=0)
    return [row + [""] * (width - len(row)) for row in rows]


def _grid(obj: SceneObject, font_size: float) -> tuple[list[list[str]], list[float], list[float], QFont]:
    rows = _cells(obj)
    font = text_font(obj, font_size)
    metrics = QFontMetricsF(font)
    columns = len(rows[0]) if rows else 0
    h_buff = param_float(obj.params, "h_buff", 1.0) * PX
    v_buff = param_float(obj.params, "v_buff", 0.5) * PX
    widths = [max(metrics.horizontalAdvance(row[c]) for row in rows) + h_buff for c in range(columns)]
    heights = [metrics.capHeight() * 1.4 + v_buff for _row in rows]
    return rows, widths, heights, font


def _cell_texts(rows: list[list[str]], widths: list[float], heights: list[float], font: QFont) -> QPainterPath:
    metrics = QFontMetricsF(font)
    path = QPainterPath()
    y = 0.0
    for row, height in zip(rows, heights):
        x = 0.0
        for cell, width in zip(row, widths):
            path.addText(QPointF(x + (width - metrics.horizontalAdvance(cell)) / 2, y + height / 2 + metrics.capHeight() / 2), font, cell)
            x += width
        y += height
    return path


def table_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    rows, widths, heights, font = _grid(obj, param_float(obj.params, "font_size", 32.0))
    if not rows:
        return []
    total_w, total_h = sum(widths), sum(heights)
    lines = QPainterPath()
    x = 0.0
    for width in widths[:-1]:
        x += width
        lines.moveTo(QPointF(x, 0))
        lines.lineTo(QPointF(x, total_h))
    y = 0.0
    for height in heights[:-1]:
        y += height
        lines.moveTo(QPointF(0, y))
        lines.lineTo(QPointF(total_w, y))
    if obj.params.get("outer_lines", True):
        lines.addRect(QRectF(0, 0, total_w, total_h))
    pen = _pen(state.stroke_color, obj.stroke_width, 1.0, state.scale)
    return [
        Primitive(path=lines, pen=pen),
        Primitive(path=_cell_texts(rows, widths, heights, font), brush=QBrush(_color(state.fill_color))),
    ]


def matrix_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    rows, widths, heights, font = _grid(obj, 48.0)
    if not rows:
        return []
    total_w, total_h = sum(widths), sum(heights)
    pad = 0.15 * PX
    brackets = QPainterPath()
    for x0, x1 in ((-pad, 0.0), (total_w + pad, total_w)):
        brackets.moveTo(QPointF(x1, -4))
        brackets.lineTo(QPointF(x0, -4))
        brackets.lineTo(QPointF(x0, total_h + 4))
        brackets.lineTo(QPointF(x1, total_h + 4))
    brush = QBrush(_color(state.fill_color, obj.fill_opacity))
    return [
        Primitive(path=brackets, pen=_pen(state.fill_color, 3.0, obj.fill_opacity, state.scale)),
        Primitive(path=_cell_texts(rows, widths, heights, font), brush=brush),
    ]


def code_primitives(obj: SceneObject) -> list[Primitive]:
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setPixelSize(max(1, round(param_float(obj.params, "font_size", 24.0) / 24.0 * 0.32 * PX)))
    metrics = QFontMetricsF(font)
    lines = str(obj.params.get("code", "")).split("\n")
    numbers = bool(obj.params.get("line_numbers", True))
    gutter = metrics.horizontalAdvance("00 ") if numbers else 0.0
    text = QPainterPath()
    number_path = QPainterPath()
    for index, line in enumerate(lines):
        y = (index + 1) * metrics.lineSpacing()
        text.addText(QPointF(gutter, y), font, line.replace("\t", "    "))
        if numbers:
            number_path.addText(QPointF(0, y), font, str(index + 1))
    content = text.boundingRect().united(number_path.boundingRect())
    margin = 0.2 * PX
    background = QPainterPath()
    background.addRoundedRect(content.adjusted(-margin, -margin, margin, margin), 0.15 * PX, 0.15 * PX)
    return [
        Primitive(path=background, pen=QPen(QColor("#FFFFFF"), 1.0), brush=QBrush(QColor("#222222"))),
        Primitive(path=number_path, brush=QBrush(QColor("#888888"))),
        Primitive(path=text, brush=QBrush(QColor("#E6E6E6"))),
    ]


_PANGO_ATTRIBUTES = re.compile(r'(fgcolor|foreground|color)\s*=\s*"([^"]*)"')


def markup_to_html(markup: str, color: str) -> str:
    """Convert a Pango markup subset to HTML for Qt."""
    html = markup.replace("\n", "<br>")
    html = re.sub(r"<span([^>]*)>", lambda m: f'<span style="color:{_span_color(m.group(1))}">', html)
    html = html.replace("<tt>", "<code>").replace("</tt>", "</code>")
    return f'<div style="color:{escape(color)}">{html}</div>'


def _span_color(attributes: str) -> str:
    match = _PANGO_ATTRIBUTES.search(attributes)
    return escape(match.group(2)) if match else "inherit"


def markup_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    document = QTextDocument()
    font = text_font(obj, param_float(obj.params, "font_size", 48.0))
    document.setDefaultFont(font)
    document.setDocumentMargin(0)
    document.setHtml(markup_to_html(str(obj.params.get("markup", "")), state.fill_color))
    size = document.size()
    scale = 2.0
    image = QImage(max(1, round(size.width() * scale)), max(1, round(size.height() * scale)), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.scale(scale, scale)
    document.drawContents(painter)
    painter.end()
    rect = QRectF(QPointF(0, 0), QSizeF(size))
    return [Primitive(image=image, rect=rect, brush=QBrush(QColor(255, 255, 255, round(255 * obj.fill_opacity))))]


def tex_primitives(obj: SceneObject, state: ObjectState, resources: StageResources) -> list[Primitive]:
    from manim_studio.ui.stage.drawing import tex_image_primitives

    return tex_image_primitives(obj, state, resources, str(obj.params.get("tex", "")), "center")


def extra_drawing(scene: Scene, obj: SceneObject, state: ObjectState, resources: StageResources) -> tuple[list[Primitive], bool] | None:
    """Primitives for the additional kinds or ``None`` for other kinds."""
    kind = obj.kind
    simple = {
        ObjectKind.VECTOR: vector_primitives,
        ObjectKind.DOUBLE_ARROW: double_arrow_primitives,
        ObjectKind.DASHED_LINE: dashed_line_primitives,
        ObjectKind.NUMBER_LINE: number_line_primitives,
        ObjectKind.ARC: arc_primitives,
        ObjectKind.SECTOR: sector_primitives,
        ObjectKind.ANNULUS: annulus_primitives,
        ObjectKind.POLYGON: polygon_primitives,
        ObjectKind.REGULAR_POLYGON: regular_polygon_primitives,
        ObjectKind.STAR: star_primitives,
        ObjectKind.TABLE: table_primitives,
        ObjectKind.MATRIX: matrix_primitives,
        ObjectKind.MARKUP_TEXT: markup_primitives,
    }
    if kind in simple:
        return simple[kind](obj, state), True
    if kind == ObjectKind.CODE:
        return code_primitives(obj), True
    if kind == ObjectKind.DECIMAL_NUMBER:
        return decimal_primitives(scene, obj, state, resources), True
    if kind == ObjectKind.TEX:
        return tex_primitives(obj, state, resources), True
    if kind == ObjectKind.BRACE:
        return brace_primitives(scene, obj, state)
    if kind == ObjectKind.HIGHLIGHT:
        return highlight_primitives(scene, obj, state), False
    if kind == ObjectKind.ANGLE:
        return angle_primitives(obj, state), False
    if kind == ObjectKind.TRACE:
        return trace_primitives(obj, state), False
    if kind == ObjectKind.VECTOR_FIELD:
        return field_primitives(scene, obj, state, resources), False
    if kind == ObjectKind.GROUP:
        return [], False
    return None
