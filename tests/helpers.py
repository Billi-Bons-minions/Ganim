"""Builders shared by the tests (fixed ids keep expectations readable)."""

from __future__ import annotations

from manim_studio.model.entities import Animation, Project, Scene, SceneObject, Step
from manim_studio.model.factory import create_animation, create_object
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind


def make_object(kind: ObjectKind, name: str, object_id: str, x: float = 0.0, y: float = 0.0, **params) -> SceneObject:
    """Create an object with a fixed id."""
    obj = create_object(kind, name, x, y, **params)
    obj.id = object_id
    return obj


def make_animation(kind: AnimationKind, target_id: str, anim_id: str = "", **params) -> Animation:
    """Create an animation with a fixed id."""
    anim = create_animation(kind, target_id, **params)
    anim.id = anim_id or f"{kind.value}-{target_id}"
    return anim


def play(*animations: Animation, step_id: str = "") -> Step:
    """Create a play step."""
    return Step(id=step_id or "step-" + "-".join(a.id for a in animations), kind=StepKind.PLAY, animations=list(animations))


def wait(seconds: float, step_id: str = "wait") -> Step:
    """Create a waiting step."""
    return Step(id=step_id, kind=StepKind.WAIT, wait_time=seconds)


def make_project(*scenes: Scene) -> Project:
    """Create a project from scenes."""
    return Project(scenes=list(scenes))


def acceptance_scene() -> Scene:
    """Circle and text; the circle is created, turned into a square, the text is written."""
    circle = make_object(ObjectKind.CIRCLE, "Kreis 1", "c1", -3.0, 0.0)
    square = make_object(ObjectKind.SQUARE, "Quadrat 1", "s1", -3.0, 0.0)
    text = make_object(ObjectKind.TEXT, "Text 1", "t1", 2.0, 1.5, text="Hallo Manim")
    steps = [
        play(make_animation(AnimationKind.CREATE, "c1")),
        play(make_animation(AnimationKind.TRANSFORM, "c1", target="s1")),
        play(make_animation(AnimationKind.WRITE, "t1")),
    ]
    return Scene(id="scene1", name="Szene 1", objects=[circle, square, text], steps=steps)
