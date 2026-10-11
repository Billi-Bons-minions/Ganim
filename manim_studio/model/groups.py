"""Groups (Manim ``VGroup``): membership queries and geometry."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.extents import base_size, rotated_extent
from manim_studio.model.types import ObjectKind

if TYPE_CHECKING:
    from manim_studio.model.state import ObjectState


def is_group(obj: SceneObject | None) -> bool:
    """Return ``True`` for group objects."""
    return obj is not None and obj.kind == ObjectKind.GROUP


def members(scene: Scene, group_id: str) -> list[str]:
    """Return the direct member ids of a group (existing objects only)."""
    group = scene.object_by_id(group_id)
    if not is_group(group):
        return []
    return [member for member in group.params.get("members", []) if scene.object_by_id(member) is not None]


def leaves(scene: Scene, object_id: str, _seen: set[str] | None = None) -> list[str]:
    """Return all non-group objects inside ``object_id`` (itself if it is no group)."""
    seen = _seen if _seen is not None else set()
    if object_id in seen:
        return []
    seen.add(object_id)
    obj = scene.object_by_id(object_id)
    if obj is None:
        return []
    if not is_group(obj):
        return [object_id]
    result: list[str] = []
    for member in members(scene, object_id):
        result += leaves(scene, member, seen)
    return result


def parent_group(scene: Scene, object_id: str) -> str | None:
    """Return the group that directly contains ``object_id``."""
    for obj in scene.objects:
        if is_group(obj) and object_id in obj.params.get("members", []):
            return obj.id
    return None


def ancestors(scene: Scene, object_id: str) -> list[str]:
    """Return the groups containing ``object_id``, innermost first."""
    result: list[str] = []
    current = parent_group(scene, object_id)
    while current is not None and current not in result:
        result.append(current)
        current = parent_group(scene, current)
    return result


def top_level(scene: Scene, object_id: str) -> str:
    """Return the outermost group containing ``object_id`` (or the object itself)."""
    chain = ancestors(scene, object_id)
    return chain[-1] if chain else object_id


def nesting_depth(scene: Scene, object_id: str) -> int:
    """Return how many groups are nested inside a group (0 for plain objects)."""
    obj = scene.object_by_id(object_id)
    if not is_group(obj):
        return 0
    return 1 + max((nesting_depth(scene, member) for member in members(scene, object_id)), default=0)


def bounds_of(scene: Scene, object_ids: list[str], states: dict[str, ObjectState]) -> tuple[float, float, float, float]:
    """Return ``(left, bottom, right, top)`` of objects using their states."""
    left = bottom = math.inf
    right = top = -math.inf
    for object_id in object_ids:
        obj = scene.object_by_id(object_id)
        state = states.get(object_id)
        if obj is None or state is None:
            continue
        shape = scene.object_by_id(state.shape_id) or obj
        width, height = base_size(scene, shape)
        width, height = rotated_extent(width * state.scale, height * state.scale, state.rotation)
        left, right = min(left, state.x - width / 2), max(right, state.x + width / 2)
        bottom, top = min(bottom, state.y - height / 2), max(top, state.y + height / 2)
    if left == math.inf:
        return 0.0, 0.0, 0.0, 0.0
    return left, bottom, right, top


def group_center(scene: Scene, group_id: str, states: dict[str, ObjectState]) -> tuple[float, float]:
    """Return the center of a group's members."""
    left, bottom, right, top = bounds_of(scene, leaves(scene, group_id), states)
    return (left + right) / 2, (bottom + top) / 2


def group_center_of_objects(scene: Scene, group_id: str) -> tuple[float, float]:
    """Return the center of a group from the members' start values."""
    from manim_studio.model.state import ObjectState

    states = {}
    for object_id in leaves(scene, group_id):
        obj = scene.object_by_id(object_id)
        if obj is not None:
            states[object_id] = ObjectState(object_id, object_id, True, obj.x, obj.y, obj.rotation, 1.0, obj.stroke_color, obj.fill_color)
    return group_center(scene, group_id, states)
