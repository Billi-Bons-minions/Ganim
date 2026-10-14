"""Curves through points: Manim's ``set_points_smoothly`` and ``set_points_as_corners``.

A polygon can be *smooth* (a cubic spline through its points, C² like Manim's
``get_smooth_cubic_bezier_handle_points``) and *open* (no edge back to the start).
The handles solve Manim's equations exactly:

* open:   ``2·H₀ + H₁ = A₀ + 2A₁``, ``H_{i-1} + 4·H_i + H_{i+1} = 4A_i + 2A_{i+1}``,
  ``2·H_{N-2} + 7·H_{N-1} = 8A_{N-1} + A_N``; second handles ``2A_{i+1} − H_{i+1}``
  and ``(A_N + H_{N-1}) / 2`` for the last curve;
* closed: ``H_{i-1} + 4·H_i + H_{i+1} = 4A_i + 2A_{i+1}`` around the loop; second handles
  ``2A_{i+1} − H_{i+1}``.
"""

from __future__ import annotations

from manim_studio.model.entities import SceneObject
from manim_studio.model.geometry import Point

#: A cubic Bézier curve: start, first handle, second handle, end.
Cubic = tuple[Point, Point, Point, Point]


def is_smooth(obj: SceneObject) -> bool:
    return bool(obj.params.get("smooth", False))


def is_open(obj: SceneObject) -> bool:
    return not bool(obj.params.get("closed", True))


def _solve(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Gaussian elimination with pivoting (the systems have a handful of rows)."""
    size = len(rhs)
    rows = [row[:] + [value] for row, value in zip(matrix, rhs)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(rows[row][column]))
        rows[column], rows[pivot] = rows[pivot], rows[column]
        for row in range(column + 1, size):
            factor = rows[row][column] / rows[column][column]
            if factor:
                for k in range(column, size + 1):
                    rows[row][k] -= factor * rows[column][k]
    result = [0.0] * size
    for row in range(size - 1, -1, -1):
        result[row] = (rows[row][size] - sum(rows[row][k] * result[k] for k in range(row + 1, size))) / rows[row][row]
    return result


def smooth_handles(anchors: list[Point], closed: bool) -> list[tuple[Point, Point]]:
    """First and second handle of every curve of Manim's smooth spline through ``anchors``.

    For a closed curve the anchors do not repeat the start; there is a curve back to it.
    """
    loop = anchors + [anchors[0]] if closed else anchors
    count = len(loop) - 1
    if count < 1:
        return []
    if count == 1:
        (x0, y0), (x1, y1) = loop
        return [((x0 + (x1 - x0) / 3, y0 + (y1 - y0) / 3), (x0 + 2 * (x1 - x0) / 3, y0 + 2 * (y1 - y0) / 3))]
    matrix = [[0.0] * count for _ in range(count)]
    for i in range(count):
        matrix[i][i] = 4.0
        if closed:
            matrix[i][(i - 1) % count] += 1.0
            matrix[i][(i + 1) % count] += 1.0
        else:
            if i > 0:
                matrix[i][i - 1] = 1.0
            if i < count - 1:
                matrix[i][i + 1] = 1.0
    if not closed:
        matrix[0][0] = 2.0
        matrix[count - 1][count - 1] = 7.0
        matrix[count - 1][count - 2] = 2.0
    first: list[list[float]] = []
    for axis in (0, 1):
        a = [point[axis] for point in loop]
        rhs = [4 * a[i] + 2 * a[i + 1] for i in range(count)]
        if not closed:
            rhs[0] = a[0] + 2 * a[1]
            rhs[count - 1] = 8 * a[count - 1] + a[count]
        first.append(_solve(matrix, rhs))
    h1 = [(first[0][i], first[1][i]) for i in range(count)]
    h2 = []
    for i in range(count):
        if i < count - 1 or closed:
            nxt = h1[(i + 1) % count]
            h2.append((2 * loop[i + 1][0] - nxt[0], 2 * loop[i + 1][1] - nxt[1]))
        else:
            h2.append((0.5 * loop[count][0] + 0.5 * h1[i][0], 0.5 * loop[count][1] + 0.5 * h1[i][1]))
    return list(zip(h1, h2))


def curve_cubics(points: list[Point], smooth: bool, closed: bool) -> list[Cubic]:
    """The Bézier curves of a polygon or curve through ``points`` (corners: straight curves)."""
    if len(points) < 2:
        return []
    loop = points + [points[0]] if closed else points
    if not smooth:
        cubics = []
        for (x0, y0), (x1, y1) in zip(loop, loop[1:]):
            cubics.append(((x0, y0), (x0 + (x1 - x0) / 3, y0 + (y1 - y0) / 3), (x0 + 2 * (x1 - x0) / 3, y0 + 2 * (y1 - y0) / 3), (x1, y1)))
        return cubics
    return [(loop[i], h1, h2, loop[i + 1]) for i, (h1, h2) in enumerate(smooth_handles(points, closed))]


def sample_cubics(cubics: list[Cubic], per_curve: int = 24) -> list[Point]:
    """Points along the curves (for paths and dashes)."""
    if not cubics:
        return []
    result = [cubics[0][0]]
    for p0, p1, p2, p3 in cubics:
        for step in range(1, per_curve + 1):
            t = step / per_curve
            u = 1 - t
            result.append(
                (
                    u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                    u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1],
                )
            )
    return result


def anchor_center(points: list[Point]) -> Point:
    """The middle of the box around the points (Manim's VMobject measures its anchors, not the handles)."""
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
