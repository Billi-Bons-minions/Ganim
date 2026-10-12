"""Boolean shapes: Manim's ``Union``, ``Intersection``, ``Difference`` and ``Exclusion``.

A boolean shape combines two closed shapes (circles, polygons, stars ... or another
boolean shape) and follows them: the generated script rebuilds it in every frame with
``always_redraw``. The stage computes the exact outline with Qt; this module (no Qt)
knows which shapes may be combined, where the parts of a boolean shape are at any
moment (``placements``) and where its result lies (the center its item is drawn at).

The outlines here are polygons (circles with ``CIRCLE_SAMPLES`` corners). The result's
bounding box is found exactly for these polygons: the outline of the result consists
of pieces of the shapes' outlines between their crossings, and a piece belongs to it
when the result is filled on one side of it but not on the other.
"""

from __future__ import annotations

import math

from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.geometry import Point, param_float
from manim_studio.model.types import ObjectKind

UNION = "union"
INTERSECTION = "intersection"
DIFFERENCE = "difference"
EXCLUSION = "exclusion"
OPERATIONS = (UNION, INTERSECTION, DIFFERENCE, EXCLUSION)
#: Manim class of each operation.
MANIM_CLASSES = {UNION: "Union", INTERSECTION: "Intersection", DIFFERENCE: "Difference", EXCLUSION: "Exclusion"}
#: Parameters that name the two shapes.
OPERAND_KEYS = ("first_shape", "second_shape")

#: Closed shapes that Manim builds from their own points (a ``VGroup`` such as a text has none).
OPERAND_KINDS = frozenset(
    {
        ObjectKind.CIRCLE,
        ObjectKind.SQUARE,
        ObjectKind.RECTANGLE,
        ObjectKind.TRIANGLE,
        ObjectKind.ELLIPSE,
        ObjectKind.POLYGON,
        ObjectKind.REGULAR_POLYGON,
        ObjectKind.STAR,
        ObjectKind.SECTOR,
        ObjectKind.ANNULUS,
        ObjectKind.BOOLEAN_SHAPE,
    }
)

CIRCLE_SAMPLES = 64
#: Distance to both sides of an outline piece at which the result is tested.
_EPSILON = 1e-6

#: Where a basic shape is: ``(object_id, shape_id, x, y, rotation, scale, matrix)``.
Placement = tuple[str, str, float, float, float, float, tuple[float, float, float, float]]


def is_boolean(obj: SceneObject | None) -> bool:
    return obj is not None and obj.kind == ObjectKind.BOOLEAN_SHAPE


def operation(obj: SceneObject) -> str:
    value = str(obj.params.get("operation", UNION))
    return value if value in OPERATIONS else UNION


def operands(scene: Scene, obj: SceneObject) -> tuple[SceneObject, SceneObject] | None:
    """The two shapes of a boolean shape (``None`` if one is missing, unsuitable or part of a cycle)."""
    found = [scene.object_by_id(obj.params.get(key)) for key in OPERAND_KEYS]
    if any(shape is None or shape.kind not in OPERAND_KINDS or shape.id == obj.id for shape in found):
        return None
    if found[0].id == found[1].id or obj.id in _descendants(scene, obj, set()):
        return None
    return found[0], found[1]


def _descendants(scene: Scene, obj: SceneObject, seen: set[str]) -> set[str]:
    """Ids of all shapes a boolean shape is built from, at any depth."""
    for key in OPERAND_KEYS:
        child = scene.object_by_id(obj.params.get(key))
        if child is None or child.id in seen:
            continue
        seen.add(child.id)
        if is_boolean(child):
            _descendants(scene, child, seen)
    return seen


def can_use(scene: Scene, boolean_id: str, candidate: SceneObject) -> bool:
    """``True`` if ``candidate`` may become a shape of the boolean shape (no cycle)."""
    if candidate.kind not in OPERAND_KINDS or candidate.id == boolean_id:
        return False
    return not is_boolean(candidate) or boolean_id not in _descendants(scene, candidate, set())


def leaves(scene: Scene, obj: SceneObject) -> list[SceneObject]:
    """The basic shapes a boolean shape is made of (each once)."""
    result: list[SceneObject] = []
    pair = operands(scene, obj)
    for shape in pair or ():
        for leaf in leaves(scene, shape) if is_boolean(shape) else [shape]:
            if all(leaf.id != known.id for known in result):
                result.append(leaf)
    return result


def dependent_booleans(scene: Scene, object_ids: set[str]) -> set[str]:
    """Boolean shapes that use one of the objects (directly or through other boolean shapes)."""
    found: set[str] = set()
    changed = True
    while changed:
        changed = False
        for obj in scene.objects:
            if is_boolean(obj) and obj.id not in found and any(obj.params.get(key) in object_ids | found for key in OPERAND_KEYS):
                found.add(obj.id)
                changed = True
    return found


# --- outlines ----------------------------------------------------------------------------


def _ring(radius_x: float, radius_y: float, samples: int = CIRCLE_SAMPLES) -> list[Point]:
    return [(radius_x * math.cos(2 * math.pi * k / samples), radius_y * math.sin(2 * math.pi * k / samples)) for k in range(samples)]


def _regular(n: int, radius: float, start: float) -> list[Point]:
    return [(radius * math.cos(math.radians(start + 360 * k / n)), radius * math.sin(math.radians(start + 360 * k / n))) for k in range(n)]


def local_contours(obj: SceneObject) -> list[list[Point]]:
    """Closed outlines of a basic shape around the center of its bounding box (Manim units)."""
    p = obj.params
    kind = obj.kind
    if kind == ObjectKind.CIRCLE:
        r = param_float(p, "radius", 1.0)
        contours = [_ring(r, r)]
    elif kind == ObjectKind.ELLIPSE:
        contours = [_ring(param_float(p, "width", 3.0) / 2, param_float(p, "height", 1.5) / 2)]
    elif kind == ObjectKind.ANNULUS:
        outer, inner = param_float(p, "outer_radius", 1.3), param_float(p, "inner_radius", 0.7)
        contours = [_ring(outer, outer), _ring(inner, inner)]
    elif kind in (ObjectKind.SQUARE, ObjectKind.RECTANGLE):
        w = param_float(p, "side_length", 2.0) if kind == ObjectKind.SQUARE else param_float(p, "width", 4.0)
        h = w if kind == ObjectKind.SQUARE else param_float(p, "height", 2.0)
        contours = [[(w / 2, h / 2), (-w / 2, h / 2), (-w / 2, -h / 2), (w / 2, -h / 2)]]
    elif kind == ObjectKind.TRIANGLE:
        contours = [_regular(3, param_float(p, "radius", 1.0), 90.0)]
    elif kind == ObjectKind.REGULAR_POLYGON:
        n = max(3, int(p.get("n", 6)))
        contours = [_regular(n, param_float(p, "radius", 1.0), 90.0 if n % 2 else 0.0)]  # Manim: 90° for odd n, else 0°
    elif kind == ObjectKind.STAR:
        n = max(3, int(p.get("n", 5)))
        outer, inner = param_float(p, "outer_radius", 1.2), param_float(p, "inner_radius", 0.5)
        contours = [[point for k in range(n) for point in (_regular(1, outer, 90 + 360 * k / n)[0], _regular(1, inner, 90 + 360 * k / n + 180 / n)[0])]]
    elif kind == ObjectKind.POLYGON:
        contours = [[(float(x), float(y)) for x, y in p.get("points", [])]]
    elif kind == ObjectKind.SECTOR:
        r, start, angle = param_float(p, "radius", 1.5), param_float(p, "start_angle", 0.0), param_float(p, "angle", 90.0)
        samples = max(2, round(abs(angle) / 360 * CIRCLE_SAMPLES))
        arc = [(r * math.cos(math.radians(start + angle * k / samples)), r * math.sin(math.radians(start + angle * k / samples))) for k in range(samples + 1)]
        contours = [[(0.0, 0.0)] + arc]
    else:
        return []
    contours = [contour for contour in contours if len(contour) >= 3]
    points = [point for contour in contours for point in contour]
    if not points:
        return []
    cx = (min(x for x, _ in points) + max(x for x, _ in points)) / 2
    cy = (min(y for _, y in points) + max(y for _, y in points)) / 2
    return [[(x - cx, y - cy) for x, y in contour] for contour in contours]


def place(points: list[Point], placement: Placement) -> list[Point]:
    """Points of a shape in the scene: ``center + R · M · (scale · point)`` like the stage draws it."""
    _object_id, _shape_id, x, y, rotation, scale, (m11, m12, m21, m22) = placement
    cos, sin = math.cos(math.radians(rotation)), math.sin(math.radians(rotation))
    result = []
    for px, py in points:
        mx, my = scale * (m11 * px + m12 * py), scale * (m21 * px + m22 * py)
        result.append((x + cos * mx - sin * my, y + sin * mx + cos * my))
    return result


def placements(scene: Scene, obj: SceneObject, states: dict) -> tuple[Placement, ...]:
    """Where the basic shapes of a boolean shape are in ``states`` (empty if one is missing)."""
    found = []
    for leaf in leaves(scene, obj):
        state = states.get(leaf.id)
        if state is None:
            return ()
        found.append((leaf.id, state.shape_id, state.x, state.y, state.rotation, state.scale, tuple(state.matrix)))
    return tuple(found)


# --- the result ------------------------------------------------------------------------------


def _inside(contours: list[list[Point]], x: float, y: float) -> bool:
    """Even-odd rule over all outlines (a ring's hole is outside)."""
    inside = False
    for contour in contours:
        j = len(contour) - 1
        for i in range(len(contour)):
            xi, yi = contour[i]
            xj, yj = contour[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
            j = i
    return inside


def _combine(op: str, a: bool, b: bool) -> bool:
    if op == UNION:
        return a or b
    if op == INTERSECTION:
        return a and b
    if op == DIFFERENCE:
        return a and not b
    return a != b


class _Tree:
    """A boolean shape with its parts placed in the scene."""

    def __init__(self, scene: Scene, obj: SceneObject, where: dict[str, Placement]) -> None:
        self.op = operation(obj)
        self.children: list[_Tree | list[list[Point]]] = []
        for shape in operands(scene, obj) or ():
            if is_boolean(shape):
                self.children.append(_Tree(scene, shape, where))
            else:
                placement = where[shape.id]
                geometry = scene.object_by_id(placement[1]) or shape
                self.children.append([place(contour, placement) for contour in local_contours(geometry)])

    def contains(self, x: float, y: float) -> bool:
        a, b = (child.contains(x, y) if isinstance(child, _Tree) else _inside(child, x, y) for child in self.children)
        return _combine(self.op, a, b)

    def contours(self) -> list[list[Point]]:
        result: list[list[Point]] = []
        for child in self.children:
            result += child.contours() if isinstance(child, _Tree) else child
        return result


def _crossings(a: Point, b: Point, segments: list[tuple[Point, Point]]) -> list[float]:
    """Parameters ``t`` in (0, 1) where the segment a→b crosses one of ``segments``."""
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    low_x, high_x, low_y, high_y = min(ax, b[0]), max(ax, b[0]), min(ay, b[1]), max(ay, b[1])
    found = []
    for (cx, cy), (ex, ey) in segments:
        if max(cx, ex) < low_x or min(cx, ex) > high_x or max(cy, ey) < low_y or min(cy, ey) > high_y:
            continue
        fx, fy = ex - cx, ey - cy
        denominator = dx * fy - dy * fx
        if abs(denominator) < 1e-15:
            continue
        t = ((cx - ax) * fy - (cy - ay) * fx) / denominator
        u = ((cx - ax) * dy - (cy - ay) * dx) / denominator
        if 1e-12 < t < 1 - 1e-12 and -1e-12 <= u <= 1 + 1e-12:
            found.append(t)
    return found


def _result_bounds(tree: _Tree) -> tuple[float, float, float, float] | None:
    contours = tree.contours()
    edges = [(contour[i], contour[(i + 1) % len(contour)]) for contour in contours for i in range(len(contour))]
    left = bottom = math.inf
    right = top = -math.inf
    for a, b in edges:
        length = math.dist(a, b)
        if length < 1e-12:
            continue
        nx, ny = (a[1] - b[1]) / length * _EPSILON, (b[0] - a[0]) / length * _EPSILON
        cuts = [0.0] + sorted(_crossings(a, b, edges)) + [1.0]
        for start, end in zip(cuts, cuts[1:]):
            middle = (start + end) / 2
            mx, my = a[0] + (b[0] - a[0]) * middle, a[1] + (b[1] - a[1]) * middle
            if tree.contains(mx + nx, my + ny) == tree.contains(mx - nx, my - ny):
                continue  # filled (or empty) on both sides: not part of the result's outline
            for t in (start, end):
                x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                left, right, bottom, top = min(left, x), max(right, x), min(bottom, y), max(top, y)
    if not math.isfinite(left):
        return None
    return left, bottom, right, top


def result_bounds(scene: Scene, obj: SceneObject, where: tuple[Placement, ...]) -> tuple[float, float, float, float] | None:
    """``(left, bottom, right, top)`` of the result (``None`` if it is empty)."""
    if not where or operands(scene, obj) is None:
        return None
    shapes = tuple(_shape_key(scene.object_by_id(placement[1])) for placement in where)
    key = (_structure(scene, obj), where, shapes)
    cached = _BOUNDS_CACHE.get(key)
    if cached is None:
        cached = (_result_bounds(_Tree(scene, obj, {placement[0]: placement for placement in where})),)
        if len(_BOUNDS_CACHE) > 512:
            _BOUNDS_CACHE.clear()
        _BOUNDS_CACHE[key] = cached
    return cached[0]


_BOUNDS_CACHE: dict[tuple, tuple] = {}


def _structure(scene: Scene, obj: SceneObject) -> tuple:
    """The operations and shapes of a boolean shape (as a cache key)."""
    parts: list = [operation(obj)]
    for shape in operands(scene, obj) or ():
        parts.append(_structure(scene, shape) if is_boolean(shape) else shape.id)
    return tuple(parts)


def _shape_key(shape: SceneObject | None) -> tuple:
    if shape is None:
        return ()
    return shape.kind.value, repr(sorted((key, repr(value)) for key, value in shape.params.items()))


def result_center(scene: Scene, obj: SceneObject, states: dict) -> Point | None:
    """Center of the result's bounding box (``None`` if it is empty)."""
    bounds = result_bounds(scene, obj, placements(scene, obj, states))
    if bounds is None:
        return None
    left, bottom, right, top = bounds
    return (left + right) / 2, (bottom + top) / 2


def start_bounds(scene: Scene, obj: SceneObject) -> tuple[float, float, float, float] | None:
    """Bounding box of the result before the first step."""
    from manim_studio.model.state import initial_state, refresh_attached_states

    states = refresh_attached_states(scene, {other.id: initial_state(scene, other) for other in scene.objects})
    return result_bounds(scene, obj, placements(scene, obj, states))
