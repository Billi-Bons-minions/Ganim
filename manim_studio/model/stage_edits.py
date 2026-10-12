"""Rules for editing objects depending on the timeline position.

At the start of the timeline, edits change the initial values of objects.
When an animation step is selected, edits are *recorded*: the step's Move,
Scale, Rotate or Change-Color animation of the object is updated – or created
if it does not exist yet, like keyframing in presentation software.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from manim_studio.model import operations as ops
from manim_studio.model.entities import STEP_SEQUENCE, Animation, Scene
from manim_studio.model.factory import create_animation
from manim_studio.model.graphs import is_bound
from manim_studio.model.schema import animation_allowed
from manim_studio.model.state import START, states_after
from manim_studio.model.types import TRANSFORM_ANIMATIONS, AnimationKind, StepKind, simultaneous_conflicts

MOVE = "move"
SCALE = "scale"
ROTATE = "rotate"
COLOR = "color"
VALUE = "value"

KIND_FOR_ACTION = {
    MOVE: AnimationKind.MOVE,
    SCALE: AnimationKind.SCALE,
    ROTATE: AnimationKind.ROTATE,
    COLOR: AnimationKind.CHANGE_COLOR,
    VALUE: AnimationKind.SET_VALUE,
}

Mutation = Callable[[Scene], None]


@dataclass(frozen=True)
class EditCheck:
    """Whether an edit is possible; ``reason`` and ``object_id`` explain a refusal."""

    allowed: bool
    reason: str = ""
    object_id: str | None = None


def is_recording(scene: Scene, cursor: int) -> bool:
    """Return ``True`` if edits at ``cursor`` become animations."""
    return 0 <= cursor < len(scene.steps) and scene.steps[cursor].kind == StepKind.PLAY


def step_animation(scene: Scene, cursor: int, object_id: str, action: str) -> Animation | None:
    """Return the animation in the selected step that an action edits."""
    if not is_recording(scene, cursor):
        return None
    wanted = KIND_FOR_ACTION[action]
    for anim in scene.steps[cursor].animations:
        if anim.kind == wanted and anim.target_id == object_id:
            return anim
    return None


def check_edit(scene: Scene, cursor: int, object_ids: Iterable[str], action: str) -> EditCheck:
    """Decide whether the objects may be edited at ``cursor``."""
    ids = list(object_ids)
    if not ids:
        return EditCheck(False, "nothing_selected")
    for object_id in ids:
        obj = scene.object_by_id(object_id)
        if obj is not None and is_bound(scene, obj):
            return EditCheck(False, "bound_graph", object_id)
    if 0 <= cursor < len(scene.steps) and scene.steps[cursor].kind == StepKind.WAIT:
        return EditCheck(False, "wait_step")
    if 0 <= cursor < len(scene.steps) and scene.steps[cursor].kind == StepKind.CODE:
        return EditCheck(False, "code_step")
    if is_recording(scene, cursor):
        transformed = {anim.target_id for anim in scene.steps[cursor].animations if anim.kind in TRANSFORM_ANIMATIONS}
        for object_id in ids:
            if object_id in transformed:
                return EditCheck(False, "transform_conflict", object_id)
            obj = scene.object_by_id(object_id)
            if obj is not None and not animation_allowed(KIND_FOR_ACTION[action], obj.kind, obj.params):
                return EditCheck(False, "not_animatable", object_id)
        step = scene.steps[cursor]
        if step.mode != STEP_SEQUENCE:
            planned = [create_animation(KIND_FOR_ACTION[action], object_id) for object_id in ids if step_animation(scene, cursor, object_id, action) is None]
            new_conflicts = simultaneous_conflicts([*step.animations, *planned]) - simultaneous_conflicts(step.animations)
            if new_conflicts:
                return EditCheck(False, "animation_conflict", sorted(new_conflicts)[0])
    return EditCheck(True)


def would_create(scene: Scene, cursor: int, object_ids: Iterable[str], action: str) -> list[str]:
    """Return the objects for which an edit would create a new animation."""
    if not is_recording(scene, cursor):
        return []
    return [object_id for object_id in object_ids if step_animation(scene, cursor, object_id, action) is None]


def _recorded_run_time(scene: Scene, cursor: int) -> float:
    duration = scene.steps[cursor].duration()
    return duration if duration > 0 else 1.0


def ensure_animation(scene: Scene, cursor: int, object_id: str, action: str, **defaults: object) -> Animation:
    """Return the step's animation for ``action``, creating it with ``defaults`` if needed."""
    anim = step_animation(scene, cursor, object_id, action)
    if anim is not None:
        return anim
    anim = create_animation(KIND_FOR_ACTION[action], object_id, run_time=_recorded_run_time(scene, cursor), **defaults)
    ops.add_animation(scene, scene.steps[cursor].id, anim)
    return anim


def move_edit(cursor: int, object_ids: list[str], dx: float, dy: float) -> Mutation:
    """Move objects at the start, or record/adjust Move animations in a step."""

    def apply(scene: Scene) -> None:
        if cursor == START:
            ops.translate_objects(scene, object_ids, dx, dy)
            return
        states = states_after(scene, cursor)
        for object_id in object_ids:
            anim = step_animation(scene, cursor, object_id, MOVE)
            if anim is None:
                state = states[object_id]
                ensure_animation(scene, cursor, object_id, MOVE, x=round(state.x + dx, 6), y=round(state.y + dy, 6))
            else:
                anim.params["x"] = round(float(anim.params.get("x", 0.0)) + dx, 6)
                anim.params["y"] = round(float(anim.params.get("y", 0.0)) + dy, 6)

    return apply


def move_each_edit(cursor: int, deltas: dict[str, tuple[float, float]]) -> Mutation:
    """Move every object by its own delta (align and distribute)."""
    moves = [move_edit(cursor, [object_id], dx, dy) for object_id, (dx, dy) in deltas.items() if dx or dy]

    def apply(scene: Scene) -> None:
        for move in moves:
            move(scene)

    return apply


def scale_edit(cursor: int, object_id: str, factor: float) -> Mutation:
    """Scale an object at the start, or record/adjust a Scale animation."""

    def apply(scene: Scene) -> None:
        if cursor == START:
            ops.scale_object(scene, object_id, factor)
            return
        anim = step_animation(scene, cursor, object_id, SCALE)
        if anim is None:
            ensure_animation(scene, cursor, object_id, SCALE, factor=round(factor, 4))
        else:
            anim.params["factor"] = round(max(0.01, float(anim.params.get("factor", 1.0)) * factor), 4)

    return apply


def rotate_edit(cursor: int, object_id: str, delta: float) -> Mutation:
    """Rotate an object at the start, or record/adjust a Rotate animation."""

    def apply(scene: Scene) -> None:
        if cursor == START:
            ops.rotate_object(scene, object_id, delta)
            return
        anim = step_animation(scene, cursor, object_id, ROTATE)
        if anim is None:
            ensure_animation(scene, cursor, object_id, ROTATE, angle=round(delta, 4))
        else:
            anim.params["angle"] = round(float(anim.params.get("angle", 0.0)) + delta, 4)

    return apply


def set_move_target(cursor: int, object_id: str, x: float, y: float) -> Mutation:
    """Set the target position of the step's Move animation (created if needed)."""

    def apply(scene: Scene) -> None:
        anim = ensure_animation(scene, cursor, object_id, MOVE, x=x, y=y)
        anim.params["x"], anim.params["y"] = round(x, 6), round(y, 6)

    return apply


def set_scale_factor(cursor: int, object_id: str, factor: float) -> Mutation:
    """Set the factor of the step's Scale animation (created if needed)."""

    def apply(scene: Scene) -> None:
        ensure_animation(scene, cursor, object_id, SCALE).params["factor"] = round(max(0.01, factor), 4)

    return apply


def set_rotation_angle(cursor: int, object_id: str, angle: float) -> Mutation:
    """Set the angle of the step's Rotate animation (created if needed)."""

    def apply(scene: Scene) -> None:
        ensure_animation(scene, cursor, object_id, ROTATE).params["angle"] = round(angle, 4)

    return apply


def value_edit(cursor: int, object_id: str, value: float) -> Mutation:
    """Set a parameter's (or number's) start value, or record a "change value" animation."""

    def apply(scene: Scene) -> None:
        if cursor == START:
            ops.set_object_param(scene, object_id, "value", round(value, 6))
            return
        anim = ensure_animation(scene, cursor, object_id, VALUE, value=round(value, 6))
        anim.params["value"] = round(value, 6)

    return apply


def color_edit(cursor: int, object_ids: list[str], field: str, color: str) -> Mutation:
    """Change a color at the start, or record a Change-Color animation in a step.

    ``field`` is ``stroke_color`` or ``fill_color``.
    """
    apply_to = "stroke" if field == "stroke_color" else "fill"

    def apply(scene: Scene) -> None:
        for object_id in object_ids:
            if cursor == START:
                ops.update_object(scene, object_id, **{field: color})
                continue
            anim = ensure_animation(scene, cursor, object_id, COLOR, color=color, apply_to=apply_to)
            previous = anim.params.get("apply_to", apply_to)
            anim.params["color"] = color
            anim.params["apply_to"] = previous if previous == apply_to else "both"

    return apply
