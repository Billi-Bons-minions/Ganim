"""Stage drawings of function graphs and the tools drawn on them.

Bound objects are computed in scene coordinates with the current parameter
values and shifted by their anchor at the start values; the item is placed at
the object's state position, so a parameter animation reshapes the drawing
while Move animations still move it as a whole.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QPainterPath, QPen

from manim_studio.model import graphs
from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.geometry import AXES_TICK_SIZE, Point, Segment, axes_to_scene, bound_axes, origin_shift, param_float
from manim_studio.model.state import ObjectState
from manim_studio.model.types import ObjectKind
from manim_studio.ui.stage.drawing import (
    PX,
    Primitive,
    StageResources,
    _color,
    _pen,
    _stroke_primitive,
    pt,
    tex_image_primitives,
    text_font,
    text_path,
)

#: Manim's ``SMALL_BUFF`` (labels next to dots).
SMALL_BUFF = 0.1
AXIS_LABEL_SIZE = 28.0
POINT_LABEL_SIZE = 24.0
DASH = 0.05


def _path(segments: list[Segment], offset: Point, closed: bool = False) -> QPainterPath:
    path = QPainterPath()
    for segment in segments:
        if len(segment) < 2:
            continue
        path.moveTo(pt(segment[0][0] - offset[0], segment[0][1] - offset[1]))
        for x, y in segment[1:]:
            path.lineTo(pt(x - offset[0], y - offset[1]))
        if closed:
            path.closeSubpath()
    return path


def _dashed(pen: QPen) -> QPen:
    dashed = QPen(pen)
    width = max(pen.widthF(), 0.5)
    dashed.setDashPattern([DASH * PX / width, DASH * PX / width])
    dashed.setCapStyle(Qt.PenCapStyle.FlatCap)
    return dashed


def _dot(center: QPointF, radius: float, obj: SceneObject, state: ObjectState) -> Primitive:
    path = QPainterPath()
    path.addEllipse(center, radius * PX, radius * PX)
    return Primitive(path=path, brush=QBrush(_color(state.fill_color, obj.fill_opacity)))


def _text_near(text: str, anchor: QPointF, direction: Point, buff: float, size: float, obj: SceneObject, state: ObjectState) -> Primitive:
    """Text placed like Manim's ``next_to(point, direction, buff)``."""
    font = text_font(obj, size)
    path = text_path(text, font)
    bounds = path.boundingRect()
    dx, dy = direction
    center_x = anchor.x() + dx * (buff * PX + bounds.width() / 2)
    center_y = anchor.y() - dy * (buff * PX + bounds.height() / 2)
    path.translate(center_x - bounds.center().x(), center_y - bounds.center().y())
    return Primitive(path=path, brush=QBrush(_color(state.fill_color, obj.fill_opacity)))


def _scene(axes: SceneObject, points: list[Point]) -> list[Point]:
    return [axes_to_scene(axes, x, y) for x, y in points]


# --- graphs ------------------------------------------------------------------------------


def graph_primitives(scene: Scene, obj: SceneObject, state: ObjectState, values: dict[str, float] | None) -> tuple[list[Primitive], bool]:
    """Function graphs of every curve type (bound to axes or free)."""
    if bound_axes(scene, obj) is not None:
        segments = graphs.graph_scene_segments(scene, obj, values)
        return [_stroke_primitive(_path(segments, graphs.bound_anchor(scene, obj)), obj, state)], False
    segments = graphs.curve_points(scene, obj, values)
    return [_stroke_primitive(_path(segments, (0.0, 0.0)), obj, state)], True


# --- graph tools -------------------------------------------------------------------------------


def tool_primitives(scene: Scene, obj: SceneObject, state: ObjectState, values: dict[str, float] | None) -> tuple[list[Primitive], bool]:
    """Areas, Riemann sums, tangents, points, markers and labels on a graph."""
    graph = graphs.tool_graph(scene, obj)
    axes = bound_axes(scene, graph) if graph is not None else None
    if axes is None:
        return [_placeholder(obj, state)], True
    offset = graphs.bound_anchor(scene, obj)
    kind = obj.kind
    if kind == ObjectKind.GRAPH_AREA:
        outline = _scene(axes, graphs.area_polygon(scene, obj, values))
        brush = QBrush(_color(state.fill_color, obj.fill_opacity))
        pen = _pen(state.stroke_color, obj.stroke_width, obj.stroke_opacity, state.scale) if obj.stroke_width > 0 else None
        return [Primitive(path=_path([outline], offset, closed=True), brush=brush, pen=pen)], False
    if kind == ObjectKind.RIEMANN:
        rectangles = [_scene(axes, rectangle) for rectangle in graphs.riemann_rectangles(scene, obj, values)]
        brush = QBrush(_color(state.fill_color, obj.fill_opacity)) if obj.fill_opacity > 0 else None
        pen = _pen(state.stroke_color, obj.stroke_width, obj.stroke_opacity, state.scale) if obj.stroke_width > 0 else None
        return [Primitive(path=_path(rectangles, offset, closed=True), brush=brush, pen=pen)], False
    if kind == ObjectKind.TANGENT:
        line = _scene(axes, graphs.tangent_points(scene, obj, values))
        return [_stroke_primitive(_path([line], offset), obj, state), *_line_label_primitives(scene, obj, state, values, axes, offset)], False
    if kind == ObjectKind.SECANT:
        return _secant_primitives(scene, obj, state, values, axes, offset), False
    if kind == ObjectKind.GRAPH_POINT:
        return _graph_point_primitives(scene, obj, state, values, axes, offset), False
    if kind == ObjectKind.TOOL_LABEL:
        return _tool_label_primitives(scene, obj, state, values, axes, offset), False
    if kind == ObjectKind.GRAPH_MARKERS:
        # Computed for the start values, exactly like the generated script.
        return _marker_primitives(scene, obj, state, None, axes, offset), False
    return _label_primitives(scene, obj, state, values, axes, offset, resources=None), False


def _placeholder(obj: SceneObject, state: ObjectState) -> Primitive:
    path = QPainterPath()
    path.addRect(QRectF(-0.3 * PX, -0.3 * PX, 0.6 * PX, 0.6 * PX))
    pen = QPen(_color(state.fill_color if obj.stroke_width == 0 else state.stroke_color, 0.6), 2, Qt.PenStyle.DashLine)
    return Primitive(path=path, pen=pen)


def _secant_primitives(scene: Scene, obj: SceneObject, state: ObjectState, values, axes: SceneObject, offset: Point) -> list[Primitive]:
    """Line, the two points and the dashed slope triangle, like ``graph_code.secant_code``."""
    found = graphs.secant(scene, obj, values)
    if found is None:
        return []
    primitives = [_stroke_primitive(_path([_scene(axes, found.line)], offset), obj, state)]
    if obj.params.get("show_triangle", True):
        corner = (found.x1, found.y0)
        legs = _path([_scene(axes, [(found.x0, found.y0), corner]), _scene(axes, [corner, (found.x1, found.y1)])], offset)
        primitives.append(Primitive(path=legs, pen=_dashed(_pen(state.stroke_color, 2.0, obj.stroke_opacity, state.scale))))
    radius = param_float(obj.params, "radius", 0.07)
    if radius > 0:
        brush = QBrush(_color(state.stroke_color, obj.stroke_opacity))
        for x, y in ((found.x0, found.y0), (found.x1, found.y1)):
            sx, sy = axes_to_scene(axes, x, y)
            path = QPainterPath()
            path.addEllipse(pt(sx - offset[0], sy - offset[1]), radius * PX, radius * PX)
            primitives.append(Primitive(path=path, brush=brush))
    return primitives + _line_label_primitives(scene, obj, state, values, axes, offset)


def _line_label_primitives(scene: Scene, obj: SceneObject, state: ObjectState, values, axes: SceneObject, offset: Point) -> list[Primitive]:
    """The term of a tangent or secant, placed like the script's ``studio_beside``."""
    label = graphs.line_label(scene, obj, values)
    if label is None:
        return []
    path = text_path(label.text, text_font(obj, POINT_LABEL_SIZE))
    bounds = path.boundingRect()
    (px, py), (qx, qy) = axes_to_scene(axes, label.x, label.y), axes_to_scene(axes, label.x + 1, label.y + label.slope)
    length = math.hypot(qx - px, qy - py)
    if not math.isfinite(length) or length == 0:
        return []
    nx, ny = label.side * -(qy - py) / length, label.side * (qx - px) / length
    distance = abs(nx) * bounds.width() / PX / 2 + abs(ny) * bounds.height() / PX / 2 + graphs.LINE_LABEL_BUFF
    center = pt(px + distance * nx - offset[0], py + distance * ny - offset[1])
    path.translate(center.x() - bounds.center().x(), center.y() - bounds.center().y())
    return [Primitive(path=path, brush=QBrush(_color(state.stroke_color, obj.stroke_opacity)))]


def _tool_label_primitives(scene: Scene, obj: SceneObject, state: ObjectState, values, axes: SceneObject, offset: Point) -> list[Primitive]:
    """A value label placed like the script: beside its line, at its point's corner or in its area."""
    from manim_studio.model.tool_labels import BESIDE, CORNER, label_shift, tool_label

    label = tool_label(scene, obj, values)
    if label is None:
        return []
    size = param_float(obj.params, "font_size", 24.0)
    px, py = axes_to_scene(axes, label.x, label.y)
    dx, dy = label_shift(obj)
    if label.placement == CORNER:
        return [_text_near(label.text, pt(px + dx - offset[0], py + dy - offset[1]), (1.0, 1.0), label.buff, size, obj, state)]
    path = text_path(label.text, text_font(obj, size))
    bounds = path.boundingRect()
    if label.placement == BESIDE:
        qx, qy = axes_to_scene(axes, label.x + 1, label.y + label.slope)
        length = math.hypot(qx - px, qy - py)
        if not math.isfinite(length) or length == 0:
            return []
        nx, ny = label.side * -(qy - py) / length, label.side * (qx - px) / length
        distance = abs(nx) * bounds.width() / PX / 2 + abs(ny) * bounds.height() / PX / 2 + graphs.LINE_LABEL_BUFF
        px, py = px + distance * nx, py + distance * ny
    center = pt(px + dx - offset[0], py + dy - offset[1])
    path.translate(center.x() - bounds.center().x(), center.y() - bounds.center().y())
    return [Primitive(path=path, brush=QBrush(_color(state.fill_color, obj.fill_opacity)))]


def _graph_point_primitives(scene: Scene, obj: SceneObject, state: ObjectState, values, axes: SceneObject, offset: Point) -> list[Primitive]:
    point = graphs.graph_point(scene, obj, values)
    if point is None:
        return []
    x0, y0 = point
    sx, sy = axes_to_scene(axes, x0, y0)
    center = pt(sx - offset[0], sy - offset[1])
    primitives = []
    if obj.params.get("show_lines", True):
        foot_x = axes_to_scene(axes, x0, origin_shift(param_float(axes.params, "y_min", -3.0), param_float(axes.params, "y_max", 3.0)))
        foot_y = axes_to_scene(axes, origin_shift(param_float(axes.params, "x_min", -5.0), param_float(axes.params, "x_max", 5.0)), y0)
        lines = _path([[(sx, sy), foot_x], [(sx, sy), foot_y]], offset)
        primitives.append(Primitive(path=lines, pen=_dashed(_pen(state.fill_color, 2.0, 1.0, state.scale))))
    radius = param_float(obj.params, "radius", 0.08)
    primitives.append(_dot(center, radius, obj, state))
    if obj.params.get("show_label"):
        corner = QPointF(center.x() + radius * PX, center.y() - radius * PX)
        live = bool(graphs.parameter_users(scene, obj))  # redrawn by Manim with two fixed decimals
        primitives.append(_text_near(graphs.point_label(x0, y0, live), corner, (1.0, 1.0), SMALL_BUFF, POINT_LABEL_SIZE, obj, state))
    return primitives


def _marker_primitives(scene: Scene, obj: SceneObject, state: ObjectState, values, axes: SceneObject, offset: Point) -> list[Primitive]:
    radius = param_float(obj.params, "radius", 0.08)
    primitives = []
    for special in graphs.marker_points(scene, obj, values):
        sx, sy = axes_to_scene(axes, special.x, special.y)
        center = pt(sx - offset[0], sy - offset[1])
        primitives.append(_dot(center, radius, obj, state))
        if obj.params.get("show_labels", True):
            dx, dy = graphs.marker_label_direction(scene, obj, special, values)
            corner = QPointF(center.x() + dx * radius * PX, center.y() - dy * radius * PX)
            primitives.append(_text_near(graphs.point_label(special.x, special.y), corner, (dx, dy), SMALL_BUFF, POINT_LABEL_SIZE, obj, state))
    return primitives


def _label_primitives(scene: Scene, obj: SceneObject, state: ObjectState, values, axes: SceneObject, offset: Point, resources: StageResources | None) -> list[Primitive]:
    anchor = graphs.label_anchor(scene, obj, values)
    if anchor is None:
        return []
    (x0, y0), direction = anchor
    sx, sy = axes_to_scene(axes, x0, y0)
    point = pt(sx - offset[0], sy - offset[1])
    size = param_float(obj.params, "font_size", 36.0)
    text = str(obj.params.get("text", "")) or " "
    if obj.params.get("use_latex") and resources is not None:
        image = tex_image_primitives(obj, state, resources, text, "align*")
        for primitive in image:
            bounds = primitive.rect if primitive.rect is not None else primitive.path.boundingRect()
            dx, dy = direction
            cx = point.x() + dx * (graphs.LABEL_BUFF * PX + bounds.width() / 2)
            cy = point.y() - dy * (graphs.LABEL_BUFF * PX + bounds.height() / 2)
            if primitive.rect is not None:
                primitive.rect = primitive.rect.translated(cx - bounds.center().x(), cy - bounds.center().y())
            else:
                primitive.path.translate(cx - bounds.center().x(), cy - bounds.center().y())
        return image
    return [_text_near(text, point, direction, graphs.LABEL_BUFF, size, obj, state)]


def label_primitives(scene: Scene, obj: SceneObject, state: ObjectState, resources: StageResources) -> tuple[list[Primitive], bool]:
    """Graph labels (needs the LaTeX cache for formulas)."""
    graph = graphs.tool_graph(scene, obj)
    axes = bound_axes(scene, graph) if graph is not None else None
    if axes is None:
        return [_placeholder(obj, state)], True
    return _label_primitives(scene, obj, state, resources.values, axes, graphs.bound_anchor(scene, obj), resources), False


def axis_label_primitives(obj: SceneObject, state: ObjectState, layout, frame_size: tuple[float, float] = (8.0 * 16 / 9, 8.0)) -> list[Primitive]:
    """``x``/``y`` labels at the ends of the axes, placed like Manim's ``get_x_axis_label``/``get_y_axis_label``.

    Manim puts the label ``next_to`` the upper right corner of the axis (its tip included),
    to the upper right for x and to the right and half up for y, and then pushes it back
    onto the screen (``shift_onto_screen``) where the axes are at the start.
    """
    primitives = []
    # half the height of the tip (or of the ticks) widens the axis around its line
    half = 0.35 / 2 if obj.params.get("tips", True) else AXES_TICK_SIZE
    ox = origin_shift(layout.x_min, layout.x_max)
    oy = origin_shift(layout.y_min, layout.y_max)
    label_obj = SceneObject(id="", kind=ObjectKind.TEXT, name="")
    color = "#FFFFFF"
    (xx, xy), (yx, yy) = layout.to_local(layout.x_max, oy), layout.to_local(ox, layout.y_max)
    for key, corner, direction in (("x_label", (xx, xy + half), (1.0, 1.0)), ("y_label", (yx + half, yy), (1.0, 0.5))):
        text = str(obj.params.get(key, "")).strip()
        if not text:
            continue
        path = text_path(text, text_font(label_obj, AXIS_LABEL_SIZE))
        bounds = path.boundingRect()
        width, height = bounds.width() / PX, bounds.height() / PX
        # lower left corner of the label (Manim units, local), then onto the screen
        left, bottom = corner[0] + SMALL_BUFF * direction[0], corner[1] + SMALL_BUFF * direction[1]
        frame_x, frame_y = frame_size[0] / 2, frame_size[1] / 2
        if obj.x + left + width > frame_x:
            left = frame_x - 0.25 - width - obj.x
        if obj.y + bottom + height > frame_y:
            bottom = frame_y - 0.25 - height - obj.y
        if obj.x + left < -frame_x:
            left = -frame_x + 0.25 - obj.x
        if obj.y + bottom < -frame_y:
            bottom = -frame_y + 0.25 - obj.y
        target = pt(left, bottom)
        path.translate(target.x() - bounds.left(), target.y() - bounds.bottom())
        primitives.append(Primitive(path=path, brush=QBrush(_color(color))))
    return primitives

