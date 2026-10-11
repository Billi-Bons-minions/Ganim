"""Factories that create model entities with sensible defaults."""

from __future__ import annotations

import copy
import re
from typing import Any, Iterable

from manim_studio.model.entities import (
    Animation,
    Project,
    RenderSettings,
    Scene,
    SceneObject,
    Step,
    new_id,
)
from manim_studio.model.schema import (
    DEFAULT_RATE_FUNC,
    animation_params,
    default_params,
    kind_info,
)
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind

_NUMBERED = re.compile(r"^(.*?)\s+(\d+)$")


def unique_name(existing: Iterable[str], base: str) -> str:
    """Return ``"<base> <n>"`` with the smallest ``n`` not yet used."""
    used = set(existing)
    match = _NUMBERED.match(base)
    stem = match.group(1) if match else base
    number = 1
    while f"{stem} {number}" in used:
        number += 1
    return f"{stem} {number}"


def create_object(kind: ObjectKind, name: str, x: float = 0.0, y: float = 0.0, **params: Any) -> SceneObject:
    """Create an object with the default style and parameters of its kind."""
    info = kind_info(kind)
    obj = SceneObject(id=new_id(), kind=kind, name=name, x=x, y=y, params=default_params(info.params))
    for key, value in info.default_style:
        setattr(obj, key, value)
    obj.params.update(params)
    return obj


def create_animation(kind: AnimationKind, target_id: str, run_time: float = 1.0, **params: Any) -> Animation:
    """Create an animation with default parameters for its kind."""
    values = default_params(animation_params(kind))
    values.update(params)
    rate_func = DEFAULT_RATE_FUNC.get(kind, "smooth")
    return Animation(id=new_id(), kind=kind, target_id=target_id, run_time=run_time, rate_func=rate_func, params=values)


def create_play_step(animations: Iterable[Animation] = ()) -> Step:
    """Create a step that plays the given animations simultaneously."""
    return Step(id=new_id(), kind=StepKind.PLAY, animations=list(animations))


def create_wait_step(seconds: float = 1.0) -> Step:
    """Create a waiting step."""
    return Step(id=new_id(), kind=StepKind.WAIT, wait_time=seconds)


def create_scene(name: str) -> Scene:
    """Create an empty scene."""
    return Scene(id=new_id(), name=name)


def create_project(scene_name: str) -> Project:
    """Create a project with one empty scene."""
    return Project(scenes=[create_scene(scene_name)], render=RenderSettings())


def clone_object(obj: SceneObject, name: str | None = None) -> SceneObject:
    """Return a deep copy of an object with a new id."""
    clone = copy.deepcopy(obj)
    clone.id = new_id()
    if name is not None:
        clone.name = name
    return clone


def clone_animation(anim: Animation) -> Animation:
    """Return a deep copy of an animation with a new id."""
    clone = copy.deepcopy(anim)
    clone.id = new_id()
    return clone


def clone_step(step: Step) -> Step:
    """Return a deep copy of a step with new ids."""
    clone = copy.deepcopy(step)
    clone.id = new_id()
    clone.animations = [clone_animation(anim) for anim in step.animations]
    return clone


def remap_references(objects: Iterable[SceneObject], steps: Iterable[Step], mapping: dict[str, str]) -> None:
    """Replace object ids in references according to ``mapping``."""
    for obj in objects:
        axes_id = obj.params.get("axes_id")
        if axes_id in mapping:
            obj.params["axes_id"] = mapping[axes_id]
    for step in steps:
        for anim in step.animations:
            anim.target_id = mapping.get(anim.target_id, anim.target_id)
            target = anim.params.get("target")
            if target in mapping:
                anim.params["target"] = mapping[target]


def clone_scene(scene: Scene, name: str) -> Scene:
    """Return a deep copy of a scene where every entity has a new id."""
    objects = [clone_object(obj) for obj in scene.objects]
    mapping = {old.id: new.id for old, new in zip(scene.objects, objects)}
    steps = [clone_step(step) for step in scene.steps]
    remap_references(objects, steps, mapping)
    return Scene(id=new_id(), name=name, background_color=scene.background_color, objects=objects, steps=steps)
