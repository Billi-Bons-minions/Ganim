"""Nonlinear maps of the plane: Manim's ``ApplyComplexFunction`` and ``ApplyPointwiseFunction``.

A map moves every point of an object to its image, e.g. ``z ↦ z²`` bends a coordinate
grid into parabolas. The state of an object keeps the maps it went through (``warps``),
the stage moves the points of its outlines accordingly.

Where a map is undefined (``1/z`` at 0) or shoots far away, the point stays where it is
or is pulled back to ``LIMIT``; the script's ``studio_map_point`` does exactly the same,
so Manim gets no invalid points.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Callable

from manim_studio.model.entities import Animation
from manim_studio.model.expression import Expression, ExpressionError, evaluate_complex, parse_complex, parse_expression
from manim_studio.model.types import AnimationKind

COMPLEX = "complex"
POINTWISE = "pointwise"
#: Images farther away than this are pulled back onto this circle (keeps Manim's points finite).
LIMIT = 1000.0
#: The longest piece of an outline that is moved as a straight line (scene units).
STEP = 0.05

#: ``(kind, terms, progress)``: a map and how far it has gone (1 = done).
Warp = tuple[str, tuple[str, ...], float]

Point = tuple[float, float]


def warp_of(anim: Animation, progress: float = 1.0) -> Warp | None:
    """The map of an animation (``None`` for other animations)."""
    if anim.kind == AnimationKind.APPLY_COMPLEX:
        return COMPLEX, (str(anim.params.get("function", "z^2")),), progress
    if anim.kind == AnimationKind.APPLY_POINTWISE:
        return POINTWISE, (str(anim.params.get("x_function", "x")), str(anim.params.get("y_function", "y"))), progress
    return None


@lru_cache(maxsize=128)
def _parsed(kind: str, terms: tuple[str, ...]) -> tuple[Expression, ...] | None:
    try:
        if kind == COMPLEX:
            return (parse_complex(terms[0]),)
        return tuple(parse_expression(term, "x", ("y",)) for term in terms)
    except ExpressionError:
        return None


def warp_error(kind: str, terms: tuple[str, ...]) -> ExpressionError | None:
    """Why the terms of a map cannot be used (``None`` if they are fine)."""
    try:
        if kind == COMPLEX:
            parse_complex(terms[0])
        else:
            for term in terms:
                parse_expression(term, "x", ("y",))
    except ExpressionError as error:
        return error
    return None


def safe_point(x: float, y: float, image: Callable[[float, float], Point]) -> Point:
    """The image of a point; the point itself where the map is undefined, at most ``LIMIT`` away."""
    try:
        u, v = image(x, y)
        u, v = float(u), float(v)
    except (ArithmeticError, ValueError, TypeError):
        return x, y
    if not (math.isfinite(u) and math.isfinite(v)):
        return x, y
    length = math.hypot(u, v)
    if length > LIMIT:
        return u / length * LIMIT, v / length * LIMIT
    return u, v


def map_function(kind: str, terms: tuple[str, ...]) -> Callable[[float, float], Point] | None:
    """The map as a function of a point (with the safety of ``safe_point``)."""
    parsed = _parsed(kind, terms)
    if parsed is None:
        return None
    if kind == COMPLEX:
        expression = parsed[0]

        def image(x: float, y: float) -> Point:
            w = evaluate_complex(expression, complex(x, y))
            return w.real, w.imag

    else:
        fx, fy = parsed

        def image(x: float, y: float) -> Point:
            return fx.evaluate(x, {"y": y}), fy.evaluate(x, {"y": y})

    return lambda x, y: safe_point(x, y, image)


def warp_point(warp: Warp, x: float, y: float) -> Point:
    """Where a point is after ``progress`` of the map.

    Points move on straight lines: ``ApplyComplexFunction`` defines an arc path (angle ``arg f(1)``),
    but Manim 0.19 to 0.22 never use it (the method that sets it is not called).
    """
    kind, terms, progress = warp
    function = map_function(kind, terms)
    if function is None:
        return x, y
    u, v = function(x, y)
    if progress >= 1.0:
        return u, v
    return x + (u - x) * progress, y + (v - y) * progress


def warp_polyline(warps: tuple[Warp, ...], points: list[Point], closed: bool = False) -> list[Point]:
    """Move a polyline through the maps; long straight pieces are split first so they can bend."""
    if not warps or not points:
        return points
    dense: list[Point] = []
    ring = points + [points[0]] if closed and points[0] != points[-1] else points
    for a, b in zip(ring, ring[1:]):
        pieces = max(1, math.ceil(math.dist(a, b) / STEP))
        dense += [(a[0] + (b[0] - a[0]) * k / pieces, a[1] + (b[1] - a[1]) * k / pieces) for k in range(pieces)]
    dense.append(ring[-1])
    result = []
    for x, y in dense:
        for warp in warps:
            x, y = warp_point(warp, x, y)
        result.append((x, y))
    return result


def warped_objects(scene, until: int | None = None) -> set[str]:
    """Ids of the objects a nonlinear map bends in the timeline (up to step ``until``; members of mapped groups included)."""
    from manim_studio.model import groups
    from manim_studio.model.types import StepKind

    found: set[str] = set()
    for step in scene.steps[: None if until is None else until + 1]:
        if step.kind != StepKind.PLAY:
            continue
        for anim in step.animations:
            if anim.kind in (AnimationKind.APPLY_COMPLEX, AnimationKind.APPLY_POINTWISE):
                obj = scene.object_by_id(anim.target_id)
                found |= set(groups.leaves(scene, anim.target_id)) if groups.is_group(obj) else {anim.target_id}
    return found
