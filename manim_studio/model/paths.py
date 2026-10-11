"""Outlines of objects used as motion paths (``MoveAlongPath``).

The points follow the order in which Manim builds the shapes, so the stage
preview moves an object the same way as the rendered video.
"""

from __future__ import annotations

import math

from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.geometry import Point, param_float, rotate_point
from manim_studio.model.types import LINE_KINDS, ObjectKind

ARC_SAMPLES = 96


def _arc(radius_x: float, radius_y: float, start: float, angle: float, samples: int = ARC_SAMPLES) -> list[Point]:
    return [
        (radius_x * math.cos(math.radians(start + angle * index / samples)), radius_y * math.sin(math.radians(start + angle * index / samples)))
        for index in range(samples + 1)
    ]


def _closed(points: list[Point]) -> list[Point]:
    return points + points[:1] if points else points


def _regular(n: int, radius: float, start: float) -> list[Point]:
    return [(radius * math.cos(math.radians(start + 360 * k / n)), radius * math.sin(math.radians(start + 360 * k / n))) for k in range(n)]


def local_outline(scene: Scene, obj: SceneObject) -> list[Point] | None:
    """Points of the outline in the object's own coordinates (``None`` = no path)."""
    p = obj.params
    kind = obj.kind
    if kind == ObjectKind.CIRCLE:
        r = param_float(p, "radius", 1.0)
        return _arc(r, r, 0.0, 360.0)
    if kind == ObjectKind.ELLIPSE:
        return _arc(param_float(p, "width", 3.0) / 2, param_float(p, "height", 1.5) / 2, 0.0, 360.0)
    if kind == ObjectKind.ARC:
        r = param_float(p, "radius", 1.5)
        return _arc(r, r, param_float(p, "start_angle", 0.0), param_float(p, "angle", 90.0))
    if kind in (ObjectKind.SQUARE, ObjectKind.RECTANGLE):
        w = param_float(p, "side_length" if kind == ObjectKind.SQUARE else "width", 2.0 if kind == ObjectKind.SQUARE else 4.0)
        h = w if kind == ObjectKind.SQUARE else param_float(p, "height", 2.0)
        return _closed([(w / 2, h / 2), (-w / 2, h / 2), (-w / 2, -h / 2), (w / 2, -h / 2)])
    if kind == ObjectKind.TRIANGLE:
        return _closed(_regular(3, param_float(p, "radius", 1.0), 90.0))
    if kind == ObjectKind.REGULAR_POLYGON:
        n = max(3, int(p.get("n", 6)))
        return _closed(_regular(n, param_float(p, "radius", 1.0), 90.0 if n % 2 else 90.0 - 180.0 / n))
    if kind == ObjectKind.POLYGON:
        return _closed([(float(x), float(y)) for x, y in p.get("points", [])])
    if kind == ObjectKind.STAR:
        n = max(3, int(p.get("n", 5)))
        outer, inner = param_float(p, "outer_radius", 1.2), param_float(p, "inner_radius", 0.5)
        points = []
        for k in range(2 * n):
            radius = outer if k % 2 == 0 else inner
            angle = math.radians(90 + 180 * k / n)
            points.append((radius * math.cos(angle), radius * math.sin(angle)))
        return _closed(points)
    if kind in LINE_KINDS:
        half = param_float(p, "length", 3.0) / 2
        return [(-half, 0.0), (half, 0.0)]
    if kind == ObjectKind.FUNCTION_GRAPH:
        from manim_studio.model import graphs

        segments = graphs.curve_points(scene, obj)
        return [point for segment in segments for point in segment] or None
    return None


def path_polyline(scene: Scene, states: dict, path_id: str) -> list[Point]:
    """The path in scene coordinates, placed where the path object currently is."""
    obj = scene.object_by_id(path_id)
    if obj is None:
        return []
    from manim_studio.model import graphs
    from manim_studio.model.geometry import bound_axes

    if obj.kind == ObjectKind.FUNCTION_GRAPH and bound_axes(scene, obj) is not None:
        segments = graphs.graph_scene_segments(scene, obj)
        points = [point for segment in segments for point in segment]
        state = states.get(path_id)
        if state is None or not points:
            return points
        ax, ay = graphs.bound_anchor(scene, obj)
        return [(x + state.x - ax, y + state.y - ay) for x, y in points]
    local = local_outline(scene, obj)
    if not local:
        return []
    xs, ys = [x for x, _y in local], [y for _x, y in local]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    state = states.get(path_id)
    x0, y0 = (state.x, state.y) if state is not None else (obj.x, obj.y)
    rotation = state.rotation if state is not None else obj.rotation
    scale = state.scale if state is not None else 1.0
    result = []
    for x, y in local:
        rx, ry = rotate_point((x - cx) * scale, (y - cy) * scale, rotation)
        result.append((x0 + rx, y0 + ry))
    return result


def point_at(points: list[Point], proportion: float) -> Point | None:
    """The point at ``proportion`` (0…1) of the path length."""
    if not points:
        return None
    if len(points) == 1:
        return points[0]
    lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
    total = sum(lengths)
    if total == 0:
        return points[0]
    target = max(0.0, min(1.0, proportion)) * total
    for (a, b), length in zip(zip(points, points[1:]), lengths):
        if target <= length and length > 0:
            t = target / length
            return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        target -= length
    return points[-1]


def path_end(scene: Scene, states: dict, path_id: str) -> Point | None:
    """Where an object ends up after moving along a path."""
    return point_at(path_polyline(scene, states, path_id), 1.0)


def arc_point(start: Point, end: Point, alpha: float, arc_degrees: float = 90.0) -> Point:
    """Manim's ``path_along_arc``: the point at ``alpha`` on an arc from start to end."""
    if arc_degrees == 0 or start == end:
        return start[0] + (end[0] - start[0]) * alpha, start[1] + (end[1] - start[1]) * alpha
    angle = math.radians(arc_degrees)
    vx, vy = end[0] - start[0], end[1] - start[1]
    cx = start[0] + vx / 2 - (vy / 2) / math.tan(angle / 2)
    cy = start[1] + vy / 2 + (vx / 2) / math.tan(angle / 2)
    rx, ry = rotate_point(start[0] - cx, start[1] - cy, math.degrees(angle * alpha))
    return cx + rx, cy + ry
