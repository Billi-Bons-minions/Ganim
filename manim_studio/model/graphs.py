"""Function graphs and the tools drawn on them (pure model logic).

Everything is computed in Manim units. Curves are evaluated with the current
parameter values (``values``: symbol -> value), so the stage can show graphs
that change while a parameter is animated. The same rules are used by the code
generator, which keeps the stage and the rendered video in sync.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from manim_studio.model.analysis import (
    FEATURE_EXTREMA,
    FEATURE_INFLECTION,
    FEATURE_INTERSECTIONS,
    KIND_MAXIMUM,
    KIND_MINIMUM,
    SpecialPoint,
    extrema,
    inflection_points,
    intersections,
    zeros,
)
from manim_studio.model.calculus import derivative
from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.expression import Expression, ExpressionError, evaluate_number, is_valid_name, parse_expression
from manim_studio.model.geometry import (
    GRAPH_SAMPLES,
    GRAPH_VALUE_LIMIT,
    Point,
    Segment,
    axes_to_scene,
    bbox_center,
    bound_axes,
    origin_shift,
    param_float,
)
from manim_studio.model.types import (
    CURVE_DERIVATIVE,
    CURVE_FUNCTION,
    CURVE_IMPLICIT,
    CURVE_PARAMETRIC,
    CURVE_PIECEWISE,
    CURVE_POLAR,
    FUNCTION_CURVES,
    GRAPH_TOOL_KINDS,
    ObjectKind,
)

Values = dict[str, float]
#: Manim's ``MED_SMALL_BUFF`` used by ``get_graph_label``.
LABEL_BUFF = 0.25
LABEL_DIRECTIONS: dict[str, Point] = {
    "up_right": (1.0, 1.0),
    "up": (0.0, 1.0),
    "right": (1.0, 0.0),
    "down_right": (1.0, -1.0),
    "down": (0.0, -1.0),
    "down_left": (-1.0, -1.0),
    "left": (-1.0, 0.0),
    "up_left": (-1.0, 1.0),
}


# --- parameters ---------------------------------------------------------------------


def parameter_objects(scene: Scene) -> list[SceneObject]:
    """Return the parameter objects of a scene."""
    return [obj for obj in scene.objects if obj.kind == ObjectKind.PARAMETER]


def parameter_symbol(obj: SceneObject) -> str:
    """Return the name a parameter has in terms (e.g. ``a``)."""
    return str(obj.params.get("symbol", "")).strip()


def parameter_symbols(scene: Scene) -> tuple[str, ...]:
    """Return the valid, unique parameter names of a scene."""
    symbols = [parameter_symbol(obj) for obj in parameter_objects(scene)]
    return tuple(sorted({symbol for symbol in symbols if is_valid_name(symbol) and symbols.count(symbol) == 1}))


def initial_values(scene: Scene) -> Values:
    """Return every parameter's start value."""
    return {parameter_symbol(obj): param_float(obj.params, "value", 0.0) for obj in parameter_objects(scene) if parameter_symbol(obj)}


def parse(scene: Scene, text: str, variable: str = "x") -> Expression | None:
    """Parse a term with the scene's parameters; ``None`` if it is invalid."""
    try:
        return parse_expression(text, variable, parameter_symbols(scene))
    except ExpressionError:
        return None


# --- function-like curves ----------------------------------------------------------------


@dataclass(frozen=True)
class Piece:
    """One part of a function: ``expression`` applies for ``low <= x < high``."""

    expression: Expression
    low: float
    high: float


def _piece_bound(text: object, default: float) -> float:
    value = evaluate_number(str(text)) if str(text).strip() else None
    return default if value is None else value


def function_pieces(scene: Scene, graph: SceneObject, _seen: frozenset[str] = frozenset()) -> list[Piece] | None:
    """Return ``y = f(x)`` of a graph as pieces (``None`` if it is no valid function)."""
    if graph.kind != ObjectKind.FUNCTION_GRAPH or graph.id in _seen:
        return None
    curve = graph.params.get("curve", CURVE_FUNCTION)
    if curve == CURVE_FUNCTION:
        expression = parse(scene, str(graph.params.get("expression", "")))
        return [Piece(expression, -math.inf, math.inf)] if expression is not None else None
    if curve == CURVE_PIECEWISE:
        pieces = []
        for row in graph.params.get("pieces", []) or []:
            if not isinstance(row, (list, tuple)) or not row:
                continue
            expression = parse(scene, str(row[0]))
            if expression is None:
                return None
            low = _piece_bound(row[1] if len(row) > 1 else "", -math.inf)
            high = _piece_bound(row[2] if len(row) > 2 else "", math.inf)
            pieces.append(Piece(expression, low, high))
        return pieces or None
    if curve == CURVE_DERIVATIVE:
        source = scene.object_by_id(graph.params.get("derive_from"))
        if source is None:
            return None
        base = function_pieces(scene, source, _seen | {graph.id})
        if base is None:
            return None
        order = 2 if str(graph.params.get("derive_order", "1")) == "2" else 1
        return [Piece(derivative(piece.expression, order), piece.low, piece.high) for piece in base]
    return None


def _evaluate(expression: Expression, x: float, values: Values | None) -> float:
    try:
        value = expression.evaluate(x, values)
    except (ArithmeticError, ValueError):
        return math.nan
    return value if math.isfinite(value) else math.nan


def piece_breaks(pieces: list[Piece], low: float, high: float) -> list[float]:
    """Return the x values inside ``(low, high)`` where one piece ends and the next begins."""
    breaks = {piece.low for piece in pieces} | {piece.high for piece in pieces}
    return sorted(value for value in breaks if low < value < high)


def evaluate_pieces(pieces: list[Piece], x: float, values: Values | None = None) -> float:
    """Evaluate a piecewise function (``nan`` where it is undefined)."""
    for index, piece in enumerate(pieces):
        last = index == len(pieces) - 1
        if piece.low <= x < piece.high or (last and x == piece.high):
            return _evaluate(piece.expression, x, values)
    return math.nan


def scene_values(scene: Scene, values: Values | None) -> Values:
    """Use the given parameter values or, if there are none, the start values."""
    return values if values is not None else initial_values(scene)


def graph_function(scene: Scene, graph: SceneObject, values: Values | None = None) -> Callable[[float], float] | None:
    """Return ``f`` of a function-like graph (``nan`` where undefined)."""
    values = scene_values(scene, values)
    pieces = function_pieces(scene, graph)
    if pieces is None:
        return None
    return lambda x: evaluate_pieces(pieces, x, values)


def is_function_curve(graph: SceneObject | None) -> bool:
    """Return ``True`` for graphs of the form ``y = f(x)``."""
    return graph is not None and graph.kind == ObjectKind.FUNCTION_GRAPH and graph.params.get("curve", CURVE_FUNCTION) in FUNCTION_CURVES


def x_range(graph: SceneObject) -> tuple[float, float]:
    """Return the x range of a function graph."""
    return param_float(graph.params, "x_min", -5.0), param_float(graph.params, "x_max", 5.0)


def y_limits(scene: Scene, graph: SceneObject) -> tuple[float, float] | None:
    """Return the y range a graph is clipped to (its axes' range) or ``None``."""
    axes = bound_axes(scene, graph)
    if axes is None or not graph.params.get("clip", True):
        return None
    return param_float(axes.params, "y_min", -3.0), param_float(axes.params, "y_max", 3.0)


def _clip_segment(points: list[Point], limits: tuple[float, float] | None) -> list[Segment]:
    if limits is None:
        return [points] if len(points) > 1 else []
    low, high = limits
    segments: list[Segment] = []
    current: Segment = []
    for index, (x, y) in enumerate(points):
        inside = low <= y <= high
        if inside:
            if not current and index > 0:
                px, py = points[index - 1]
                current.append(_crossing(px, py, x, y, low, high))
            current.append((x, y))
        elif current:
            current.append(_crossing(current[-1][0], current[-1][1], x, y, low, high))
            segments.append(current)
            current = []
    if current:
        segments.append(current)
    return [segment for segment in segments if _has_extent(segment)]


def _has_extent(segment: Segment) -> bool:
    return len(segment) > 1 and any(abs(x - segment[0][0]) + abs(y - segment[0][1]) > 1e-9 for x, y in segment[1:])


def _crossing(x0: float, y0: float, x1: float, y1: float, low: float, high: float) -> Point:
    edge = high if max(y0, y1) > high else low
    if y1 == y0:
        return x1, edge
    t = (edge - y0) / (y1 - y0)
    return x0 + (x1 - x0) * t, edge


def sample_curve(function: Callable[[float], float], low: float, high: float, limits: tuple[float, float] | None, samples: int = GRAPH_SAMPLES) -> list[Segment]:
    """Sample ``y = f(x)``; split where it is undefined or jumps, clip to ``limits``."""
    if high <= low:
        return []
    runs: list[list[Point]] = []
    current: list[Point] = []
    for index in range(samples + 1):
        x = low + (high - low) * index / samples
        y = function(x)
        defined = math.isfinite(y) and abs(y) <= GRAPH_VALUE_LIMIT
        if defined and current and limits is not None and _jumps(current[-1][1], y, limits):
            runs.append(current)
            current = []
        if defined:
            current.append((x, y))
        elif current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)
    segments: list[Segment] = []
    for run in runs:
        segments += _clip_segment(run, limits)
    return segments


def _jumps(previous: float, value: float, limits: tuple[float, float]) -> bool:
    """Detect a pole between two samples (a jump across the whole visible range)."""
    low, high = limits
    middle = (low + high) / 2
    return abs(value - previous) > 2 * (high - low) and (previous - middle) * (value - middle) < 0


def curve_points(scene: Scene, graph: SceneObject, values: Values | None = None) -> list[Segment]:
    """Return the curve in the graph's own coordinates (axes coordinates if bound)."""
    values = scene_values(scene, values)
    curve = graph.params.get("curve", CURVE_FUNCTION)
    if curve in FUNCTION_CURVES:
        pieces = function_pieces(scene, graph)
        if pieces is None:
            return []
        low, high = x_range(graph)
        limits = y_limits(scene, graph)
        segments: list[Segment] = []
        for piece in pieces:
            a, b = max(low, piece.low), min(high, piece.high)
            if b <= a:
                continue
            samples = max(40, round(GRAPH_SAMPLES * (b - a) / (high - low)))
            segments += sample_curve(lambda x, e=piece.expression: _evaluate(e, x, values), a, b, limits, samples)
        return segments
    if curve == CURVE_IMPLICIT:
        return implicit_segments(scene, graph, values)
    t_min, t_max = param_float(graph.params, "t_min", 0.0), param_float(graph.params, "t_max", math.tau)
    if curve == CURVE_PARAMETRIC:
        fx = parse(scene, str(graph.params.get("x_expression", "")), "t")
        fy = parse(scene, str(graph.params.get("y_expression", "")), "t")
        if fx is None or fy is None:
            return []
        point = lambda t: (fx.evaluate(t, values), fy.evaluate(t, values))  # noqa: E731
    elif curve == CURVE_POLAR:
        fr = parse(scene, str(graph.params.get("r_expression", "")), "t")
        if fr is None:
            return []
        point = lambda t: (fr.evaluate(t, values) * math.cos(t), fr.evaluate(t, values) * math.sin(t))  # noqa: E731
    else:
        return []
    return _sample_parametric(point, t_min, t_max)


IMPLICIT_GRID = (96, 64)
_implicit_cache: dict[tuple, list[Segment]] = {}


def implicit_range(scene: Scene, graph: SceneObject) -> tuple[float, float, float, float]:
    """Where an implicit curve is searched: the range of its axes (like Manim) or the frame."""
    axes = bound_axes(scene, graph)
    if axes is None:
        return -7.0, 7.0, -4.0, 4.0
    return (
        param_float(axes.params, "x_min", -5.0),
        param_float(axes.params, "x_max", 5.0),
        param_float(axes.params, "y_min", -3.0),
        param_float(axes.params, "y_max", 3.0),
    )


def implicit_expression(scene: Scene, graph: SceneObject) -> Expression | None:
    try:
        return parse_expression(str(graph.params.get("implicit_expression", "")), "x", ("y", *parameter_symbols(scene)))
    except ExpressionError:
        return None


def implicit_segments(scene: Scene, graph: SceneObject, values: Values | None = None) -> list[Segment]:
    """The curve f(x, y) = 0 found with marching squares (short pieces in axes coordinates)."""
    expression = implicit_expression(scene, graph)
    if expression is None:
        return []
    values = scene_values(scene, values)
    x0, x1, y0, y1 = implicit_range(scene, graph)
    used = expression.used_parameters()
    key = (str(graph.params.get("implicit_expression")), x0, x1, y0, y1, tuple(sorted((k, round(v, 9)) for k, v in values.items() if k in used)))
    if key in _implicit_cache:
        return _implicit_cache[key]
    nx, ny = IMPLICIT_GRID
    xs = [x0 + (x1 - x0) * i / nx for i in range(nx + 1)]
    ys = [y0 + (y1 - y0) * j / ny for j in range(ny + 1)]

    def value(x: float, y: float) -> float:
        try:
            result = expression.evaluate(x, {**values, "y": y})
        except (ArithmeticError, ValueError, OverflowError):
            return math.nan
        return result if math.isfinite(result) else math.nan

    grid = [[value(x, y) for y in ys] for x in xs]
    segments: list[Segment] = []
    for i in range(nx):
        for j in range(ny):
            corners = [(xs[i], ys[j], grid[i][j]), (xs[i + 1], ys[j], grid[i + 1][j]), (xs[i + 1], ys[j + 1], grid[i + 1][j + 1]), (xs[i], ys[j + 1], grid[i][j + 1])]
            if any(math.isnan(c[2]) for c in corners):
                continue
            crossings = []
            for (ax, ay, av), (bx, by, bv) in zip(corners, corners[1:] + corners[:1]):
                if (av < 0) != (bv < 0):
                    t = av / (av - bv)
                    crossings.append((ax + (bx - ax) * t, ay + (by - ay) * t))
            if len(crossings) == 2:
                segments.append(crossings)
            elif len(crossings) == 4:
                segments += [crossings[:2], crossings[2:]]
    if len(_implicit_cache) > 32:
        _implicit_cache.clear()
    _implicit_cache[key] = segments
    return segments


def _sample_parametric(point: Callable[[float], Point], low: float, high: float) -> list[Segment]:
    segments: list[Segment] = []
    current: Segment = []
    if high <= low:
        return segments
    samples = GRAPH_SAMPLES * 2
    for index in range(samples + 1):
        t = low + (high - low) * index / samples
        try:
            x, y = point(t)
        except (ArithmeticError, ValueError):
            x = y = math.nan
        if math.isfinite(x) and math.isfinite(y) and max(abs(x), abs(y)) <= GRAPH_VALUE_LIMIT:
            current.append((x, y))
        elif current:
            segments.append(current)
            current = []
    if current:
        segments.append(current)
    return [segment for segment in segments if len(segment) > 1]


def graph_scene_segments(scene: Scene, graph: SceneObject, values: Values | None = None) -> list[Segment]:
    """Return the curve of a graph attached to axes, in scene coordinates."""
    axes = bound_axes(scene, graph)
    if axes is None:
        return []
    return [[axes_to_scene(axes, x, y) for x, y in segment] for segment in curve_points(scene, graph, values)]


# --- graph tools -----------------------------------------------------------------------------


def tool_graph(scene: Scene, obj: SceneObject) -> SceneObject | None:
    """Return the function graph a tool is drawn on (only if it lies on axes)."""
    graph = scene.object_by_id(obj.params.get("graph_id"))
    if graph is None or graph.id == obj.id or bound_axes(scene, graph) is None:
        return None
    return graph


def tool_x(scene: Scene, obj: SceneObject, values: Values | None) -> float:
    """Return the x position of a tangent or point (a parameter's value if linked)."""
    parameter = scene.object_by_id(obj.params.get("x_parameter"))
    if parameter is not None and parameter.kind == ObjectKind.PARAMETER:
        symbol = parameter_symbol(parameter)
        if values is not None and symbol in values:
            return float(values[symbol])
        return param_float(parameter.params, "value", 0.0)
    return param_float(obj.params, "x_value", 0.0)


def _baseline(axes: SceneObject) -> float:
    return origin_shift(param_float(axes.params, "y_min", -3.0), param_float(axes.params, "y_max", 3.0))


def _xs(low: float, high: float, samples: int = 200) -> list[float]:
    return [low + (high - low) * index / samples for index in range(samples + 1)]


def area_polygon(scene: Scene, obj: SceneObject, values: Values | None = None) -> list[Point]:
    """Outline of an area tool in axes coordinates."""
    graph = tool_graph(scene, obj)
    function = graph_function(scene, graph, values) if graph is not None else None
    if graph is None or function is None:
        return []
    axes = bound_axes(scene, graph)
    assert axes is not None
    low, high = param_float(obj.params, "x_min", -1.0), param_float(obj.params, "x_max", 2.0)
    g_low, g_high = x_range(graph)
    low, high = max(low, g_low), min(high, g_high)
    if high <= low:
        return []
    clamp = _clamper(y_limits(scene, graph))
    top = [(x, clamp(function(x))) for x in _xs(low, high)]
    top = [(x, y) for x, y in top if math.isfinite(y)]
    if not top:
        return []
    mode = obj.params.get("mode", "under")
    if mode == "between":
        other = scene.object_by_id(obj.params.get("other_graph_id"))
        other_function = graph_function(scene, other, values) if other is not None and other.id != graph.id else None
        if other_function is None:
            return []
        other_clamp = _clamper(y_limits(scene, other))
        bottom = [(x, other_clamp(other_function(x))) for x in _xs(low, high)]
        bottom = [(x, y) for x, y in bottom if math.isfinite(y)]
        return top + bottom[::-1]
    if mode in ("above", "below"):
        edge = param_float(axes.params, "y_max" if mode == "above" else "y_min", 3.0 if mode == "above" else -3.0)
        return top + [(top[-1][0], edge), (top[0][0], edge)]
    base = _baseline(axes)
    return [(top[0][0], base)] + top + [(top[-1][0], base)]


def _clamper(limits: tuple[float, float] | None) -> Callable[[float], float]:
    """Clip values like a clipped graph does (its area follows the cut edge)."""
    if limits is None:
        return lambda y: y
    low, high = limits
    return lambda y: min(max(y, low), high) if math.isfinite(y) else y


def riemann_rectangles(scene: Scene, obj: SceneObject, values: Values | None = None) -> list[list[Point]]:
    """Rectangles of a Riemann sum (like Manim's ``get_riemann_rectangles``)."""
    graph = tool_graph(scene, obj)
    function = graph_function(scene, graph, values) if graph is not None else None
    if graph is None or function is None:
        return []
    axes = bound_axes(scene, graph)
    assert axes is not None
    low, high = param_float(obj.params, "x_min", 0.0), param_float(obj.params, "x_max", 3.0)
    dx = param_float(obj.params, "dx", 0.25)
    if dx <= 0 or high <= low or (high - low) / dx > 2000:
        return []
    offset = {"left": 0.0, "center": 0.5, "right": 1.0}.get(str(obj.params.get("sample", "left")), 0.0)
    base = _baseline(axes)
    rectangles = []
    count = math.ceil((high - low) / dx - 1e-9)
    for index in range(count):
        x = low + index * dx
        y = function(x + offset * dx)
        if not math.isfinite(y):
            continue
        rectangles.append([(x, base), (x + dx, base), (x + dx, y), (x, y)])
    return rectangles


def tangent_points(scene: Scene, obj: SceneObject, values: Values | None = None) -> list[Point]:
    """End points of a tangent line in axes coordinates."""
    graph = tool_graph(scene, obj)
    pieces = function_pieces(scene, graph) if graph is not None else None
    if pieces is None:
        return []
    values = scene_values(scene, values)
    x0 = tool_x(scene, obj, values)
    y0 = evaluate_pieces(pieces, x0, values)
    slope_pieces = [Piece(derivative(piece.expression), piece.low, piece.high) for piece in pieces]
    slope = evaluate_pieces(slope_pieces, x0, values)
    if not (math.isfinite(y0) and math.isfinite(slope)):
        return []
    half = param_float(obj.params, "width", 3.0) / 2
    return [(x0 - half, y0 - slope * half), (x0 + half, y0 + slope * half)]


def tangent_slope(scene: Scene, obj: SceneObject, values: Values | None = None) -> float | None:
    """Return the slope of a tangent (for labels and code generation)."""
    points = tangent_points(scene, obj, values)
    if len(points) != 2:
        return None
    (x0, y0), (x1, y1) = points
    return (y1 - y0) / (x1 - x0) if x1 != x0 else None


def graph_point(scene: Scene, obj: SceneObject, values: Values | None = None) -> Point | None:
    """The point ``(x, f(x))`` of a point-on-graph tool."""
    graph = tool_graph(scene, obj)
    function = graph_function(scene, graph, values) if graph is not None else None
    if function is None:
        return None
    x0 = tool_x(scene, obj, values)
    y0 = function(x0)
    return (x0, y0) if math.isfinite(y0) else None


def marker_points(scene: Scene, obj: SceneObject, values: Values | None = None) -> list[SpecialPoint]:
    """Zeros, extrema, inflection points or intersections of a graph."""
    graph = tool_graph(scene, obj)
    pieces = function_pieces(scene, graph) if graph is not None else None
    if graph is None or pieces is None:
        return []
    values = scene_values(scene, values)
    low, high = x_range(graph)
    feature = obj.params.get("feature", "zeros")
    other_pieces: list[Piece] | None = None
    if feature == FEATURE_INTERSECTIONS:
        other = scene.object_by_id(obj.params.get("other_graph_id"))
        other_pieces = function_pieces(scene, other) if other is not None and other.id != graph.id else None
        if other is None or other_pieces is None:
            return []
        low, high = max(low, x_range(other)[0]), min(high, x_range(other)[1])
    points: list[SpecialPoint] = []
    for piece in pieces:
        a, b = max(low, piece.low), min(high, piece.high)
        if b <= a:
            continue
        if feature == FEATURE_EXTREMA:
            found = extrema(piece.expression, a, b, values)
        elif feature == FEATURE_INFLECTION:
            found = inflection_points(piece.expression, a, b, values)
        elif other_pieces is not None:
            found = []
            for other_piece in other_pieces:
                c, d = max(a, other_piece.low), min(b, other_piece.high)
                if d > c:
                    found += intersections(piece.expression, other_piece.expression, c, d, values)
        else:
            found = zeros(piece.expression, a, b, values)
        points += found
    limits = y_limits(scene, graph)
    if limits is not None:
        points = [point for point in points if limits[0] - 1e-9 <= point.y <= limits[1] + 1e-9]
    return points


def format_coordinate(value: float) -> str:
    """Format a coordinate for labels: at most two decimals, no ``-0``."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def point_label(x: float, y: float) -> str:
    """Return the label of a point, e.g. ``(1.57 | 1)``."""
    return f"({format_coordinate(x)} | {format_coordinate(y)})"


def marker_label_direction(scene: Scene, obj: SceneObject, special: SpecialPoint, values: Values | None = None) -> Point:
    """Direction of a marker label (like Manim's ``next_to``) that keeps it off the curve.

    Maxima get their label above, minima below; other points sit on the side the curve
    does not pass through (below right where it rises, above right where it falls).
    """
    if special.kind == KIND_MAXIMUM:
        return (0.0, 1.0)
    if special.kind == KIND_MINIMUM:
        return (0.0, -1.0)
    graph = tool_graph(scene, obj)
    function = graph_function(scene, graph, values) if graph is not None else None
    if function is None:
        return (1.0, 1.0)
    step = 1e-3
    slope = (function(special.x + step) - function(special.x - step)) / (2 * step)
    return (1.0, -1.0) if math.isfinite(slope) and slope > 0 else (1.0, 1.0)


def label_anchor(scene: Scene, obj: SceneObject, values: Values | None = None) -> tuple[Point, Point] | None:
    """Return the graph point and the direction of a graph label (axes coordinates)."""
    graph = tool_graph(scene, obj)
    if graph is None:
        return None
    x0 = param_float(obj.params, "x_value", 2.0)
    if is_function_curve(graph):
        function = graph_function(scene, graph, values)
        y0 = function(x0) if function is not None else math.nan
    else:
        return None
    if not math.isfinite(y0):
        return None
    return (x0, y0), LABEL_DIRECTIONS.get(str(obj.params.get("direction", "up_right")), (1.0, 1.0))


# --- placement -----------------------------------------------------------------------------------


def data_axes(scene: Scene, obj: SceneObject) -> SceneObject | None:
    """Return the coordinate system of a data plot."""
    axes = scene.object_by_id(obj.params.get("axes_id"))
    return axes if axes is not None and axes.kind in (ObjectKind.AXES, ObjectKind.NUMBER_PLANE) else None


def data_fit(obj: SceneObject):
    """Return the regression of a data plot or ``None``."""
    from manim_studio.model.data import data_points, regression

    kind = str(obj.params.get("regression", "none"))
    return regression(data_points(obj), kind) if kind != "none" else None


def regression_points(obj: SceneObject, samples: int = 120) -> list[Point]:
    """Samples of the regression curve over the x range of the data."""
    from manim_studio.model.data import data_points

    fit = data_fit(obj)
    points = data_points(obj)
    if fit is None or not points:
        return []
    low, high = min(x for x, _y in points), max(x for x, _y in points)
    result = []
    for x in _xs(low, high, samples):
        try:
            y = fit.evaluate(x)
        except OverflowError:
            continue
        if math.isfinite(y):
            result.append((x, y))
    return result


def is_bound(scene: Scene, obj: SceneObject) -> bool:
    """Return ``True`` for objects placed by a coordinate system (graphs on axes and graph tools)."""
    if obj.kind == ObjectKind.FUNCTION_GRAPH:
        return bound_axes(scene, obj) is not None
    if obj.kind == ObjectKind.DATA_PLOT:
        return data_axes(scene, obj) is not None
    if obj.kind in (ObjectKind.SURFACE, ObjectKind.CURVE_3D, ObjectKind.SOLID):
        from manim_studio.model.three_d import axes_of

        return axes_of(scene, obj) is not None
    if obj.kind in GRAPH_TOOL_KINDS:
        return tool_graph(scene, obj) is not None
    return False


def tool_axes_points(scene: Scene, obj: SceneObject, values: Values | None = None) -> list[Point]:
    """All characteristic points of a bound object in axes coordinates."""
    kind = obj.kind
    if kind == ObjectKind.GRAPH_AREA:
        return area_polygon(scene, obj, values)
    if kind == ObjectKind.RIEMANN:
        return [point for rectangle in riemann_rectangles(scene, obj, values) for point in rectangle]
    if kind == ObjectKind.TANGENT:
        return tangent_points(scene, obj, values)
    if kind == ObjectKind.GRAPH_POINT:
        point = graph_point(scene, obj, values)
        return [point] if point is not None else []
    if kind == ObjectKind.GRAPH_MARKERS:
        return [(point.x, point.y) for point in marker_points(scene, obj, values)]
    if kind == ObjectKind.GRAPH_LABEL:
        anchor = label_anchor(scene, obj, values)
        if anchor is None:
            return []
        (x0, y0), (dx, dy) = anchor
        return [(x0 + dx * 0.6, y0 + dy * 0.4)]
    return []


def bound_anchor(scene: Scene, obj: SceneObject, values: Values | None = None) -> Point:
    """Return the center of a bound object in scene coordinates."""
    if obj.kind == ObjectKind.FUNCTION_GRAPH:
        center = bbox_center(graph_scene_segments(scene, obj, values))
        axes = bound_axes(scene, obj)
        if center is not None:
            return center
        return (axes.x, axes.y) if axes is not None else (obj.x, obj.y)
    if obj.kind in (ObjectKind.SURFACE, ObjectKind.CURVE_3D, ObjectKind.SOLID):
        from manim_studio.model import three_d

        view = three_d.view_of(scene)
        if obj.kind == ObjectKind.SOLID:
            points3 = [point for quad in three_d.solid_quads(scene, obj) for point in quad]
        elif obj.kind == ObjectKind.SURFACE:
            points3 = [point for line in three_d.surface_grid(scene, obj) for point in line]
        else:
            points3 = three_d.curve_points(scene, obj)
        flat = three_d.project(points3, view)
        center = bbox_center([flat]) if flat else None
        return center if center is not None else (obj.x, obj.y)
    if obj.kind == ObjectKind.DATA_PLOT:
        from manim_studio.model.data import data_points

        axes = data_axes(scene, obj)
        raw = data_points(obj) + regression_points(obj)
    else:
        graph = tool_graph(scene, obj)
        axes = bound_axes(scene, graph) if graph is not None else None
        raw = tool_axes_points(scene, obj, values) if axes is not None else []
    if axes is None:
        return obj.x, obj.y
    points = [axes_to_scene(axes, x, y) for x, y in raw]
    center = bbox_center([points]) if points else None
    return center if center is not None else (axes.x, axes.y)


def area_value(scene: Scene, obj: SceneObject, values: Values | None = None) -> float | None:
    """Signed area of an area tool (integral of the upper minus the lower boundary)."""
    graph = tool_graph(scene, obj)
    function = graph_function(scene, graph, values) if graph is not None else None
    if graph is None or function is None:
        return None
    axes = bound_axes(scene, graph)
    assert axes is not None
    low, high = param_float(obj.params, "x_min", -1.0), param_float(obj.params, "x_max", 2.0)
    g_low, g_high = x_range(graph)
    low, high = max(low, g_low), min(high, g_high)
    if high <= low:
        return None
    mode = obj.params.get("mode", "under")
    if mode == "between":
        other = scene.object_by_id(obj.params.get("other_graph_id"))
        lower = graph_function(scene, other, values) if other is not None else None
        if lower is None:
            return None
    elif mode in ("above", "below"):
        edge = param_float(axes.params, "y_max" if mode == "above" else "y_min", 0.0)
        lower = lambda x: edge  # noqa: E731
    else:
        base = _baseline(axes)
        lower = lambda x: base  # noqa: E731
    samples = 2000
    step = (high - low) / samples
    total = 0.0
    previous = None
    for index in range(samples + 1):
        x = low + index * step
        value = function(x) - lower(x)
        if not math.isfinite(value):
            return None
        if previous is not None:
            total += (previous + value) / 2 * step
        previous = value
    return -total if mode == "above" else total


def riemann_value(scene: Scene, obj: SceneObject, values: Values | None = None) -> float | None:
    """Sum of the (signed) rectangle areas of a Riemann sum."""
    rectangles = riemann_rectangles(scene, obj, values)
    if not rectangles:
        return None
    return sum((rect[1][0] - rect[0][0]) * (rect[2][1] - rect[1][1]) for rect in rectangles)


def _expression_texts(obj: SceneObject) -> list[tuple[str, str]]:
    texts = [(str(obj.params.get(key, "")), variable) for key, variable in (("expression", "x"), ("x_expression", "t"), ("y_expression", "t"), ("r_expression", "t"))]
    texts += [(str(row[0]), "x") for row in obj.params.get("pieces", []) or [] if isinstance(row, (list, tuple)) and row]
    return texts


def parameter_users(scene: Scene, obj: SceneObject, _seen: frozenset[str] = frozenset()) -> set[str]:
    """Return the ids of the parameters an object depends on (directly or through its graph)."""
    if obj.id in _seen:
        return set()
    seen = _seen | {obj.id}
    by_symbol = {parameter_symbol(p): p.id for p in parameter_objects(scene)}
    used: set[str] = set()
    for key in ("x_parameter", "parameter_id"):
        reference = scene.object_by_id(obj.params.get(key))
        if reference is not None and reference.kind == ObjectKind.PARAMETER:
            used.add(reference.id)
    if obj.kind == ObjectKind.FUNCTION_GRAPH:
        for text, variable in _expression_texts(obj):
            expression = parse(scene, text, variable) if text.strip() else None
            if expression is not None:
                used |= {by_symbol[symbol] for symbol in expression.used_parameters() if symbol in by_symbol}
        if obj.params.get("curve") == CURVE_IMPLICIT:
            expression = implicit_expression(scene, obj)
            if expression is not None:
                used |= {by_symbol[symbol] for symbol in expression.used_parameters() if symbol in by_symbol}
    if obj.kind == ObjectKind.VECTOR_FIELD:
        from manim_studio.model.fields import field_users

        used |= {by_symbol[symbol] for symbol in field_users(scene, obj) if symbol in by_symbol}
    if obj.kind in (ObjectKind.SURFACE, ObjectKind.CURVE_3D):
        # 3D objects with parameters are redrawn while the parameters change
        texts = [(obj.params.get("expression", ""), "x", ("y",))] if obj.kind == ObjectKind.SURFACE else [(obj.params.get(key, ""), "t", ()) for key in ("x_expression", "y_expression", "z_expression")]
        for text, variable, extra in texts:
            try:
                expression = parse_expression(str(text), variable, (*extra, *parameter_symbols(scene)))
            except ExpressionError:
                continue
            used |= {by_symbol[symbol] for symbol in expression.used_parameters() if symbol in by_symbol}
    for key in ("graph_id", "other_graph_id", "derive_from"):
        reference = scene.object_by_id(obj.params.get(key))
        if reference is not None:
            used |= parameter_users(scene, reference, seen)
    return used
