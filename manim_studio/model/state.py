"""Compute what the scene looks like after a given timeline step."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from manim_studio.model import groups
from manim_studio.model.entities import Animation, Scene, SceneObject
from manim_studio.model.extents import base_size, rotated_extent
from manim_studio.model.gradients import gradient_color, gradient_parts
from manim_studio.model.graphs import bound_anchor, is_bound
from manim_studio.model.paths import arc_point
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
    pivot_of,
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
    #: Second colors of a gradient (``set_fill([a, b])``); empty for a single color.
    stroke_color2: str = ""
    fill_color2: str = ""
    opacity: float = 1.0
    draw: float = 1.0
    fill: float = 1.0
    morph_to: str | None = None
    morph_t: float = 0.0
    #: On an arc (``path_arc``): complex weights ``(source, target)`` of the two outlines in the object's own coordinates.
    morph_weights: tuple[complex, complex] | None = None
    outline: float = 0.0
    outline_color: str = "#F7D96F"
    value: float = 0.0
    #: Orientation of a 3D camera (degrees).
    phi: float = 0.0
    theta: float = 0.0
    #: Extra geometry of attached objects (angle marks: start angle and sweep in degrees).
    geometry: tuple[float, ...] = ()
    #: Linear map applied to the shape around its center (``(m11, m12, m21, m22)``, scene axes).
    matrix: tuple[float, float, float, float] = (1.0, 0.0, 0.0, 1.0)
    #: Colors of single vertices and edges of a network (``(part, color)`` pairs).
    part_colors: tuple[tuple[tuple[str, str, str], str], ...] = ()
    #: Where the shapes of a boolean shape are (see ``model/booleans.py``).
    parts: tuple = ()
    #: Nonlinear maps the object went through, in order (see ``model/warps.py``).
    warps: tuple = ()
    #: A moved or turned 3D solid: its points are ``anchor3d + orientation · local point`` (scene coordinates).
    anchor3d: tuple = ()
    orientation: tuple = ()


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
    fill_gradient, stroke_gradient = gradient_parts(obj)
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
        stroke_color2=gradient_color(obj) if stroke_gradient else "",
        fill_color2=gradient_color(obj) if fill_gradient else "",
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
    # a new color replaces a gradient (Manim's set_color with one color)
    stroke2 = "" if apply_to in ("both", "stroke") else state.stroke_color2
    fill2 = "" if apply_to in ("both", "fill") else state.fill_color2
    return replace(state, stroke_color=stroke, fill_color=fill, stroke_color2=stroke2, fill_color2=fill2, visible=True)


def _apply_modifier(state: ObjectState, anim: Animation) -> ObjectState:
    params = anim.params
    if anim.kind == AnimationKind.MOVE:
        return replace(state, x=float(params.get("x", state.x)), y=float(params.get("y", state.y)), visible=True)
    if anim.kind == AnimationKind.SCALE:
        return replace(state, scale=state.scale * float(params.get("factor", 1.0)), visible=True)
    if anim.kind == AnimationKind.ROTATE:
        angle = float(params.get("angle", 0.0))
        pivot = pivot_of(anim)
        x, y = _rotate_about(state.x, state.y, pivot[0], pivot[1], angle) if pivot else (state.x, state.y)
        return replace(state, rotation=state.rotation + angle, x=x, y=y, visible=True)
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
    elif kind == AnimationKind.APPLY_MATRIX:
        if not returns:
            states[anim.target_id] = apply_matrix(current, matrix_of(anim), 1.0)
    elif kind in (AnimationKind.APPLY_COMPLEX, AnimationKind.APPLY_POINTWISE):
        from manim_studio.model.warps import warp_of

        warp = warp_of(anim)
        if not returns and warp is not None:
            states[anim.target_id] = replace(current, warps=(*current.warps, warp), visible=True)
    elif kind == AnimationKind.NETWORK_PARTS:
        if not returns and anim.params.get("effect", "color") == "color":
            colors = dict(current.part_colors)
            for part in network_animation_parts(scene, anim):
                colors[part] = str(anim.params.get("color", current.fill_color))
            states[anim.target_id] = replace(current, part_colors=tuple(colors.items()))
    elif kind == AnimationKind.SET_VALUE:
        if not returns:
            states[anim.target_id] = replace(current, value=float(anim.params.get("value", current.value)))
    elif kind == AnimationKind.AMBIENT_ROTATION:
        return  # the camera turns while time passes (see ``ambient_rates``)
    elif kind in (AnimationKind.MOVE_3D, AnimationKind.ROTATE_3D):
        if not returns and scene is not None:
            states[anim.target_id] = solid_motion(scene, current, anim, 1.0)
    elif kind == AnimationKind.ORBIT:
        if not returns:
            states[anim.target_id] = replace(current, phi=float(anim.params.get("phi", current.phi)), theta=float(anim.params.get("theta", current.theta)))
    elif not returns:
        states[anim.target_id] = _apply_modifier(current, anim)
    else:
        states[anim.target_id] = replace(current, visible=True)


Matrix = tuple[float, float, float, float]


def matrix_of(anim: Animation) -> Matrix:
    """The 2×2 matrix of a "linear map" animation."""
    return tuple(float(anim.params.get(key, default)) for key, default in (("m11", 1.0), ("m12", 0.0), ("m21", 0.0), ("m22", 1.0)))  # type: ignore[return-value]


def _multiply(first: Matrix, second: Matrix) -> Matrix:
    a, b, c, d = first
    e, f, g, h = second
    return (a * e + b * g, a * f + b * h, c * e + d * g, c * f + d * h)


def apply_matrix(state: ObjectState, matrix: Matrix, progress: float) -> ObjectState:
    """Deform an object with a linear map around the scene's origin (like Manim's ``ApplyMatrix``).

    Manim moves every point straight to its image, so after ``progress`` the map is
    ``(1 - t)·I + t·M``. The object's center moves with it; the rest of the map is kept in
    the object's own (rotated) frame so that later moves, turns and scalings still work.
    """
    t = progress
    m11, m12, m21, m22 = matrix
    current: Matrix = (1 - t + t * m11, t * m12, t * m21, 1 - t + t * m22)
    x = current[0] * state.x + current[1] * state.y
    y = current[2] * state.x + current[3] * state.y
    radians = math.radians(state.rotation)
    cos, sin = math.cos(radians), math.sin(radians)
    local = _multiply(_multiply((cos, sin, -sin, cos), current), _multiply((cos, -sin, sin, cos), state.matrix))
    return replace(state, x=x, y=y, matrix=tuple(round(value, 12) for value in local), visible=True)  # type: ignore[arg-type]


def solid_motion(scene: Scene, state: ObjectState, anim: Animation, progress: float) -> ObjectState:
    """A 3D solid moved (``move_to``) or turned (``Rotate``) ``progress`` of the way."""
    from manim_studio.model.three_d import moved_solid, turned_solid

    obj = scene.object_by_id(anim.target_id)
    if obj is None:
        return state
    if anim.kind == AnimationKind.MOVE_3D:
        target = tuple(float(anim.params.get(key, 0.0)) for key in ("x", "y", "z"))
        placement = moved_solid(scene, obj, state, target, progress)  # type: ignore[arg-type]
    else:
        placement = turned_solid(scene, obj, state, str(anim.params.get("axis", "z")), float(anim.params.get("angle", 90.0)) * progress)
    if placement is None:
        return state
    return replace(state, anchor3d=placement[0], orientation=placement[1], visible=True)


def network_animation_parts(scene: Scene | None, anim: Animation) -> list[tuple[str, str, str]]:
    """The existing vertices and edges a "highlight vertices/edges" animation names."""
    from manim_studio.model.networks import network_parts

    obj = scene.object_by_id(anim.target_id) if scene is not None else None
    if obj is None or obj.kind != ObjectKind.NETWORK:
        return []
    return network_parts(obj, str(anim.params.get("parts", "")))[0]


def part_color(state: ObjectState, part: tuple[str, str, str]) -> str:
    """Current color of a vertex (fill) or an edge (stroke) of a network."""
    for key, color in state.part_colors:
        if key == part:
            return color
    return state.fill_color if part[0] == "v" else state.stroke_color


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
                x, y = arc_point((cx, cy), (float(params.get("x", cx)), float(params.get("y", cy))), progress, float(params.get("path_arc", 0.0)))
                dx, dy = x - cx, y - cy
                states[leaf] = replace(state, x=state.x + dx, y=state.y + dy, visible=True)
            elif anim.kind == AnimationKind.SCALE:
                factor = 1 + (float(params.get("factor", 1.0)) - 1) * progress
                states[leaf] = replace(state, scale=state.scale * factor, x=cx + (state.x - cx) * factor, y=cy + (state.y - cy) * factor, visible=True)
            else:
                angle = float(params.get("angle", 0.0)) * progress
                px, py = pivot_of(anim) or (cx, cy)
                x, y = _rotate_about(state.x, state.y, px, py, angle)
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
    return refresh_attached_states(scene, states)


def refresh_attached_states(scene: Scene, states: dict[str, ObjectState]) -> dict[str, ObjectState]:
    """Coupled objects follow their target or formula; highlights follow their target (same place, turn and size)."""
    from manim_studio.model.attach import attached_positions

    coupled = attached_positions(scene, lambda object_id: (states[object_id].x, states[object_id].y) if object_id in states else None, parameter_values(scene, states))
    for object_id, (x, y) in coupled.items():
        if object_id in states:
            states[object_id] = replace(states[object_id], x=x, y=y)
    for obj in scene.objects:
        if obj.id not in states:
            continue
        if obj.kind == ObjectKind.HIGHLIGHT:
            target = states.get(str(obj.params.get("target")))
            if target is not None and target.object_id != obj.id:
                states[obj.id] = replace(states[obj.id], x=target.x, y=target.y, rotation=target.rotation, scale=target.scale)
        elif obj.kind == ObjectKind.ANGLE:
            from manim_studio.model.angles import angle_geometry

            geometry = angle_geometry(scene, obj, states)
            if geometry is None:
                states[obj.id] = replace(states[obj.id], geometry=())
            else:
                states[obj.id] = replace(states[obj.id], x=geometry.x, y=geometry.y, rotation=0.0, scale=1.0, geometry=(geometry.start, geometry.sweep))
        elif obj.kind == ObjectKind.BOOLEAN_SHAPE:
            from manim_studio.model.booleans import placements, result_bounds

            parts = placements(scene, obj, states)
            bounds = result_bounds(scene, obj, parts)
            if bounds is None:
                states[obj.id] = replace(states[obj.id], parts=())
            else:
                left, bottom, right, top = bounds
                states[obj.id] = replace(states[obj.id], x=(left + right) / 2, y=(bottom + top) / 2, rotation=0.0, parts=parts)
    return states


def ambient_rates(scene: Scene, step_index: int) -> dict[str, tuple[str, float]]:
    """The 3D camera's lasting rotations during step ``step_index``: angle -> (camera id, degrees per second).

    A lasting rotation (``begin_ambient_camera_rotation``) starts with its step and goes on
    through all later steps (waiting included) until another one about the same angle replaces
    or stops it (rate 0).
    """
    rates: dict[str, tuple[str, float]] = {}
    for step in scene.steps[: step_index + 1]:
        if step.kind != StepKind.PLAY:
            continue
        for anim in step.animations:
            if anim.kind == AnimationKind.AMBIENT_ROTATION:
                about = str(anim.params.get("about", "theta"))
                rate = float(anim.params.get("rate", 10.0))
                if rate:
                    rates[about] = (anim.target_id, rate)
                else:
                    rates.pop(about, None)
    return rates


def turn_camera(states: dict[str, ObjectState], rates: dict[str, tuple[str, float]], seconds: float) -> None:
    """Add ``seconds`` of the lasting rotations to the camera's angles."""
    for about, (camera_id, rate) in rates.items():
        state = states.get(camera_id)
        if state is not None and about in ("theta", "phi"):
            states[camera_id] = replace(state, **{about: getattr(state, about) + rate * seconds})


def states_after(scene: Scene, step_index: int) -> dict[str, ObjectState]:
    """Return the state of every object after ``step_index`` (``START`` = before step 1)."""
    states = refresh_attached_states(scene, {obj.id: initial_state(scene, obj) for obj in scene.objects})
    last = min(step_index, len(scene.steps) - 1)
    turning = any(anim.kind == AnimationKind.AMBIENT_ROTATION for step in scene.steps for anim in step.animations)
    for index, step in enumerate(scene.steps[: last + 1]):
        if turning:
            turn_camera(states, ambient_rates(scene, index), step.duration())
        if step.kind != StepKind.PLAY:
            continue
        for anim in step.animations:
            apply_animation(states, anim, scene)
        refresh_group_states(scene, states)
    return states


def state_before_step(scene: Scene, step_index: int) -> dict[str, ObjectState]:
    """Return the state right before ``step_index`` is played."""
    return states_after(scene, step_index - 1)
