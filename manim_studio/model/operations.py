"""Mutating operations on the model.

The UI never edits dataclasses directly; it calls these functions through the
undo-aware document so that every change is recorded.
"""

from __future__ import annotations

from dataclasses import fields
from typing import Any, Iterable

from manim_studio.model.entities import Animation, Project, Scene, SceneObject, Step
from manim_studio.model.factory import (
    clone_object,
    clone_scene,
    clone_step,
    remap_references,
    unique_name,
)
from manim_studio.model.schema import kind_info

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


def remove_objects(scene: Scene, object_ids: Iterable[str]) -> None:
    """Delete objects together with all animations and references using them."""
    ids = set(object_ids)
    scene.objects = [obj for obj in scene.objects if obj.id not in ids]
    for obj in scene.objects:
        if obj.params.get("axes_id") in ids:
            obj.params["axes_id"] = None
    for step in scene.steps:
        step.animations = [
            anim for anim in step.animations if anim.target_id not in ids and anim.params.get("target") not in ids
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


def translate_objects(scene: Scene, object_ids: Iterable[str], dx: float, dy: float) -> None:
    """Move objects by a delta."""
    for object_id in object_ids:
        obj = require_object(scene, object_id)
        obj.x = round(obj.x + dx, 6)
        obj.y = round(obj.y + dy, 6)


def scale_object(scene: Scene, object_id: str, factor: float) -> None:
    """Scale all size parameters of an object by ``factor``."""
    obj = require_object(scene, object_id)
    for spec in kind_info(obj.kind).params:
        if not spec.scalable:
            continue
        value = float(obj.params.get(spec.key, spec.default)) * factor
        if spec.minimum is not None:
            value = max(spec.minimum, value)
        if spec.maximum is not None:
            value = min(spec.maximum, value)
        obj.params[spec.key] = round(value, 4)


def rotate_object(scene: Scene, object_id: str, delta: float) -> None:
    """Rotate an object by ``delta`` degrees."""
    obj = require_object(scene, object_id)
    obj.rotation = round((obj.rotation + delta + 180.0) % 360.0 - 180.0, 4)


def change_z_index(scene: Scene, object_ids: Iterable[str], delta: int) -> None:
    """Move objects up (positive) or down (negative) in the layer order."""
    for object_id in object_ids:
        obj = require_object(scene, object_id)
        obj.z_index += delta


def paste_objects(scene: Scene, objects: Iterable[SceneObject], dx: float, dy: float) -> list[str]:
    """Insert copies of objects (new ids and names) and return their ids."""
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
    for clone in copies:
        if clone.params.get("axes_id") and scene.object_by_id(clone.params["axes_id"]) is None:
            if clone.params["axes_id"] not in mapping.values():
                clone.params["axes_id"] = None
        scene.objects.append(clone)
    return [clone.id for clone in copies]


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
