"""Create new animations with sensible defaults for the selected objects."""

from __future__ import annotations

from manim_studio.model.entities import Animation, Scene, SceneObject
from manim_studio.model.factory import create_animation
from manim_studio.model.schema import animation_allowed
from manim_studio.model.state import ObjectState, states_after
from manim_studio.model.types import REFERENCE_PARAMS, TRANSFORM_ANIMATIONS, UNADDED_KINDS, AnimationKind


def reference_candidates(scene: Scene, kind: AnimationKind, object_id: str) -> list[SceneObject]:
    """Objects that can be the second object of a transform, path or swap."""
    from manim_studio.model.paths import local_outline

    result = []
    for obj in scene.objects:
        if obj.id == object_id or obj.kind in UNADDED_KINDS:
            continue
        if kind == AnimationKind.MOVE_ALONG_PATH:
            if local_outline(scene, obj) is not None:
                result.append(obj)
        elif kind == AnimationKind.SWAP or animation_allowed(kind, obj.kind, obj.params):
            result.append(obj)
    return result


def allowed_for_objects(scene: Scene, kind: AnimationKind, object_ids: list[str]) -> bool:
    """Return ``True`` if ``kind`` can be applied to all given objects."""
    objects = [scene.object_by_id(object_id) for object_id in object_ids]
    if not objects or any(obj is None for obj in objects):
        return False
    if kind in REFERENCE_PARAMS and not reference_candidates(scene, kind, object_ids[0]):
        return False
    return all(animation_allowed(kind, obj.kind, obj.params) for obj in objects if obj is not None)


def default_transform_target(scene: Scene, source_id: str, states: dict[str, ObjectState], kind: AnimationKind) -> str | None:
    """Pick a target for a transform: preferably an object that is not visible yet."""
    candidates = [
        obj
        for obj in scene.objects
        if obj.id != source_id and animation_allowed(kind, obj.kind, obj.params)
    ]
    hidden = [obj for obj in candidates if obj.id in states and not states[obj.id].visible]
    chosen = (hidden or candidates)[:1]
    return chosen[0].id if chosen else None


def _defaults(kind: AnimationKind, state: ObjectState | None) -> dict[str, object]:
    if kind == AnimationKind.MOVE and state is not None:
        return {"x": round(state.x + 1.0, 4), "y": round(state.y, 4)}
    if kind == AnimationKind.ORBIT and state is not None:
        return {"phi": round(state.phi, 4), "theta": round(state.theta + 45.0, 4)}
    if kind == AnimationKind.SET_VALUE and state is not None:
        return {"value": round(state.value + (1.0 if abs(state.value) < 10 else abs(state.value)), 4)}
    return {}


def build_animations(scene: Scene, kind: AnimationKind, object_ids: list[str], cursor: int) -> list[Animation]:
    """Create animations of ``kind`` for the selected objects.

    The state at ``cursor`` (the step after which the animation is inserted)
    provides defaults, e.g. the current position for a Move. For transforms,
    a selection of two objects means "first becomes second".
    """
    states = states_after(scene, cursor)
    if kind in TRANSFORM_ANIMATIONS:
        source = object_ids[0]
        target = object_ids[1] if len(object_ids) > 1 else default_transform_target(scene, source, states, kind)
        return [create_animation(kind, source, target=target)]
    if kind in REFERENCE_PARAMS:
        source = object_ids[0]
        candidates = [obj.id for obj in reference_candidates(scene, kind, source)]
        other = object_ids[1] if len(object_ids) > 1 and object_ids[1] in candidates else (candidates[:1] or [None])[0]
        return [create_animation(kind, source, **{REFERENCE_PARAMS[kind]: other})]
    return [create_animation(kind, object_id, **_defaults(kind, states.get(object_id))) for object_id in object_ids]
