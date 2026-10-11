"""Create new animations with sensible defaults for the selected objects."""

from __future__ import annotations

from manim_studio.model.entities import Animation, Scene
from manim_studio.model.factory import create_animation
from manim_studio.model.schema import animation_allowed
from manim_studio.model.state import ObjectState, states_after
from manim_studio.model.types import TRANSFORM_ANIMATIONS, AnimationKind


def allowed_for_objects(scene: Scene, kind: AnimationKind, object_ids: list[str]) -> bool:
    """Return ``True`` if ``kind`` can be applied to all given objects."""
    objects = [scene.object_by_id(object_id) for object_id in object_ids]
    if not objects or any(obj is None for obj in objects):
        return False
    if kind in TRANSFORM_ANIMATIONS and len(scene.objects) < 2:
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
    return [create_animation(kind, object_id, **_defaults(kind, states.get(object_id))) for object_id in object_ids]
