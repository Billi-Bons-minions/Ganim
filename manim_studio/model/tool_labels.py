"""Value labels: separate objects that show a value of a graph tool and follow it.

A value label belongs to a tangent or secant (its term, equation or slope), to a point
on a graph (its coordinates or the function value) or to an area (its size or the signed
integral). It is drawn in the coordinates of the tool's axes and changes with the tool,
but it is an object of its own: it can appear later than the tool, be highlighted or
fade out on its own.

The texts are formatted exactly like the script's ``studio_label_text``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from manim_studio.model import graphs
from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.geometry import bound_axes, param_float
from manim_studio.model.types import LABELED_TOOL_KINDS, ObjectKind

#: What a value label can show; "auto" picks the first one that fits its tool.
CONTENTS = ("auto", "term", "equation", "slope", "coordinates", "function_value", "area", "integral")
#: The contents that fit each kind of tool (the first one is the automatic choice).
CONTENTS_FOR = {
    ObjectKind.TANGENT: ("term", "equation", "slope"),
    ObjectKind.SECANT: ("term", "equation", "slope"),
    ObjectKind.GRAPH_POINT: ("coordinates", "function_value"),
    ObjectKind.GRAPH_AREA: ("area", "integral"),
}
#: Distance between a point and its label beyond the point's radius (Manim's ``SMALL_BUFF``).
SMALL_BUFF = 0.1
#: Simpson steps for areas, like the script's ``studio_integral``.
AREA_STEPS = graphs.INTEGRAL_STEPS

BESIDE = "beside"
CORNER = "corner"
CENTER = "center"


def label_tool(scene: Scene, obj: SceneObject) -> SceneObject | None:
    """The tangent, secant, point or area a value label belongs to."""
    tool = scene.object_by_id(obj.params.get("tool_id"))
    if tool is None or tool.id == obj.id or tool.kind not in LABELED_TOOL_KINDS:
        return None
    return tool


def label_content(scene: Scene, obj: SceneObject) -> str | None:
    """The content actually shown (``auto`` resolved, one that does not fit replaced by the automatic one)."""
    tool = label_tool(scene, obj)
    if tool is None:
        return None
    fitting = CONTENTS_FOR[tool.kind]
    chosen = str(obj.params.get("content", "auto"))
    return chosen if chosen in fitting else fitting[0]


def content_fits(scene: Scene, obj: SceneObject) -> bool:
    tool = label_tool(scene, obj)
    chosen = str(obj.params.get("content", "auto"))
    return tool is None or chosen == "auto" or chosen in CONTENTS_FOR[tool.kind]


def _number(value: float, decimals: int) -> str:
    """A fixed number of decimals, a real minus sign and never "−0.00" (like ``graphs.line_term``)."""
    text = f"{abs(value):.{decimals}f}"
    return ("−" if value < 0 and float(text) != 0 else "") + text


def label_text(content: str, decimals: int, first: float, second: float, name: str) -> str:
    """The text of a value label; the script's ``studio_label_text`` does exactly the same.

    ``first``/``second`` are slope and intercept (lines), x and y (points) or the area.
    """
    if content in graphs.LINE_LABEL_STYLES:
        return graphs.line_term(name, first, second, decimals, content)
    if content == "coordinates":
        return f"({_number(first, decimals)} | {_number(second, decimals)})"
    if content == "function_value":
        return f"{name}({_number(first, decimals)}) = {_number(second, decimals)}"
    if content == "area":
        return f"A = {_number(abs(first), decimals)}"
    return f"∫ {name}(x) dx = {_number(first, decimals)}"


def function_name(graph: SceneObject | None) -> str:
    """How a graph is called in labels: its name if that is a plain name, otherwise ``f``."""
    from manim_studio.model.expression import is_valid_name

    name = graph.name.strip() if graph is not None else ""
    return name if is_valid_name(name) else "f"


@dataclass(frozen=True)
class ToolLabel:
    """Text and placement of a value label (anchor in axes coordinates)."""

    text: str
    x: float
    y: float
    #: ``beside`` a line (with ``slope`` and ``side``), at the ``corner`` of a point (``buff``) or at the ``center`` of an area
    placement: str
    slope: float = 0.0
    side: int = 1
    buff: float = 0.0


def simpson(function, start: float, end: float, steps: int = AREA_STEPS) -> float:
    """Simpson's rule exactly like the script's ``studio_integral`` (``nan`` where undefined)."""
    if end == start:
        return 0.0
    count = 2 * steps
    h = (end - start) / count
    total = 0.0
    for index in range(count + 1):
        x = start + (end - start) * index / count
        try:
            y = float(function(x))
        except (ArithmeticError, ValueError):
            return math.nan
        weight = 1 if index in (0, count) else (4 if index % 2 else 2)
        total += weight * y
    return h / 3 * total


def area_bounds(scene: Scene, area: SceneObject):
    """``(low, high, f, lower)`` of an area tool: the x range on the graph and the two boundaries."""
    graph = graphs.tool_graph(scene, area)
    if graph is None:
        return None
    low, high = param_float(area.params, "x_min", -1.0), param_float(area.params, "x_max", 2.0)
    g_low, g_high = graphs.x_range(graph)
    low, high = max(low, g_low), min(high, g_high)
    if high <= low:
        return None
    return low, high, graph


def tool_label(scene: Scene, obj: SceneObject, values: graphs.Values | None = None) -> ToolLabel | None:
    """What a value label shows and where (``None`` if its tool is missing or undefined)."""
    tool = label_tool(scene, obj)
    content = label_content(scene, obj)
    graph = graphs.tool_graph(scene, tool) if tool is not None else None
    pieces = graphs.function_pieces(scene, graph) if graph is not None else None
    if tool is None or content is None or pieces is None:
        return None
    values = graphs.scene_values(scene, values)
    decimals = max(0, min(6, int(param_float(obj.params, "decimals", 2.0))))
    name = function_name(graph)
    if tool.kind in (ObjectKind.TANGENT, ObjectKind.SECANT):
        if tool.kind == ObjectKind.SECANT:
            found = graphs.secant(scene, tool, values)
            if found is None:
                return None
            x, y, slope, line_name = (found.x0 + found.x1) / 2, (found.y0 + found.y1) / 2, found.slope, "s"
        else:
            slope = graphs.tangent_slope(scene, tool, values)
            x = graphs.tool_x(scene, tool, values)
            y = graphs.evaluate_pieces(pieces, x, values)
            if slope is None or not math.isfinite(y):
                return None
            line_name = "t"
        side = graphs.label_side(str(obj.params.get("label_side", "auto")), lambda t: graphs.evaluate_pieces(pieces, t, values), x, y)
        return ToolLabel(label_text(content, decimals, slope, y - slope * x, line_name), x, y, BESIDE, slope, side)
    if tool.kind == ObjectKind.GRAPH_POINT:
        point = graphs.graph_point(scene, tool, values)
        if point is None:
            return None
        buff = param_float(tool.params, "radius", 0.08) + SMALL_BUFF
        return ToolLabel(label_text(content, decimals, point[0], point[1], name), point[0], point[1], CORNER, buff=buff)
    bounds = area_bounds(scene, tool)
    if bounds is None:
        return None
    low, high, _graph = bounds
    upper, lower = area_functions(scene, tool, values)
    if upper is None or lower is None:
        return None
    if content == "area":
        value = simpson(lambda x: abs(upper(x) - lower(x)), low, high)
    else:
        value = simpson(lambda x: upper(x) - lower(x), low, high)
        if tool.params.get("mode") == "above":
            value = -value  # the area lies above the graph: from f up to the edge
    middle = (low + high) / 2
    try:
        y = (upper(middle) + lower(middle)) / 2
    except (ArithmeticError, ValueError):
        return None
    if not (math.isfinite(value) and math.isfinite(y)):
        return None
    return ToolLabel(label_text(content, decimals, value, 0.0, name), middle, y, CENTER)


def area_functions(scene: Scene, area: SceneObject, values: graphs.Values | None):
    """The upper and lower boundary of an area tool (``None`` where one is missing)."""
    graph = graphs.tool_graph(scene, area)
    upper = graphs.graph_function(scene, graph, values) if graph is not None else None
    axes = bound_axes(scene, graph) if graph is not None else None
    mode = area.params.get("mode", "under")
    if mode == "between":
        other = scene.object_by_id(area.params.get("other_graph_id"))
        lower = graphs.graph_function(scene, other, values) if other is not None and graphs.is_function_curve(other) else None
    elif axes is None:
        lower = None
    elif mode in ("above", "below"):
        edge = param_float(axes.params, "y_max" if mode == "above" else "y_min", 0.0)
        lower = lambda x: edge  # noqa: E731
    else:
        base = graphs.baseline(axes)
        lower = lambda x: base  # noqa: E731
    return upper, lower


def estimated_center(scene: Scene, obj: SceneObject, values: graphs.Values | None = None) -> tuple[float, float] | None:
    """Rough center of the label in axes coordinates (the stage measures the real text)."""
    from manim_studio.model.extents import _text_size
    from manim_studio.model.geometry import axes_to_scene

    label = tool_label(scene, obj, values)
    graph = graphs.tool_graph(scene, obj)
    axes = bound_axes(scene, graph) if graph is not None else None
    if label is None or axes is None:
        return None
    width, height = _text_size(label.text, param_float(obj.params, "font_size", 24.0))
    px, py = axes_to_scene(axes, label.x, label.y)
    if label.placement == CENTER:
        dx, dy = label_shift(obj)
        return scene_to_axes(axes, px + dx, py + dy)
    if label.placement == CORNER:
        cx, cy = px + label.buff + width / 2, py + label.buff + height / 2
    else:
        qx, qy = axes_to_scene(axes, label.x + 1, label.y + label.slope)
        length = math.hypot(qx - px, qy - py) or 1.0
        nx, ny = label.side * -(qy - py) / length, label.side * (qx - px) / length
        distance = abs(nx) * width / 2 + abs(ny) * height / 2 + graphs.LINE_LABEL_BUFF
        cx, cy = px + distance * nx, py + distance * ny
    dx, dy = label_shift(obj)
    return scene_to_axes(axes, cx + dx, cy + dy)


def label_shift(obj: SceneObject) -> tuple[float, float]:
    """How far the label is moved away from its automatic place (scene units)."""
    return param_float(obj.params, "shift_x", 0.0), param_float(obj.params, "shift_y", 0.0)


def scene_to_axes(axes: SceneObject, x: float, y: float) -> tuple[float, float]:
    """Inverse of ``axes_to_scene`` (the mapping is affine)."""
    from manim_studio.model.geometry import axes_to_scene

    ox, oy = axes_to_scene(axes, 0.0, 0.0)
    ux, uy = axes_to_scene(axes, 1.0, 0.0)
    vx, vy = axes_to_scene(axes, 0.0, 1.0)
    a, b, c, d = ux - ox, vx - ox, uy - oy, vy - oy
    det = a * d - b * c
    if abs(det) < 1e-12:
        return 0.0, 0.0
    dx, dy = x - ox, y - oy
    return (d * dx - b * dy) / det, (-c * dx + a * dy) / det
