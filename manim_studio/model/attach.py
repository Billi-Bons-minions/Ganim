"""Objects that are coupled to something else (Manim updaters).

* **follow**: the object keeps its distance to another object and moves with it
  (``m.move_to(target.get_center() + offset)``), e.g. a label next to a moving dot.
* **formula**: the position is computed from parameters (``ValueTracker``),
  e.g. ``x = 2 cos(w)``, ``y = 2 sin(w)`` moves a dot on a circle when ``w`` changes.
* **between** (lines and arrows): the line runs from the center of one object to the
  center of another (``always_redraw(lambda: Line(a.get_center(), b.get_center()))``),
  e.g. the sides of a triangle whose corners are dots that move.

The settings live in the object's ``params`` (``attach``, ``attach_target``,
``attach_x``, ``attach_y``) because they apply to many object kinds.
"""

from __future__ import annotations

import math
from typing import Callable

from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.expression import Expression
from manim_studio.model.schema import ParamSpec, ParamType
from manim_studio.model.types import ObjectKind

ATTACH_NONE = "none"
ATTACH_FOLLOW = "follow"
ATTACH_FORMULA = "formula"
ATTACH_BETWEEN = "between"
ATTACH_MODES = (ATTACH_NONE, ATTACH_FOLLOW, ATTACH_FORMULA, ATTACH_BETWEEN)
#: Line-like objects that can run between two objects.
CONNECTABLE_KINDS = frozenset({ObjectKind.LINE, ObjectKind.ARROW, ObjectKind.DOUBLE_ARROW, ObjectKind.DASHED_LINE})

#: Placeholder variable of position formulas (they only use parameters).
FORMULA_VARIABLE = "x"

#: Objects that can be coupled: they have a free position of their own.
ATTACHABLE_KINDS = frozenset(
    {
        ObjectKind.CIRCLE,
        ObjectKind.SQUARE,
        ObjectKind.RECTANGLE,
        ObjectKind.TRIANGLE,
        ObjectKind.ELLIPSE,
        ObjectKind.LINE,
        ObjectKind.ARROW,
        ObjectKind.DOT,
        ObjectKind.TEXT,
        ObjectKind.MATH_TEX,
        ObjectKind.TEX,
        ObjectKind.MARKUP_TEXT,
        ObjectKind.IMAGE,
        ObjectKind.VECTOR,
        ObjectKind.DOUBLE_ARROW,
        ObjectKind.DASHED_LINE,
        ObjectKind.POLYGON,
        ObjectKind.REGULAR_POLYGON,
        ObjectKind.STAR,
        ObjectKind.ARC,
        ObjectKind.SECTOR,
        ObjectKind.ANNULUS,
        ObjectKind.DECIMAL_NUMBER,
        ObjectKind.TABLE,
        ObjectKind.MATRIX,
        ObjectKind.CODE,
        ObjectKind.BULLET_LIST,
        ObjectKind.NETWORK,
        ObjectKind.CAMERA,  # 2D only: the camera follows an object
    }
)

#: Objects another object can follow (their position is a real, moving center).
FOLLOWABLE_KINDS = (ATTACHABLE_KINDS - {ObjectKind.CAMERA}) | {ObjectKind.NUMBER_PLANE, ObjectKind.AXES, ObjectKind.NUMBER_LINE}

ATTACH_SPECS: tuple[ParamSpec, ...] = (
    ParamSpec("attach", ParamType.CHOICE, ATTACH_NONE, choices=ATTACH_MODES),
    ParamSpec("attach_target", ParamType.OBJECT_REF, None, ref_kinds=tuple(sorted(FOLLOWABLE_KINDS, key=lambda kind: kind.value)), visible_when=("attach", (ATTACH_FOLLOW,))),
    ParamSpec("attach_x", ParamType.EXPRESSION, "0", visible_when=("attach", (ATTACH_FORMULA,))),
    ParamSpec("attach_y", ParamType.EXPRESSION, "0", visible_when=("attach", (ATTACH_FORMULA,))),
    ParamSpec("attach_start", ParamType.OBJECT_REF, None, ref_kinds=tuple(sorted(FOLLOWABLE_KINDS, key=lambda kind: kind.value)), visible_when=("attach", (ATTACH_BETWEEN,))),
    ParamSpec("attach_end", ParamType.OBJECT_REF, None, ref_kinds=tuple(sorted(FOLLOWABLE_KINDS, key=lambda kind: kind.value)), visible_when=("attach", (ATTACH_BETWEEN,))),
)


def attach_specs(kind: ObjectKind) -> tuple[ParamSpec, ...]:
    """The coupling settings of a kind: only lines and arrows can run between two objects."""
    if kind in CONNECTABLE_KINDS:
        return ATTACH_SPECS
    first = ATTACH_SPECS[0]
    modes = ParamSpec(first.key, first.type, first.default, choices=(ATTACH_NONE, ATTACH_FOLLOW, ATTACH_FORMULA))
    return (modes,) + tuple(spec for spec in ATTACH_SPECS[1:] if spec.key not in ("attach_start", "attach_end"))


def attach_mode(obj: SceneObject | None) -> str:
    """``none``, ``follow`` or ``formula`` (only for objects that can be coupled)."""
    if obj is None or obj.kind not in ATTACHABLE_KINDS:
        return ATTACH_NONE
    mode = str(obj.params.get("attach", ATTACH_NONE))
    if mode == ATTACH_BETWEEN and obj.kind not in CONNECTABLE_KINDS:
        return ATTACH_NONE
    return mode if mode in ATTACH_MODES else ATTACH_NONE


def connection_targets(scene: Scene, obj: SceneObject) -> tuple[SceneObject, SceneObject] | None:
    """The two objects a line runs between (``None`` if one is missing or unsuitable).

    The ends may follow or have formulas, but not run between objects themselves (no chains).
    """
    if attach_mode(obj) != ATTACH_BETWEEN:
        return None
    ends = [scene.object_by_id(obj.params.get(key)) for key in ("attach_start", "attach_end")]
    if any(end is None or end.id == obj.id or end.kind not in FOLLOWABLE_KINDS or attach_mode(end) == ATTACH_BETWEEN for end in ends):
        return None
    if ends[0].id == ends[1].id:
        return None
    return ends[0], ends[1]


def connection_geometry(start: tuple[float, float], end: tuple[float, float]) -> tuple[float, float, float, float]:
    """``(x, y, rotation, length)`` of a line from ``start`` to ``end`` (its middle, its angle in degrees)."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    return (start[0] + end[0]) / 2, (start[1] + end[1]) / 2, math.degrees(math.atan2(dy, dx)), math.hypot(dx, dy)


def is_attached(obj: SceneObject | None) -> bool:
    return attach_mode(obj) != ATTACH_NONE


def follow_target(scene: Scene, obj: SceneObject) -> SceneObject | None:
    """The object that ``obj`` follows (``None`` if missing, unsuitable or circular)."""
    if attach_mode(obj) != ATTACH_FOLLOW:
        return None
    target = scene.object_by_id(obj.params.get("attach_target"))
    if target is None or target.id == obj.id or target.kind not in FOLLOWABLE_KINDS or follows_circularly(scene, obj):
        return None
    return target


def follows_circularly(scene: Scene, obj: SceneObject) -> bool:
    """``True`` if following the chain of targets leads back to ``obj``."""
    seen = {obj.id}
    current = obj
    while attach_mode(current) == ATTACH_FOLLOW:
        current = scene.object_by_id(current.params.get("attach_target"))
        if current is None:
            return False
        if current.id in seen:
            return True
        seen.add(current.id)
    return False


def can_follow(scene: Scene, follower_id: str, candidate: SceneObject) -> bool:
    """Whether ``candidate`` may become the target of ``follower_id`` (no cycles)."""
    if candidate.id == follower_id or candidate.kind not in FOLLOWABLE_KINDS:
        return False
    current: SceneObject | None = candidate
    while current is not None and attach_mode(current) == ATTACH_FOLLOW:
        if current.params.get("attach_target") == follower_id:
            return False
        current = scene.object_by_id(current.params.get("attach_target"))
    return True


def follow_offset(scene: Scene, obj: SceneObject, target: SceneObject) -> tuple[float, float]:
    """The distance to the target, as placed at the start of the scene."""
    tx, ty = _start_position(scene, target)
    return round(obj.x - tx, 6), round(obj.y - ty, 6)


def _start_position(scene: Scene, obj: SceneObject, depth: int = 0) -> tuple[float, float]:
    """Where an object is at the start (coupled ones included)."""
    if attach_mode(obj) == ATTACH_FORMULA:
        from manim_studio.model.graphs import initial_values

        return formula_position(scene, obj, initial_values(scene)) or (obj.x, obj.y)
    target = follow_target(scene, obj) if depth < 50 else None
    if target is None:
        return obj.x, obj.y
    tx, ty = _start_position(scene, target, depth + 1)
    dx, dy = follow_offset(scene, obj, target)
    return tx + dx, ty + dy


def position_formulas(scene: Scene, obj: SceneObject) -> tuple[Expression, Expression] | None:
    """The parsed ``x``/``y`` formulas (``None`` if one of them is invalid); they may use graph values like ``f(a)``."""
    from manim_studio.model.graphs import parse_formula

    try:
        return tuple(parse_formula(scene, str(obj.params.get(key, ""))) for key in ("attach_x", "attach_y"))  # type: ignore[return-value]
    except Exception:  # noqa: BLE001 - any parse problem means "no position"
        return None


def formula_error(scene: Scene, obj: SceneObject) -> str | None:
    """A readable reason why a position formula cannot be used (or ``None``)."""
    from manim_studio.model.graphs import formula_error as check_formula

    for key in ("attach_x", "attach_y"):
        error = check_formula(scene, str(obj.params.get(key, "")))
        if error is not None:
            return error.code + (f": {error.detail}" if error.detail else "")
    return None


def formula_position(scene: Scene, obj: SceneObject, values: dict[str, float]) -> tuple[float, float] | None:
    formulas = position_formulas(scene, obj)
    if formulas is None:
        return None
    try:
        x, y = (formula.evaluate(0.0, values) for formula in formulas)
    except (ArithmeticError, ValueError):
        return None
    return x, y


def set_attach_mode(scene: Scene, object_id: str, mode: str) -> None:
    """Switch the coupling of an object, with useful starting values.

    Following picks the nearest suitable object if none is chosen yet; a formula
    starts with the object's current position, so nothing jumps.
    """
    obj = scene.object_by_id(object_id)
    if obj is None or mode not in ATTACH_MODES:
        return
    obj.params["attach"] = mode
    if mode == ATTACH_FOLLOW and not (scene.object_by_id(obj.params.get("attach_target")) and can_follow(scene, object_id, scene.object_by_id(obj.params.get("attach_target")))):
        candidates = [other for other in scene.objects if can_follow(scene, object_id, other)]
        if obj.kind == ObjectKind.CAMERA:
            # a camera rather follows something that moves than the coordinate grid
            moving = [other for other in candidates if other.kind not in (ObjectKind.NUMBER_PLANE, ObjectKind.AXES, ObjectKind.NUMBER_LINE)]
            candidates = moving or candidates
        nearest = min(candidates, key=lambda other: (other.x - obj.x) ** 2 + (other.y - obj.y) ** 2, default=None)
        obj.params["attach_target"] = nearest.id if nearest is not None else None
    target = scene.object_by_id(obj.params.get("attach_target"))
    if mode == ATTACH_FOLLOW and obj.kind == ObjectKind.CAMERA and target is not None:
        # a following camera keeps its target in the middle of the picture
        obj.x, obj.y = _start_position(scene, target)
    if mode == ATTACH_BETWEEN and connection_targets(scene, obj) is None:
        # the objects nearest to the two ends of the line
        half = float(obj.params.get("length", 3.0)) / 2
        angle = math.radians(obj.rotation)
        ends = [(obj.x - half * math.cos(angle), obj.y - half * math.sin(angle)), (obj.x + half * math.cos(angle), obj.y + half * math.sin(angle))]
        candidates = [other for other in scene.objects if other.id != obj.id and other.kind in FOLLOWABLE_KINDS and attach_mode(other) != ATTACH_BETWEEN]
        chosen: list[str] = []
        for key, (ex, ey) in zip(("attach_start", "attach_end"), ends):
            free = [other for other in candidates if other.id not in chosen]
            nearest = min(free, key=lambda other: (other.x - ex) ** 2 + (other.y - ey) ** 2, default=None)
            obj.params[key] = nearest.id if nearest is not None else None
            if nearest is not None:
                chosen.append(nearest.id)
    if mode == ATTACH_FORMULA and not obj.params.get("attach_x") and not obj.params.get("attach_y"):
        obj.params["attach_x"] = f"{round(obj.x, 4):g}"
        obj.params["attach_y"] = f"{round(obj.y, 4):g}"


def attached_positions(scene: Scene, position_of: Callable[[str], tuple[float, float] | None], values: dict[str, float]) -> dict[str, tuple[float, float]]:
    """Where every coupled object is, given the current positions of the others.

    Followers of followers are resolved in order; circular chains are left alone.
    """
    result: dict[str, tuple[float, float]] = {}
    pending = [obj for obj in scene.objects if is_attached(obj)]

    def current(object_id: str) -> tuple[float, float] | None:
        return result.get(object_id) or position_of(object_id)

    for _round in range(len(pending) + 1):
        remaining = []
        for obj in pending:
            if attach_mode(obj) == ATTACH_BETWEEN:
                continue  # placed after the others (``refresh_attached_states``)
            if attach_mode(obj) == ATTACH_FORMULA:
                position = formula_position(scene, obj, values)
                if position is not None:
                    result[obj.id] = position
                continue
            target = follow_target(scene, obj)
            if target is None:
                continue
            if is_attached(target) and target.id not in result and any(other.id == target.id for other in pending):
                remaining.append(obj)
                continue
            base = current(target.id)
            if base is not None:
                dx, dy = follow_offset(scene, obj, target)
                result[obj.id] = (base[0] + dx, base[1] + dy)
        if not remaining or len(remaining) == len(pending):
            break
        pending = remaining
    return result
