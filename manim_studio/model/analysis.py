"""Numerical curve analysis: zeros, extrema, inflection points and intersections.

Derivatives are exact (symbolic, see :mod:`manim_studio.model.calculus`);
roots are found by sampling for sign changes and refining with bisection.
Points where a function jumps (poles such as ``1/x``) are not reported.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from manim_studio.model.calculus import derivative, difference
from manim_studio.model.expression import Expression

SAMPLES = 1200
TOLERANCE = 1e-10
MERGE_DISTANCE = 1e-6
TOUCH_LIMIT = 1e-7

FEATURE_ZEROS = "zeros"
FEATURE_EXTREMA = "extrema"
FEATURE_INFLECTION = "inflection"
FEATURE_INTERSECTIONS = "intersections"
FEATURES = (FEATURE_ZEROS, FEATURE_EXTREMA, FEATURE_INFLECTION, FEATURE_INTERSECTIONS)

KIND_ZERO = "zero"
KIND_MAXIMUM = "maximum"
KIND_MINIMUM = "minimum"
KIND_INFLECTION = "inflection"
KIND_INTERSECTION = "intersection"


@dataclass(frozen=True)
class SpecialPoint:
    """A notable point of a curve."""

    x: float
    y: float
    kind: str


def safe(function: Callable[[float], float]) -> Callable[[float], float]:
    """Wrap a function so that undefined values become ``nan``."""

    def wrapped(x: float) -> float:
        try:
            value = float(function(x))
        except (ArithmeticError, ValueError):
            return math.nan
        return value if math.isfinite(value) else math.nan

    return wrapped


def _bisect(f: Callable[[float], float], a: float, b: float, fa: float) -> float:
    for _ in range(200):
        middle = (a + b) / 2
        fm = f(middle)
        if math.isnan(fm):
            return middle
        if fm == 0 or (b - a) / 2 < TOLERANCE:
            return middle
        if (fm > 0) == (fa > 0):
            a, fa = middle, fm
        else:
            b = middle
    return (a + b) / 2


def _golden_minimum(f: Callable[[float], float], a: float, b: float) -> float:
    ratio = (math.sqrt(5) - 1) / 2
    c, d = b - ratio * (b - a), a + ratio * (b - a)
    for _ in range(120):
        if abs(f(c)) < abs(f(d)):
            b = d
        else:
            a = c
        c, d = b - ratio * (b - a), a + ratio * (b - a)
    return (a + b) / 2


def find_roots(function: Callable[[float], float], low: float, high: float, samples: int = SAMPLES) -> list[float]:
    """Return the zeros of ``function`` in ``[low, high]`` (sign changes and touching zeros)."""
    if not (math.isfinite(low) and math.isfinite(high)) or high <= low:
        return []
    f = safe(function)
    xs = [low + (high - low) * index / samples for index in range(samples + 1)]
    ys = [f(x) for x in xs]
    roots: list[float] = []
    scale = max((abs(y) for y in ys if not math.isnan(y)), default=1.0) or 1.0
    for index in range(samples):
        x0, x1, y0, y1 = xs[index], xs[index + 1], ys[index], ys[index + 1]
        if math.isnan(y0) or math.isnan(y1):
            continue
        if y0 == 0:
            roots.append(x0)
        elif (y0 > 0) != (y1 > 0) and y1 != 0:
            root = _bisect(f, x0, x1, y0)
            value = f(root)
            if not math.isnan(value) and abs(value) <= 1e-6 * max(1.0, scale):
                roots.append(root)
    if not math.isnan(ys[-1]) and ys[-1] == 0:
        roots.append(xs[-1])
    for index in range(1, samples):
        y_prev, y, y_next = ys[index - 1], ys[index], ys[index + 1]
        if any(math.isnan(v) for v in (y_prev, y, y_next)) or y == 0:
            continue
        if abs(y) <= abs(y_prev) and abs(y) <= abs(y_next) and (y > 0) == (y_prev > 0) == (y_next > 0):
            candidate = _golden_minimum(f, xs[index - 1], xs[index + 1])
            value = f(candidate)
            if not math.isnan(value) and abs(value) < TOUCH_LIMIT * max(1.0, scale):
                roots.append(candidate)
    return _merge(sorted(roots))


def _merge(values: list[float]) -> list[float]:
    merged: list[float] = []
    for value in values:
        if not merged or abs(value - merged[-1]) > max(MERGE_DISTANCE, 1e-9 * abs(value)):
            merged.append(value)
    return merged


def _clean(value: float) -> float:
    rounded = round(value, 9)
    return 0.0 if rounded == 0 else rounded


def changes_sign(function: Callable[[float], float], x: float, width: float) -> int:
    """Return +1/-1 for an increasing/decreasing sign change at ``x``, 0 otherwise."""
    f = safe(function)
    for step in (width, width / 10, width / 100):
        left, right = f(x - step), f(x + step)
        if math.isnan(left) or math.isnan(right):
            continue
        if left < 0 < right:
            return 1
        if left > 0 > right:
            return -1
    return 0


def zeros(expression: Expression, low: float, high: float, values: dict[str, float] | None = None) -> list[SpecialPoint]:
    """Zeros of ``f``."""
    f = lambda x: expression.evaluate(x, values)  # noqa: E731
    return [SpecialPoint(_clean(x), 0.0, KIND_ZERO) for x in find_roots(f, low, high)]


def extrema(expression: Expression, low: float, high: float, values: dict[str, float] | None = None) -> list[SpecialPoint]:
    """Local maxima and minima (zeros of ``f'`` with a sign change)."""
    first = derivative(expression)
    f = safe(lambda x: expression.evaluate(x, values))
    df = lambda x: first.evaluate(x, values)  # noqa: E731
    width = (high - low) / SAMPLES
    points = []
    for x in find_roots(df, low, high):
        change = changes_sign(df, x, width)
        y = f(x)
        if change == 0 or math.isnan(y):
            continue
        points.append(SpecialPoint(_clean(x), _clean(y), KIND_MINIMUM if change > 0 else KIND_MAXIMUM))
    return points


def inflection_points(expression: Expression, low: float, high: float, values: dict[str, float] | None = None) -> list[SpecialPoint]:
    """Inflection points (zeros of ``f''`` with a sign change)."""
    second = derivative(expression, 2)
    f = safe(lambda x: expression.evaluate(x, values))
    d2f = lambda x: second.evaluate(x, values)  # noqa: E731
    width = (high - low) / SAMPLES
    points = []
    for x in find_roots(d2f, low, high):
        y = f(x)
        if changes_sign(d2f, x, width) != 0 and not math.isnan(y):
            points.append(SpecialPoint(_clean(x), _clean(y), KIND_INFLECTION))
    return points


def intersections(
    first: Expression, second: Expression, low: float, high: float, values: dict[str, float] | None = None
) -> list[SpecialPoint]:
    """Points where two graphs meet."""
    gap = difference(first, second)
    f = safe(lambda x: first.evaluate(x, values))
    points = []
    for x in find_roots(lambda x: gap.evaluate(x, values), low, high):
        y = f(x)
        if not math.isnan(y):
            points.append(SpecialPoint(_clean(x), _clean(y), KIND_INTERSECTION))
    return points
