"""Compute what the scene looks like after a given timeline step."""

from __future__ import annotations

from dataclasses import dataclass, replace

from manim_studio.model.entities import Animation, Scene, SceneObject
from manim_studio.model.geometry import graph_anchor, is_bound_graph
from manim_studio.model.types import (
    ENTRANCE_ANIMATIONS,
    EXIT_ANIMATIONS,
    RETURNING_RATE_FUNCTIONS,
    AnimationKind,
    StepKind,
    Visibility,
)

START = -1


@dataclass(frozen=True)
class ObjectState:
    """Appearance of one object at a point in the timeline.

    ``shape_id`` names the object whose geometry is displayed; it differs from
    ``object_id`` after a ``Transform``.
    """

    object_id: str
    shape_id: str
    visible: bool
    x: float
    y: float
    rotation: float
    scale: float
    stroke_color: str
    fill_color: str
    opacity: float = 1.0
    draw: float = 1.0
    fill: float = 1.0
    morph_to: str | None = None
    morph_t: float = 0.0
    outline: float = 0.0
    outline_color: str = "#F7D96F"


def first_reference(scene: Scene, object_id: str) -> tuple[Animation, bool] | None:
    """Return the first animation using an object and whether it is the main target."""
    for step in scene.steps:
        if step.kind != StepKind.PLAY:
            continue
        for anim in step.animations:
            if anim.target_id == object_id:
                return anim, True
            if anim.params.get("target") == object_id:
                return anim, False
    return None


def visible_at_start(scene: Scene, obj: SceneObject) -> bool:
    """Decide whether an object is added before the first step.

    In automatic mode an object starts hidden if it is introduced by an
    entrance animation or first used as the target of a transform.
    """
    if obj.visibility == Visibility.SHOWN:
        return True
    if obj.visibility == Visibility.HIDDEN:
        return False
    reference = first_reference(scene, obj.id)
    if reference is None:
        return True
    anim, is_main_target = reference
    if not is_main_target:
        return False
    return anim.kind not in ENTRANCE_ANIMATIONS


def initial_state(scene: Scene, obj: SceneObject) -> ObjectState:
    """Return the state of an object before the first step."""
    x, y = graph_anchor(scene, obj) if is_bound_graph(scene, obj) else (obj.x, obj.y)
    rotation = 0.0 if is_bound_graph(scene, obj) else obj.rotation
    return ObjectState(
        object_id=obj.id,
        shape_id=obj.id,
        visible=visible_at_start(scene, obj),
        x=x,
        y=y,
        rotation=rotation,
        scale=1.0,
        stroke_color=obj.stroke_color,
        fill_color=obj.fill_color,
    )


def _apply_color(state: ObjectState, anim: Animation) -> ObjectState:
    color = str(anim.params.get("color", state.stroke_color))
    apply_to = anim.params.get("apply_to", "both")
    stroke = color if apply_to in ("both", "stroke") else state.stroke_color
    fill = color if apply_to in ("both", "fill") else state.fill_color
    return replace(state, stroke_color=stroke, fill_color=fill, visible=True)


def _apply_modifier(state: ObjectState, anim: Animation) -> ObjectState:
    params = anim.params
    if anim.kind == AnimationKind.MOVE:
        return replace(state, x=float(params.get("x", state.x)), y=float(params.get("y", state.y)), visible=True)
    if anim.kind == AnimationKind.SCALE:
        return replace(state, scale=state.scale * float(params.get("factor", 1.0)), visible=True)
    if anim.kind == AnimationKind.ROTATE:
        return replace(state, rotation=state.rotation + float(params.get("angle", 0.0)), visible=True)
    return _apply_color(state, anim)


def apply_animation(states: dict[str, ObjectState], anim: Animation) -> None:
    """Update ``states`` in place with the end result of one animation."""
    current = states.get(anim.target_id)
    if current is None:
        return
    returns = anim.rate_func in RETURNING_RATE_FUNCTIONS
    kind = anim.kind
    if kind in ENTRANCE_ANIMATIONS:
        states[anim.target_id] = replace(current, visible=not returns)
    elif kind in EXIT_ANIMATIONS:
        states[anim.target_id] = replace(current, visible=False)
    elif kind == AnimationKind.TRANSFORM:
        target = states.get(str(anim.params.get("target")))
        if target is not None and not returns:
            states[anim.target_id] = replace(target, object_id=anim.target_id, visible=True)
    elif kind == AnimationKind.REPLACEMENT_TRANSFORM:
        target_id = str(anim.params.get("target"))
        if target_id in states and not returns:
            states[anim.target_id] = replace(current, visible=False)
            states[target_id] = replace(states[target_id], visible=True)
    elif kind == AnimationKind.INDICATE:
        states[anim.target_id] = replace(current, visible=True)
    elif kind == AnimationKind.CIRCUMSCRIBE:
        return
    elif not returns:
        states[anim.target_id] = _apply_modifier(current, anim)
    else:
        states[anim.target_id] = replace(current, visible=True)


def states_after(scene: Scene, step_index: int) -> dict[str, ObjectState]:
    """Return the state of every object after ``step_index`` (``START`` = before step 1)."""
    states = {obj.id: initial_state(scene, obj) for obj in scene.objects}
    last = min(step_index, len(scene.steps) - 1)
    for step in scene.steps[: last + 1]:
        if step.kind != StepKind.PLAY:
            continue
        for anim in step.animations:
            apply_animation(states, anim)
    return states


def state_before_step(scene: Scene, step_index: int) -> dict[str, ObjectState]:
    """Return the state right before ``step_index`` is played."""
    return states_after(scene, step_index - 1)
