"""Mutating operations on the model.

The UI never edits dataclasses directly; it calls these functions through the
undo-aware document so that every change is recorded.
"""

from __future__ import annotations

from dataclasses import fields
from typing import Any, Iterable

from manim_studio.model.entities import Animation, Project, Scene, SceneObject, Step
from manim_studio.model.factory import (
    ANIMATION_REFERENCE_KEYS,
    OBJECT_REFERENCE_KEYS,
    clone_object,
    clone_scene,
    clone_step,
    remap_references,
    unique_name,
)
from manim_studio.model.schema import kind_info
from manim_studio.model.types import CURVE_DERIVATIVE, GRAPH_TOOL_KINDS, ObjectKind, StepKind

_OBJECT_FIELDS = {f.name for f in fields(SceneObject)} - {"id", "kind", "params"}
_ANIMATION_FIELDS = {"run_time", "rate_func", "target_id", "kind"}


class ModelError(ValueError):
    """Raised when an operation refers to missing entities."""


def require_scene(project: Project, scene_id: str) -> Scene:
    """Return a scene or raise :class:`ModelError`."""
    scene = project.scene_by_id(scene_id)
    if scene is None:
        raise ModelError(f"unknown scene {scene_id}")
    return scene


def require_object(scene: Scene, object_id: str) -> SceneObject:
    """Return an object or raise :class:`ModelError`."""
    obj = scene.object_by_id(object_id)
    if obj is None:
        raise ModelError(f"unknown object {object_id}")
    return obj


def require_step(scene: Scene, step_id: str) -> Step:
    """Return a step or raise :class:`ModelError`."""
    step = scene.step_by_id(step_id)
    if step is None:
        raise ModelError(f"unknown step {step_id}")
    return step


def require_animation(scene: Scene, animation_id: str) -> Animation:
    """Return an animation or raise :class:`ModelError`."""
    found = scene.find_animation(animation_id)
    if found is None:
        raise ModelError(f"unknown animation {animation_id}")
    return found[1]


# --- objects -----------------------------------------------------------------


def add_object(scene: Scene, obj: SceneObject, index: int | None = None) -> str:
    """Insert an object and return its id."""
    position = len(scene.objects) if index is None else max(0, min(index, len(scene.objects)))
    scene.objects.insert(position, obj)
    return obj.id


#: Object parameters that refer to other objects.
REFERENCE_PARAMS = OBJECT_REFERENCE_KEYS


def expand_for_delete(scene: Scene, object_ids: Iterable[str]) -> set[str]:
    ids: set[str] = set()
    for object_id in object_ids:
        ids.add(object_id)
        obj = scene.object_by_id(object_id)
        if obj is not None and obj.kind.value == "group":
            ids |= expand_for_delete(scene, obj.params.get("members", []))
    return ids


def dependent_objects(scene: Scene, object_ids: Iterable[str]) -> set[str]:
    """Objects that cannot exist without the given ones (a tangent without its graph ...)."""
    removed = set(object_ids)
    found: set[str] = set()
    changed = True
    while changed:
        changed = False
        for obj in scene.objects:
            if obj.id in removed or obj.id in found:
                continue
            params = obj.params
            needs = (
                (obj.kind in GRAPH_TOOL_KINDS and params.get("graph_id"))
                or (obj.kind == ObjectKind.HIGHLIGHT and params.get("target"))
                or (obj.kind in (ObjectKind.DATA_PLOT, ObjectKind.SURFACE, ObjectKind.CURVE_3D) and params.get("axes_id"))
                or (obj.kind == ObjectKind.FUNCTION_GRAPH and params.get("curve") == CURVE_DERIVATIVE and params.get("derive_from"))
            )
            if needs and needs in removed | found:
                found.add(obj.id)
                changed = True
    return found


def remove_objects(scene: Scene, object_ids: Iterable[str]) -> None:
    """Delete objects (groups with their members), their dependents and every reference to them."""
    ids = expand_for_delete(scene, object_ids)
    ids |= dependent_objects(scene, ids)
    scene.objects = [obj for obj in scene.objects if obj.id not in ids]
    for obj in scene.objects:
        for key in REFERENCE_PARAMS:
            if obj.params.get(key) in ids:
                obj.params[key] = None
        if isinstance(obj.params.get("members"), list):
            obj.params["members"] = [member for member in obj.params["members"] if member not in ids]
    empty_groups = [obj.id for obj in scene.objects if obj.kind.value == "group" and not obj.params.get("members")]
    if empty_groups:
        scene.objects = [obj for obj in scene.objects if obj.id not in empty_groups]
    for step in scene.steps:
        step.animations = [
            anim
            for anim in step.animations
            if anim.target_id not in ids | set(empty_groups) and not any(anim.params.get(key) in ids for key in ANIMATION_REFERENCE_KEYS)
        ]


def update_object(scene: Scene, object_id: str, **values: Any) -> None:
    """Set top-level attributes of an object (``x``, ``name``, ``fill_color`` ...)."""
    obj = require_object(scene, object_id)
    for key, value in values.items():
        if key not in _OBJECT_FIELDS:
            raise ModelError(f"unknown object field {key}")
        setattr(obj, key, value)


def set_object_param(scene: Scene, object_id: str, key: str, value: Any) -> None:
    """Set a kind-specific parameter of an object."""
    obj = require_object(scene, object_id)
    if kind_info(obj.kind).param(key) is None:
        raise ModelError(f"unknown parameter {key} for {obj.kind.value}")
    obj.params[key] = value
    if obj.kind == ObjectKind.HIGHLIGHT and key in ("style", "target"):
        place_highlight(scene, obj.id)


def place_highlight(scene: Scene, object_id: str) -> None:
    """A background highlight lies directly behind its target, the other styles in front of it."""
    from manim_studio.model.arrange import drawing_order, move_layer

    obj = scene.object_by_id(object_id)
    target = scene.object_by_id(obj.params.get("target")) if obj is not None else None
    if obj is None or target is None or target.id == obj.id:
        return
    order = drawing_order(scene)
    if obj.id not in order or target.id not in order:
        return
    behind = obj.params.get("style") == "background"
    if behind and order.index(obj.id) > order.index(target.id):
        move_layer(scene, obj.id, None, target.id)
    elif not behind and order.index(obj.id) < order.index(target.id):
        move_layer(scene, obj.id, target.id, None)


def _movable_leaves(scene: Scene, object_ids: Iterable[str]) -> list[str]:
    from manim_studio.model import groups

    result: list[str] = []
    for object_id in object_ids:
        for leaf in groups.leaves(scene, object_id):
            if leaf not in result:
                result.append(leaf)
    return result


def translate_objects(scene: Scene, object_ids: Iterable[str], dx: float, dy: float) -> None:
    """Move objects (groups move all their members) by a delta."""
    for object_id in _movable_leaves(scene, object_ids):
        obj = require_object(scene, object_id)
        obj.x = round(obj.x + dx, 6)
        obj.y = round(obj.y + dy, 6)


def _scale_params(obj: SceneObject, factor: float) -> None:
    for spec in kind_info(obj.kind).params:
        if not spec.scalable:
            continue
        if spec.key == "points":
            obj.params["points"] = [[round(float(x) * factor, 4), round(float(y) * factor, 4)] for x, y in obj.params.get("points", [])]
            continue
        value = float(obj.params.get(spec.key, spec.default)) * factor
        if spec.minimum is not None:
            value = max(spec.minimum, value)
        if spec.maximum is not None:
            value = min(spec.maximum, value)
        obj.params[spec.key] = round(value, 4)


def scale_object(scene: Scene, object_id: str, factor: float) -> None:
    """Scale an object's size parameters (groups: members around the group center)."""
    from manim_studio.model import groups

    obj = require_object(scene, object_id)
    if not groups.is_group(obj):
        _scale_params(obj, factor)
        return
    cx, cy = groups.group_center_of_objects(scene, object_id)
    for leaf in groups.leaves(scene, object_id):
        member = require_object(scene, leaf)
        _scale_params(member, factor)
        member.x = round(cx + (member.x - cx) * factor, 6)
        member.y = round(cy + (member.y - cy) * factor, 6)


def rotate_object(scene: Scene, object_id: str, delta: float) -> None:
    """Rotate an object by ``delta`` degrees (groups: around the group center)."""
    import math

    from manim_studio.model import groups

    obj = require_object(scene, object_id)
    targets = groups.leaves(scene, object_id) if groups.is_group(obj) else [object_id]
    cx, cy = groups.group_center_of_objects(scene, object_id) if groups.is_group(obj) else (obj.x, obj.y)
    radians = math.radians(delta)
    for leaf in targets:
        member = require_object(scene, leaf)
        member.rotation = round((member.rotation + delta + 180.0) % 360.0 - 180.0, 4)
        if groups.is_group(obj):
            dx, dy = member.x - cx, member.y - cy
            member.x = round(cx + dx * math.cos(radians) - dy * math.sin(radians), 6)
            member.y = round(cy + dx * math.sin(radians) + dy * math.cos(radians), 6)


def group_objects(scene: Scene, object_ids: list[str], name: str) -> str:
    """Put objects into a new group and return the group id."""
    from manim_studio.model import groups
    from manim_studio.model.factory import create_object
    from manim_studio.model.types import ObjectKind

    ids = [object_id for object_id in dict.fromkeys(object_ids) if scene.object_by_id(object_id) is not None]
    if len(ids) < 2:
        raise ModelError("a group needs at least two objects")
    for object_id in ids:
        parent = groups.parent_group(scene, object_id)
        if parent is not None:
            require_object(scene, parent).params["members"].remove(object_id)
    group = create_object(ObjectKind.GROUP, name, members=list(ids))
    first = min(scene.objects.index(require_object(scene, object_id)) for object_id in ids)
    scene.objects.insert(first, group)
    return group.id


def ungroup(scene: Scene, group_id: str) -> list[str]:
    """Dissolve a group; its animations are copied to the members. Returns the members."""
    from manim_studio.model import groups
    from manim_studio.model.factory import clone_animation
    from manim_studio.model.types import TRANSFORM_ANIMATIONS

    group = require_object(scene, group_id)
    if not groups.is_group(group):
        raise ModelError("not a group")
    member_ids = list(group.params.get("members", []))
    parent = groups.parent_group(scene, group_id)
    if parent is not None:
        parent_members = require_object(scene, parent).params["members"]
        index = parent_members.index(group_id)
        parent_members[index:index + 1] = member_ids
    for step in scene.steps:
        updated: list[Animation] = []
        for anim in step.animations:
            if anim.target_id != group_id:
                updated.append(anim)
                continue
            if anim.kind in TRANSFORM_ANIMATIONS:
                continue
            for member in member_ids:
                copy_anim = clone_animation(anim)
                copy_anim.target_id = member
                updated.append(copy_anim)
        step.animations = updated
    scene.objects.remove(group)
    for obj in scene.objects:
        if obj.params.get("target") == group_id:
            obj.params["target"] = None
    return member_ids


def reorder_objects(scene: Scene, ordered_ids: list[str]) -> None:
    """Reorder the object list (drawing order) to match ``ordered_ids``."""
    by_id = {obj.id: obj for obj in scene.objects}
    if sorted(ordered_ids) != sorted(by_id):
        raise ModelError("object order does not match the scene")
    scene.objects = [by_id[object_id] for object_id in ordered_ids]


def set_editor_flags(scene: Scene, object_ids: Iterable[str], locked: bool | None = None, hidden: bool | None = None) -> None:
    """Lock or hide objects in the editor (has no effect on the rendered video)."""
    for object_id in object_ids:
        obj = require_object(scene, object_id)
        if locked is not None:
            obj.locked = locked
        if hidden is not None:
            obj.editor_hidden = hidden


def _points_center(points: list[list[float]]) -> tuple[float, float]:
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def _set_points_anchored(obj: SceneObject, points: list[list[float]]) -> None:
    """Replace the vertices and shift the center so that unchanged vertices stay in place.

    The object position is the center of the vertices' bounding box (Manim's
    ``move_to``), so the center moves with the bounding box, rotated like the shape.
    """
    import math

    old = obj.params.get("points", [])
    if old and points:
        (ox, oy), (nx, ny) = _points_center(old), _points_center(points)
        dx, dy = nx - ox, ny - oy
        radians = math.radians(obj.rotation)
        obj.x = round(obj.x + dx * math.cos(radians) - dy * math.sin(radians), 6)
        obj.y = round(obj.y + dx * math.sin(radians) + dy * math.cos(radians), 6)
    obj.params["points"] = points


def _polygon_points(obj: SceneObject) -> list[list[float]]:
    return [[float(x), float(y)] for x, y in obj.params.get("points", [])]


def set_polygon_point(scene: Scene, object_id: str, index: int, x: float, y: float) -> None:
    """Move one vertex of a polygon (in the polygon's own coordinates); the others keep their place."""
    obj = require_object(scene, object_id)
    points = _polygon_points(obj)
    if not 0 <= index < len(points):
        raise ModelError("unknown vertex")
    points[index] = [round(x, 4), round(y, 4)]
    _set_points_anchored(obj, points)


def insert_polygon_point(scene: Scene, object_id: str, index: int, x: float, y: float) -> None:
    """Insert a vertex before ``index``."""
    obj = require_object(scene, object_id)
    points = _polygon_points(obj)
    points.insert(max(0, min(index, len(points))), [round(x, 4), round(y, 4)])
    _set_points_anchored(obj, points)


def remove_polygon_point(scene: Scene, object_id: str, index: int) -> None:
    """Remove a vertex (at least three remain)."""
    obj = require_object(scene, object_id)
    points = _polygon_points(obj)
    if len(points) <= 3:
        raise ModelError("a polygon needs at least three vertices")
    if not 0 <= index < len(points):
        raise ModelError("unknown vertex")
    points.pop(index)
    _set_points_anchored(obj, points)


MIN_LINE_LENGTH = 0.05


def line_endpoints(obj: SceneObject) -> tuple[tuple[float, float], tuple[float, float]]:
    """Return the start and end point of a line-like object."""
    import math

    half = float(obj.params.get("length", 3.0)) / 2
    radians = math.radians(obj.rotation)
    dx, dy = half * math.cos(radians), half * math.sin(radians)
    return (obj.x - dx, obj.y - dy), (obj.x + dx, obj.y + dy)


def set_line_endpoint(scene: Scene, object_id: str, which: int, x: float, y: float) -> None:
    """Move the start (0) or end (1) of a line; the other end stays where it is."""
    import math

    obj = require_object(scene, object_id)
    ends = list(line_endpoints(obj))
    ends[1 if which else 0] = (x, y)
    (x0, y0), (x1, y1) = ends
    length = math.hypot(x1 - x0, y1 - y0)
    if length < MIN_LINE_LENGTH:
        raise ModelError("line too short")
    obj.x, obj.y = round((x0 + x1) / 2, 6), round((y0 + y1) / 2, 6)
    obj.rotation = round(math.degrees(math.atan2(y1 - y0, x1 - x0)), 6)
    obj.params["length"] = round(length, 6)


def apply_style(scene: Scene, object_ids: Iterable[str], values: dict[str, Any]) -> None:
    """Give objects (and the members of groups) a saved look where it applies."""
    from manim_studio.model import groups

    for object_id in object_ids:
        for leaf in groups.leaves(scene, object_id):
            obj = require_object(scene, leaf)
            info = kind_info(obj.kind)
            for key, value in values.items():
                if key in info.style:
                    setattr(obj, key, value)
                elif info.param(key) is not None:
                    obj.params[key] = value


def change_z_index(scene: Scene, object_ids: Iterable[str], delta: int) -> None:
    """Move objects up (positive) or down (negative) in the layer order."""
    for object_id in object_ids:
        obj = require_object(scene, object_id)
        obj.z_index += delta


def paste_objects(scene: Scene, objects: Iterable[SceneObject], dx: float, dy: float) -> list[str]:
    """Insert copies of objects (new ids and names) and return the top-level ids.

    Groups keep their members if they are part of ``objects``; references to
    objects that are not copied stay as they are (or are cleared if missing).
    """
    originals = list(objects)
    copies: list[SceneObject] = []
    names = [obj.name for obj in scene.objects]
    for original in originals:
        clone = clone_object(original, unique_name(names, original.name))
        names.append(clone.name)
        clone.x = round(clone.x + dx, 6)
        clone.y = round(clone.y + dy, 6)
        copies.append(clone)
    mapping = {old.id: new.id for old, new in zip(originals, copies)}
    remap_references(copies, [], mapping)
    existing = {obj.id for obj in scene.objects} | set(mapping.values())
    for clone in copies:
        for key in REFERENCE_PARAMS:
            if clone.params.get(key) and clone.params[key] not in existing:
                clone.params[key] = None
        if isinstance(clone.params.get("members"), list):
            clone.params["members"] = [member for member in clone.params["members"] if member in mapping.values()]
        scene.objects.append(clone)
    member_ids = {member for clone in copies for member in clone.params.get("members", []) or []}
    return [clone.id for clone in copies if clone.id not in member_ids]


# --- steps and animations ----------------------------------------------------


def add_step(scene: Scene, step: Step, index: int | None = None) -> str:
    """Insert a step (at the end by default) and return its id."""
    position = len(scene.steps) if index is None else max(0, min(index, len(scene.steps)))
    scene.steps.insert(position, step)
    return step.id


def remove_steps(scene: Scene, step_ids: Iterable[str]) -> None:
    """Delete steps."""
    ids = set(step_ids)
    scene.steps = [step for step in scene.steps if step.id not in ids]


def duplicate_step(scene: Scene, step_id: str) -> str:
    """Insert a copy of a step right after it and return the new id."""
    index = scene.step_index(step_id)
    if index < 0:
        raise ModelError(f"unknown step {step_id}")
    clone = clone_step(scene.steps[index])
    scene.steps.insert(index + 1, clone)
    return clone.id


def reorder_steps(scene: Scene, ordered_ids: list[str]) -> None:
    """Reorder steps to match ``ordered_ids`` (must contain every step id once)."""
    by_id = {step.id: step for step in scene.steps}
    if sorted(ordered_ids) != sorted(by_id):
        raise ModelError("step order does not match the scene")
    scene.steps = [by_id[step_id] for step_id in ordered_ids]


def move_step(scene: Scene, step_id: str, new_index: int) -> None:
    """Move one step to a new position."""
    step = require_step(scene, step_id)
    scene.steps.remove(step)
    scene.steps.insert(max(0, min(new_index, len(scene.steps))), step)


def set_wait_time(scene: Scene, step_id: str, seconds: float) -> None:
    """Change the duration of a waiting step."""
    require_step(scene, step_id).wait_time = max(0.01, float(seconds))


STEP_FIELDS = ("section", "subcaption", "sound", "sound_gain", "sound_offset", "code", "wait_time")


def set_step_fields(scene: Scene, step_id: str, **values: Any) -> None:
    """Change section, subtitle, sound or code of a step."""
    step = require_step(scene, step_id)
    for key, value in values.items():
        if key not in STEP_FIELDS:
            raise ModelError(f"unknown step field {key}")
        setattr(step, key, value)


def add_animation(scene: Scene, step_id: str, anim: Animation, index: int | None = None) -> str:
    """Add an animation to a step and return its id."""
    step = require_step(scene, step_id)
    position = len(step.animations) if index is None else max(0, min(index, len(step.animations)))
    step.animations.insert(position, anim)
    return anim.id


def remove_animations(scene: Scene, animation_ids: Iterable[str]) -> None:
    """Delete animations from their steps."""
    ids = set(animation_ids)
    for step in scene.steps:
        step.animations = [anim for anim in step.animations if anim.id not in ids]


def update_animation(scene: Scene, animation_id: str, **values: Any) -> None:
    """Set ``run_time``, ``rate_func``, ``target_id`` or ``kind`` of an animation."""
    anim = require_animation(scene, animation_id)
    for key, value in values.items():
        if key not in _ANIMATION_FIELDS:
            raise ModelError(f"unknown animation field {key}")
        setattr(anim, key, value)


def set_animation_param(scene: Scene, animation_id: str, key: str, value: Any) -> None:
    """Set a kind-specific parameter of an animation."""
    require_animation(scene, animation_id).params[key] = value


def set_animation_timing(scene: Scene, animation_id: str, delay: float | None = None, run_time: float | None = None) -> None:
    """Change the delay and/or duration of an animation."""
    anim = require_animation(scene, animation_id)
    if delay is not None:
        anim.delay = round(max(0.0, float(delay)), 4)
    if run_time is not None:
        anim.run_time = round(max(0.05, float(run_time)), 4)


def move_animation(scene: Scene, animation_id: str, step_id: str, index: int | None = None) -> None:
    """Move an animation into another step; an emptied play step is removed."""
    found = scene.find_animation(animation_id)
    target = require_step(scene, step_id)
    if found is None:
        raise ModelError(f"unknown animation {animation_id}")
    source, anim = found
    if target.kind != StepKind.PLAY:
        raise ModelError("animations can only be moved into play steps")
    source.animations.remove(anim)
    position = len(target.animations) if index is None else max(0, min(index, len(target.animations)))
    target.animations.insert(position, anim)
    if source is not target and not source.animations:
        scene.steps.remove(source)


def move_animation_to_new_step(scene: Scene, animation_id: str, step_index: int) -> str:
    """Put an animation into a new play step at ``step_index`` and return the step id."""
    from manim_studio.model.factory import create_play_step

    step = create_play_step()
    add_step(scene, step, step_index)
    move_animation(scene, animation_id, step.id)
    return step.id


def duplicate_animation(scene: Scene, animation_id: str) -> str:
    """Insert a copy of an animation right after it and return the new id."""
    from manim_studio.model.factory import clone_animation

    found = scene.find_animation(animation_id)
    if found is None:
        raise ModelError(f"unknown animation {animation_id}")
    step, anim = found
    clone = clone_animation(anim)
    step.animations.insert(step.animations.index(anim) + 1, clone)
    return clone.id


def set_step_mode(scene: Scene, step_id: str, mode: str, lag_ratio: float | None = None) -> None:
    """Change how the animations of a step are arranged in time."""
    from manim_studio.model.entities import STEP_MODES

    step = require_step(scene, step_id)
    if mode not in STEP_MODES:
        raise ModelError(f"unknown step mode {mode}")
    step.mode = mode
    if lag_ratio is not None:
        step.lag_ratio = round(max(0.0, min(1.0, float(lag_ratio))), 4)


# --- scenes ------------------------------------------------------------------


def add_scene(project: Project, scene: Scene, index: int | None = None) -> str:
    """Insert a scene and return its id."""
    position = len(project.scenes) if index is None else max(0, min(index, len(project.scenes)))
    project.scenes.insert(position, scene)
    return scene.id


def remove_scene(project: Project, scene_id: str) -> None:
    """Delete a scene; the last remaining scene cannot be deleted."""
    if len(project.scenes) <= 1:
        raise ModelError("a project needs at least one scene")
    project.scenes.remove(require_scene(project, scene_id))


def rename_scene(project: Project, scene_id: str, name: str) -> None:
    """Rename a scene."""
    require_scene(project, scene_id).name = name


def duplicate_scene(project: Project, scene_id: str, name: str) -> str:
    """Insert a copy of a scene after it and return the new id."""
    scene = require_scene(project, scene_id)
    clone = clone_scene(scene, name)
    project.scenes.insert(project.scenes.index(scene) + 1, clone)
    return clone.id


def move_scene(project: Project, scene_id: str, new_index: int) -> None:
    """Move a scene to another position."""
    scene = require_scene(project, scene_id)
    project.scenes.remove(scene)
    project.scenes.insert(max(0, min(new_index, len(project.scenes))), scene)


def set_background(scene: Scene, color: str) -> None:
    """Change the background color of a scene."""
    scene.background_color = color
