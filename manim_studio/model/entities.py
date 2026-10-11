"""Dataclasses forming the project model – the single source of truth."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from manim_studio.model.types import AnimationKind, ObjectKind, StepKind, Visibility


def new_id() -> str:
    """Return a new random identifier for model entities."""
    return uuid.uuid4().hex[:12]


@dataclass
class SceneObject:
    """A visual object placed on the stage.

    ``x``/``y`` are the center of the object in Manim units, ``rotation`` is in
    degrees (counter-clockwise). Type-specific values live in ``params``; the
    available keys are described in :mod:`manim_studio.model.schema`.
    """

    id: str
    kind: ObjectKind
    name: str
    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0
    stroke_color: str = "#58C4DD"
    fill_color: str = "#58C4DD"
    stroke_width: float = 4.0
    stroke_opacity: float = 1.0
    fill_opacity: float = 0.0
    z_index: int = 0
    visibility: Visibility = Visibility.AUTO
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class Animation:
    """One animation inside a timeline step."""

    id: str
    kind: AnimationKind
    target_id: str
    run_time: float = 1.0
    rate_func: str = "smooth"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class Step:
    """A timeline step: one ``self.play(...)`` or one ``self.wait(...)``."""

    id: str
    kind: StepKind = StepKind.PLAY
    animations: list[Animation] = field(default_factory=list)
    wait_time: float = 1.0

    def duration(self) -> float:
        """Return how long the step lasts in seconds."""
        if self.kind == StepKind.WAIT:
            return self.wait_time
        return max((anim.run_time for anim in self.animations), default=0.0)


@dataclass
class Scene:
    """A Manim scene with its objects and timeline."""

    id: str
    name: str
    background_color: str = "#000000"
    objects: list[SceneObject] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)

    def object_by_id(self, object_id: str | None) -> SceneObject | None:
        """Return the object with the given id or ``None``."""
        for obj in self.objects:
            if obj.id == object_id:
                return obj
        return None

    def step_by_id(self, step_id: str | None) -> Step | None:
        """Return the step with the given id or ``None``."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def step_index(self, step_id: str | None) -> int:
        """Return the index of a step or -1 if it does not exist."""
        for index, step in enumerate(self.steps):
            if step.id == step_id:
                return index
        return -1

    def find_animation(self, animation_id: str | None) -> tuple[Step, Animation] | None:
        """Return ``(step, animation)`` for an animation id or ``None``."""
        for step in self.steps:
            for anim in step.animations:
                if anim.id == animation_id:
                    return step, anim
        return None


@dataclass
class RenderSettings:
    """Export settings stored with the project."""

    quality: str = "h"
    width: int = 1920
    height: int = 1080
    fps: int = 60
    format: str = "mp4"
    output_dir: str = ""
    png_after_step: int = -1


@dataclass
class Project:
    """A complete Manim Studio project."""

    scenes: list[Scene] = field(default_factory=list)
    render: RenderSettings = field(default_factory=RenderSettings)

    def scene_by_id(self, scene_id: str | None) -> Scene | None:
        """Return the scene with the given id or ``None``."""
        for scene in self.scenes:
            if scene.id == scene_id:
                return scene
        return None
