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


def target_size(scene: Scene, target: SceneObject) -> tuple[float, float]:
    """Size of an object another one is attached to (groups: the box around their members)."""
    from manim_studio.model import groups

    if groups.is_group(target):
        from manim_studio.model.state import initial_state

        leaf_ids = groups.leaves(scene, target.id)
        states = {leaf: initial_state(scene, scene.object_by_id(leaf)) for leaf in leaf_ids}
        left, bottom, right, top = groups.bounds_of(scene, leaf_ids, states)
        if not all(math.isfinite(value) for value in (left, bottom, right, top)):
            return 1.0, 1.0
        return right - left, top - bottom
    return base_size(scene, target)


def highlight_box(scene: Scene, obj: SceneObject) -> tuple[float, float] | None:
    """Width and height of the target of a highlight (``None`` without target)."""
    target = scene.object_by_id(obj.params.get("target"))
    if target is None or target.id == obj.id or target.kind == ObjectKind.HIGHLIGHT:
        return None
    return target_size(scene, target)


def base_size(scene: Scene, obj: SceneObject) -> tuple[float, float]:
    """Return the estimated width and height of an unrotated, unscaled object."""
    p = obj.params
    kind = obj.kind
    if kind == ObjectKind.NETWORK:
        from manim_studio.model.networks import network_layout

        points = list(network_layout(obj).values())
        radius = param_float(p, "radius", 0.3)
        if not points:
            return 2 * radius, 2 * radius
        xs, ys = [x for x, _ in points], [y for _, y in points]
        return max(xs) - min(xs) + 2 * radius, max(ys) - min(ys) + 2 * radius
    if kind == ObjectKind.BULLET_LIST:
        from manim_studio.model.lists import list_lines

        lines = list_lines(obj) or [" "]
        size = param_float(p, "font_size", 36.0)
        width = max(_text_size(line, size)[0] for line in lines)
        return width, len(lines) * _text_size("X", size)[1] + (len(lines) - 1) * param_float(p, "buff", 0.25)
    if kind == ObjectKind.VECTOR_FIELD:
        return param_float(p, "x_max", 7.0) - param_float(p, "x_min", -7.0) + 0.5, param_float(p, "y_max", 4.0) - param_float(p, "y_min", -4.0) + 0.5
    if kind == ObjectKind.TRACE:
        return 0.5, 0.5
    if kind == ObjectKind.ANGLE:
        radius = param_float(p, "radius", 0.6)
        return 2 * radius, 2 * radius
    if kind == ObjectKind.ZOOM_LENS:
        from manim_studio.model.lenses import lens_geometry

        lens = lens_geometry(obj)
        return lens.frame_width, lens.frame_height
    if kind == ObjectKind.BOOLEAN_SHAPE:
        from manim_studio.model.booleans import start_bounds

        bounds = start_bounds(scene, obj)
        return (bounds[2] - bounds[0], bounds[3] - bounds[1]) if bounds is not None else (0.5, 0.5)
    if kind == ObjectKind.HIGHLIGHT:
        box = highlight_box(scene, obj)
        if box is None:
            return 1.0, 1.0
        buff = param_float(p, "buff", 0.15)
        if p.get("style") == "underline":
            return box[0], box[1] / 2 + buff
        return box[0] + 2 * buff, box[1] + 2 * buff
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
    if kind == ObjectKind.CURVED_ARROW:
        from manim_studio.model.curved import curved_size

        return curved_size(obj)
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
    if kind == ObjectKind.FUNCTION_GRAPH or kind in GRAPH_TOOL_KINDS or kind == ObjectKind.DATA_PLOT:
        return _graph_size(scene, obj)
    if kind == ObjectKind.BAR_CHART:
        return param_float(p, "x_length", 6.0) + 0.8, param_float(p, "y_length", 4.0) + 0.6
    if kind == ObjectKind.BRACE:
        width = param_float(p, "width", 3.0)
        horizontal = p.get("direction", "down") in ("down", "up")
        return (width, 0.3) if horizontal else (0.3, width)
    return 1.0, 1.0


def _graph_size(scene: Scene, obj: SceneObject) -> tuple[float, float]:
    from manim_studio.model import graphs
    from manim_studio.model.geometry import axes_to_scene

    if obj.kind == ObjectKind.DATA_PLOT:
        from manim_studio.model.data import data_points

        axes = graphs.data_axes(scene, obj)
        raw = data_points(obj) + graphs.regression_points(obj)
        points = [list(axes_to_scene(axes, x, y)) for x, y in raw] if axes is not None else [list(p) for p in raw]
        return _points_size(points) if len(points) > 1 else (0.3, 0.3)
    if obj.kind == ObjectKind.TOOL_LABEL:
        from manim_studio.model.tool_labels import tool_label

        label = tool_label(scene, obj)
        return _text_size(label.text if label is not None else "?", param_float(obj.params, "font_size", 24.0))
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
