"""Limited 3D: 3D axes, surfaces z = f(x, y), 3D curves and the 3D camera.

The projection mirrors Manim's ``ThreeDCamera`` (rotation by ``theta`` and
``phi``, perspective with ``focal_distance`` 20), so the stage shows the same
picture as the rendered video.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.expression import Expression, ExpressionError, parse_expression
from manim_studio.model.geometry import param_float
from manim_studio.model.types import ObjectKind

THREE_D_KINDS = frozenset({ObjectKind.AXES_3D, ObjectKind.SURFACE, ObjectKind.CURVE_3D, ObjectKind.SOLID, ObjectKind.VECTOR_3D})
#: Shapes of a 3D solid.
SOLID_SHAPES = ("sphere", "cube", "prism", "cone", "cylinder", "torus", "tetrahedron", "octahedron", "icosahedron", "dodecahedron")
#: The Platonic solids among them (Manim's polyhedra, sized by their edge length).
POLYHEDRA = ("tetrahedron", "octahedron", "icosahedron", "dodecahedron")
#: Radius of their corner spheres (Manim's ``Dot3D`` default).
POLYHEDRON_VERTEX_RADIUS = 0.08
DEFAULT_PHI = 70.0
DEFAULT_THETA = -45.0
FOCAL_DISTANCE = 20.0

Point3 = tuple[float, float, float]


def is_3d(scene: Scene) -> bool:
    """Return ``True`` if the scene needs Manim's ``ThreeDScene``."""
    return any(obj.kind in THREE_D_KINDS for obj in scene.objects)


@dataclass(frozen=True)
class View:
    """Camera orientation in degrees (Manim's ``phi`` and ``theta``) and zoom."""

    phi: float = DEFAULT_PHI
    theta: float = DEFAULT_THETA
    zoom: float = 1.0


def _matrix(view: View) -> list[list[float]]:
    """``rotation_matrix(-phi, RIGHT) · rotation_about_z(-theta - 90°)``."""
    a = math.radians(-view.theta - 90.0)
    b = math.radians(-view.phi)
    rz = [[math.cos(a), -math.sin(a), 0.0], [math.sin(a), math.cos(a), 0.0], [0.0, 0.0, 1.0]]
    rx = [[1.0, 0.0, 0.0], [0.0, math.cos(b), -math.sin(b)], [0.0, math.sin(b), math.cos(b)]]
    return [[sum(rx[i][k] * rz[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def project(points: list[Point3], view: View) -> list[tuple[float, float]]:
    """Project 3D points onto the screen like Manim's ``ThreeDCamera.project_points``."""
    matrix = _matrix(view)
    result = []
    for x, y, z in points:
        px = matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z
        py = matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z
        pz = matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z
        denominator = FOCAL_DISTANCE - pz
        factor = FOCAL_DISTANCE / denominator if denominator > 0 else 1e6
        result.append((px * factor * view.zoom, py * factor * view.zoom))
    return result


# --- axes ----------------------------------------------------------------------------------


def axes_ranges(axes: SceneObject) -> dict[str, tuple[float, float, float]]:
    """``{"x": (min, max, length), ...}`` of 3D axes."""
    result = {}
    for axis, (low, high, length) in {"x": (-5.0, 5.0, 8.0), "y": (-5.0, 5.0, 8.0), "z": (-3.0, 3.0, 5.0)}.items():
        result[axis] = (
            param_float(axes.params, f"{axis}_min", low),
            param_float(axes.params, f"{axis}_max", high),
            param_float(axes.params, f"{axis}_length", length),
        )
    return result


def _origin_shift(low: float, high: float) -> float:
    if low > 0:
        return low
    if high < 0:
        return high
    return 0.0


def to_space(axes: SceneObject, x: float, y: float, z: float) -> Point3:
    """Axes coordinates → scene coordinates (like ``ThreeDAxes.c2p``, centered on the object)."""
    ranges = axes_ranges(axes)
    coordinates = {"x": x, "y": y, "z": z}
    values = []
    for axis in ("x", "y", "z"):
        low, high, length = ranges[axis]
        span = high - low or 1.0
        values.append((coordinates[axis] - (low + high) / 2) / span * length)
    return values[0] + axes.x, values[1] + axes.y, values[2]


def from_space(axes: SceneObject, point: Point3) -> Point3:
    """Scene coordinates → axes coordinates (the inverse of ``to_space``)."""
    ranges = axes_ranges(axes)
    shifted = (point[0] - axes.x, point[1] - axes.y, point[2])
    values = []
    for axis, value in zip(("x", "y", "z"), shifted):
        low, high, length = ranges[axis]
        values.append(value / (length or 1.0) * (high - low) + (low + high) / 2)
    return values[0], values[1], values[2]


def solid_axes_center(scene: Scene, obj: SceneObject, state=None) -> Point3 | None:
    """Where the center of a solid's bounding box is, in the coordinates of its axes."""
    placement = solid_placement(scene, obj, state)
    axes = axes_of(scene, obj)
    if placement is None or axes is None:
        return None
    return from_space(axes, _box_center(obj, *placement))


def axes_lines(axes: SceneObject) -> list[list[Point3]]:
    """Axis lines and tick marks in scene coordinates."""
    ranges = axes_ranges(axes)
    origin = {axis: _origin_shift(low, high) for axis, (low, high, _length) in ranges.items()}
    lines = []
    for axis in ("x", "y", "z"):
        low, high, _length = ranges[axis]
        start = dict(origin)
        end = dict(origin)
        start[axis], end[axis] = low, high
        lines.append([to_space(axes, start["x"], start["y"], start["z"]), to_space(axes, end["x"], end["y"], end["z"])])
        step = param_float(axes.params, f"{axis}_step", 1.0)
        if step > 0 and (high - low) / step <= 60:
            other = "y" if axis == "x" else "x"
            tick = 0.1 * (ranges[other][1] - ranges[other][0]) / max(ranges[other][2], 0.01)
            value = math.ceil(low / step) * step
            while value <= high + 1e-9:
                if abs(value - origin[axis]) > 1e-9:
                    a, b = dict(origin), dict(origin)
                    a[axis] = b[axis] = value
                    a[other] -= tick
                    b[other] += tick
                    lines.append([to_space(axes, a["x"], a["y"], a["z"]), to_space(axes, b["x"], b["y"], b["z"])])
                value += step
    return lines


def axis_tips(axes: SceneObject) -> list[tuple[Point3, Point3]]:
    """``(end, point just before the end)`` of the positive x, y and z axes."""
    ranges = axes_ranges(axes)
    origin = {axis: _origin_shift(low, high) for axis, (low, high, _length) in ranges.items()}
    tips = []
    for axis in ("x", "y", "z"):
        low, high, length = ranges[axis]
        back = 0.3 * (high - low) / max(length, 0.01)
        end, before = dict(origin), dict(origin)
        end[axis], before[axis] = high, high - back
        tips.append((to_space(axes, end["x"], end["y"], end["z"]), to_space(axes, before["x"], before["y"], before["z"])))
    return tips


def axes_of(scene: Scene, obj: SceneObject) -> SceneObject | None:
    """The 3D axes a surface or curve belongs to."""
    axes = scene.object_by_id(obj.params.get("axes_id"))
    return axes if axes is not None and axes.kind == ObjectKind.AXES_3D else None


# --- surfaces and curves -----------------------------------------------------------------------


def surface_expression(obj: SceneObject, parameters: tuple[str, ...] = ()) -> Expression | None:
    """``z = f(x, y)`` (``y`` is passed as an extra name)."""
    try:
        return parse_expression(str(obj.params.get("expression", "")), "x", ("y", *parameters))
    except ExpressionError:
        return None


def _value(expression: Expression, x: float, y: float, values: dict[str, float], second: str = "y") -> float:
    try:
        result = expression.evaluate(x, {**values, second: y})
    except (ArithmeticError, ValueError, OverflowError):
        return math.nan
    return result if math.isfinite(result) else math.nan


#: The three formulas of a parametric surface x(u, v), y(u, v), z(u, v).
SURFACE_UV_KEYS = ("x_uv", "y_uv", "z_uv")


def is_parametric_surface(obj: SceneObject) -> bool:
    return obj.kind == ObjectKind.SURFACE and obj.params.get("form") == "parametric"


def surface_uv_expressions(obj: SceneObject, parameters: tuple[str, ...] = ()) -> list[Expression] | None:
    """``x(u, v), y(u, v), z(u, v)`` of a parametric surface (``v`` is passed as an extra name)."""
    try:
        return [parse_expression(str(obj.params.get(key, "")), "u", ("v", *parameters)) for key in SURFACE_UV_KEYS]
    except ExpressionError:
        return None


def _uv_grid(scene: Scene, obj: SceneObject, axes: SceneObject, values: dict[str, float]) -> list[list[Point3]]:
    from manim_studio.model.graphs import parameter_symbols

    expressions = surface_uv_expressions(obj, parameter_symbols(scene))
    if expressions is None:
        return []
    u0, u1 = param_float(obj.params, "u_min", 0.0), param_float(obj.params, "u_max", math.tau)
    v0, v1 = param_float(obj.params, "v_min", 0.0), param_float(obj.params, "v_max", math.pi)
    steps = max(2, min(64, int(param_float(obj.params, "resolution", 16))))
    us = [u0 + (u1 - u0) * i / steps for i in range(steps + 1)]
    vs = [v0 + (v1 - v0) * j / steps for j in range(steps + 1)]

    def point(u: float, v: float) -> Point3:
        coordinates = [_value(expression, u, v, values, "v") for expression in expressions]
        return to_space(axes, *coordinates) if all(math.isfinite(c) for c in coordinates) else (math.nan, math.nan, math.nan)

    lines = [[point(u, v) for v in vs] for u in us] + [[point(u, v) for u in us] for v in vs]
    return [[p for p in line if math.isfinite(p[2])] for line in lines]


def surface_grid(scene: Scene, obj: SceneObject, values: dict[str, float] | None = None) -> list[list[Point3]]:
    """Grid lines of a surface in scene coordinates (rows and columns)."""
    from manim_studio.model.graphs import parameter_symbols, scene_values

    axes = axes_of(scene, obj)
    if axes is not None and is_parametric_surface(obj):
        return _uv_grid(scene, obj, axes, scene_values(scene, values))
    expression = surface_expression(obj, parameter_symbols(scene))
    if axes is None or expression is None:
        return []
    values = scene_values(scene, values)
    u0, u1 = param_float(obj.params, "x_min", -2.0), param_float(obj.params, "x_max", 2.0)
    v0, v1 = param_float(obj.params, "y_min", -2.0), param_float(obj.params, "y_max", 2.0)
    steps = max(2, min(64, int(param_float(obj.params, "resolution", 16))))
    us = [u0 + (u1 - u0) * i / steps for i in range(steps + 1)]
    vs = [v0 + (v1 - v0) * j / steps for j in range(steps + 1)]
    lines = []
    for u in us:
        lines.append([to_space(axes, u, v, _value(expression, u, v, values)) for v in vs])
    for v in vs:
        lines.append([to_space(axes, u, v, _value(expression, u, v, values)) for u in us])
    return [[point for point in line if math.isfinite(point[2])] for line in lines]


def surface_faces(scene: Scene, obj: SceneObject, values: dict[str, float] | None = None) -> list[Face]:
    """The faces of a surface like Manim's ``Surface`` builds them (for shading and painting from back to front)."""
    from manim_studio.model.graphs import parameter_symbols, scene_values

    axes = axes_of(scene, obj)
    if axes is None:
        return []
    values = scene_values(scene, values)
    steps = max(2, min(64, int(param_float(obj.params, "resolution", 16))))
    if is_parametric_surface(obj):
        expressions = surface_uv_expressions(obj, parameter_symbols(scene))
        if expressions is None:
            return []

        def function(u: float, v: float) -> Point3:
            return to_space(axes, *(_value(expression, u, v, values, "v") for expression in expressions))

        u_range = (param_float(obj.params, "u_min", 0.0), param_float(obj.params, "u_max", math.tau))
        v_range = (param_float(obj.params, "v_min", 0.0), param_float(obj.params, "v_max", math.pi))
    else:
        expression = surface_expression(obj, parameter_symbols(scene))
        if expression is None:
            return []

        def function(u: float, v: float) -> Point3:
            return to_space(axes, u, v, _value(expression, u, v, values))

        u_range = (param_float(obj.params, "x_min", -2.0), param_float(obj.params, "x_max", 2.0))
        v_range = (param_float(obj.params, "y_min", -2.0), param_float(obj.params, "y_max", 2.0))
    faces = _grid_faces(function, u_range, v_range, steps, steps)
    return [face for face in faces if all(math.isfinite(value) for point in face[1] for value in point)]


def curve_points(scene: Scene, obj: SceneObject, values: dict[str, float] | None = None) -> list[Point3]:
    """A 3D parametric curve ``(x(t), y(t), z(t))`` in scene coordinates."""
    from manim_studio.model.graphs import parameter_symbols, scene_values

    axes = axes_of(scene, obj)
    if axes is None:
        return []
    values = scene_values(scene, values)
    parameters = parameter_symbols(scene)
    try:
        functions = [parse_expression(str(obj.params.get(key, "")), "t", parameters) for key in ("x_expression", "y_expression", "z_expression")]
    except ExpressionError:
        return []
    t0, t1 = param_float(obj.params, "t_min", 0.0), param_float(obj.params, "t_max", 6.2832)
    points = []
    for index in range(301):
        t = t0 + (t1 - t0) * index / 300
        try:
            x, y, z = (function.evaluate(t, values) for function in functions)
        except (ArithmeticError, ValueError, OverflowError):
            continue
        if all(math.isfinite(value) for value in (x, y, z)):
            points.append(to_space(axes, x, y, z))
    return points


# --- camera ------------------------------------------------------------------------------------


def view_of(scene: Scene, states: dict | None = None) -> View:
    """Current 3D camera orientation (from the camera object and its animations)."""
    camera = next((obj for obj in scene.objects if obj.kind == ObjectKind.CAMERA), None)
    if camera is None:
        return View()
    state = (states or {}).get(camera.id)
    if state is not None:
        return View(state.phi, state.theta, 1.0)
    return View(param_float(camera.params, "phi", DEFAULT_PHI), param_float(camera.params, "theta", DEFAULT_THETA), 1.0)


# --- drawing order --------------------------------------------------------------------------------

#: Kinds whose parts Manim shades in 3D and sorts by depth (``ThreeDAxes`` cuts its axes into
#: shaded pieces); everything else, e.g. 3D curves and texts, is drawn above them.
SHADED_KINDS = frozenset({ObjectKind.AXES_3D, ObjectKind.SURFACE, ObjectKind.SOLID, ObjectKind.VECTOR_3D})


def depth_order(scene: Scene, view: View, values: dict[str, float] | None = None, states: dict | None = None) -> dict[str, int]:
    """Rank of each shaded 3D object from back to front, like ``ThreeDCamera.get_mobjects_to_display``.

    Manim sorts every face by its own depth; the stage sorts whole objects by their center.
    """
    row = _matrix(view)[2]
    depths = []
    for obj in scene.objects:
        if obj.kind not in SHADED_KINDS:
            continue
        if obj.kind == ObjectKind.AXES_3D:
            points = [(obj.x, obj.y, 0.0)]
        elif obj.kind == ObjectKind.SOLID:
            placement = solid_placement(scene, obj, (states or {}).get(obj.id))
            points = [placement[0]] if placement is not None else []
        elif obj.kind == ObjectKind.VECTOR_3D:
            points = vector_points(scene, obj)
        else:
            points = [point for line in surface_grid(scene, obj, values) for point in line]
        if not points:
            continue
        middle = [(min(p[i] for p in points) + max(p[i] for p in points)) / 2 for i in range(3)]
        depths.append((sum(row[i] * middle[i] for i in range(3)), obj.id))
    return {object_id: rank for rank, (_depth, object_id) in enumerate(sorted(depths, key=lambda item: item[0]))}


# --- solids --------------------------------------------------------------------------------------

Quad = list[Point3]


def solid_center(scene: Scene, obj: SceneObject) -> Point3 | None:
    """Center of a solid in scene coordinates (its position is given in axes coordinates)."""
    axes = axes_of(scene, obj)
    if axes is None:
        return None
    return to_space(axes, *(param_float(obj.params, key, 0.0) for key in ("center_x", "center_y", "center_z")))


def vector_points(scene: Scene, obj: SceneObject) -> list[Point3]:
    """Start and end of a 3D arrow or line, or the position of a 3D point (scene coordinates)."""
    axes = axes_of(scene, obj)
    if axes is None:
        return []
    end = to_space(axes, *(param_float(obj.params, key, default) for key, default in (("to_x", 2.0), ("to_y", 1.0), ("to_z", 2.0))))
    if obj.params.get("element", "arrow") == "point":
        return [end]
    start = to_space(axes, *(param_float(obj.params, key, 0.0) for key in ("from_x", "from_y", "from_z")))
    return [start, end]


#: A face: its corners and the Bézier points Manim stores for it (they decide the shading).
Face = tuple[Quad, list[Point3]]


def _mapped_points(function, corners: list[tuple[float, float]]) -> list[Point3]:
    """Bézier points of a face of ``Surface``: straight sides in (u, v) mapped like ``VMobject.apply_function``.

    Manim pulls the handles to a hundredth of their distance before mapping and stretches them
    back afterwards, so they point along the tangents of the mapped sides.
    """
    points: list[Point3] = []
    for index, a in enumerate(corners):
        b = corners[(index + 1) % len(corners)]
        fa, fb = function(*a), function(*b)
        near_a = function(a[0] + 0.01 * (b[0] - a[0]) / 3, a[1] + 0.01 * (b[1] - a[1]) / 3)
        near_b = function(b[0] + 0.01 * (a[0] - b[0]) / 3, b[1] + 0.01 * (a[1] - b[1]) / 3)
        h1 = tuple(fa[k] + 100 * (near_a[k] - fa[k]) for k in range(3))
        h2 = tuple(fb[k] + 100 * (near_b[k] - fb[k]) for k in range(3))
        points += [fa, h1, h2, fb]
    return points


def _grid_faces(function, u_range: tuple[float, float], v_range: tuple[float, float], nu: int, nv: int) -> list[Face]:
    """Faces of a ``Surface`` with corners in Manim's order (u1 v1, u2 v1, u2 v2, u1 v2)."""
    us = [u_range[0] + (u_range[1] - u_range[0]) * i / nu for i in range(nu + 1)]
    vs = [v_range[0] + (v_range[1] - v_range[0]) * j / nv for j in range(nv + 1)]
    faces = []
    for i in range(nu):
        for j in range(nv):
            uv = [(us[i], vs[j]), (us[i + 1], vs[j]), (us[i + 1], vs[j + 1]), (us[i], vs[j + 1])]
            faces.append(([function(*corner) for corner in uv], _mapped_points(function, uv)))
    return faces


def _grid_quads(function, u_range: tuple[float, float], v_range: tuple[float, float], nu: int, nv: int) -> list[Quad]:
    return [corners for corners, _points in _grid_faces(function, u_range, v_range, nu, nv)]


def _disc(radius: float, z: float, corners: int, shaded: bool = True) -> Face:
    """A filled circle (base of a cylinder or cone) as one face, counter-clockwise like ``Circle``.

    A face without points is not shaded (Manim's cone base has ``shade_in_3d=False``; the 3D
    camera draws such parts after all shaded ones).
    """
    ring = [(radius * math.cos(math.tau * k / corners), radius * math.sin(math.tau * k / corners), z) for k in range(corners)]
    return ring, face_points(ring) if shaded else []


def _box(width: float, depth: float, height: float) -> list[Quad]:
    """The faces of Manim's ``Cube``/``Prism`` with its corners in Manim's order (it decides the shading)."""
    x, y, z = width / 2, depth / 2, height / 2
    corners = {(sx, sy, sz): (sx * x, sy * y, sz * z) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)}
    faces = [
        [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1)],
        [(-1, 1, 1), (1, 1, 1), (1, -1, 1), (-1, -1, 1)],
        [(-1, 1, -1), (-1, 1, 1), (-1, -1, 1), (-1, -1, -1)],
        [(1, 1, 1), (1, 1, -1), (1, -1, -1), (1, -1, 1)],
        [(-1, 1, -1), (1, 1, -1), (1, 1, 1), (-1, 1, 1)],
        [(-1, -1, 1), (1, -1, 1), (1, -1, -1), (-1, -1, -1)],
    ]
    return [[corners[key] for key in face] for face in faces]


# --- light (Manim's ThreeDCamera shades every face of a 3D object) ------------------------------------

#: Where ``ThreeDCamera`` puts its light (``9 * DOWN + 7 * LEFT + 10 * OUT``); it does not move with the camera.
LIGHT_SOURCE: Point3 = (-7.0, -9.0, 10.0)


def _sub(a: Point3, b: Point3) -> Point3:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def _cross(a: Point3, b: Point3) -> Point3:
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def _unit_normal(v1: Point3, v2: Point3, tol: float = 1e-6) -> Point3:
    """Manim's ``get_unit_normal`` (with its answers for vectors that are zero or parallel)."""
    div1, div2 = max(abs(c) for c in v1), max(abs(c) for c in v2)
    if div1 == 0 and div2 == 0:
        return (0.0, -1.0, 0.0)
    if div1 == 0:
        u = tuple(c / div2 for c in v2)
    elif div2 == 0:
        u = tuple(c / div1 for c in v1)
    else:
        cp = _cross(tuple(c / div1 for c in v1), tuple(c / div2 for c in v2))
        length = math.sqrt(sum(c * c for c in cp))
        if length > tol:
            return tuple(c / length for c in cp)
        u = tuple(c / div1 for c in v1)
    if abs(u[0]) < tol and abs(u[1]) < tol:
        return (0.0, -1.0, 0.0)
    cp = (-u[0] * u[2], -u[1] * u[2], u[0] * u[0] + u[1] * u[1])
    length = math.sqrt(sum(c * c for c in cp))
    return tuple(c / length for c in cp)


def face_points(corners: Quad) -> list[Point3]:
    """The Bézier points Manim stores for a face with straight sides (handles at a third)."""
    points: list[Point3] = []
    for index, a in enumerate(corners):
        b = corners[(index + 1) % len(corners)]
        d = _sub(b, a)
        points += [a, (a[0] + d[0] / 3, a[1] + d[1] / 3, a[2] + d[2] / 3), (a[0] + 2 * d[0] / 3, a[1] + 2 * d[1] / 3, a[2] + 2 * d[2] / 3), b]
    return points


def _normal_at(points: list[Point3], i: int) -> Point3:
    count = len(points)
    im3 = i - 3 if i > 2 else count - 4
    ip3 = i + 3 if i < count - 3 else 3
    return _unit_normal(_sub(points[ip3], points[i]), _sub(points[im3], points[i]))


def _light(point: Point3, normal: Point3) -> float:
    """Manim's ``get_shaded_rgb``: how much is added to each color channel (negative: shadow)."""
    to_sun = _sub(LIGHT_SOURCE, point)
    length = math.sqrt(sum(c * c for c in to_sun)) or 1.0
    light = 0.5 * (sum(n * s for n, s in zip(normal, to_sun)) / length) ** 3
    return light * 0.5 if light < 0 else light


def face_shading(points: list[Point3]) -> tuple[Point3, Point3, float, float]:
    """Start and end of the face's color gradient and the light added there (``modified_rgbas``).

    ``points`` are the face's Bézier points (``face_points`` for straight sides).
    """
    end = ((len(points) - 1) // 6) * 3
    return points[0], points[end], _light(points[0], _normal_at(points, 0)), _light(points[end], _normal_at(points, end))


def _polyhedron(shape: str, edge: float) -> tuple[list[Point3], list[list[int]]]:
    """Vertices and faces exactly as in ``manim.mobject.three_d.polyhedra``."""
    if shape == "tetrahedron":
        u = edge * math.sqrt(2) / 4
        return [(u, u, u), (u, -u, -u), (-u, u, -u), (-u, -u, u)], [[0, 1, 2], [3, 0, 2], [0, 1, 3], [3, 1, 2]]
    if shape == "octahedron":
        u = edge * math.sqrt(2) / 2
        vertices = [(u, 0.0, 0.0), (-u, 0.0, 0.0), (0.0, u, 0.0), (0.0, -u, 0.0), (0.0, 0.0, u), (0.0, 0.0, -u)]
        return vertices, [[2, 4, 1], [0, 4, 2], [4, 3, 0], [1, 3, 4], [3, 5, 0], [1, 5, 3], [2, 5, 1], [0, 5, 2]]
    a = edge * (1 + math.sqrt(5)) / 4
    if shape == "icosahedron":
        b = edge / 2
        vertices = [(0.0, b, a), (0.0, -b, a), (0.0, b, -a), (0.0, -b, -a), (b, a, 0.0), (b, -a, 0.0), (-b, a, 0.0), (-b, -a, 0.0), (a, 0.0, b), (a, 0.0, -b), (-a, 0.0, b), (-a, 0.0, -b)]
        faces = [[1, 8, 0], [1, 5, 7], [8, 5, 1], [7, 3, 5], [5, 9, 3], [8, 9, 5], [3, 2, 9], [9, 4, 2], [8, 4, 9], [0, 4, 8], [6, 4, 0], [6, 2, 4]]
        faces += [[11, 2, 6], [3, 11, 2], [0, 6, 10], [10, 1, 0], [10, 7, 1], [11, 7, 3], [10, 11, 7], [10, 11, 6]]
        return vertices, faces
    b, c = edge * (3 + math.sqrt(5)) / 4, edge / 2
    vertices = [(sx * a, sy * a, sz * a) for sx in (1, -1) for sy in (1, -1) for sz in (1, -1)]
    vertices += [(0.0, c, b), (0.0, c, -b), (0.0, -c, -b), (0.0, -c, b), (c, b, 0.0), (-c, b, 0.0), (c, -b, 0.0), (-c, -b, 0.0)]
    vertices += [(b, 0.0, c), (-b, 0.0, c), (b, 0.0, -c), (-b, 0.0, -c)]
    faces = [[18, 16, 0, 12, 1], [3, 18, 16, 2, 14], [3, 10, 9, 1, 18], [1, 9, 5, 13, 12], [0, 8, 4, 13, 12], [2, 16, 0, 8, 11]]
    faces += [[4, 17, 6, 11, 8], [17, 19, 5, 13, 4], [19, 7, 15, 6, 17], [6, 15, 14, 2, 11], [19, 5, 9, 10, 7], [7, 10, 3, 14, 15]]
    return vertices, faces


def solid_vertices(scene: Scene, obj: SceneObject, state=None) -> list[Point3]:
    """The corners of a Platonic solid in scene coordinates (empty for other shapes)."""
    placement = solid_placement(scene, obj, state)
    shape = obj.params.get("shape", "sphere")
    if placement is None or shape not in POLYHEDRA:
        return []
    anchor, orientation = placement
    vertices, _faces = _polyhedron(shape, param_float(obj.params, "side", 2.0))
    return [tuple(anchor[i] + value for i, value in enumerate(_turn(orientation, vertex))) for vertex in vertices]  # type: ignore[misc]


def solid_quads(scene: Scene, obj: SceneObject, scale: float = 1.0) -> list[Quad]:
    """The faces of a solid in scene coordinates (like the Manim mobject after ``move_to``).

    A "quad" may also be a triangle or pentagon (faces of Platonic solids).
    """
    return [corners for corners, _points in solid_faces(scene, obj, scale)]


def solid_faces(scene: Scene, obj: SceneObject, scale: float = 1.0, state=None) -> list[Face]:
    """The faces of a solid with Manim's Bézier points, in scene coordinates (where ``state`` has moved and turned it)."""
    placement = solid_placement(scene, obj, state)
    if placement is None:
        return []
    anchor, orientation = placement

    def placed(points: list[Point3]) -> list[Point3]:
        return [tuple(anchor[i] + scale * value for i, value in enumerate(_turn(orientation, point))) for point in points]

    return [(placed(corners), placed(points)) for corners, points in local_solid_faces(obj)]


def local_solid_faces(obj: SceneObject) -> list[Face]:
    """The faces of a solid around the center of its bounding box (before it is placed)."""
    return list(_local_faces(obj.params.get("shape", "sphere"), repr(sorted((key, repr(value)) for key, value in obj.params.items()))))


@lru_cache(maxsize=64)
def _local_faces(shape: str, key: str) -> tuple[Face, ...]:
    import ast

    p = {name: ast.literal_eval(value) for name, value in ast.literal_eval(key)}
    shape = p.get("shape", "sphere")
    n = max(4, min(48, int(p.get("resolution", 16))))
    radius = param_float(p, "radius", 1.0)
    height = param_float(p, "height", 2.0)
    tau = 2 * math.pi
    if shape in POLYHEDRA:
        vertices, faces = _polyhedron(shape, param_float(p, "side", 2.0))
        polygons = [[vertices[index] for index in face] for face in faces]
        found = [(corners, face_points(corners)) for corners in polygons]
    elif shape == "cube":
        side = param_float(p, "side", 2.0)
        found = [(corners, face_points(corners)) for corners in _box(side, side, side)]
    elif shape == "prism":
        found = [(corners, face_points(corners)) for corners in _box(param_float(p, "width", 3.0), param_float(p, "depth", 2.0), param_float(p, "height", 1.0))]
    elif shape == "cylinder":
        found = _grid_faces(lambda u, v: (radius * math.cos(v), radius * math.sin(v), u), (-height / 2, height / 2), (0.0, tau), 2, 2 * n)
        found += [_disc(radius, z, 2 * n) for z in (-height / 2, height / 2)]
    elif shape == "cone":
        # apex on top, base at the bottom; centered like move_to() does with the bounding box
        found = _grid_faces(lambda u, v: (u * radius * math.cos(v), u * radius * math.sin(v), height / 2 - u * height), (0.0, 1.0), (0.0, tau), n, 2 * n)
        found.append(_disc(radius, -height / 2, 2 * n, shaded=False))
    elif shape == "torus":
        minor = param_float(p, "minor_radius", 0.3)
        found = _grid_faces(
            lambda u, v: ((radius - minor * math.cos(v)) * math.cos(u), (radius - minor * math.cos(v)) * math.sin(u), -minor * math.sin(v)),
            (0.0, tau),
            (0.0, tau),
            2 * n,
            n,
        )
    else:
        found = _grid_faces(lambda u, v: (radius * math.cos(u) * math.sin(v), radius * math.sin(u) * math.sin(v), -radius * math.cos(v)), (0.0, tau), (0.0, math.pi), 2 * n, n)
    return tuple(found)


# --- moving and turning solids (like Manim's move_to and Rotate) ---------------------------------

Matrix3 = tuple[float, float, float, float, float, float, float, float, float]
IDENTITY3: Matrix3 = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
#: Axes a solid can turn about (Manim's ``RIGHT``, ``UP``, ``OUT``).
TURN_AXES = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}


def _turn(matrix: Matrix3, point: Point3) -> Point3:
    x, y, z = point
    return (matrix[0] * x + matrix[1] * y + matrix[2] * z, matrix[3] * x + matrix[4] * y + matrix[5] * z, matrix[6] * x + matrix[7] * y + matrix[8] * z)


def _product(a: Matrix3, b: Matrix3) -> Matrix3:
    return tuple(sum(a[3 * row + k] * b[3 * k + column] for k in range(3)) for row in range(3) for column in range(3))  # type: ignore[return-value]


def rotation(axis: str, degrees: float) -> Matrix3:
    """Turning by ``degrees`` about an axis through the origin (right-hand rule, like ``rotation_matrix``)."""
    ux, uy, uz = TURN_AXES.get(axis, TURN_AXES["z"])
    angle = math.radians(degrees)
    c, s, t = math.cos(angle), math.sin(angle), 1 - math.cos(angle)
    return (
        t * ux * ux + c, t * ux * uy - s * uz, t * ux * uz + s * uy,
        t * ux * uy + s * uz, t * uy * uy + c, t * uy * uz - s * ux,
        t * ux * uz - s * uy, t * uy * uz + s * ux, t * uz * uz + c,
    )  # fmt: skip


def solid_placement(scene: Scene, obj: SceneObject, state=None) -> tuple[Point3, Matrix3] | None:
    """``(anchor, orientation)``: the solid's points are ``anchor + orientation · local point``."""
    if state is not None and getattr(state, "orientation", ()):
        return tuple(state.anchor3d), tuple(state.orientation)  # type: ignore[return-value]
    center = solid_center(scene, obj)
    return (center, IDENTITY3) if center is not None else None


def _box_center(obj: SceneObject, anchor: Point3, orientation: Matrix3) -> Point3:
    """Center of the bounding box of all of the solid's points (Manim's ``get_center``)."""
    points = [_turn(orientation, point) for _corners, face in local_solid_faces(obj) for point in face]
    if not points:
        return anchor
    return tuple(anchor[i] + (min(p[i] for p in points) + max(p[i] for p in points)) / 2 for i in range(3))  # type: ignore[return-value]


def moved_solid(scene: Scene, obj: SceneObject, state, target: Point3, progress: float = 1.0) -> tuple[Point3, Matrix3] | None:
    """``move_to``: the center of the bounding box goes (``progress`` of the way) to ``target`` (axes coordinates)."""
    placement = solid_placement(scene, obj, state)
    axes = axes_of(scene, obj)
    if placement is None or axes is None:
        return None
    anchor, orientation = placement
    center = _box_center(obj, anchor, orientation)
    goal = to_space(axes, *target)
    return tuple(anchor[i] + (goal[i] - center[i]) * progress for i in range(3)), orientation  # type: ignore[return-value]


def turned_solid(scene: Scene, obj: SceneObject, state, axis: str, degrees: float) -> tuple[Point3, Matrix3] | None:
    """``Rotate(solid, angle, axis)``: turning about the center of its bounding box."""
    placement = solid_placement(scene, obj, state)
    if placement is None:
        return None
    anchor, orientation = placement
    center = _box_center(obj, anchor, orientation)
    turn = rotation(axis, degrees)
    offset = _turn(turn, tuple(anchor[i] - center[i] for i in range(3)))  # type: ignore[arg-type]
    return tuple(center[i] + offset[i] for i in range(3)), _product(turn, orientation)  # type: ignore[return-value]
