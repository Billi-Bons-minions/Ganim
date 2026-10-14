"""Stage drawings for the additional object kinds (approximations of Manim)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
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
    QTransform,
)

from manim_studio.model.curved import curved_bounds, curved_parts
from manim_studio.model.dashes import dash_polylines, is_dashed
from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.extents import base_size, highlight_box, rotated_extent
from manim_studio.model.geometry import param_float, tick_values
from manim_studio.model.graphs import number_value
from manim_studio.model.groups import bounds_of, is_group, leaves
from manim_studio.model.state import ObjectState, initial_state
from manim_studio.model.types import ObjectKind
from manim_studio.ui.stage.drawing import (
    ARROW_TIP,
    EM_PER_POINT,
    PX,
    Primitive,
    StageResources,
    _color,
    _pen,
    _polygon,
    _shape_primitive,
    _stroke_primitive,
    manim_text_font,
    text_font,
)

NUMBER_LABEL_SIZE = 24.0
BRACE_THICKNESS = 0.27


def pt(x: float, y: float) -> QPointF:
    return QPointF(x * PX, -y * PX)


def _label_font(points: float) -> QFont:
    font = manim_text_font()
    font.setPixelSize(max(1, round(EM_PER_POINT * points * PX)))
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


def dashed_line_primitives(scene: Scene, obj: SceneObject, state: ObjectState) -> list[Primitive]:
    """Manim's DashedLine: the dashes start and end at the ends of the line."""
    path = QPainterPath()
    for dash in dash_polylines(scene, obj):
        path.moveTo(pt(*dash[0]))
        for point in dash[1:]:
            path.lineTo(pt(*point))
    return [_stroke_primitive(path, obj, state)]


def dash_primitives(scene: Scene, obj: SceneObject, state: ObjectState) -> list[Primitive]:
    """A dashed shape: one open piece per dash (Manim's DashedVMobject), the outline's pen, no fill."""
    pen = _pen(state.stroke_color, obj.stroke_width, obj.stroke_opacity, state.scale) if obj.stroke_width > 0 else None
    primitives = []
    for dash in dash_polylines(scene, obj):
        path = QPainterPath(pt(*dash[0]))
        for point in dash[1:]:
            path.lineTo(pt(*point))
        primitives.append(Primitive(path=path, pen=pen))
    return primitives


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
    for value in tick_values(low, high, step, bool(tip))[:401]:
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


def curved_arrow_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    """Arc and filled tips exactly like Manim's curved arrows (see ``model/curved.py``)."""
    parts = curved_parts(obj)
    path = QPainterPath(pt(*parts.shaft[0]))
    for index in range(0, len(parts.shaft) - 3, 4):
        path.cubicTo(*(pt(*point) for point in parts.shaft[index + 1 : index + 4]))
    # Manim centers the arrow on the box around all points, the handles included
    left, bottom, right, top = curved_bounds(obj)
    primitives = [Primitive(rect=QRectF(pt(left, top), pt(right, bottom))), _stroke_primitive(path, obj, state)]
    if parts.tips:
        # Manim fills the tips completely, whatever the line's opacity
        brush = QBrush(_color(state.stroke_color))
        primitives += [Primitive(path=_polygon(tip), brush=brush) for tip in parts.tips]
    return primitives


def placement_transform(placement: tuple) -> QTransform:
    """Scene-pixel transform of a shape placed at ``center + R · M · (scale · point)`` (y down)."""
    _object_id, _shape_id, x, y, rotation, scale, (m11, m12, m21, m22) = placement
    cos, sin = math.cos(math.radians(rotation)), math.sin(math.radians(rotation))
    a11, a12 = scale * (cos * m11 - sin * m21), scale * (cos * m12 - sin * m22)
    a21, a22 = scale * (sin * m11 + cos * m21), scale * (sin * m12 + cos * m22)
    # flip y on both sides: (x, y) -> (a11 x - a12 y, -a21 x + a22 y)
    return QTransform(a11, -a21, -a12, a22, x * PX, -y * PX)


def _placed_shape_path(scene: Scene, shape: SceneObject, placement: tuple, resources: StageResources) -> QPainterPath:
    """The outline of a basic shape where it currently is (scene pixels)."""
    from manim_studio.ui.stage.drawing import build_drawing

    geometry = scene.object_by_id(placement[1]) or shape
    drawing = build_drawing(scene, geometry, initial_state(scene, geometry), resources)
    path = QPainterPath()
    for primitive in drawing.primitives:
        if primitive.path is not None:
            path.addPath(primitive.path)
    return placement_transform(placement).map(path)


def _boolean_path(scene: Scene, obj: SceneObject, where: dict[str, tuple], resources: StageResources) -> QPainterPath | None:
    from manim_studio.model.booleans import DIFFERENCE, INTERSECTION, UNION, is_boolean, operands, operation

    paths = []
    for shape in operands(scene, obj) or ():
        if is_boolean(shape):
            path = _boolean_path(scene, shape, where, resources)
        else:
            path = _placed_shape_path(scene, shape, where[shape.id], resources) if shape.id in where else None
        if path is None:
            return None
        paths.append(path)
    if len(paths) != 2:
        return None
    first, second = paths
    op = operation(obj)
    if op == UNION:
        return first.united(second)
    if op == INTERSECTION:
        return first.intersected(second)
    if op == DIFFERENCE:
        return first.subtracted(second)
    return first.united(second).subtracted(first.intersected(second))


def boolean_primitives(scene: Scene, obj: SceneObject, state: ObjectState, resources: StageResources) -> list[Primitive]:
    """Union, intersection, difference or exclusion of the two shapes where they are now (see ``model/booleans.py``)."""
    if not state.parts:
        return []
    path = _boolean_path(scene, obj, {placement[0]: placement for placement in state.parts}, resources)
    if path is None or path.isEmpty():
        return []
    path.translate(-state.x * PX, state.y * PX)
    return [_shape_primitive(path, obj, state)]


def lens_primitives(scene: Scene, obj: SceneObject, state: ObjectState) -> list[Primitive]:
    """The lens frame and its display, which shows the framed part of the stage magnified (``ZoomedScene``)."""
    from manim_studio.model.lenses import lens_geometry

    lens = lens_geometry(obj, state.scale)
    pen = _pen(state.stroke_color, obj.stroke_width, 1.0, 1.0)
    frame = QPainterPath()
    frame.addRect(QRectF(pt(-lens.frame_width / 2, lens.frame_height / 2), pt(lens.frame_width / 2, -lens.frame_height / 2)))
    # the display lies where it is in the scene, also while the frame moves
    dx, dy = lens.display_x - state.x, lens.display_y - state.y
    display = QRectF(pt(dx - lens.display_width / 2, dy + lens.display_height / 2), pt(dx + lens.display_width / 2, dy - lens.display_height / 2))
    source = QRectF(pt(state.x - lens.frame_width / 2, state.y + lens.frame_height / 2), pt(state.x + lens.frame_width / 2, state.y - lens.frame_height / 2))
    background = QPainterPath()
    background.addRect(display)
    border = QPainterPath()
    border.addRect(display)
    # the zoomed camera also sees the inner half of its own frame: magnified, it lines the display
    magnified = pen.widthF() / 2 * lens.display_width / max(lens.frame_width, 1e-6)
    inner = QPainterPath()
    inner.addRect(display.adjusted(magnified / 2, magnified / 2, -magnified / 2, -magnified / 2))
    lining = QPen(pen)
    lining.setWidthF(magnified)
    lining.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    return [
        Primitive(path=background, brush=QBrush(_color(scene.background_color))),
        Primitive(rect=display, view_source=source),
        Primitive(path=inner, pen=lining),
        Primitive(path=border, pen=pen),
        Primitive(path=frame, pen=pen),
    ]


def sector_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    points = arc_points(param_float(obj.params, "radius", 1.5), param_float(obj.params, "start_angle", 0.0), param_float(obj.params, "angle", 90.0))
    # Manim's order: center, out to the end of the arc, back along it (AnnularSector with inner radius 0)
    return [_shape_primitive(_polygon([(0.0, 0.0)] + points[::-1]), obj, state)]


def annulus_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    outer, inner = param_float(obj.params, "outer_radius", 1.3), param_float(obj.params, "inner_radius", 0.7)
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.OddEvenFill)
    path.addEllipse(QPointF(0, 0), outer * PX, outer * PX)
    path.addEllipse(QPointF(0, 0), inner * PX, inner * PX)
    return [_shape_primitive(path, obj, state)]


def polygon_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    from manim_studio.model.curves import curve_cubics, is_open, is_smooth

    points = [(float(x), float(y)) for x, y in obj.params.get("points", [])] or [(0.0, 0.0)]
    if not is_smooth(obj) and not is_open(obj):
        return [_shape_primitive(_polygon(points), obj, state)]
    cubics = curve_cubics(points, is_smooth(obj), not is_open(obj))
    path = QPainterPath(pt(*points[0]))
    for _start, first, second, end in cubics:
        path.cubicTo(pt(*first), pt(*second), pt(*end))
    if not is_open(obj):
        path.closeSubpath()
    primitive = _shape_primitive(path, obj, state)
    # Manim's move_to centers the box around the anchors (the curve may bulge out of it)
    xs, ys = [pt(*point).x() for point in points], [pt(*point).y() for point in points]
    primitive.rect = QRectF(QPointF(min(xs), min(ys)), QPointF(max(xs), max(ys)))
    return [primitive]


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
    cells = _table_cells(scene, obj, state)
    if cells is not None:
        return cells
    box = highlight_box(scene, obj)
    if box is None:
        return []
    width, height = box
    return _highlight_shape(obj, state, QRectF(-width * PX / 2, -height * PX / 2, width * PX, height * PX), param_float(obj.params, "buff", 0.15))


def _table_cells(scene: Scene, obj: SceneObject, state: ObjectState) -> list[Primitive] | None:
    """A highlight on a cell, row or column of a table: the box of ``studio_table_cells`` (like ``get_cell``)."""
    from manim_studio.model.tables import highlighted_table, table_selection

    selection = table_selection(scene, obj)
    table = highlighted_table(scene, obj)
    layout = table_layout(table) if table is not None and selection is not None else None
    if layout is None:
        return None
    # the highlight sits on the table's center with its turn and scale: the table's own coordinates
    bounds = QRectF()
    for primitive in table_primitives(table, state):
        bounds = bounds.united(primitive.path.boundingRect())
    box = layout.cell(*selection).translated(-bounds.center().x(), -bounds.center().y())
    # the buff is measured in the scene, the box grows with the table
    return _highlight_shape(obj, state, box, param_float(obj.params, "buff", 0.15) / max(state.scale, 0.01))


def _highlight_shape(obj: SceneObject, state: ObjectState, box: QRectF, buff: float) -> list[Primitive]:
    """Frame, background, underline or cross around a box (pixels, the target's coordinates)."""
    style = obj.params.get("style", "frame")
    center = box.center()
    width, height = box.width() / PX, box.height() / PX
    w, h = (width + 2 * buff) * PX, (height + 2 * buff) * PX
    path = QPainterPath()
    if style == "underline":
        y = (height / 2 + buff) * PX
        path.moveTo(-width * PX / 2, y)
        path.lineTo(width * PX / 2, y)
        return [_stroke_primitive(path.translated(center), obj, state)]
    if style == "cross":
        path.moveTo(-width * PX / 2, -height * PX / 2)
        path.lineTo(width * PX / 2, height * PX / 2)
        path.moveTo(-width * PX / 2, height * PX / 2)
        path.lineTo(width * PX / 2, -height * PX / 2)
        return [_stroke_primitive(path.translated(center), obj, state)]
    if style == "background":
        path.addRect(QRectF(-w / 2, -h / 2, w, h))
        return [Primitive(path=path.translated(center), brush=QBrush(_color(state.fill_color, param_float(obj.params, "opacity", 0.75))))]
    radius = min(param_float(obj.params, "corner_radius", 0.0) * PX, w / 2, h / 2)
    path.addRoundedRect(QRectF(-w / 2, -h / 2, w, h), radius, radius)
    return [_shape_primitive(path.translated(center), obj, state)]


def network_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    """Edges (arrows for directed networks), vertices and their labels around the object's position."""
    from manim_studio.model.networks import network_edges, network_layout, network_vertices

    layout = network_layout(obj)
    if not layout:
        return []
    radius = param_float(obj.params, "radius", 0.3)
    labels = bool(obj.params.get("labels", True))
    font = text_font(obj, param_float(obj.params, "label_size", 28.0))
    radii = {vertex: radius for vertex in network_vertices(obj)}

    def local(point: tuple[float, float]) -> QPointF:
        return QPointF(point[0] * PX, -point[1] * PX)

    directed = bool(obj.params.get("directed"))
    colors = dict(state.part_colors)
    # one path per color: highlighted vertices and edges are drawn in their own color
    edge_paths: dict[str, tuple[QPainterPath, QPainterPath]] = {}
    for a, b in network_edges(obj):
        if a not in layout or b not in layout:
            continue
        (ax, ay), (bx, by) = layout[a], layout[b]
        length = math.hypot(bx - ax, by - ay)
        if length < 1e-9:
            continue
        edges, tips = edge_paths.setdefault(colors.get(("e", a, b), state.stroke_color), (QPainterPath(), QPainterPath()))
        ux, uy = (bx - ax) / length, (by - ay) / length
        start = (ax + ux * radii[a], ay + uy * radii[a])
        end = (bx - ux * radii[b], by - uy * radii[b])
        if directed:
            tip = 0.2
            base = (end[0] - ux * tip, end[1] - uy * tip)
            edges.moveTo(local(start))
            edges.lineTo(local(base))
            tips.addPolygon(QPolygonF([local(end), local((base[0] - uy * tip / 2, base[1] + ux * tip / 2)), local((base[0] + uy * tip / 2, base[1] - ux * tip / 2))]))
            tips.closeSubpath()
        else:
            edges.moveTo(local(start))
            edges.lineTo(local(end))
    primitives = []
    for color, (edges, tips) in edge_paths.items():
        primitives.append(Primitive(path=edges, pen=_pen(color, obj.stroke_width, obj.stroke_opacity, state.scale)))
        if directed:
            primitives.append(Primitive(path=tips, brush=QBrush(_color(color, obj.stroke_opacity))))
    dot_paths: dict[str, QPainterPath] = {}
    for vertex, point in layout.items():
        dot_paths.setdefault(colors.get(("v", vertex, ""), state.fill_color), QPainterPath()).addEllipse(local(point), radii[vertex] * PX, radii[vertex] * PX)
    for color, dots in dot_paths.items():
        primitives.append(Primitive(path=dots, brush=QBrush(_color(color, obj.fill_opacity))))
    if labels:
        text_path_all = QPainterPath()
        for vertex, point in layout.items():
            text = QPainterPath()
            text.addText(QPointF(0, 0), font, vertex)
            bounds = text.boundingRect()
            center = local(point)
            text.translate(center.x() - bounds.center().x(), center.y() - bounds.center().y())
            text_path_all.addPath(text)
        primitives.append(Primitive(path=text_path_all, brush=QBrush(_color(str(obj.params.get("label_color", "#000000")), 1.0))))
    return primitives


def list_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    """Lines stacked like ``arrange(DOWN, aligned_edge=LEFT, buff=...)``."""
    from manim_studio.model.lists import list_lines

    font = text_font(obj, param_float(obj.params, "font_size", 36.0))
    path = QPainterPath()
    top = 0.0
    for line in list_lines(obj) or [" "]:
        single = QPainterPath()
        single.addText(QPointF(0, 0), font, line)
        bounds = single.boundingRect()
        single.translate(-bounds.left(), top - bounds.top())
        path.addPath(single)
        top += bounds.height() + param_float(obj.params, "buff", 0.25) * PX
    return [Primitive(path=path, brush=QBrush(_color(state.fill_color, obj.fill_opacity)))]


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
    from manim_studio.ui.stage.drawing import decimal_number_path

    value = number_value(scene, obj, resources.values, state.value)
    # like DecimalNumber: every character on its own, close together, a minus in the middle of the digits
    path, _first = decimal_number_path(decimal_text(obj, value), param_float(obj.params, "font_size", 48.0))
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


@dataclass
class TableLayout:
    """Manim's ``Table`` on the stage (pixels, y down, the entries' bounding box starts at 0, 0).

    ``arrange_in_grid``: a column is as wide as its widest entry, a row as high as its highest
    one (the ink of the text), with ``h_buff``/``v_buff`` between them; every entry sits in the
    middle of its cell. Lines and cells reach half a buff beyond the entries.
    """

    texts: QPainterPath
    columns: list[tuple[float, float]]
    rows: list[tuple[float, float]]
    h_buff: float
    v_buff: float

    def cell(self, row: int = 0, column: int = 0) -> QRectF:
        """Manim's ``get_cell`` for a cell, a whole row (``column`` 0), a whole column (``row`` 0) or the table."""
        cols = self.columns[column - 1 : column] if 0 < column <= len(self.columns) else self.columns
        lines = self.rows[row - 1 : row] if 0 < row <= len(self.rows) else self.rows
        left, right = cols[0][0] - self.h_buff / 2, cols[-1][1] + self.h_buff / 2
        top, bottom = lines[0][0] - self.v_buff / 2, lines[-1][1] + self.v_buff / 2
        return QRectF(QPointF(left, top), QPointF(right, bottom))


def table_layout(obj: SceneObject) -> TableLayout | None:
    """Where Manim puts the entries, cells and lines of a table."""
    cells = _cells(obj)
    if not cells or not cells[0]:
        return None
    font = text_font(obj, param_float(obj.params, "font_size", 32.0))
    inks = []
    for row in cells:
        line = []
        for text in row:
            path = QPainterPath()
            path.addText(QPointF(0, 0), font, text)
            line.append(path)
        inks.append(line)
    widths = [max(inks[r][c].boundingRect().width() for r in range(len(cells))) for c in range(len(cells[0]))]
    heights = [max(path.boundingRect().height() for path in line) for line in inks]
    h_buff = param_float(obj.params, "h_buff", 1.0) * PX
    v_buff = param_float(obj.params, "v_buff", 0.5) * PX
    columns, x = [], 0.0
    for width in widths:
        columns.append((x, x + width))
        x += width + h_buff
    rows, y = [], 0.0
    for height in heights:
        rows.append((y, y + height))
        y += height + v_buff
    texts = QPainterPath()
    for (top, bottom), line in zip(rows, inks):
        for (left, right), path in zip(columns, line):
            box = path.boundingRect()
            if box.isEmpty() and box.width() == 0:
                continue
            texts.addPath(path.translated((left + right) / 2 - box.center().x(), (top + bottom) / 2 - box.center().y()))
    return TableLayout(texts, columns, rows, h_buff, v_buff)


def table_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    layout = table_layout(obj)
    if layout is None:
        return []
    whole = layout.cell()
    lines = QPainterPath()
    # Table._add_horizontal_lines/_add_vertical_lines: between rows and columns, half a buff beyond the entries
    for (_top, bottom), (top, _bottom) in zip(layout.rows, layout.rows[1:]):
        y = (bottom + top) / 2
        lines.moveTo(QPointF(whole.left(), y))
        lines.lineTo(QPointF(whole.right(), y))
    for (_left, right), (left, _right) in zip(layout.columns, layout.columns[1:]):
        x = (right + left) / 2
        lines.moveTo(QPointF(x, whole.top()))
        lines.lineTo(QPointF(x, whole.bottom()))
    if obj.params.get("outer_lines", True):
        lines.addRect(whole)
    pen = _pen(state.stroke_color, obj.stroke_width, 1.0, state.scale)
    return [Primitive(path=lines, pen=pen), Primitive(path=layout.texts, brush=QBrush(_color(state.fill_color)))]


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
    if is_dashed(obj):
        # centered on the dashes like Manim's move_to (its bounding box has only the dashes)
        return dash_primitives(scene, obj, state), True
    if kind == ObjectKind.DASHED_LINE:
        return dashed_line_primitives(scene, obj, state), True
    simple = {
        ObjectKind.VECTOR: vector_primitives,
        ObjectKind.DOUBLE_ARROW: double_arrow_primitives,
        ObjectKind.NUMBER_LINE: number_line_primitives,
        ObjectKind.ARC: arc_primitives,
        ObjectKind.CURVED_ARROW: curved_arrow_primitives,
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
    if kind == ObjectKind.BOOLEAN_SHAPE:
        return boolean_primitives(scene, obj, state, resources), False
    if kind == ObjectKind.ZOOM_LENS:
        return lens_primitives(scene, obj, state), False
    if kind == ObjectKind.TRACE:
        return trace_primitives(obj, state), False
    if kind == ObjectKind.VECTOR_FIELD:
        return field_primitives(scene, obj, state, resources), False
    if kind == ObjectKind.BULLET_LIST:
        return list_primitives(obj, state), True
    if kind == ObjectKind.NETWORK:
        return network_primitives(obj, state), False
    if kind == ObjectKind.GROUP:
        return [], False
    return None
