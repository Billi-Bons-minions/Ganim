"""Stage drawings of 3D axes, surfaces and curves (projected like Manim's 3D camera)."""

from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QPainterPath

from manim_studio.model import graphs
from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.state import ObjectState
from manim_studio.model.three_d import View, _matrix, axes_lines, axes_of, axis_tips, curve_points, project, surface_grid
from manim_studio.model.types import ObjectKind
from manim_studio.ui.stage.drawing import Primitive, StageResources, _color, _pen, pt


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
    if obj.kind == ObjectKind.CURVE_3D:
        line = project(curve_points(scene, obj, values), view)
        return [Primitive(path=_path([line], offset), pen=_pen(state.stroke_color, obj.stroke_width, obj.stroke_opacity, state.scale))], False
    grid = surface_grid(scene, obj, values)
    if not grid:
        return [], False
    rows = grid[: len(grid) // 2]
    quads = []
    for i in range(len(rows) - 1):
        for j in range(min(len(rows[i]), len(rows[i + 1])) - 1):
            corners = [rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]]
            depth = sum(_depth(view, corner) for corner in corners) / 4
            quads.append((depth, corners))
    quads.sort(key=lambda item: item[0])
    path = QPainterPath()
    for _depth_value, corners in quads:
        flat = project(corners, view)
        path.moveTo(pt(flat[0][0] - offset[0], flat[0][1] - offset[1]))
        for x, y in flat[1:]:
            path.lineTo(pt(x - offset[0], y - offset[1]))
        path.closeSubpath()
    path.setFillRule(Qt.FillRule.WindingFill)
    brush = QBrush(_color(state.fill_color, obj.fill_opacity * 0.85)) if obj.fill_opacity > 0 else None
    pen = _pen(state.stroke_color, obj.stroke_width, obj.stroke_opacity, state.scale) if obj.stroke_width > 0 else None
    return [Primitive(path=path, brush=brush, pen=pen)], False
