"""Rules for editing objects on the stage depending on the timeline position.

At the start of the timeline, dragging changes the initial values of objects.
When a step is selected, dragging changes the target values of that step's
Move/Scale/Rotate animation of the object; without such an animation the
object is locked in that step.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from manim_studio.model import operations as ops
from manim_studio.model.entities import Animation, Scene
from manim_studio.model.geometry import is_bound_graph
from manim_studio.model.state import START
from manim_studio.model.types import AnimationKind, StepKind

MOVE = "move"
SCALE = "scale"
ROTATE = "rotate"

_KIND_FOR_ACTION = {MOVE: AnimationKind.MOVE, SCALE: AnimationKind.SCALE, ROTATE: AnimationKind.ROTATE}


@dataclass(frozen=True)
class EditCheck:
    """Whether an edit is possible; ``reason`` and ``object_id`` explain a refusal."""

    allowed: bool
    reason: str = ""
    object_id: str | None = None


def step_animation(scene: Scene, cursor: int, object_id: str, action: str) -> Animation | None:
    """Return the animation in the selected step that an action would edit."""
    if not 0 <= cursor < len(scene.steps):
        return None
    step = scene.steps[cursor]
    if step.kind != StepKind.PLAY:
        return None
    wanted = _KIND_FOR_ACTION[action]
    for anim in step.animations:
        if anim.kind == wanted and anim.target_id == object_id:
            return anim
    return None


def check_edit(scene: Scene, cursor: int, object_ids: Iterable[str], action: str) -> EditCheck:
    """Decide whether the objects may be moved/scaled/rotated at ``cursor``."""
    ids = list(object_ids)
    if not ids:
        return EditCheck(False, "nothing_selected")
    if cursor == START:
        for object_id in ids:
            obj = scene.object_by_id(object_id)
            if obj is not None and is_bound_graph(scene, obj):
                return EditCheck(False, "bound_graph", object_id)
        return EditCheck(True)
    if 0 <= cursor < len(scene.steps) and scene.steps[cursor].kind == StepKind.WAIT:
        return EditCheck(False, "wait_step")
    for object_id in ids:
        if step_animation(scene, cursor, object_id, action) is None:
            return EditCheck(False, f"needs_{action}", object_id)
    return EditCheck(True)


def move_edit(cursor: int, object_ids: list[str], dx: float, dy: float) -> Callable[[Scene], None]:
    """Return a scene mutation that moves objects or their Move targets."""

    def apply(scene: Scene) -> None:
        if cursor == START:
            ops.translate_objects(scene, object_ids, dx, dy)
            return
        for object_id in object_ids:
            anim = step_animation(scene, cursor, object_id, MOVE)
            if anim is not None:
                anim.params["x"] = round(float(anim.params.get("x", 0.0)) + dx, 6)
                anim.params["y"] = round(float(anim.params.get("y", 0.0)) + dy, 6)

    return apply


def scale_edit(cursor: int, object_id: str, factor: float) -> Callable[[Scene], None]:
    """Return a scene mutation that scales an object or its Scale factor."""

    def apply(scene: Scene) -> None:
        if cursor == START:
            ops.scale_object(scene, object_id, factor)
            return
        anim = step_animation(scene, cursor, object_id, SCALE)
        if anim is not None:
            anim.params["factor"] = round(max(0.01, float(anim.params.get("factor", 1.0)) * factor), 4)

    return apply


def rotate_edit(cursor: int, object_id: str, delta: float) -> Callable[[Scene], None]:
    """Return a scene mutation that rotates an object or changes its Rotate angle."""

    def apply(scene: Scene) -> None:
        if cursor == START:
            ops.rotate_object(scene, object_id, delta)
            return
        anim = step_animation(scene, cursor, object_id, ROTATE)
        if anim is not None:
            anim.params["angle"] = round(float(anim.params.get("angle", 0.0)) + delta, 4)

    return apply
