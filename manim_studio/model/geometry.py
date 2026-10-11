"""Pure geometry helpers shared by the state computation and the stage.

All coordinates are Manim units with y pointing up. The helpers mirror how
Manim lays out coordinate systems so that the stage matches the rendering.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.expression import Expression, ExpressionError, parse_expression
from manim_studio.model.types import ObjectKind

AXES_TIP_LENGTH = 0.35
AXES_TICK_SIZE = 0.1
GRAPH_SAMPLES = 400
GRAPH_VALUE_LIMIT = 1.0e4

Point = tuple[float, float]
Segment = list[Point]


def origin_shift(low: float, high: float) -> float:
    """Return where the other axis crosses an axis range (Manim's ``_origin_shift``)."""
    if low > 0:
        return low
    if high < 0:
        return high
    return 0.0


def rotate_point(x: float, y: float, degrees: float) -> Point:
    """Rotate a point counter-clockwise around the origin."""
    radians = math.radians(degrees)
    cos_a, sin_a = math.cos(radians), math.sin(radians)
    return x * cos_a - y * sin_a, x * sin_a + y * cos_a


@dataclass(frozen=True)
class AxesLayout:
    """Layout of an ``Axes``/``NumberPlane`` relative to its bounding-box center."""

    x_min: float
    x_max: float
    y_min: float
    y_max: float
    x_length: float
    y_length: float
    offset: Point

    def to_local(self, xv: float, yv: float) -> Point:
        """Map axes coordinates onto local coordinates (bounding-box center = 0)."""
        x_span = self.x_max - self.x_min or 1.0
        y_span = self.y_max - self.y_min or 1.0
        lx = (xv - (self.x_min + self.x_max) / 2) / x_span * self.x_length
        ly = (yv - (self.y_min + self.y_max) / 2) / y_span * self.y_length
        return lx - self.offset[0], ly - self.offset[1]

    def origin_local(self) -> Point:
        """Return the local point where both axes intersect."""
        return self.to_local(origin_shift(self.x_min, self.x_max), origin_shift(self.y_min, self.y_max))


def axes_layout(obj: SceneObject) -> AxesLayout:
    """Compute the layout of a coordinate system object.

    Manim centers the plot area and then ``move_to`` uses the bounding box,
    which is enlarged by the arrow tips (or ticks) on the axis lines.
    """
    params = obj.params
    x_min, x_max = float(params.get("x_min", -5.0)), float(params.get("x_max", 5.0))
    y_min, y_max = float(params.get("y_min", -3.0)), float(params.get("y_max", 3.0))
    x_length, y_length = float(params.get("x_length", 10.0)), float(params.get("y_length", 6.0))
    plain = AxesLayout(x_min, x_max, y_min, y_max, x_length, y_length, (0.0, 0.0))
    if obj.kind == ObjectKind.NUMBER_PLANE:
        return plain
    half = AXES_TIP_LENGTH / 2 if params.get("tips", True) else AXES_TICK_SIZE
    axis_x, axis_y = plain.origin_local()
    left = min(-x_length / 2, axis_x - half)
    right = max(x_length / 2, axis_x + half)
    bottom = min(-y_length / 2, axis_y - half)
    top = max(y_length / 2, axis_y + half)
    offset = ((left + right) / 2, (bottom + top) / 2)
    return AxesLayout(x_min, x_max, y_min, y_max, x_length, y_length, offset)


def local_to_scene(obj: SceneObject, local: Point) -> Point:
    """Place a local point using the object's position and rotation."""
    rx, ry = rotate_point(local[0], local[1], obj.rotation)
    return obj.x + rx, obj.y + ry


def axes_to_scene(axes: SceneObject, xv: float, yv: float) -> Point:
    """Map axes coordinates of a coordinate system onto scene coordinates."""
    return local_to_scene(axes, axes_layout(axes).to_local(xv, yv))


def try_parse(text: str) -> Expression | None:
    """Parse a function term and return ``None`` if it is invalid."""
    try:
        return parse_expression(text)
    except ExpressionError:
        return None


def sample_function(expression: Expression, x_min: float, x_max: float, samples: int = GRAPH_SAMPLES) -> list[Segment]:
    """Sample ``y = f(x)`` and split the curve where it is undefined."""
    segments: list[Segment] = []
    current: Segment = []
    if x_max <= x_min:
        return segments
    for index in range(samples + 1):
        xv = x_min + (x_max - x_min) * index / samples
        try:
            yv = expression.evaluate(xv)
        except (ArithmeticError, ValueError):
            yv = math.nan
        if math.isfinite(yv) and abs(yv) <= GRAPH_VALUE_LIMIT:
            current.append((xv, yv))
        elif current:
            segments.append(current)
            current = []
    if current:
        segments.append(current)
    return segments


def bound_axes(scene: Scene, graph: SceneObject) -> SceneObject | None:
    """Return the coordinate system a function graph is attached to."""
    axes = scene.object_by_id(graph.params.get("axes_id"))
    if axes is None or axes.kind not in (ObjectKind.AXES, ObjectKind.NUMBER_PLANE):
        return None
    return axes


def graph_scene_segments(scene: Scene, graph: SceneObject) -> list[Segment]:
    """Return the curve of a graph attached to axes, in scene coordinates."""
    axes = bound_axes(scene, graph)
    expression = try_parse(str(graph.params.get("expression", "")))
    if axes is None or expression is None:
        return []
    raw = sample_function(expression, float(graph.params.get("x_min", -5.0)), float(graph.params.get("x_max", 5.0)))
    return [[axes_to_scene(axes, xv, yv) for xv, yv in segment] for segment in raw]


def bbox_center(segments: list[Segment]) -> Point | None:
    """Return the center of the bounding box of point segments."""
    points = [point for segment in segments for point in segment]
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def graph_anchor(scene: Scene, graph: SceneObject) -> Point:
    """Return the initial center of a function graph.

    Graphs attached to axes are positioned by the axes; free graphs use their
    own ``x``/``y``.
    """
    axes = bound_axes(scene, graph)
    if axes is None:
        return graph.x, graph.y
    center = bbox_center(graph_scene_segments(scene, graph))
    return center if center is not None else (axes.x, axes.y)


def is_bound_graph(scene: Scene, obj: SceneObject) -> bool:
    """Return ``True`` for function graphs attached to a coordinate system."""
    return obj.kind == ObjectKind.FUNCTION_GRAPH and bound_axes(scene, obj) is not None


def param_float(params: dict[str, Any], key: str, default: float) -> float:
    """Read a numeric parameter defensively."""
    try:
        return float(params.get(key, default))
    except (TypeError, ValueError):
        return default
