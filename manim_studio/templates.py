"""Built-in scene templates: good starting points for typical videos."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from manim_studio.i18n import tr
from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.factory import create_animation, create_object, create_play_step, create_scene, create_wait_step
from manim_studio.model.types import AnimationKind, ObjectKind


@dataclass(frozen=True)
class BuiltinTemplate:
    """A scene template that is created in code (texts in the active language)."""

    key: str
    icon: str
    build: Callable[[], Scene]


def _add(scene: Scene, obj: SceneObject) -> SceneObject:
    scene.objects.append(obj)
    return obj


def _play(scene: Scene, *animations) -> None:
    scene.steps.append(create_play_step(animations))


def title_and_subtitle() -> Scene:
    scene = create_scene(tr("template.title.name"))
    scene.background_color = "#1E1E2E"
    title = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 1", 0.0, 0.7, text=tr("template.title.title"), font_size=64.0, bold=True))
    subtitle = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 2", 0.0, -0.6, text=tr("template.title.subtitle"), font_size=32.0))
    subtitle.fill_color = "#58C4DD"
    line = _add(scene, create_object(ObjectKind.LINE, tr("kind.line") + " 1", 0.0, 0.0, length=7.0))
    _play(scene, create_animation(AnimationKind.WRITE, title.id, run_time=1.5))
    _play(scene, create_animation(AnimationKind.GROW_FROM_CENTER, line.id), create_animation(AnimationKind.FADE_IN, subtitle.id, shift="up"))
    scene.steps.append(create_wait_step(1.5))
    return scene


def analyze_function() -> Scene:
    scene = create_scene(tr("template.analysis.name"))
    axes = _add(scene, create_object(ObjectKind.AXES, tr("kind.axes") + " 1", 0.0, -0.3, x_label="x", y_label="y", x_length=10.0, y_length=6.0))
    graph = _add(scene, create_object(ObjectKind.FUNCTION_GRAPH, "f", expression="x^3/3 - x", axes_id=axes.id))
    zeros = _add(scene, create_object(ObjectKind.GRAPH_MARKERS, tr("feature.zeros"), graph_id=graph.id, feature="zeros"))
    extrema = _add(scene, create_object(ObjectKind.GRAPH_MARKERS, tr("feature.extrema"), graph_id=graph.id, feature="extrema"))
    extrema.fill_color = "#83C167"
    label = _add(scene, create_object(ObjectKind.GRAPH_LABEL, tr("kind.graph_label") + " 1", graph_id=graph.id, text="f(x) = x³/3 − x", x_value=2.2))
    _play(scene, create_animation(AnimationKind.CREATE, axes.id, run_time=1.5))
    _play(scene, create_animation(AnimationKind.CREATE, graph.id, run_time=2.0), create_animation(AnimationKind.FADE_IN, label.id))
    _play(scene, create_animation(AnimationKind.FADE_IN, zeros.id))
    _play(scene, create_animation(AnimationKind.FADE_IN, extrema.id))
    scene.steps.append(create_wait_step(1.0))
    return scene


def explore_parameter() -> Scene:
    scene = create_scene(tr("template.parameter.name"))
    parameter = _add(scene, create_object(ObjectKind.PARAMETER, "a", symbol="a", value=1.0, minimum=0.0, maximum=3.0))
    axes = _add(scene, create_object(ObjectKind.AXES, tr("kind.axes") + " 1", 0.0, -0.3))
    graph = _add(scene, create_object(ObjectKind.FUNCTION_GRAPH, "f", expression="a sin(x)", axes_id=axes.id))
    point = _add(scene, create_object(ObjectKind.GRAPH_POINT, tr("kind.graph_point") + " 1", graph_id=graph.id, x_parameter=parameter.id, show_label=True))
    number = _add(scene, create_object(ObjectKind.DECIMAL_NUMBER, "a =", -5.0, 3.3, parameter_id=parameter.id, font_size=40.0))
    _play(scene, create_animation(AnimationKind.CREATE, axes.id), create_animation(AnimationKind.CREATE, graph.id), create_animation(AnimationKind.FADE_IN, number.id))
    _play(scene, create_animation(AnimationKind.FADE_IN, point.id))
    _play(scene, create_animation(AnimationKind.SET_VALUE, parameter.id, run_time=3.0, value=3.0))
    _play(scene, create_animation(AnimationKind.SET_VALUE, parameter.id, run_time=2.0, value=1.0))
    return scene


def two_columns() -> Scene:
    scene = create_scene(tr("template.columns.name"))
    left = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 1", -3.5, 2.8, text=tr("template.columns.left"), font_size=40.0))
    right = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 2", 3.5, 2.8, text=tr("template.columns.right"), font_size=40.0))
    divider = _add(scene, create_object(ObjectKind.LINE, tr("kind.line") + " 1", 0.0, 0.0, length=6.0, rotation=0.0))
    divider.rotation = 90.0
    divider.stroke_color = "#888888"
    box_left = _add(scene, create_object(ObjectKind.RECTANGLE, tr("kind.rectangle") + " 1", -3.5, -0.4, width=5.0, height=4.0))
    box_right = _add(scene, create_object(ObjectKind.RECTANGLE, tr("kind.rectangle") + " 2", 3.5, -0.4, width=5.0, height=4.0))
    box_right.stroke_color = box_right.fill_color = "#FC6255"
    _play(scene, create_animation(AnimationKind.CREATE, divider.id))
    _play(scene, create_animation(AnimationKind.WRITE, left.id), create_animation(AnimationKind.CREATE, box_left.id))
    _play(scene, create_animation(AnimationKind.WRITE, right.id), create_animation(AnimationKind.CREATE, box_right.id))
    return scene


def data_analysis() -> Scene:
    scene = create_scene(tr("template.data.name"))
    title = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 1", 0.0, 3.4, text=tr("template.data.title"), font_size=36.0))
    axes = _add(scene, create_object(ObjectKind.AXES, tr("kind.axes") + " 1", 0.0, -0.4, show_numbers=True, x_label="x", y_label="y", x_length=10.0, y_length=6.0))
    data = _add(scene, create_object(ObjectKind.DATA_PLOT, tr("kind.data_plot") + " 1", axes_id=axes.id, regression="linear"))
    data.stroke_color = "#FC6255"
    _play(scene, create_animation(AnimationKind.WRITE, title.id), create_animation(AnimationKind.CREATE, axes.id))
    _play(scene, create_animation(AnimationKind.CREATE, data.id, run_time=2.0))
    scene.steps.append(create_wait_step(1.0))
    return scene


BUILTIN_TEMPLATES: tuple[BuiltinTemplate, ...] = (
    BuiltinTemplate("title", "text", title_and_subtitle),
    BuiltinTemplate("analysis", "graph", analyze_function),
    BuiltinTemplate("parameter", "a_set_value", explore_parameter),
    BuiltinTemplate("columns", "layers", two_columns),
    BuiltinTemplate("data", "graph", data_analysis),
)
