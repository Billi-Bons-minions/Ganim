"""Stage drawings of 3D axes, surfaces and curves (projected like Manim's 3D camera)."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainterPath

from manim_studio.model import graphs
from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.geometry import param_float
from manim_studio.model.state import ObjectState
from manim_studio.model.three_d import (
    POLYHEDRON_VERTEX_RADIUS,
    View,
    _matrix,
    axes_lines,
    axes_of,
    axis_tips,
    curve_points,
    face_shading,
    project,
    solid_faces,
    solid_vertices,
    surface_faces,
    vector_points,
)
from manim_studio.model.types import ObjectKind
from manim_studio.ui.stage.drawing import PX, Primitive, StageResources, _color, _pen, pt


def _path(lines: list[list[tuple[float, float]]], offset: tuple[float, float]) -> QPainterPath:
    path = QPainterPath()
    for line in lines:
        if len(line) < 2:
            continue
        path.moveTo(pt(line[0][0] - offset[0], line[0][1] - offset[1]))
        for x, y in line[1:]:
            path.lineTo(pt(x - offset[0], y - offset[1]))
    return path


def _depth(view: View, point: tuple[float, float, float]) -> float:
    matrix = _matrix(view)
    return matrix[2][0] * point[0] + matrix[2][1] * point[1] + matrix[2][2] * point[2]


def three_d_primitives(scene: Scene, obj: SceneObject, state: ObjectState, resources: StageResources) -> tuple[list[Primitive], bool]:
    view = resources.view3d or View()
    values = resources.values
    if obj.kind == ObjectKind.AXES_3D:
        offset = (state.x, state.y)
        lines = [project(line, view) for line in axes_lines(obj)]
        pen = _pen(state.stroke_color, obj.stroke_width, 1.0, state.scale)
        tips = QPainterPath()
        for end, before in axis_tips(obj):
            (ex, ey), (bx, by) = project([end, before], view)
            dx, dy = ex - bx, ey - by
            length = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / length * 0.12, dx / length * 0.12
            tips.moveTo(pt(ex - offset[0], ey - offset[1]))
            tips.lineTo(pt(bx + nx - offset[0], by + ny - offset[1]))
            tips.lineTo(pt(bx - nx - offset[0], by - ny - offset[1]))
            tips.closeSubpath()
        return [Primitive(path=_path(lines, offset), pen=pen), Primitive(path=tips, brush=QBrush(_color(state.stroke_color)))], False
    offset = graphs.bound_anchor(scene, obj) if axes_of(scene, obj) is not None else (state.x, state.y)
    if obj.kind == ObjectKind.VECTOR_3D:
        return _vector_primitives(obj, state, project(vector_points(scene, obj), view), offset), False
    if obj.kind == ObjectKind.CURVE_3D:
        line = project(curve_points(scene, obj, values), view)
        return [Primitive(path=_path([line], offset), pen=_pen(state.stroke_color, obj.stroke_width, obj.stroke_opacity, state.scale))], False
    if obj.kind == ObjectKind.SOLID:
        # the item is scaled by the stage, so the faces are computed unscaled around the anchor
        faces = solid_faces(scene, obj, state=state)
    else:
        faces = surface_faces(scene, obj, values)
    return _face_primitives(scene, obj, state, view, faces, offset), False


def _shaded(color: str, light: float, opacity: float) -> QColor:
    """A color with Manim's light added (``get_shaded_rgb``, clipped like Cairo does)."""
    base = QColor(color)
    if not base.isValid():
        base = QColor("#FFFFFF")
    shaded = QColor.fromRgbF(*(max(0.0, min(1.0, channel + light)) for channel in (base.redF(), base.greenF(), base.blueF())))
    shaded.setAlphaF(max(0.0, min(1.0, opacity)))
    return shaded


def _gradient(color: str, light_start: float, light_end: float, opacity: float, start: QPointF, end: QPointF) -> QBrush:
    if math.hypot(end.x() - start.x(), end.y() - start.y()) < 1e-6:
        return QBrush(_shaded(color, (light_start + light_end) / 2, opacity))
    gradient = QLinearGradient(start, end)
    gradient.setColorAt(0.0, _shaded(color, light_start, opacity))
    gradient.setColorAt(1.0, _shaded(color, light_end, opacity))
    return QBrush(gradient)


def _face_primitives(scene: Scene, obj: SceneObject, state: ObjectState, view: View, faces: list, offset: tuple[float, float]) -> list[Primitive]:
    """Faces and corners one by one from back to front, so front faces cover the back like in Manim.

    Every face is shaded like Manim's ``ThreeDCamera`` does it: a gradient from its first corner to
    a point near its third, lighter where it faces the light at (-7, -9, 10), darker where it does not.
    """
    items = []
    for corners, points in faces:
        flat = project(corners, view)
        path = QPainterPath()
        path.moveTo(pt(flat[0][0] - offset[0], flat[0][1] - offset[1]))
        for x, y in flat[1:]:
            path.lineTo(pt(x - offset[0], y - offset[1]))
        path.closeSubpath()
        if points:
            start, end, light_start, light_end = face_shading(points)
            (sx, sy), (ex, ey) = project([start, end], view)
            a, b = pt(sx - offset[0], sy - offset[1]), pt(ex - offset[0], ey - offset[1])
        else:
            a = b = QPointF()
            light_start = light_end = 0.0
        brush = _gradient(state.fill_color, light_start, light_end, obj.fill_opacity, a, b) if obj.fill_opacity > 0 else None
        pen = None
        if obj.stroke_width > 0:
            pen = _pen(state.stroke_color, obj.stroke_width, obj.stroke_opacity, state.scale)
            pen.setBrush(_gradient(state.stroke_color, light_start, light_end, obj.stroke_opacity, a, b))
        # unshaded parts come last, like the 3D camera sorts them
        depth = sum(_depth(view, corner) for corner in corners) / len(corners) if points else math.inf
        items.append((depth, Primitive(path=path, brush=brush, pen=pen)))
    if obj.kind == ObjectKind.SOLID and obj.params.get("show_vertices", False):
        dot = QBrush(_color(state.stroke_color))
        vertices = solid_vertices(scene, obj, state)
        for vertex, (x, y) in zip(vertices, project(vertices, view)):
            path = QPainterPath()
            path.addEllipse(pt(x - offset[0], y - offset[1]), POLYHEDRON_VERTEX_RADIUS * PX, POLYHEDRON_VERTEX_RADIUS * PX)
            items.append((_depth(view, vertex), Primitive(path=path, brush=dot)))
    items.sort(key=lambda item: item[0])
    return [primitive for _depth_value, primitive in items]


def _vector_primitives(obj: SceneObject, state: ObjectState, flat: list[tuple[float, float]], offset: tuple[float, float]) -> list[Primitive]:
    """A 3D arrow (shaft and cone, seen from the camera), a 3D line or a 3D point."""
    brush = QBrush(_color(state.stroke_color, obj.stroke_opacity))
    if len(flat) == 1:
        radius = param_float(obj.params, "radius", 0.08)
        path = QPainterPath()
        path.addEllipse(pt(flat[0][0] - offset[0], flat[0][1] - offset[1]), radius * PX, radius * PX)
        return [Primitive(path=path, brush=brush)]
    if len(flat) < 2:
        return []
    (sx, sy), (ex, ey) = flat
    length = math.hypot(ex - sx, ey - sy)
    pen = _pen(state.stroke_color, obj.stroke_width, obj.stroke_opacity, state.scale)
    if obj.params.get("element", "arrow") != "arrow" or length < 1e-6:
        return [Primitive(path=_path([[(sx, sy), (ex, ey)]], offset), pen=pen)]
    # Manim's Arrow3D: a cone of height 0.3 and radius 0.08 at the end
    tip = min(0.3, length * 0.5)
    ux, uy = (ex - sx) / length, (ey - sy) / length
    bx, by = ex - ux * tip, ey - uy * tip
    head = QPainterPath()
    head.moveTo(pt(ex - offset[0], ey - offset[1]))
    head.lineTo(pt(bx - uy * 0.08 - offset[0], by + ux * 0.08 - offset[1]))
    head.lineTo(pt(bx + uy * 0.08 - offset[0], by - ux * 0.08 - offset[1]))
    head.closeSubpath()
    return [Primitive(path=_path([[(sx, sy), (bx, by)]], offset), pen=pen), Primitive(path=head, brush=brush)]
