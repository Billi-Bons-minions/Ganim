"""Dashed outlines like Manim's ``DashedVMobject`` (and ``DashedLine``).

Manim cuts the outline into ``num_dashes`` pieces of equal arc length: a dash takes
``dashed_ratio`` of each period. Closed outlines have as many gaps as dashes, open ones
start and end with a dash. The dashes follow the outline in the order Manim builds it
(``paths.local_outline``), so they lie where the video has them.
"""

from __future__ import annotations

import math

from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.geometry import Point, param_float
from manim_studio.model.types import ObjectKind

#: Shapes that can be drawn dashed (their outline only).
DASHED_KINDS = frozenset(
    {
        ObjectKind.CIRCLE,
        ObjectKind.ELLIPSE,
        ObjectKind.ARC,
        ObjectKind.SQUARE,
        ObjectKind.RECTANGLE,
        ObjectKind.TRIANGLE,
        ObjectKind.REGULAR_POLYGON,
        ObjectKind.POLYGON,
        ObjectKind.STAR,
        ObjectKind.SECTOR,
    }
)
#: Manim's defaults of ``DashedVMobject``.
DEFAULT_DASHES = 15
DEFAULT_RATIO = 0.5
#: Graphs are long: more dashes than Manim's default by default.
DEFAULT_GRAPH_DASHES = 40
#: Curves of a function graph that can be dashed (implicit curves are many separate pieces).
DASHED_CURVES = ("function", "derivative", "piecewise", "antiderivative", "parametric", "polar")


def is_dashed(obj: SceneObject | None) -> bool:
    """``True`` for a shape drawn as ``DashedVMobject`` (not for the dashed line, which is its own kind)."""
    return obj is not None and obj.kind in DASHED_KINDS and bool(obj.params.get("dashed", False))


def is_dashed_graph(obj: SceneObject | None) -> bool:
    """``True`` for a function graph drawn with dashes (its tools keep using the graph itself)."""
    return (
        obj is not None
        and obj.kind == ObjectKind.FUNCTION_GRAPH
        and bool(obj.params.get("dashed", False))
        and obj.params.get("curve", "function") in DASHED_CURVES
    )


def dash_settings(obj: SceneObject) -> tuple[int, float]:
    """``(num_dashes, dashed_ratio)`` of a dashed shape or a dashed line."""
    ratio = min(max(param_float(obj.params, "dashed_ratio", DEFAULT_RATIO), 0.01), 0.99)
    if obj.kind == ObjectKind.DASHED_LINE:
        # DashedLine._calculate_num_dashes
        length = param_float(obj.params, "length", 3.0)
        dash = max(param_float(obj.params, "dash_length", 0.15), 1e-6)
        return max(2, math.ceil(length / dash * ratio)), ratio
    default = DEFAULT_GRAPH_DASHES if obj.kind == ObjectKind.FUNCTION_GRAPH else DEFAULT_DASHES
    return max(1, int(obj.params.get("num_dashes", default))), ratio


def dash_intervals(count: int, ratio: float, closed: bool, offset: float = 0.0) -> list[tuple[float, float]]:
    """Start and end of every dash as fractions of the length (``DashedVMobject.__init__``)."""
    if count <= 0:
        return []
    dash = ratio / count
    if closed:
        void = (1 - ratio) / count
    else:
        void = 1 - ratio if count == 1 else (1 - ratio) / (count - 1)
    period = dash + void
    shift = (offset % 1) * period
    pattern = 1.0 if closed else 1.0 + void
    starts = [(i * period + shift) % pattern for i in range(count)]
    ends = [(i * period + dash + shift) % pattern for i in range(count)]
    if not closed:
        if ends[-1] > 1 and starts[-1] > 1:
            ends.pop()
            starts.pop()
        elif ends[-1] < dash:
            if starts[-1] < 1:
                starts.append(0)
                ends.append(ends[-1])
                ends[-2] = 1
            else:
                starts[-1] = 0
        elif starts[-1] > 1 - dash:
            ends[-1] = 1
    return list(zip(starts, ends))


def _point_at(points: list[Point], lengths: list[float], target: float) -> tuple[int, Point]:
    """The segment index and the point at arc length ``target``."""
    for index in range(1, len(points)):
        if lengths[index] >= target or index == len(points) - 1:
            span = lengths[index] - lengths[index - 1]
            t = 0.0 if span <= 0 else min(max((target - lengths[index - 1]) / span, 0.0), 1.0)
            a, b = points[index - 1], points[index]
            return index, (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    return 1, points[-1]


def _piece(points: list[Point], lengths: list[float], start: float, end: float) -> list[Point]:
    first_index, first = _point_at(points, lengths, start)
    last_index, last = _point_at(points, lengths, end)
    return [first] + points[first_index:last_index] + [last]


def cut_dashes(points: list[Point], intervals: list[tuple[float, float]], closed: bool) -> list[list[Point]]:
    """Cut a polyline into dashes; on a closed outline a dash may run over the start point."""
    if len(points) < 2:
        return []
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1] + math.dist(a, b))
    total = lengths[-1]
    if total <= 0:
        return []
    dashes = []
    for start, end in intervals:
        if end >= start:
            dashes.append(_piece(points, lengths, start * total, end * total))
        elif closed:
            dashes.append(_piece(points, lengths, start * total, total) + _piece(points, lengths, 0.0, end * total)[1:])
    return dashes


def cut_segments(segments: list[list[Point]], intervals: list[tuple[float, float]], closed: bool) -> list[list[Point]]:
    """Cut a curve made of several pieces; the gaps between pieces do not count (Manim appends the pieces' curves)."""
    pieces = [segment for segment in segments if len(segment) >= 2]
    if len(pieces) == 1:
        return cut_dashes(pieces[0], intervals, closed)
    lengths = [sum(math.dist(a, b) for a, b in zip(piece, piece[1:])) for piece in pieces]
    total = sum(lengths)
    if total <= 0:
        return []
    dashes: list[list[Point]] = []
    for start, end in intervals:
        begin, finish = start * total, end * total
        dash: list[Point] = []
        offset = 0.0
        for piece, length in zip(pieces, lengths):
            low, high = max(begin, offset), min(finish, offset + length)
            if high > low and length > 0:
                part = cut_dashes(piece, [((low - offset) / length, (high - offset) / length)], False)
                if part:
                    if dash:
                        dashes.append(dash)  # a dash over a gap: Manim's subcurve jumps, two pieces here
                    dash = part[0]
            offset += length
        if dash:
            dashes.append(dash)
    return dashes


def graph_dashes(obj: SceneObject, segments: list[list[Point]]) -> list[list[Point]]:
    """The dashes of a dashed graph from its curve pieces in scene coordinates."""
    pieces = [segment for segment in segments if len(segment) >= 2]
    if not pieces:
        return []
    count, ratio = dash_settings(obj)
    # like VMobject.is_closed: one piece that ends where it starts (a whole circle or rose)
    closed = len(pieces) == 1 and math.dist(pieces[0][0], pieces[0][-1]) < 1e-6
    return cut_segments(pieces, dash_intervals(count, ratio, closed), closed)


def dash_polylines(scene: Scene, obj: SceneObject) -> list[list[Point]]:
    """The dashes of a dashed shape or line, centered like the stage draws the object (bounding box at 0, 0)."""
    from manim_studio.model.paths import local_outline

    outline = local_outline(scene, obj)
    if not outline or len(outline) < 2:
        return []
    from manim_studio.model.paths import outline_center

    closed = obj.kind not in (ObjectKind.ARC, ObjectKind.DASHED_LINE) and not (obj.kind == ObjectKind.POLYGON and not obj.params.get("closed", True))
    count, ratio = dash_settings(obj)
    cx, cy = outline_center(obj, outline)
    centered = [(x - cx, y - cy) for x, y in outline]
    return cut_dashes(centered, dash_intervals(count, ratio, closed), closed)
