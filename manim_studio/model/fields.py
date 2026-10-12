"""Vector fields (arrows or stream lines) like Manim's ``ArrowVectorField`` and ``StreamLines``.

The stage mirrors Manim: arrows start at the grid points and are
``0.45 * sigmoid(|v|)`` long; stream lines start at the same jittered points
(NumPy's generator with seed 0) and follow the field with Euler steps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.expression import Expression, ExpressionError, parse_expression
from manim_studio.model.geometry import param_float

#: Manim's ``DEFAULT_SCALAR_FIELD_COLORS`` (slow → fast).
FIELD_COLORS = ("#236B8E", "#83C167", "#F7D96F", "#FC6255")
STREAM_DT = 0.05
STREAM_PADDING = 3.0
MAX_ANCHORS = 100


@dataclass(frozen=True)
class FieldArrow:
    x: float
    y: float
    dx: float
    dy: float
    color: str


def field_expressions(scene: Scene, obj: SceneObject) -> tuple[Expression, Expression] | None:
    """The two components ``(f_x(x, y), f_y(x, y))`` (``None`` if one is invalid)."""
    from manim_studio.model.graphs import parameter_symbols

    symbols = ("y", *parameter_symbols(scene))
    try:
        return tuple(parse_expression(str(obj.params.get(key, "")), "x", symbols) for key in ("x_expression", "y_expression"))  # type: ignore[return-value]
    except ExpressionError:
        return None


def _value(expression: Expression, x: float, y: float, values: dict[str, float]) -> float:
    try:
        result = expression.evaluate(x, {**values, "y": y})
    except (ArithmeticError, ValueError, OverflowError):
        return math.nan
    return result if math.isfinite(result) else math.nan


def _grid(start: float, stop: float, step: float) -> list[float]:
    """``np.arange(start, stop + step, step)`` like Manim's range handling."""
    if step <= 0:
        return []
    count = max(0, math.ceil((stop + step - start) / step - 1e-12))
    return [start + index * step for index in range(min(count, 400))]


def field_ranges(obj: SceneObject) -> tuple[list[float], list[float], float]:
    """Grid coordinates (scene units, around the object's position) and spacing."""
    step = max(0.05, param_float(obj.params, "step", 0.5))
    xs = _grid(obj.x + param_float(obj.params, "x_min", -7.0), obj.x + param_float(obj.params, "x_max", 7.0), step)
    ys = _grid(obj.y + param_float(obj.params, "y_min", -4.0), obj.y + param_float(obj.params, "y_max", 4.0), step)
    return xs, ys, step


def magnitude_color(obj: SceneObject, magnitude: float) -> str:
    """Color of a field value: the object's color or Manim's gradient over the magnitude."""
    if not obj.params.get("colored", True):
        return obj.stroke_color
    top = max(1e-9, param_float(obj.params, "max_color", 2.0))
    alpha = min(max(magnitude, 0.0), top) / top * (len(FIELD_COLORS) - 1)
    first = FIELD_COLORS[int(alpha)]
    second = FIELD_COLORS[min(int(alpha) + 1, len(FIELD_COLORS) - 1)]
    t = alpha % 1
    channels = []
    for index in (1, 3, 5):
        a, b = int(first[index : index + 2], 16), int(second[index : index + 2], 16)
        channels.append(round(a + (b - a) * t))
    return "#" + "".join(f"{value:02X}" for value in channels)


def field_arrows(scene: Scene, obj: SceneObject, values: dict[str, float] | None = None) -> list[FieldArrow]:
    """The arrows of an ``ArrowVectorField`` (start point, vector, color)."""
    from manim_studio.model.graphs import scene_values

    expressions = field_expressions(scene, obj)
    if expressions is None:
        return []
    values = scene_values(scene, values)
    xs, ys, _step = field_ranges(obj)
    arrows = []
    for x in xs:
        for y in ys:
            vx, vy = (_value(expression, x, y, values) for expression in expressions)
            if not (math.isfinite(vx) and math.isfinite(vy)):
                continue
            norm = math.hypot(vx, vy)
            if norm > 0:
                length = 0.45 / (1 + math.exp(-norm))
                vx, vy = vx * length / norm, vy * length / norm
            arrows.append(FieldArrow(x, y, vx, vy, magnitude_color(obj, norm)))
    return arrows


def _start_points(xs: list[float], ys: list[float], noise: float) -> list[tuple[float, float]]:
    try:
        import numpy as np
    except ImportError:  # without NumPy: same grid, deterministic but different jitter
        import random

        generator = random.Random(0)
        return [(x - noise / 2 + noise * generator.random(), y - noise / 2 + noise * generator.random()) for x in xs for y in ys]
    rng = np.random.default_rng(0)
    points = []
    for x in xs:
        for y in ys:
            jitter = rng.random(3)
            points.append((x - noise / 2 + noise * jitter[0], y - noise / 2 + noise * jitter[1]))
    return points


_stream_cache: dict[tuple, list[list[tuple[float, float, float]]]] = {}


def stream_lines(scene: Scene, obj: SceneObject, values: dict[str, float] | None = None) -> list[list[tuple[float, float, float]]]:
    """Lines of ``StreamLines``: ``(x, y, |v|)`` along each line (cached: integrating is slow)."""
    from manim_studio.model.graphs import scene_values

    expressions = field_expressions(scene, obj)
    if expressions is None:
        return []
    values = scene_values(scene, values)
    used = set().union(*(expression.used_parameters() for expression in expressions))
    key = (
        str(obj.params.get("x_expression")),
        str(obj.params.get("y_expression")),
        round(obj.x, 6),
        round(obj.y, 6),
        tuple(round(param_float(obj.params, name, 0.0), 6) for name in ("x_min", "x_max", "y_min", "y_max", "step", "virtual_time")),
        tuple(sorted((name, round(value, 9)) for name, value in values.items() if name in used)),
    )
    if key not in _stream_cache:
        if len(_stream_cache) > 32:
            _stream_cache.clear()
        _stream_cache[key] = _integrate(obj, expressions, values)
    return _stream_cache[key]


def _integrate(obj: SceneObject, expressions: tuple[Expression, Expression], values: dict[str, float]) -> list[list[tuple[float, float, float]]]:
    xs, ys, step = field_ranges(obj)
    if not xs or not ys:
        return []
    low_x, high_x = xs[0] - STREAM_PADDING, xs[-1] + STREAM_PADDING
    low_y, high_y = ys[0] - STREAM_PADDING, ys[-1] + STREAM_PADDING
    steps = math.ceil(param_float(obj.params, "virtual_time", 3.0) / STREAM_DT) + 1
    lines = []
    for x, y in _start_points(xs, ys, step / 2):
        points = [(x, y)]
        for _ in range(steps):
            px, py = points[-1]
            vx, vy = (_value(expression, px, py, values) for expression in expressions)
            if not (math.isfinite(vx) and math.isfinite(vy)):
                break
            nx, ny = px + STREAM_DT * vx, py + STREAM_DT * vy
            if nx < low_x or nx > high_x or ny < low_y or ny > high_y:
                break
            points.append((nx, ny))
        stride = max(1, len(points) // MAX_ANCHORS)
        kept = points[::stride]
        if len(kept) < 2:
            continue
        lines.append([(px, py, math.hypot(*(_value(e, px, py, values) for e in expressions))) for px, py in kept])
    return lines


def field_users(scene: Scene, obj: SceneObject) -> set[str]:
    """Parameter symbols a field uses."""
    expressions = field_expressions(scene, obj)
    return set().union(*(expression.used_parameters() for expression in expressions)) if expressions else set()
