"""Built-in example projects (created in code, texts in the active language)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from manim_studio.i18n import tr
from manim_studio.model.entities import Project, Scene, SceneObject
from manim_studio.model.factory import create_animation, create_object, create_play_step, create_project, create_wait_step
from manim_studio.model.types import AnimationKind, ObjectKind


@dataclass(frozen=True)
class Example:
    """An example project shown in the welcome dialog."""

    key: str
    icon: str
    needs_latex: bool
    build: Callable[[], Project]


def _scene(name_key: str) -> tuple[Project, Scene]:
    project = create_project(tr(name_key))
    return project, project.scenes[0]


def _add(scene: Scene, obj: SceneObject) -> SceneObject:
    scene.objects.append(obj)
    return obj


def _play(scene: Scene, *animations) -> None:
    scene.steps.append(create_play_step(animations))


def circle_to_square() -> Project:
    """A circle appears, turns into a square, then a text is written."""
    project, scene = _scene("example.circle_to_square.scene")
    circle = _add(scene, create_object(ObjectKind.CIRCLE, tr("kind.circle") + " 1", -3.0, 0.0, radius=1.4))
    circle.fill_opacity = 0.4
    square = _add(scene, create_object(ObjectKind.SQUARE, tr("kind.square") + " 1", -3.0, 0.0, side_length=2.6))
    square.fill_opacity = 0.4
    text = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 1", 2.4, 0.0, text="Hallo Manim!"))
    _play(scene, create_animation(AnimationKind.CREATE, circle.id))
    _play(scene, create_animation(AnimationKind.TRANSFORM, circle.id, target=square.id))
    _play(scene, create_animation(AnimationKind.WRITE, text.id, run_time=1.5))
    _play(scene, create_animation(AnimationKind.INDICATE, text.id))
    return project


def function_graph() -> Project:
    """Axes, a sine graph and a title."""
    project, scene = _scene("example.function_graph.scene")
    axes = _add(scene, create_object(ObjectKind.AXES, tr("kind.axes") + " 1", 0.0, -0.4, show_numbers=True, x_length=11.0, y_length=5.5))
    graph = _add(scene, create_object(ObjectKind.FUNCTION_GRAPH, tr("kind.function_graph") + " 1", expression="2 sin(x)", axes_id=axes.id))
    graph.stroke_width = 5.0
    title = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 1", 0.0, 3.3, text="f(x) = 2·sin(x)", font_size=40.0))
    _play(scene, create_animation(AnimationKind.CREATE, axes.id, run_time=1.5))
    _play(scene, create_animation(AnimationKind.CREATE, graph.id, run_time=2.0), create_animation(AnimationKind.WRITE, title.id, run_time=2.0))
    scene.steps.append(create_wait_step(1.0))
    _play(scene, create_animation(AnimationKind.CIRCUMSCRIBE, title.id))
    return project


def motion() -> Project:
    """Shapes that move, rotate, grow and change color."""
    project, scene = _scene("example.motion.scene")
    dot = _add(scene, create_object(ObjectKind.DOT, tr("kind.dot") + " 1", -5.0, 2.0, radius=0.2))
    square = _add(scene, create_object(ObjectKind.SQUARE, tr("kind.square") + " 1", -2.0, -1.0))
    square.fill_opacity = 0.5
    triangle = _add(scene, create_object(ObjectKind.TRIANGLE, tr("kind.triangle") + " 1", 3.0, -1.0, radius=1.2))
    triangle.fill_opacity = 0.5
    _play(scene, *(create_animation(AnimationKind.FADE_IN, obj.id, shift="up") for obj in (dot, square, triangle)))
    _play(
        scene,
        create_animation(AnimationKind.MOVE, dot.id, run_time=2.0, x=5.0, y=2.0),
        create_animation(AnimationKind.ROTATE, square.id, run_time=2.0, angle=180.0),
        create_animation(AnimationKind.SCALE, triangle.id, run_time=2.0, factor=1.5),
    )
    _play(scene, create_animation(AnimationKind.CHANGE_COLOR, square.id, color="#83C167"), create_animation(AnimationKind.CHANGE_COLOR, triangle.id, color="#FC6255"))
    _play(scene, *(create_animation(AnimationKind.FADE_OUT, obj.id) for obj in (dot, square, triangle)))
    return project


def formula() -> Project:
    """Pythagoras written as a formula and highlighted."""
    project, scene = _scene("example.formula.scene")
    title = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 1", 0.0, 2.0, text=tr("example.formula.title"), font_size=40.0))
    tex = _add(scene, create_object(ObjectKind.MATH_TEX, tr("kind.math_tex") + " 1", 0.0, -0.2, latex="a^2 + b^2 = c^2", font_size=72.0))
    _play(scene, create_animation(AnimationKind.FADE_IN, title.id, shift="down"))
    _play(scene, create_animation(AnimationKind.WRITE, tex.id, run_time=2.0))
    _play(scene, create_animation(AnimationKind.CIRCUMSCRIBE, tex.id, run_time=1.5))
    return project


def title_card() -> Project:
    """A title and subtitle intro."""
    project, scene = _scene("example.title_card.scene")
    scene.background_color = "#1E1E2E"
    title = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 1", 0.0, 0.6, text=tr("example.title_card.title"), font_size=72.0, bold=True))
    subtitle = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 2", 0.0, -0.6, text=tr("example.title_card.subtitle"), font_size=32.0))
    subtitle.fill_color = "#58C4DD"
    line = _add(scene, create_object(ObjectKind.LINE, tr("kind.line") + " 1", 0.0, -0.05, length=6.0))
    _play(scene, create_animation(AnimationKind.WRITE, title.id, run_time=1.5))
    _play(scene, create_animation(AnimationKind.GROW_FROM_CENTER, line.id), create_animation(AnimationKind.FADE_IN, subtitle.id, shift="up"))
    scene.steps.append(create_wait_step(1.5))
    _play(scene, *(create_animation(AnimationKind.FADE_OUT, obj.id) for obj in (title, subtitle, line)))
    return project


EXAMPLES: tuple[Example, ...] = (
    Example("circle_to_square", "a_transform", False, circle_to_square),
    Example("function_graph", "graph", False, function_graph),
    Example("motion", "move", False, motion),
    Example("title_card", "text", False, title_card),
    Example("formula", "a_write", True, formula),
)


def example_by_key(key: str) -> Example | None:
    """Return the example with ``key``."""
    return next((example for example in EXAMPLES if example.key == key), None)
