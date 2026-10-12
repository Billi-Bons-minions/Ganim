"""Motion traces: the line an object draws behind itself (Manim's ``TracedPath``)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace

from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.geometry import param_float
from manim_studio.model.types import ENTRANCE_ANIMATIONS, EXIT_ANIMATIONS, ObjectKind, StepKind

#: Samples per second of animation time (and a cap for very long scenes).
SAMPLES_PER_SECOND = 24
MAX_SAMPLES = 360

_cache: dict[tuple, list[tuple[float, float]]] = {}


def trace_target(scene: Scene, trace: SceneObject) -> SceneObject | None:
    target = scene.object_by_id(trace.params.get("target"))
    if target is None or target.id == trace.id or target.kind == ObjectKind.TRACE:
        return None
    return target


def _active_window(scene: Scene, trace: SceneObject) -> tuple[float, float]:
    """From when to when the trace records (it starts when it appears and stops when it is removed)."""
    from manim_studio.model.playback import step_spans
    from manim_studio.model.state import visible_at_start

    spans = step_spans(scene)
    start = 0.0 if visible_at_start(scene, trace) else None
    end = spans[-1][1] if spans else 0.0
    for step, (step_start, _step_end) in zip(scene.steps, spans):
        if step.kind != StepKind.PLAY:
            continue
        for anim, (begin, finish) in zip(step.animations, step.windows()):
            if anim.target_id != trace.id:
                continue
            if anim.kind in ENTRANCE_ANIMATIONS and start is None:
                start = step_start + begin
            elif anim.kind in EXIT_ANIMATIONS and start is not None:
                return start, min(end, step_start + finish)
    return (start if start is not None else end), end


def _signature(scene: Scene) -> str:
    from manim_studio.model.serialization import scene_to_dict

    return hashlib.sha1(json.dumps(scene_to_dict(scene), sort_keys=True, default=str).encode("utf-8")).hexdigest()


def trace_points(scene: Scene, trace: SceneObject, until: float) -> list[tuple[float, float]]:
    """Positions of the traced object from the start of the trace up to ``until`` seconds."""
    from manim_studio.model.playback import state_at_time

    target = trace_target(scene, trace)
    if target is None:
        return []
    start, end = _active_window(scene, trace)
    stop = min(until, end)
    fading = param_float(trace.params, "dissipating_time", 0.0)
    if fading > 0:
        start = max(start, stop - fading)
    if stop <= start + 1e-9:
        return []
    key = (_signature(scene), trace.id, round(start, 4), round(stop, 4))
    if key in _cache:
        return _cache[key]
    count = max(2, min(MAX_SAMPLES, int((stop - start) * SAMPLES_PER_SECOND) + 1))
    # Manim records from the first frame after the trace was added, i.e. after a
    # jump such as the start of "move along path"
    first = min(start + 1e-4, stop)
    points = []
    for index in range(count):
        time = first + (stop - first) * index / (count - 1)
        state = state_at_time(scene, time).get(target.id)
        if state is not None:
            points.append((state.x, state.y))
    if len(_cache) > 64:
        _cache.clear()
    _cache[key] = points
    return points


def with_traces(scene: Scene, states: dict, until: float) -> dict:
    """Add the recorded points of every trace to ``states`` (for drawing on the stage)."""
    for obj in scene.objects:
        if obj.kind == ObjectKind.TRACE and obj.id in states:
            flat = tuple(value for point in trace_points(scene, obj, until) for value in point)
            states[obj.id] = replace(states[obj.id], x=0.0, y=0.0, rotation=0.0, scale=1.0, geometry=flat)
    return states
