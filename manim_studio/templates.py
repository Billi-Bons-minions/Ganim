"""Built-in scene templates: good starting points for typical videos."""

from __future__ import annotations

import math
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
    caption = _add(scene, create_object(ObjectKind.TEXT, "a =", -5.9, 3.3, text="a =", font_size=40.0))
    number = _add(scene, create_object(ObjectKind.DECIMAL_NUMBER, tr("kind.decimal_number") + " a", -4.65, 3.3, parameter_id=parameter.id, font_size=40.0))
    _play(
        scene,
        create_animation(AnimationKind.CREATE, axes.id),
        create_animation(AnimationKind.CREATE, graph.id),
        create_animation(AnimationKind.FADE_IN, caption.id),
        create_animation(AnimationKind.FADE_IN, number.id),
    )
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


def _line(scene: Scene, name: str, start: tuple[float, float], end: tuple[float, float]) -> SceneObject:
    """A line from ``start`` to ``end`` (stored as center, length and angle)."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    line = _add(scene, create_object(ObjectKind.LINE, name, (start[0] + end[0]) / 2, (start[1] + end[1]) / 2, length=round(math.hypot(dx, dy), 6)))
    line.rotation = round(math.degrees(math.atan2(dy, dx)), 6)
    return line


def pythagoras() -> Scene:
    scene = create_scene(tr("template.pythagoras.name"))
    a_start, b_end, c_end = (-4.0, -1.5), (-1.0, -1.5), (-4.0, 0.5)
    side_a = _line(scene, "a", a_start, b_end)
    side_b = _line(scene, "b", a_start, c_end)
    side_c = _line(scene, "c", b_end, c_end)
    side_c.stroke_color = "#FC6255"
    corner = _add(scene, create_object(ObjectKind.ANGLE, tr("kind.angle") + " 1", first_line=side_a.id, second_line=side_b.id, right_angle=True, radius=0.4))
    labels = [
        _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " a", -2.5, -2.0, text="a", font_size=40.0)),
        _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " b", -4.45, -0.5, text="b", font_size=40.0)),
        _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " c", -2.25, -0.2, text="c", font_size=40.0)),
    ]
    labels[2].fill_color = "#FC6255"
    formula = _add(scene, create_object(ObjectKind.TEXT, tr("template.pythagoras.formula_name"), 2.8, 0.0, text="a² + b² = c²", font_size=56.0))
    frame = _add(scene, create_object(ObjectKind.HIGHLIGHT, tr("kind.highlight") + " 1", target=formula.id))
    _play(scene, *(create_animation(AnimationKind.CREATE, line.id, run_time=1.0) for line in (side_a, side_b, side_c)))
    _play(scene, create_animation(AnimationKind.CREATE, corner.id), *(create_animation(AnimationKind.WRITE, label.id) for label in labels))
    _play(scene, *(create_animation(AnimationKind.TRANSFORM_FROM_COPY, label.id, run_time=1.5, target=formula.id) for label in labels[:1]))
    _play(scene, create_animation(AnimationKind.CREATE, frame.id), create_animation(AnimationKind.INDICATE, formula.id))
    scene.steps.append(create_wait_step(1.0))
    return scene


def orbit_with_trace() -> Scene:
    scene = create_scene(tr("template.orbit.name"))
    title = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 1", 0.0, 3.3, text=tr("template.orbit.title"), font_size=40.0))
    orbit = _add(scene, create_object(ObjectKind.ELLIPSE, tr("template.orbit.path"), 0.0, -0.3, width=8.0, height=4.4))
    orbit.stroke_opacity = 0.35
    orbit.fill_opacity = 0.0
    sun = _add(scene, create_object(ObjectKind.DOT, tr("template.orbit.sun"), 1.2, -0.3, radius=0.35))
    sun.fill_color = sun.stroke_color = "#F7D96F"
    planet = _add(scene, create_object(ObjectKind.DOT, tr("template.orbit.planet"), 4.0, -0.3, radius=0.15))
    planet.fill_color = planet.stroke_color = "#58C4DD"
    trace = _add(scene, create_object(ObjectKind.TRACE, tr("kind.trace") + " 1", target=planet.id, dissipating_time=1.5))
    trace.stroke_color = "#58C4DD"
    _play(scene, create_animation(AnimationKind.WRITE, title.id), create_animation(AnimationKind.CREATE, orbit.id), create_animation(AnimationKind.GROW_FROM_CENTER, sun.id))
    _play(scene, create_animation(AnimationKind.FADE_IN, planet.id))
    _play(scene, create_animation(AnimationKind.MOVE_ALONG_PATH, planet.id, run_time=4.0, path=orbit.id))
    _play(scene, create_animation(AnimationKind.FLASH, sun.id))
    return scene


def flow_field() -> Scene:
    scene = create_scene(tr("template.flow.name"))
    field = _add(scene, create_object(ObjectKind.VECTOR_FIELD, tr("kind.vector_field") + " 1", display="stream", x_expression="sin(y)", y_expression="cos(x) - 0.3 y", step=0.6))
    field.stroke_width = 2.0
    title = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 1", 0.0, 3.3, text="v(x, y) = (sin y, cos x − 0.3 y)", font_size=34.0))
    back = _add(scene, create_object(ObjectKind.HIGHLIGHT, tr("kind.highlight") + " 1", target=title.id, style="background"))
    scene.objects.remove(back)
    scene.objects.insert(scene.objects.index(title), back)
    _play(scene, create_animation(AnimationKind.FADE_IN, field.id, run_time=1.5))
    _play(scene, create_animation(AnimationKind.FADE_IN, back.id), create_animation(AnimationKind.WRITE, title.id))
    scene.steps.append(create_wait_step(3.0))
    return scene


def solids_in_space() -> Scene:
    scene = create_scene(tr("template.solids.name"))
    axes = _add(scene, create_object(ObjectKind.AXES_3D, tr("kind.axes_3d") + " 1"))
    shapes = [("sphere", -2.5, 0.0, "#58C4DD"), ("cube", 0.0, 0.0, "#83C167"), ("torus", 2.5, 0.0, "#FC6255")]
    solids = []
    for shape, x, y, color in shapes:
        solid = _add(scene, create_object(ObjectKind.SOLID, tr(f"choice.shape.{shape}"), axes_id=axes.id, shape=shape, center_x=x, center_y=y, radius=0.9, minor_radius=0.3, side=1.4, resolution=12))
        solid.fill_color = color
        solid.stroke_color = color
        solids.append(solid)
    camera = _add(scene, create_object(ObjectKind.CAMERA, tr("kind.camera") + " 1", phi=70.0, theta=-60.0))
    title = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 1", 0.0, 3.3, text=tr("template.solids.title"), font_size=40.0))
    _play(scene, create_animation(AnimationKind.CREATE, axes.id), create_animation(AnimationKind.WRITE, title.id))
    _play(scene, *(create_animation(AnimationKind.GROW_FROM_CENTER, solid.id) for solid in solids))
    _play(scene, create_animation(AnimationKind.ORBIT, camera.id, run_time=4.0, phi=55.0, theta=30.0))
    # the cube turns in place while the torus rises (Rotate and move_to in space)
    _play(scene, create_animation(AnimationKind.ROTATE_3D, solids[1].id, run_time=2.0, angle=90.0, axis="z"), create_animation(AnimationKind.MOVE_3D, solids[2].id, run_time=2.0, x=2.5, y=0.0, z=1.5))
    # then the camera keeps turning slowly while the picture stays (begin_ambient_camera_rotation)
    _play(scene, create_animation(AnimationKind.AMBIENT_ROTATION, camera.id, run_time=0.5, rate=15.0))
    scene.steps.append(create_wait_step(4.0))
    return scene


def conic_sections() -> Scene:
    scene = create_scene(tr("template.conics.name"))
    radius = _add(scene, create_object(ObjectKind.PARAMETER, "r", symbol="r", value=1.0, minimum=0.5, maximum=3.0))
    axes = _add(scene, create_object(ObjectKind.AXES, tr("kind.axes") + " 1", 0.0, -0.3))
    circle = _add(scene, create_object(ObjectKind.FUNCTION_GRAPH, "x² + y² = r²", axes_id=axes.id, curve="implicit", implicit_expression="x^2 + y^2 - r^2"))
    circle.stroke_color = "#FC6255"
    hyperbola = _add(scene, create_object(ObjectKind.FUNCTION_GRAPH, "x²/4 − y² = 1", axes_id=axes.id, curve="implicit", implicit_expression="x^2/4 - y^2 - 1"))
    hyperbola.stroke_color = "#83C167"
    caption = _add(scene, create_object(ObjectKind.TEXT, "r =", -5.9, 3.3, text="r =", font_size=40.0))
    number = _add(scene, create_object(ObjectKind.DECIMAL_NUMBER, tr("kind.decimal_number") + " r", -4.65, 3.3, parameter_id=radius.id, font_size=40.0))
    _play(scene, create_animation(AnimationKind.CREATE, axes.id))
    _play(
        scene,
        create_animation(AnimationKind.CREATE, circle.id),
        create_animation(AnimationKind.CREATE, hyperbola.id),
        create_animation(AnimationKind.FADE_IN, caption.id),
        create_animation(AnimationKind.FADE_IN, number.id),
    )
    _play(scene, create_animation(AnimationKind.SET_VALUE, radius.id, run_time=3.0, value=2.5))
    _play(scene, create_animation(AnimationKind.SET_VALUE, radius.id, run_time=2.0, value=1.5))
    return scene


def presentation_slide() -> Scene:
    scene = create_scene(tr("template.slide.name"))
    scene.background_color = "#1E1E2E"
    title = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 1", 0.0, 3.0, text=tr("template.slide.title"), font_size=56.0, bold=True))
    rule = _add(scene, create_object(ObjectKind.LINE, tr("kind.line") + " 1", 0.0, 2.3, length=11.0))
    rule.stroke_color = "#58C4DD"
    items = _add(scene, create_object(ObjectKind.BULLET_LIST, tr("kind.bullet_list") + " 1", -1.2, 0.0, items=tr("template.slide.items"), font_size=40.0, buff=0.45))
    _play(scene, create_animation(AnimationKind.WRITE, title.id, run_time=1.2))
    _play(scene, create_animation(AnimationKind.GROW_FROM_EDGE, rule.id, run_time=0.8, edge="left"))
    _play(scene, create_animation(AnimationKind.ONE_BY_ONE, items.id, run_time=2.5))
    scene.steps.append(create_wait_step(2.0))
    return scene


def shortest_path() -> Scene:
    scene = create_scene(tr("template.network.name"))
    title = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 1", 0.0, 3.3, text=tr("template.network.title"), font_size=40.0))
    network = _add(
        scene,
        create_object(
            ObjectKind.NETWORK,
            tr("kind.network") + " 1",
            0.0,
            -0.4,
            vertices="A, B, C, D, E, F",
            edges="A-B\nA-C\nB-D\nC-D\nC-E\nD-F\nE-F\nB-C",
            layout="spring",
            seed=49,  # the path A → F runs from left to right
            layout_scale=3.6,
            radius=0.32,
        ),
    )
    red = "#FC6255"
    _play(scene, create_animation(AnimationKind.FADE_IN, title.id), create_animation(AnimationKind.CREATE, network.id, run_time=2.0))
    _play(scene, create_animation(AnimationKind.NETWORK_PARTS, network.id, run_time=0.6, parts="A", color=red))
    for parts in ("A-C, C", "C-E, E", "E-F, F"):
        _play(scene, create_animation(AnimationKind.NETWORK_PARTS, network.id, run_time=0.8, parts=parts, color=red))
    _play(scene, create_animation(AnimationKind.NETWORK_PARTS, network.id, parts="F", effect="flash", color=red))
    scene.steps.append(create_wait_step(1.5))
    return scene


def linear_map() -> Scene:
    scene = create_scene(tr("template.linear_map.name"))
    # larger than the picture, so that the deformed grid still fills it
    plane = _add(
        scene,
        create_object(ObjectKind.NUMBER_PLANE, tr("kind.number_plane") + " 1", 0.0, 0.0, x_min=-16.0, x_max=16.0, x_length=32.0, y_min=-10.0, y_max=10.0, y_length=20.0),
    )
    i_hat = _add(scene, create_object(ObjectKind.VECTOR, "i", 0.5, 0.0, length=1.0))
    j_hat = _add(scene, create_object(ObjectKind.VECTOR, "j", 0.0, 0.5, length=1.0))
    j_hat.rotation = 90.0
    i_hat.stroke_color = i_hat.fill_color = "#83C167"
    j_hat.stroke_color = j_hat.fill_color = "#FC6255"
    # a text instead of a LaTeX matrix, so that the template also works without LaTeX
    title = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 1", -3.4, 3.3, text=tr("template.linear_map.title"), font_size=34.0))
    title.z_index = 1  # in front of the grid, so that its background (one layer lower) covers the grid lines
    backdrop = _add(scene, create_object(ObjectKind.HIGHLIGHT, tr("kind.highlight") + " 1", target=title.id, style="background", opacity=0.85))
    shear = {"m11": 1.0, "m12": 1.0, "m21": 0.0, "m22": 1.0}
    _play(scene, create_animation(AnimationKind.CREATE, plane.id, run_time=1.5))
    _play(scene, create_animation(AnimationKind.GROW_ARROW, i_hat.id), create_animation(AnimationKind.GROW_ARROW, j_hat.id))
    _play(scene, create_animation(AnimationKind.FADE_IN, backdrop.id), create_animation(AnimationKind.WRITE, title.id))
    _play(scene, *(create_animation(AnimationKind.APPLY_MATRIX, target.id, run_time=2.5, **shear) for target in (plane, i_hat, j_hat)))
    scene.steps.append(create_wait_step(1.5))
    return scene


def secant_to_tangent() -> Scene:
    """The derivative as a limit: h runs to 0 and the secant turns into the tangent."""
    scene = create_scene(tr("template.secant.name"))
    step = _add(scene, create_object(ObjectKind.PARAMETER, "h", symbol="h", value=2.0, minimum=0.0, maximum=2.0))
    axes = _add(
        scene,
        create_object(ObjectKind.AXES, tr("kind.axes") + " 1", 0.0, -0.6, x_min=-1.0, x_max=4.0, y_min=-1.0, y_max=5.0, x_length=8.0, y_length=5.5, x_label="x", y_label="y"),
    )
    graph = _add(scene, create_object(ObjectKind.FUNCTION_GRAPH, "f", expression="x^2/2", axes_id=axes.id))
    secant = _add(scene, create_object(ObjectKind.SECANT, tr("kind.secant") + " 1", graph_id=graph.id, x_value=1.0, h_parameter=step.id))
    tangent = _add(scene, create_object(ObjectKind.TANGENT, tr("kind.tangent") + " 1", graph_id=graph.id, x_value=1.0, width=4.0))
    title = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 1", 0.0, 3.4, text=tr("template.secant.title"), font_size=36.0))
    caption = _add(scene, create_object(ObjectKind.TEXT, "h =", -5.6, 2.2, text="h =", font_size=36.0))
    number = _add(scene, create_object(ObjectKind.DECIMAL_NUMBER, tr("kind.decimal_number") + " h", -4.5, 2.2, parameter_id=step.id, font_size=36.0))
    caption.fill_color = number.fill_color = secant.stroke_color
    _play(scene, create_animation(AnimationKind.CREATE, axes.id), create_animation(AnimationKind.CREATE, graph.id), create_animation(AnimationKind.WRITE, title.id))
    _play(scene, create_animation(AnimationKind.CREATE, secant.id), create_animation(AnimationKind.FADE_IN, caption.id), create_animation(AnimationKind.FADE_IN, number.id))
    _play(scene, create_animation(AnimationKind.SET_VALUE, step.id, run_time=4.0, value=0.0))
    _play(scene, create_animation(AnimationKind.CREATE, tangent.id))
    scene.steps.append(create_wait_step(1.0))
    return scene


def moving_tangent() -> Scene:
    """A tangent slides along the graph; its label shows the current term."""
    scene = create_scene(tr("template.tangent.name"))
    # from -1.5 to 1.5 the label stays clear of the axes at the start and the end
    position = _add(scene, create_object(ObjectKind.PARAMETER, "a", symbol="a", value=-1.5, minimum=-2.0, maximum=2.0))
    axes = _add(
        scene,
        create_object(ObjectKind.AXES, tr("kind.axes") + " 1", 0.0, -0.3, x_min=-3.0, x_max=3.0, y_min=-2.0, y_max=2.0, x_length=10.0, y_length=6.0, x_label="x", y_label="y"),
    )
    graph = _add(scene, create_object(ObjectKind.FUNCTION_GRAPH, "f", expression="x^3/3 - x", axes_id=axes.id))
    tangent = _add(scene, create_object(ObjectKind.TANGENT, tr("kind.tangent") + " 1", graph_id=graph.id, x_parameter=position.id, width=2.5))
    point = _add(scene, create_object(ObjectKind.GRAPH_POINT, tr("kind.graph_point") + " 1", graph_id=graph.id, x_parameter=position.id, show_lines=False))
    point.fill_color = tangent.stroke_color
    # the term is an object of its own: it is written after the tangent appeared and then moves with it
    term = _add(scene, create_object(ObjectKind.TOOL_LABEL, tr("tool_label.name", tool=tangent.name), tool_id=tangent.id, content="term"))
    term.fill_color = tangent.stroke_color
    _play(scene, create_animation(AnimationKind.CREATE, axes.id), create_animation(AnimationKind.CREATE, graph.id, run_time=1.5))
    _play(scene, create_animation(AnimationKind.CREATE, tangent.id), create_animation(AnimationKind.FADE_IN, point.id))
    _play(scene, create_animation(AnimationKind.WRITE, term.id))
    _play(scene, create_animation(AnimationKind.SET_VALUE, position.id, run_time=6.0, value=1.5))
    scene.steps.append(create_wait_step(1.0))
    return scene


def complex_map() -> Scene:
    """3Blue1Brown style: the complex plane is bent by w = z²; a faint plane with numbers stays behind it."""
    scene = create_scene(tr("template.complex_map.name"))
    ranges = {"x_min": -4.0, "x_max": 4.0, "x_length": 8.0, "y_min": -3.0, "y_max": 3.0, "y_length": 6.0}
    background = _add(scene, create_object(ObjectKind.NUMBER_PLANE, tr("kind.number_plane") + " 1", 0.0, 0.0, numbers="complex", **ranges))
    background.stroke_opacity = 0.35
    plane = _add(scene, create_object(ObjectKind.NUMBER_PLANE, tr("kind.number_plane") + " 2", 0.0, 0.0, **ranges))
    plane.stroke_color = "#F7D96F"
    circle = _add(scene, create_object(ObjectKind.CIRCLE, tr("kind.circle") + " 1", 1.0, 1.0, radius=0.5))
    circle.stroke_color = "#FC6255"
    # a text instead of LaTeX, so that the template also works without LaTeX
    title = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 1", -4.9, 3.3, text="w = z²", font_size=40.0))
    title.z_index = 1
    backdrop = _add(scene, create_object(ObjectKind.HIGHLIGHT, tr("kind.highlight") + " 1", target=title.id, style="background", opacity=0.85))
    _play(scene, create_animation(AnimationKind.CREATE, background.id, run_time=1.0))
    _play(scene, create_animation(AnimationKind.CREATE, plane.id, run_time=1.5), create_animation(AnimationKind.CREATE, circle.id))
    _play(scene, create_animation(AnimationKind.FADE_IN, backdrop.id), create_animation(AnimationKind.WRITE, title.id))
    _play(scene, *(create_animation(AnimationKind.APPLY_COMPLEX, target.id, run_time=3.0, function="z^2") for target in (plane, circle)))
    scene.steps.append(create_wait_step(1.5))
    return scene


def zoom_lens() -> Scene:
    """Local linearity: the lens zooms into a graph and its tangent until they look the same."""
    scene = create_scene(tr("template.lens.name"))
    axes = _add(
        scene,
        create_object(ObjectKind.AXES, tr("kind.axes") + " 1", -2.4, -0.4, x_min=-3.0, x_max=3.0, y_min=-2.0, y_max=2.0, x_length=7.5, y_length=6.0, x_label="x", y_label="y"),
    )
    graph = _add(scene, create_object(ObjectKind.FUNCTION_GRAPH, "f", expression="sin(2x) + x^2/4", axes_id=axes.id, x_min=-3.0, x_max=3.0))
    tangent = _add(scene, create_object(ObjectKind.TANGENT, tr("kind.tangent") + " 1", graph_id=graph.id, x_value=0.5, width=3.0))
    # thin lines: the lens magnifies the line widths as well (like a real magnifying glass)
    graph.stroke_width = tangent.stroke_width = 2.0
    from manim_studio.model.geometry import axes_to_scene
    from manim_studio.model.graphs import graph_function

    # the lens looks at the point of contact (scene coordinates of x = 0.5 on the axes)
    x0, y0 = axes_to_scene(axes, 0.5, graph_function(scene, graph)(0.5))
    lens = _add(scene, create_object(ObjectKind.ZOOM_LENS, tr("kind.zoom_lens"), x0, y0, zoom=3.0, display_x=4.7, display_y=0.7, display_width=3.6, display_height=3.6))
    lens.stroke_width = 1.5
    caption = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 1", 4.7, -2.0, text=tr("template.lens.caption"), font_size=28.0, alignment="center"))
    _play(scene, create_animation(AnimationKind.CREATE, axes.id), create_animation(AnimationKind.CREATE, graph.id, run_time=1.5))
    _play(scene, create_animation(AnimationKind.CREATE, tangent.id))
    _play(scene, create_animation(AnimationKind.FADE_IN, lens.id, run_time=1.5))
    _play(scene, create_animation(AnimationKind.SCALE, lens.id, run_time=3.0, factor=0.4), create_animation(AnimationKind.WRITE, caption.id))
    scene.steps.append(create_wait_step(1.5))
    return scene


def venn_diagram() -> Scene:
    """Two sets: their intersection follows a moving circle, then A without B."""
    scene = create_scene(tr("template.venn.name"))
    first = _add(scene, create_object(ObjectKind.CIRCLE, "A", -1.0, -0.2, radius=1.8))
    second = _add(scene, create_object(ObjectKind.CIRCLE, "B", 1.0, -0.2, radius=1.8))
    first.fill_opacity = second.fill_opacity = 0.15
    second.stroke_color = second.fill_color = "#FC6255"
    # the letters keep their place above the circles (coupling)
    label_a = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " A", -1.0, 2.15, text="A", font_size=44.0, attach="follow", attach_target=first.id))
    label_b = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " B", 1.0, 2.15, text="B", font_size=44.0, attach="follow", attach_target=second.id))
    label_a.fill_color, label_b.fill_color = first.stroke_color, second.stroke_color
    both = _add(scene, create_object(ObjectKind.BOOLEAN_SHAPE, "A ∩ B", operation="intersection", first_shape=first.id, second_shape=second.id))
    only_a = _add(scene, create_object(ObjectKind.BOOLEAN_SHAPE, "A ∖ B", operation="difference", first_shape=first.id, second_shape=second.id))
    only_a.stroke_color = only_a.fill_color = "#83C167"
    caption_both = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 1", 0.0, -2.75, text=tr("template.venn.intersection"), font_size=36.0))
    caption_only = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 2", 0.0, -2.75, text=tr("template.venn.difference"), font_size=36.0))
    caption_both.fill_color, caption_only.fill_color = both.fill_color, only_a.fill_color
    _play(scene, *(create_animation(AnimationKind.CREATE, shape.id) for shape in (first, second)), *(create_animation(AnimationKind.WRITE, label.id) for label in (label_a, label_b)))
    _play(scene, create_animation(AnimationKind.FADE_IN, both.id), create_animation(AnimationKind.FADE_IN, caption_both.id))
    # the intersection shrinks while B moves away (and grows when it comes back)
    _play(scene, create_animation(AnimationKind.MOVE, second.id, run_time=1.5, x=2.4, y=-0.2))
    _play(scene, create_animation(AnimationKind.MOVE, second.id, run_time=1.5, x=1.0, y=-0.2))
    _play(scene, create_animation(AnimationKind.FADE_OUT, both.id), create_animation(AnimationKind.FADE_OUT, caption_both.id))
    _play(scene, create_animation(AnimationKind.FADE_IN, only_a.id), create_animation(AnimationKind.FADE_IN, caption_only.id))
    scene.steps.append(create_wait_step(1.5))
    return scene


def integral_function() -> Scene:
    """F(x) = ∫₀ˣ f(t) dt: the slope of F is the value of f; the areas above and below cancel at x = 3."""
    scene = create_scene(tr("template.integral.name"))
    position = _add(scene, create_object(ObjectKind.PARAMETER, "a", symbol="a", value=0.6, minimum=0.0, maximum=4.0))
    axes = _add(
        scene,
        create_object(ObjectKind.AXES, tr("kind.axes") + " 1", 0.0, -0.4, x_min=-1.0, x_max=4.5, y_min=-1.5, y_max=2.5, x_length=11.0, y_length=6.0, x_label="x", y_label="y"),
    )
    # f(x) = (x − 1)(x − 3)/2: F rises up to x = 1, falls back to 0 at x = 3 and rises again
    graph = _add(scene, create_object(ObjectKind.FUNCTION_GRAPH, "f", expression="0.5x^2 - 2x + 1.5", axes_id=axes.id, x_min=-0.6, x_max=4.3))
    integral = _add(
        scene,
        create_object(ObjectKind.FUNCTION_GRAPH, "F", curve="antiderivative", derive_from=graph.id, integral_from=0.0, integral_constant=0.0, axes_id=axes.id, x_min=-0.6, x_max=4.3),
    )
    graph.stroke_color, integral.stroke_color = "#58C4DD", "#F7D96F"
    label_f = _add(scene, create_object(ObjectKind.GRAPH_LABEL, tr("kind.graph_label") + " 1", graph_id=graph.id, text="f", x_value=4.1, direction="right"))
    label_big = _add(scene, create_object(ObjectKind.GRAPH_LABEL, tr("kind.graph_label") + " 2", graph_id=integral.id, text="F", x_value=4.1, direction="right"))
    label_f.fill_color, label_big.fill_color = graph.stroke_color, integral.stroke_color
    above = _add(scene, create_object(ObjectKind.GRAPH_AREA, tr("kind.graph_area") + " 1", graph_id=graph.id, x_min=0.0, x_max=1.0))
    below = _add(scene, create_object(ObjectKind.GRAPH_AREA, tr("kind.graph_area") + " 2", graph_id=graph.id, x_min=1.0, x_max=3.0))
    above.fill_opacity = below.fill_opacity = 0.35
    below.fill_color = "#FC6255"
    tangent = _add(scene, create_object(ObjectKind.TANGENT, tr("kind.tangent") + " 1", graph_id=integral.id, x_parameter=position.id, width=1.6))
    tangent.stroke_color = "#FF862F"
    on_integral = _add(scene, create_object(ObjectKind.GRAPH_POINT, tr("kind.graph_point") + " 1", graph_id=integral.id, x_parameter=position.id, show_lines=False))
    on_graph = _add(scene, create_object(ObjectKind.GRAPH_POINT, tr("kind.graph_point") + " 2", graph_id=graph.id, x_parameter=position.id, show_lines=False))
    on_integral.fill_color, on_graph.fill_color = tangent.stroke_color, graph.stroke_color
    # the slope of the tangent at F is the value of f below it
    slope = _add(scene, create_object(ObjectKind.TOOL_LABEL, tr("tool_label.name", tool=tangent.name), tool_id=tangent.id, content="slope", label_side="above"))
    slope.fill_color = tangent.stroke_color
    extrema = _add(scene, create_object(ObjectKind.GRAPH_MARKERS, tr("kind.graph_markers") + " 1", graph_id=integral.id, feature="extrema", show_labels=False))
    _play(scene, create_animation(AnimationKind.CREATE, axes.id), create_animation(AnimationKind.CREATE, graph.id, run_time=1.5), create_animation(AnimationKind.WRITE, label_f.id))
    _play(scene, create_animation(AnimationKind.FADE_IN, above.id), create_animation(AnimationKind.FADE_IN, below.id))
    _play(scene, create_animation(AnimationKind.CREATE, integral.id, run_time=2.0), create_animation(AnimationKind.WRITE, label_big.id))
    _play(scene, create_animation(AnimationKind.CREATE, tangent.id), *(create_animation(AnimationKind.FADE_IN, point.id) for point in (on_integral, on_graph)))
    _play(scene, create_animation(AnimationKind.WRITE, slope.id))
    _play(scene, create_animation(AnimationKind.SET_VALUE, position.id, run_time=6.0, value=3.7))
    _play(scene, create_animation(AnimationKind.FADE_IN, extrema.id))
    scene.steps.append(create_wait_step(1.5))
    return scene


def value_table() -> Scene:
    """A table of values is read column by column: each pair becomes a point, then the graph joins them."""
    scene = create_scene(tr("template.value_table.name"))
    xs = (-2, -1, 0, 1, 2)
    rows = [["x", *(str(x) for x in xs)], ["f(x)", *(f"{0.5 * x * x - 1:g}" for x in xs)]]
    table = _add(scene, create_object(ObjectKind.TABLE, tr("kind.table") + " 1", 0.0, 2.6, rows=rows, font_size=30.0, h_buff=0.7, v_buff=0.35))
    axes = _add(
        scene,
        create_object(ObjectKind.AXES, tr("kind.axes") + " 1", 0.0, -1.3, x_min=-3.0, x_max=3.0, y_min=-1.5, y_max=1.5, x_length=8.0, y_length=4.0, x_label="x", y_label="y"),
    )
    graph = _add(scene, create_object(ObjectKind.FUNCTION_GRAPH, "f", expression="0.5x^2 - 1", axes_id=axes.id, x_min=-2.6, x_max=2.6))
    graph.stroke_color = "#58C4DD"
    frames, points = [], []
    for column, x in enumerate(xs, start=2):
        # the frame lies exactly on the column (buff 0); the point shows its coordinates on the axes
        frame = _add(scene, create_object(ObjectKind.HIGHLIGHT, tr("kind.highlight") + f" {column - 1}", target=table.id, table_column=column, buff=0.0, corner_radius=0.0))
        point = _add(scene, create_object(ObjectKind.GRAPH_POINT, tr("kind.graph_point") + f" {column - 1}", graph_id=graph.id, x_value=float(x), show_lines=True))
        point.fill_color = frame.stroke_color
        frames.append(frame)
        points.append(point)
    _play(scene, create_animation(AnimationKind.CREATE, table.id, run_time=1.5), create_animation(AnimationKind.CREATE, axes.id, run_time=1.5))
    for index, (frame, point) in enumerate(zip(frames, points)):
        leaving = [create_animation(AnimationKind.FADE_OUT, frames[index - 1].id, run_time=0.5)] if index else []
        _play(scene, *leaving, create_animation(AnimationKind.CREATE, frame.id, run_time=0.6), create_animation(AnimationKind.FADE_IN, point.id, run_time=0.8))
    _play(scene, create_animation(AnimationKind.FADE_OUT, frames[-1].id, run_time=0.5), create_animation(AnimationKind.CREATE, graph.id, run_time=2.0))
    scene.steps.append(create_wait_step(1.5))
    return scene


def thales() -> Scene:
    """Thales' theorem: C moves on the circle over AB (on arcs), the sides follow, the angle at C stays 90°."""
    scene = create_scene(tr("template.thales.name"))
    cx, cy, radius = 0.0, -0.6, 2.6

    def on_circle(degrees: float) -> tuple[float, float]:
        return round(cx + radius * math.cos(math.radians(degrees)), 4), round(cy + radius * math.sin(math.radians(degrees)), 4)

    circle = _add(scene, create_object(ObjectKind.CIRCLE, tr("kind.circle") + " 1", cx, cy, radius=radius, dashed=True, num_dashes=40))
    circle.stroke_color = "#888888"
    corners = {}
    for name, degrees in (("A", 180.0), ("B", 0.0), ("C", 120.0)):
        corners[name] = _add(scene, create_object(ObjectKind.DOT, name, *on_circle(degrees), radius=0.1))
        corners[name].z_index = 1  # the corners lie on top of the sides
    corners["C"].fill_color = "#FC6255"
    # the names of the corners next to them (C's label goes along)
    labels = {}
    for name, (dx, dy) in (("A", (-0.35, -0.3)), ("B", (0.35, -0.3)), ("C", (-0.3, 0.35))):
        corner = corners[name]
        labels[name] = _add(scene, create_object(ObjectKind.TEXT, tr("name_label.name", name=name), corner.x + dx, corner.y + dy, text=name, font_size=36.0, attach="follow", attach_target=corner.id))
        labels[name].fill_color = corner.fill_color
    # the sides run between the corners and follow C
    sides = {}
    for start, end in (("A", "B"), ("C", "A"), ("C", "B")):
        side = _add(scene, create_object(ObjectKind.LINE, start + end, 0.0, 0.0, attach="between", attach_start=corners[start].id, attach_end=corners[end].id))
        side.stroke_color = "#58C4DD"
        sides[start + end] = side
    angle = _add(scene, create_object(ObjectKind.ANGLE, tr("kind.angle") + " 1", first_line=sides["CA"].id, second_line=sides["CB"].id, radius=0.45, right_angle=True, label="degrees"))
    angle.stroke_color = "#FC6255"
    title = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 1", 0.0, 3.3, text=tr("template.thales.caption"), font_size=36.0))
    _play(scene, create_animation(AnimationKind.CREATE, circle.id, run_time=1.5), create_animation(AnimationKind.WRITE, title.id))
    _play(scene, *(create_animation(AnimationKind.FADE_IN, corners[name].id) for name in ("A", "B")), *(create_animation(AnimationKind.WRITE, labels[name].id) for name in ("A", "B")), create_animation(AnimationKind.CREATE, sides["AB"].id))
    _play(scene, create_animation(AnimationKind.FADE_IN, corners["C"].id), create_animation(AnimationKind.WRITE, labels["C"].id), *(create_animation(AnimationKind.CREATE, sides[key].id) for key in ("CA", "CB")))
    _play(scene, create_animation(AnimationKind.CREATE, angle.id))
    # C walks on the circle: an arc with the central angle between the two places
    for start, end, run_time in ((120.0, 45.0, 2.0), (45.0, 160.0, 2.5), (160.0, 95.0, 1.5)):
        x, y = on_circle(end)
        _play(scene, create_animation(AnimationKind.MOVE, corners["C"].id, run_time=run_time, x=x, y=y, path_arc=end - start))
    scene.steps.append(create_wait_step(1.5))
    return scene


def measure_triangle() -> Scene:
    """A triangle measures itself: its side lengths (dist) sit at the sides and change while C moves."""
    scene = create_scene(tr("template.triangle.name"))
    corners = {}
    for name, x, y in (("A", -3.0, -1.6), ("B", 3.0, -1.6), ("C", -0.6, 1.9)):
        corners[name] = _add(scene, create_object(ObjectKind.DOT, name, x, y, radius=0.1))
        corners[name].z_index = 1
    corners["C"].fill_color = "#FC6255"
    labels = {}
    for name, (dx, dy) in (("A", (-0.35, -0.3)), ("B", (0.35, -0.3)), ("C", (0.0, 0.4))):
        corner = corners[name]
        labels[name] = _add(scene, create_object(ObjectKind.TEXT, tr("name_label.name", name=name), corner.x + dx, corner.y + dy, text=name, font_size=36.0, attach="follow", attach_target=corner.id))
        labels[name].fill_color = corner.fill_color
    area = _add(scene, create_object(ObjectKind.POLYGON, tr("kind.polygon") + " 1", attach="corners", attach_corners=[corners[name].id for name in ("A", "B", "C")]))
    area.stroke_width, area.fill_opacity = 0.0, 0.25
    area.fill_color = "#58C4DD"
    sides = {}
    for start, end in (("A", "B"), ("B", "C"), ("C", "A")):
        side = _add(scene, create_object(ObjectKind.LINE, start + end, attach="between", attach_start=corners[start].id, attach_end=corners[end].id))
        side.stroke_color = "#58C4DD"
        sides[start + end] = side
    # every length sits next to the middle of its side (A.x, A.y … in the position formulas)
    lengths = []
    for start, end, dx, dy in (("A", "B", 0.0, -0.45), ("B", "C", 0.55, 0.25), ("C", "A", -0.55, 0.25)):
        number = _add(
            scene,
            create_object(
                ObjectKind.DECIMAL_NUMBER,
                f"|{start}{end}|",
                formula=f"dist({start}, {end})",
                decimals=2,
                font_size=30.0,
                attach="formula",
                attach_x=f"({start}.x + {end}.x)/2 + {dx}",
                attach_y=f"({start}.y + {end}.y)/2 + {dy}",
            ),
        )
        number.fill_color = "#FFFF00"
        lengths.append(number)
    caption = _add(scene, create_object(ObjectKind.TEXT, tr("kind.text") + " 1", -4.6, 3.2, text=tr("template.triangle.perimeter"), font_size=32.0))
    perimeter = _add(scene, create_object(ObjectKind.DECIMAL_NUMBER, tr("template.triangle.perimeter"), -2.7, 3.2, formula="dist(A, B) + dist(B, C) + dist(C, A)", decimals=2, font_size=32.0))
    perimeter.fill_color = "#FFFF00"
    _play(scene, *(create_animation(AnimationKind.FADE_IN, corners[name].id) for name in corners), *(create_animation(AnimationKind.WRITE, labels[name].id) for name in labels))
    _play(scene, *(create_animation(AnimationKind.CREATE, side.id) for side in sides.values()), create_animation(AnimationKind.FADE_IN, area.id))
    _play(scene, *(create_animation(AnimationKind.WRITE, number.id) for number in lengths))
    _play(scene, create_animation(AnimationKind.WRITE, caption.id), create_animation(AnimationKind.WRITE, perimeter.id))
    for x, y, arc, run_time in ((2.2, 2.3, -40.0, 2.5), (-2.4, 0.9, 50.0, 2.5), (-0.6, 1.9, -30.0, 1.5)):
        _play(scene, create_animation(AnimationKind.MOVE, corners["C"].id, run_time=run_time, x=x, y=y, path_arc=arc))
    scene.steps.append(create_wait_step(1.0))
    return scene


BUILTIN_TEMPLATES: tuple[BuiltinTemplate, ...] = (
    BuiltinTemplate("title", "text", title_and_subtitle),
    BuiltinTemplate("analysis", "graph", analyze_function),
    BuiltinTemplate("parameter", "a_set_value", explore_parameter),
    BuiltinTemplate("columns", "layers", two_columns),
    BuiltinTemplate("data", "graph", data_analysis),
    BuiltinTemplate("pythagoras", "a_transform_from_copy", pythagoras),
    BuiltinTemplate("orbit", "a_move_along_path", orbit_with_trace),
    BuiltinTemplate("flow", "a_apply_wave", flow_field),
    BuiltinTemplate("solids", "a_orbit", solids_in_space),
    BuiltinTemplate("conics", "a_set_value", conic_sections),
    BuiltinTemplate("slide", "a_one_by_one", presentation_slide),
    BuiltinTemplate("network", "a_network_parts", shortest_path),
    BuiltinTemplate("linear_map", "a_apply_matrix", linear_map),
    BuiltinTemplate("secant", "graph", secant_to_tangent),
    BuiltinTemplate("tangent", "graph", moving_tangent),
    BuiltinTemplate("venn", "a_fade_in", venn_diagram),
    BuiltinTemplate("complex_map", "a_apply_complex", complex_map),
    BuiltinTemplate("lens", "zoom_in", zoom_lens),
    BuiltinTemplate("integral", "graph", integral_function),
    BuiltinTemplate("value_table", "graph", value_table),
    BuiltinTemplate("thales", "a_move_along_path", thales),
    BuiltinTemplate("triangle", "a_move_along_path", measure_triangle),
)
