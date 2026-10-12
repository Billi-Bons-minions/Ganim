"""Scene state at an arbitrary point in time (for playback on the stage)."""

from __future__ import annotations

import math
from dataclasses import replace

from manim_studio.model import groups
from manim_studio.model.entities import Animation, Scene, Step
from manim_studio.model.paths import arc_point, path_polyline, point_at
from manim_studio.model.rate_functions import rate
from manim_studio.model.state import (
    START,
    ObjectState,
    apply_animation,
    apply_to_group,
    refresh_group_states,
    states_after,
)
from manim_studio.model.types import ENTRANCE_ANIMATIONS, EXIT_ANIMATIONS, TRANSFORM_ANIMATIONS, AnimationKind, StepKind, pivot_of

_SHIFTS = {"up": (0.0, 1.0), "down": (0.0, -1.0), "left": (-1.0, 0.0), "right": (1.0, 0.0)}


def step_spans(scene: Scene) -> list[tuple[float, float]]:
    """Return ``(start, end)`` in seconds of every step."""
    spans: list[tuple[float, float]] = []
    time = 0.0
    for step in scene.steps:
        duration = step.duration()
        spans.append((time, time + duration))
        time += duration
    return spans


def total_duration(scene: Scene) -> float:
    """Return the length of the scene in seconds."""
    return sum(step.duration() for step in scene.steps)


def step_end_time(scene: Scene, index: int) -> float:
    """Return the time at which step ``index`` ends (``START`` → 0)."""
    spans = step_spans(scene)
    if index < 0 or not spans:
        return 0.0
    return spans[min(index, len(spans) - 1)][1]


def step_start_time(scene: Scene, index: int) -> float:
    """Return the time at which step ``index`` starts."""
    spans = step_spans(scene)
    if index < 0 or not spans:
        return 0.0
    return spans[min(index, len(spans) - 1)][0]


def step_at_time(scene: Scene, time: float) -> int:
    """Return the index of the step running at ``time`` (``START`` before the first)."""
    if time <= 0:
        return START
    spans = step_spans(scene)
    for index, (start, end) in enumerate(spans):
        if start <= time < end:
            return index
    return len(spans) - 1


def _mix(first: str, second: str, t: float) -> str:
    def channels(value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        try:
            return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
        except (ValueError, IndexError):
            return 255, 255, 255

    a, b = channels(first), channels(second)
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(a, b))


def _partial_entrance(state: ObjectState, anim: Animation, progress: float) -> ObjectState:
    kind = anim.kind
    if kind == AnimationKind.DRAW_BORDER_THEN_FILL:
        return replace(state, visible=True, draw=min(1.0, 2 * progress), fill=max(0.0, 2 * progress - 1))
    if kind in (AnimationKind.CREATE, AnimationKind.WRITE):
        return replace(state, visible=True, draw=progress, fill=progress if kind == AnimationKind.WRITE else state.fill)
    if kind == AnimationKind.UNCREATE:
        return replace(state, draw=1 - progress)
    if kind == AnimationKind.GROW_FROM_CENTER:
        return replace(state, visible=True, scale=state.scale * max(progress, 0.001))
    if kind == AnimationKind.SPIN_IN:
        return replace(state, visible=True, scale=state.scale * max(progress, 0.001), rotation=state.rotation - 90.0 * (1 - progress))
    if kind == AnimationKind.ONE_BY_ONE:
        return replace(state, visible=True, draw=max(progress, 0.001), opacity=min(1.0, 0.3 + progress))
    if kind in (AnimationKind.ADD_LETTERS, AnimationKind.GROW_ARROW, AnimationKind.TYPE_WITH_CURSOR):
        return replace(state, visible=True, draw=max(progress, 0.001))
    if kind == AnimationKind.UNWRITE:
        return replace(state, draw=1 - progress, fill=state.fill * (1 - progress))
    if kind == AnimationKind.SHRINK_TO_CENTER:
        return replace(state, scale=state.scale * max(1 - progress, 0.001))
    if kind == AnimationKind.GROW_FROM_EDGE:
        # grows out of one edge: shrink towards that edge while the scale is small
        ex, ey = _SHIFTS.get(str(anim.params.get("edge", "down")), (0.0, -1.0))
        return replace(state, visible=True, scale=state.scale * max(progress, 0.001), x=state.x + ex * (1 - progress), y=state.y + ey * (1 - progress))
    dx, dy = _SHIFTS.get(str(anim.params.get("shift", "none")), (0.0, 0.0))
    zoom = float(anim.params.get("scale", 1.0))
    if kind == AnimationKind.FADE_IN:
        size = state.scale * (zoom + (1 - zoom) * progress)
        return replace(state, visible=True, opacity=progress, scale=size, x=state.x - dx * (1 - progress), y=state.y - dy * (1 - progress))
    size = state.scale * (1 + (zoom - 1) * progress)
    return replace(state, opacity=1 - progress, scale=size, x=state.x + dx * progress, y=state.y + dy * progress)


def _partial_transform(states: dict[str, ObjectState], anim: Animation, progress: float) -> None:
    source = states[anim.target_id]
    target = states.get(str(anim.params.get("target")))
    if target is None:
        return
    # TransformFromCopy leaves the source alone; the target appears out of a copy of it
    key = target.object_id if anim.kind == AnimationKind.TRANSFORM_FROM_COPY else anim.target_id
    states[key] = replace(
        source,
        object_id=key,
        visible=True,
        morph_to=target.shape_id,
        morph_t=progress,
        x=source.x + (target.x - source.x) * progress,
        y=source.y + (target.y - source.y) * progress,
        rotation=source.rotation + (target.rotation - source.rotation) * progress,
        scale=source.scale + (target.scale - source.scale) * progress,
        stroke_color=_mix(source.stroke_color, target.stroke_color, progress),
        fill_color=_mix(source.fill_color, target.fill_color, progress),
    )


def _partial_modifier(state: ObjectState, anim: Animation, progress: float) -> ObjectState:
    params = anim.params
    kind = anim.kind
    if kind == AnimationKind.MOVE:
        x, y = float(params.get("x", state.x)), float(params.get("y", state.y))
        return replace(state, visible=True, x=state.x + (x - state.x) * progress, y=state.y + (y - state.y) * progress)
    if kind == AnimationKind.SCALE:
        return replace(state, visible=True, scale=state.scale * (1 + (float(params.get("factor", 1.0)) - 1) * progress))
    if kind == AnimationKind.ROTATE:
        angle = float(params.get("angle", 0.0)) * progress
        pivot = pivot_of(anim)
        if pivot is None:
            return replace(state, visible=True, rotation=state.rotation + angle)
        radians = math.radians(angle)
        dx, dy = state.x - pivot[0], state.y - pivot[1]
        x, y = pivot[0] + dx * math.cos(radians) - dy * math.sin(radians), pivot[1] + dx * math.sin(radians) + dy * math.cos(radians)
        return replace(state, visible=True, rotation=state.rotation + angle, x=x, y=y)
    color = str(params.get("color", state.stroke_color))
    apply_to = params.get("apply_to", "both")
    stroke = _mix(state.stroke_color, color, progress) if apply_to in ("both", "stroke") else state.stroke_color
    fill = _mix(state.fill_color, color, progress) if apply_to in ("both", "fill") else state.fill_color
    return replace(state, visible=True, stroke_color=stroke, fill_color=fill)


def apply_partial(states: dict[str, ObjectState], anim: Animation, progress: float, scene: Scene | None = None) -> None:
    """Update ``states`` with an animation that is ``progress`` (0…1, eased) done."""
    state = states.get(anim.target_id)
    if state is None:
        return
    if scene is not None and groups.is_group(scene.object_by_id(anim.target_id)):
        apply_to_group(states, scene, anim, progress, partial=True)
        return
    kind = anim.kind
    if kind in ENTRANCE_ANIMATIONS | EXIT_ANIMATIONS:
        states[anim.target_id] = _partial_entrance(state, anim, progress)
    elif kind in TRANSFORM_ANIMATIONS:
        _partial_transform(states, anim, progress)
    elif kind == AnimationKind.MOVE_ALONG_PATH:
        if scene is not None:
            point = point_at(path_polyline(scene, states, str(anim.params.get("path"))), progress)
            if point is not None:
                states[anim.target_id] = replace(state, visible=True, x=point[0], y=point[1])
    elif kind == AnimationKind.SWAP:
        partner = states.get(str(anim.params.get("partner")))
        if partner is not None:
            x, y = arc_point((state.x, state.y), (partner.x, partner.y), progress)
            px, py = arc_point((partner.x, partner.y), (state.x, state.y), progress)
            states[anim.target_id] = replace(state, visible=True, x=x, y=y)
            states[partner.object_id] = replace(partner, visible=True, x=px, y=py)
    elif kind in (AnimationKind.FLASH, AnimationKind.FOCUS_ON):
        color = str(anim.params.get("color", "#F7D96F"))
        states[anim.target_id] = replace(state, outline=progress, outline_color=color)
    elif kind == AnimationKind.WIGGLE:
        wiggle = math.sin(progress * math.pi * 6) * math.sin(progress * math.pi)
        states[anim.target_id] = replace(state, visible=True, rotation=state.rotation + 6.0 * wiggle, scale=state.scale * (1 + 0.1 * math.sin(progress * math.pi)))
    elif kind == AnimationKind.APPLY_WAVE:
        amplitude = float(anim.params.get("amplitude", 0.2))
        states[anim.target_id] = replace(state, visible=True, y=state.y + amplitude * math.sin(progress * math.pi))
    elif kind == AnimationKind.INDICATE:
        color = str(anim.params.get("color", state.fill_color))
        factor = 1 + (float(anim.params.get("scale_factor", 1.2)) - 1) * progress
        states[anim.target_id] = replace(
            state,
            visible=True,
            scale=state.scale * factor,
            stroke_color=_mix(state.stroke_color, color, progress),
            fill_color=_mix(state.fill_color, color, progress),
        )
    elif kind in (AnimationKind.CIRCUMSCRIBE, AnimationKind.PASSING_FLASH, AnimationKind.BROADCAST):
        states[anim.target_id] = replace(state, outline=progress, outline_color=str(anim.params.get("color", "#F7D96F")))
    elif kind == AnimationKind.SET_VALUE:
        target = float(anim.params.get("value", state.value))
        states[anim.target_id] = replace(state, value=state.value + (target - state.value) * progress)
    elif kind == AnimationKind.ORBIT:
        phi, theta = float(anim.params.get("phi", state.phi)), float(anim.params.get("theta", state.theta))
        states[anim.target_id] = replace(state, phi=state.phi + (phi - state.phi) * progress, theta=state.theta + (theta - state.theta) * progress)
    else:
        states[anim.target_id] = _partial_modifier(state, anim, progress)


def _step_state(scene: Scene, index: int, step: Step, local_time: float) -> dict[str, ObjectState]:
    states = states_after(scene, index - 1)
    if step.kind != StepKind.PLAY:
        return states
    for anim, (start, end) in zip(step.animations, step.windows()):
        if local_time >= end:
            apply_animation(states, anim, scene)
        elif local_time > start:
            linear_progress = (local_time - start) / max(end - start, 1e-9)
            if anim.kind == AnimationKind.CIRCUMSCRIBE:
                apply_partial(states, anim, linear_progress, scene)
            else:
                apply_partial(states, anim, rate(anim.rate_func, linear_progress), scene)
        elif anim.kind in (AnimationKind.CREATE, AnimationKind.WRITE, AnimationKind.DRAW_BORDER_THEN_FILL, AnimationKind.FADE_IN, AnimationKind.GROW_FROM_CENTER):
            apply_partial(states, anim, 0.0, scene)
    return states


def state_at_time(scene: Scene, time: float) -> dict[str, ObjectState]:
    """Return the state of every object at ``time`` seconds."""
    if time <= 0 or not scene.steps:
        return states_after(scene, START)
    spans = step_spans(scene)
    if time >= spans[-1][1]:
        return states_after(scene, len(scene.steps) - 1)
    index = step_at_time(scene, time)
    start, _end = spans[index]
    return refresh_group_states(scene, _step_state(scene, index, scene.steps[index], time - start))
