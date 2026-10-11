"""Approximate sizes of objects (for groups and braces in the model).

The stage measures the real drawings; these estimates are only used where
the model itself needs a size, e.g. the center of a group or where a brace
attached to another object starts.
"""

from __future__ import annotations

import math

from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.geometry import axes_layout, bound_axes, param_float
from manim_studio.model.types import GRAPH_TOOL_KINDS, ObjectKind

CHAR_WIDTH_PER_POINT = 3.29 / 10 / 48
LINE_HEIGHT_PER_POINT = 0.64 / 48


def _text_size(text: str, font_size: float) -> tuple[float, float]:
    lines = text.split("\n") or [""]
    width = max(len(line) for line in lines) * CHAR_WIDTH_PER_POINT * font_size
    height = (len(lines) * 1.2 - 0.2) * LINE_HEIGHT_PER_POINT * font_size
    return max(width, 0.1), max(height, 0.1)


def _points_size(points: list) -> tuple[float, float]:
    if not points:
        return 0.1, 0.1
    xs, ys = [float(p[0]) for p in points], [float(p[1]) for p in points]
    return max(xs) - min(xs), max(ys) - min(ys)


def _arc_size(radius: float, start: float, angle: float, include_center: bool) -> tuple[float, float]:
    points = [
        (radius * math.cos(math.radians(start + angle * i / 32)), radius * math.sin(math.radians(start + angle * i / 32)))
        for i in range(33)
    ]
    if include_center:
        points.append((0.0, 0.0))
    return _points_size([list(p) for p in points])


def _table_size(rows: list, font_size: float, h_buff: float, v_buff: float) -> tuple[float, float]:
    if not rows:
        return 1.0, 1.0
    columns = max(len(row) for row in rows)
    widths = [max(_text_size(str(row[c]) if c < len(row) else "", font_size)[0] for row in rows) for c in range(columns)]
    height = len(rows) * (LINE_HEIGHT_PER_POINT * font_size + v_buff)
    return sum(widths) + columns * h_buff, height


def base_size(scene: Scene, obj: SceneObject) -> tuple[float, float]:
    """Return the estimated width and height of an unrotated, unscaled object."""
    p = obj.params
    kind = obj.kind
    if kind in (ObjectKind.CIRCLE, ObjectKind.DOT, ObjectKind.REGULAR_POLYGON):
        radius = param_float(p, "radius", 1.0)
        return 2 * radius, 2 * radius
    if kind == ObjectKind.STAR:
        radius = param_float(p, "outer_radius", 1.0)
        return 2 * radius, 2 * radius
    if kind == ObjectKind.ANNULUS:
        radius = param_float(p, "outer_radius", 1.3)
        return 2 * radius, 2 * radius
    if kind == ObjectKind.SQUARE:
        side = param_float(p, "side_length", 2.0)
        return side, side
    if kind in (ObjectKind.RECTANGLE, ObjectKind.ELLIPSE):
        return param_float(p, "width", 3.0), param_float(p, "height", 1.5)
    if kind == ObjectKind.TRIANGLE:
        radius = param_float(p, "radius", 1.0)
        return math.sqrt(3) * radius, 1.5 * radius
    if kind in (ObjectKind.LINE, ObjectKind.DASHED_LINE):
        return param_float(p, "length", 3.0), 0.05
    if kind in (ObjectKind.ARROW, ObjectKind.VECTOR, ObjectKind.DOUBLE_ARROW):
        return param_float(p, "length", 3.0), 0.35
    if kind == ObjectKind.NUMBER_LINE:
        return param_float(p, "length", 10.0), 0.6 if p.get("show_numbers") else 0.2
    if kind in (ObjectKind.AXES, ObjectKind.NUMBER_PLANE):
        layout = axes_layout(obj)
        return layout.x_length, layout.y_length
    if kind == ObjectKind.POLYGON:
        return _points_size(list(p.get("points", [])))
    if kind == ObjectKind.ARC:
        return _arc_size(param_float(p, "radius", 1.5), param_float(p, "start_angle", 0.0), param_float(p, "angle", 120.0), False)
    if kind == ObjectKind.SECTOR:
        return _arc_size(param_float(p, "radius", 1.5), param_float(p, "start_angle", 0.0), param_float(p, "angle", 90.0), True)
    if kind == ObjectKind.TEXT:
        return _text_size(str(p.get("text", "")), param_float(p, "font_size", 48.0))
    if kind == ObjectKind.MARKUP_TEXT:
        import re

        return _text_size(re.sub(r"<[^>]+>", "", str(p.get("markup", ""))), param_float(p, "font_size", 48.0))
    if kind in (ObjectKind.MATH_TEX, ObjectKind.TEX):
        source = str(p.get("latex" if kind == ObjectKind.MATH_TEX else "tex", ""))
        width, height = _text_size(source, param_float(p, "font_size", 48.0))
        return width * 0.6, height
    if kind == ObjectKind.DECIMAL_NUMBER:
        digits = len(f"{param_float(p, 'value', 0.0):.{int(p.get('decimals', 2))}f}") + len(str(p.get("unit", "")))
        return _text_size("0" * digits, param_float(p, "font_size", 48.0))
    if kind in (ObjectKind.TABLE, ObjectKind.MATRIX):
        rows = list(p.get("rows", []))
        size = _table_size(rows, param_float(p, "font_size", 48.0 if kind == ObjectKind.MATRIX else 32.0), param_float(p, "h_buff", 1.0), param_float(p, "v_buff", 0.5))
        return (size[0] + 0.6, size[1]) if kind == ObjectKind.MATRIX else size
    if kind == ObjectKind.CODE:
        width, height = _text_size(str(p.get("code", "")), param_float(p, "font_size", 24.0) * 1.15)
        return width + 0.8, height + 0.5
    if kind == ObjectKind.IMAGE:
        height = param_float(p, "height", 2.0)
        return height * 1.5, height
    if kind == ObjectKind.FUNCTION_GRAPH or kind in GRAPH_TOOL_KINDS:
        return _graph_size(scene, obj)
    if kind == ObjectKind.BRACE:
        width = param_float(p, "width", 3.0)
        horizontal = p.get("direction", "down") in ("down", "up")
        return (width, 0.3) if horizontal else (0.3, width)
    return 1.0, 1.0


def _graph_size(scene: Scene, obj: SceneObject) -> tuple[float, float]:
    from manim_studio.model import graphs
    from manim_studio.model.geometry import axes_to_scene

    if obj.kind in GRAPH_TOOL_KINDS:
        graph = graphs.tool_graph(scene, obj)
        axes = bound_axes(scene, graph) if graph is not None else None
        points = [list(axes_to_scene(axes, x, y)) for x, y in graphs.tool_axes_points(scene, obj)] if axes is not None else []
        return _points_size(points) if len(points) > 1 else (0.3, 0.3)
    if bound_axes(scene, obj) is not None:
        segments = graphs.graph_scene_segments(scene, obj)
    else:
        segments = graphs.curve_points(scene, obj)
    points = [list(point) for segment in segments for point in segment]
    return _points_size(points) if points else (1.0, 1.0)


def rotated_extent(width: float, height: float, rotation: float) -> tuple[float, float]:
    """Return the axis-aligned size of a rotated rectangle."""
    radians = math.radians(rotation)
    cos_a, sin_a = abs(math.cos(radians)), abs(math.sin(radians))
    return width * cos_a + height * sin_a, width * sin_a + height * cos_a
