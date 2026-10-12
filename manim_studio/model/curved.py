"""Curved arrows: Manim's ``ArcBetweenPoints``, ``CurvedArrow`` and ``CurvedDoubleArrow``.

The geometry follows Manim step by step, so that the stage shows exactly the
rendered shape: the arc runs from the start to the end of a horizontal chord
(positive angles bend it below the chord, like Manim), a tip is placed along the
arc's tangent and the arc is shrunk so that it ends at the tip's base. For the
double arrow Manim then maps everything (including the first tip) so that the
start moves to the second tip's base.
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass

from manim_studio.model.entities import SceneObject
from manim_studio.model.geometry import Point, param_float

#: Manim's ``DEFAULT_ARROW_TIP_LENGTH`` (tips are as wide as they are long).
TIP_LENGTH = 0.35
TIP_CHOICES = ("end", "both", "none")


#: Manim's ``Arc`` is made of this many cubic Bézier curves.
ARC_CURVES = 8


@dataclass(frozen=True)
class CurvedParts:
    """The arc and the filled tip triangles, in the object's own coordinates.

    ``shaft`` holds Manim's Bézier points: anchor, handle, handle, anchor for each
    curve (``ARC_CURVES`` curves, or one for a straight line).
    """

    shaft: list[Point]
    tips: list[list[Point]]


def _arc(start: complex, end: complex, angle: float) -> list[complex]:
    """Bézier points of Manim's ``ArcBetweenPoints(start, end, angle)``."""
    if abs(angle) < 1e-9:
        return [start, start + (end - start) / 3, start + 2 * (end - start) / 3, end]
    chord = end - start
    # the center lies on the perpendicular bisector; seen from the chord's direction it is on the left for angle > 0
    middle = (start + end) / 2
    distance = abs(chord) / 2 / math.tan(angle / 2)
    center = middle + chord / abs(chord) * 1j * distance
    first = start - center
    step = angle / ARC_CURVES
    anchors = [center + first * cmath.exp(1j * step * i) for i in range(ARC_CURVES + 1)]
    # handles along the tangents, 4/3 tan(step/4) of the radius long (as in Manim's Arc)
    factor = 4 / 3 * math.tan(step / 4)
    points = []
    for a, b in zip(anchors[:-1], anchors[1:]):
        points += [a, a + factor * 1j * (a - center), b - factor * 1j * (b - center), b]
    return points


def _direction(start: complex, end: complex, angle: float, at_end: bool) -> complex:
    """Unit tangent of the arc (in the direction of travel) at its start or end."""
    chord = cmath.phase(end - start)
    return cmath.exp(1j * (chord + angle / 2 if at_end else chord - angle / 2))


def _tip(point: complex, forward: complex, length: float) -> list[complex]:
    """Manim's ``ArrowTriangleFilledTip``: point, then the two corners of the base."""
    base = point - forward * length
    side = forward * 1j * length / 2
    return [point, base + side, base - side]


def curved_parts(obj: SceneObject) -> CurvedParts:
    """Arc and tips of a curved arrow before it is placed (chord from -length/2 to length/2)."""
    half = param_float(obj.params, "length", 3.0) / 2
    angle = math.radians(param_float(obj.params, "angle", 60.0))
    tips = obj.params.get("tips_at", "end")
    start, end = complex(-half, 0.0), complex(half, 0.0)
    if tips not in ("end", "both") or half <= 0:
        return CurvedParts(_points(_arc(start, end, angle)), [])
    end_forward = _direction(start, end, angle, at_end=True)
    end_tip = _tip(end, end_forward, TIP_LENGTH)
    end_base = end - end_forward * TIP_LENGTH
    if tips == "end":
        return CurvedParts(_points(_arc(start, end_base, angle)), [_points(end_tip)])
    # the second tip points backwards along the (already shortened) arc
    start_back = -_direction(start, end_base, angle, at_end=False)
    start_tip = _tip(start, start_back, TIP_LENGTH)
    start_base = start - start_back * TIP_LENGTH
    # put_start_and_end_on(start_base, end): a similarity that keeps the end in place
    factor = (end - start_base) / (end - start)

    def mapped(point: complex) -> complex:
        return start_base + (point - start) * factor

    shaft = _arc(mapped(start), mapped(end_base), angle)
    return CurvedParts(_points(shaft), [_points([mapped(point) for point in end_tip]), _points(start_tip)])


def curved_bounds(obj: SceneObject) -> tuple[float, float, float, float]:
    """``(left, bottom, right, top)`` of all points, handles included, as Manim measures it."""
    parts = curved_parts(obj)
    points = parts.shaft + [point for tip in parts.tips for point in tip]
    xs, ys = [x for x, _ in points], [y for _, y in points]
    return min(xs), min(ys), max(xs), max(ys)


def curved_size(obj: SceneObject) -> tuple[float, float]:
    """Width and height of a curved arrow's bounding box."""
    left, bottom, right, top = curved_bounds(obj)
    return right - left, top - bottom


def _points(values: list[complex]) -> list[Point]:
    return [(value.real, value.imag) for value in values]
