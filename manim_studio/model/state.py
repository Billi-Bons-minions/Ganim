"""Compute what the scene looks like after a given timeline step."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from manim_studio.model import groups
from manim_studio.model.entities import Animation, Scene, SceneObject
from manim_studio.model.extents import base_size, rotated_extent
from manim_studio.model.graphs import bound_anchor, is_bound
from manim_studio.model.types import (
    DETACHED_EFFECTS,
    ENTRANCE_ANIMATIONS,
    EXIT_ANIMATIONS,
    MODIFIER_ANIMATIONS,
    REPLACING_TRANSFORMS,
    RETURNING_RATE_FUNCTIONS,
    AnimationKind,
    ObjectKind,
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
    value: float = 0.0
    #: Orientation of a 3D camera (degrees).
    phi: float = 0.0
    theta: float = 0.0


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


def _first_reference_with_groups(scene: Scene, object_id: str) -> tuple[Animation, bool] | None:
    """Like :func:`first_reference` but also counts animations of enclosing groups."""
    ids = [object_id] + groups.ancestors(scene, object_id)
    for step in scene.steps:
        if step.kind != StepKind.PLAY:
            continue
        for anim in step.animations:
            if anim.target_id in ids:
                return anim, True
            if anim.params.get("target") in ids:
                return anim, False
    return None


def visible_at_start(scene: Scene, obj: SceneObject) -> bool:
    """Decide whether an object is added before the first step.

    In automatic mode an object starts hidden if it (or a group containing it)
    is introduced by an entrance animation or first used as the target of a
    transform.
    """
    if obj.visibility == Visibility.SHOWN:
        return True
    if obj.visibility == Visibility.HIDDEN:
        return False
    for group_id in groups.ancestors(scene, obj.id):
        group = scene.object_by_id(group_id)
        if group is not None and group.visibility == Visibility.HIDDEN:
            return False
    reference = _first_reference_with_groups(scene, obj.id)
    if reference is None:
        return True
    anim, is_main_target = reference
    if not is_main_target:
        return False
    return anim.kind not in ENTRANCE_ANIMATIONS


_BRACE_THICKNESS = 0.27


def brace_anchor(scene: Scene, brace: SceneObject) -> tuple[float, float] | None:
    """Return the center of a brace attached to another object (estimated)."""
    target = scene.object_by_id(brace.params.get("target"))
    if target is None or target.id == brace.id:
        return None
    if groups.is_group(target):
        tx, ty = groups.group_center_of_objects(scene, target.id)
        left, bottom, right, top = groups.bounds_of(scene, groups.leaves(scene, target.id), {
            leaf: initial_state(scene, scene.object_by_id(leaf)) for leaf in groups.leaves(scene, target.id)
        })
        width, height = right - left, top - bottom
    else:
        tx, ty = bound_anchor(scene, target) if is_bound(scene, target) else (target.x, target.y)
        width, height = rotated_extent(*base_size(scene, target), target.rotation)
    buff = float(brace.params.get("buff", 0.2))
    offset_y = height / 2 + buff + _BRACE_THICKNESS / 2
    offset_x = width / 2 + buff + _BRACE_THICKNESS / 2
    direction = brace.params.get("direction", "down")
    return {
        "down": (tx, ty - offset_y),
        "up": (tx, ty + offset_y),
        "left": (tx - offset_x, ty),
        "right": (tx + offset_x, ty),
    }.get(direction, (tx, ty - offset_y))


def initial_state(scene: Scene, obj: SceneObject) -> ObjectState:
    """Return the state of an object before the first step."""
    bound = is_bound(scene, obj)
    if bound:
        x, y = bound_anchor(scene, obj)
    elif groups.is_group(obj):
        x, y = groups.group_center_of_objects(scene, obj.id)
    elif obj.kind == ObjectKind.BRACE and brace_anchor(scene, obj) is not None:
        x, y = brace_anchor(scene, obj)
    else:
        x, y = obj.x, obj.y
    rotation = 0.0 if bound or groups.is_group(obj) else obj.rotation
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
        value=_initial_value(obj),
        phi=float(obj.params.get("phi", 70.0)) if obj.kind == ObjectKind.CAMERA else 0.0,
        theta=float(obj.params.get("theta", -45.0)) if obj.kind == ObjectKind.CAMERA else 0.0,
    )


def _initial_value(obj: SceneObject) -> float:
    if obj.kind in (ObjectKind.PARAMETER, ObjectKind.DECIMAL_NUMBER):
        try:
            return float(obj.params.get("value", 0.0))
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def parameter_values(scene: Scene, states: dict[str, ObjectState]) -> dict[str, float]:
    """Return the current value of every parameter symbol."""
    from manim_studio.model.graphs import parameter_objects, parameter_symbol

    return {parameter_symbol(obj): states[obj.id].value for obj in parameter_objects(scene) if obj.id in states and parameter_symbol(obj)}


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


def apply_animation(states: dict[str, ObjectState], anim: Animation, scene: Scene | None = None) -> None:
    """Update ``states`` in place with the end result of one animation."""
    current = states.get(anim.target_id)
    if current is None:
        return
    if scene is not None and groups.is_group(scene.object_by_id(anim.target_id)):
        apply_to_group(states, scene, anim, 1.0, partial=False)
        return
    returns = anim.rate_func in RETURNING_RATE_FUNCTIONS
    kind = anim.kind
    if kind in ENTRANCE_ANIMATIONS:
        states[anim.target_id] = replace(current, visible=not returns)
    elif kind in EXIT_ANIMATIONS:
        states[anim.target_id] = replace(current, visible=False)
    elif kind == AnimationKind.TRANSFORM_FROM_COPY:
        target_id = str(anim.params.get("target"))
        if target_id in states and not returns:
            states[target_id] = replace(states[target_id], visible=True)
    elif kind == AnimationKind.TRANSFORM:
        target = states.get(str(anim.params.get("target")))
        if target is not None and not returns:
            states[anim.target_id] = replace(target, object_id=anim.target_id, visible=True)
    elif kind in REPLACING_TRANSFORMS:
        target_id = str(anim.params.get("target"))
        if target_id in states and not returns:
            states[anim.target_id] = replace(current, visible=False)
            states[target_id] = replace(states[target_id], visible=True)
    elif kind in (AnimationKind.INDICATE, AnimationKind.WIGGLE, AnimationKind.APPLY_WAVE):
        states[anim.target_id] = replace(current, visible=True)
    elif kind in DETACHED_EFFECTS:
        return
    elif kind == AnimationKind.MOVE_ALONG_PATH:
        if scene is not None and not returns:
            from manim_studio.model.paths import path_end

            end = path_end(scene, states, str(anim.params.get("path")))
            if end is not None:
                states[anim.target_id] = replace(current, x=end[0], y=end[1], visible=True)
    elif kind == AnimationKind.SWAP:
        partner = states.get(str(anim.params.get("partner")))
        if partner is not None and not returns:
            states[anim.target_id] = replace(current, x=partner.x, y=partner.y, visible=True)
            states[partner.object_id] = replace(partner, x=current.x, y=current.y, visible=True)
    elif kind == AnimationKind.SET_VALUE:
        if not returns:
            states[anim.target_id] = replace(current, value=float(anim.params.get("value", current.value)))
    elif kind == AnimationKind.ORBIT:
        if not returns:
            states[anim.target_id] = replace(current, phi=float(anim.params.get("phi", current.phi)), theta=float(anim.params.get("theta", current.theta)))
    elif not returns:
        states[anim.target_id] = _apply_modifier(current, anim)
    else:
        states[anim.target_id] = replace(current, visible=True)


def _rotate_about(x: float, y: float, cx: float, cy: float, degrees: float) -> tuple[float, float]:
    radians = math.radians(degrees)
    dx, dy = x - cx, y - cy
    return cx + dx * math.cos(radians) - dy * math.sin(radians), cy + dx * math.sin(radians) + dy * math.cos(radians)


def apply_to_group(states: dict[str, ObjectState], scene: Scene, anim: Animation, progress: float, partial: bool) -> None:
    """Apply an animation of a group to all of its members.

    ``progress`` is the eased progress (1.0 for a finished animation);
    ``partial`` selects the playback variant of the per-member effects.
    """
    from manim_studio.model.playback import apply_partial

    leaf_ids = [leaf for leaf in groups.leaves(scene, anim.target_id) if leaf in states]
    returns = anim.rate_func in RETURNING_RATE_FUNCTIONS and not partial
    cx, cy = groups.group_center(scene, anim.target_id, states)
    params = anim.params
    if anim.kind in MODIFIER_ANIMATIONS - {AnimationKind.CHANGE_COLOR}:
        if returns:
            return
        for leaf in leaf_ids:
            state = states[leaf]
            if anim.kind == AnimationKind.MOVE:
                dx = (float(params.get("x", cx)) - cx) * progress
                dy = (float(params.get("y", cy)) - cy) * progress
                states[leaf] = replace(state, x=state.x + dx, y=state.y + dy, visible=True)
            elif anim.kind == AnimationKind.SCALE:
                factor = 1 + (float(params.get("factor", 1.0)) - 1) * progress
                states[leaf] = replace(state, scale=state.scale * factor, x=cx + (state.x - cx) * factor, y=cy + (state.y - cy) * factor, visible=True)
            else:
                angle = float(params.get("angle", 0.0)) * progress
                x, y = _rotate_about(state.x, state.y, cx, cy, angle)
                states[leaf] = replace(state, rotation=state.rotation + angle, x=x, y=y, visible=True)
    else:
        for leaf in leaf_ids:
            member_anim = Animation(anim.id, anim.kind, leaf, anim.run_time, anim.rate_func, dict(anim.params), anim.delay)
            if partial:
                apply_partial(states, member_anim, progress)
            else:
                apply_animation(states, member_anim)
    group_state = states.get(anim.target_id)
    if group_state is not None:
        gx, gy = groups.group_center(scene, anim.target_id, states)
        visible = any(states[leaf].visible for leaf in leaf_ids) if leaf_ids else group_state.visible
        states[anim.target_id] = replace(group_state, x=gx, y=gy, visible=visible)


def refresh_group_states(scene: Scene, states: dict[str, ObjectState]) -> dict[str, ObjectState]:
    """Recompute group centers and visibility from their members (after members moved on their own)."""
    for obj in scene.objects:
        if not groups.is_group(obj) or obj.id not in states:
            continue
        leaf_ids = [leaf for leaf in groups.leaves(scene, obj.id) if leaf in states]
        if not leaf_ids:
            continue
        gx, gy = groups.group_center(scene, obj.id, states)
        visible = any(states[leaf].visible for leaf in leaf_ids)
        states[obj.id] = replace(states[obj.id], x=gx, y=gy, visible=visible)
    return states


def states_after(scene: Scene, step_index: int) -> dict[str, ObjectState]:
    """Return the state of every object after ``step_index`` (``START`` = before step 1)."""
    states = {obj.id: initial_state(scene, obj) for obj in scene.objects}
    last = min(step_index, len(scene.steps) - 1)
    for step in scene.steps[: last + 1]:
        if step.kind != StepKind.PLAY:
            continue
        for anim in step.animations:
            apply_animation(states, anim, scene)
        refresh_group_states(scene, states)
    return states


def state_before_step(scene: Scene, step_index: int) -> dict[str, ObjectState]:
    """Return the state right before ``step_index`` is played."""
    return states_after(scene, step_index - 1)
