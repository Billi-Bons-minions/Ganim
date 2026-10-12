"""Live labels of tangents and secants: the current term follows the line (user request)."""

from __future__ import annotations

import importlib.util

import pytest

from manim_studio.codegen import generate_script
from manim_studio.codegen.graph_code import STUDIO_TERM_SOURCE
from manim_studio.model import graphs
from manim_studio.model.entities import Scene
from manim_studio.model.types import AnimationKind, ObjectKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_animation, make_object, make_project, play

HAS_MANIM = importlib.util.find_spec("manim") is not None


def label_scene(**tangent) -> Scene:
    axes = make_object(ObjectKind.AXES, "Achsen", "ax", x_min=-3.0, x_max=3.0, y_min=-2.0, y_max=2.0)
    a = make_object(ObjectKind.PARAMETER, "a", "pa", symbol="a", value=-2.0, minimum=-2.5, maximum=2.5)
    g = make_object(ObjectKind.FUNCTION_GRAPH, "f", "g", expression="x^3/3 - x", axes_id="ax")
    t = make_object(ObjectKind.TANGENT, "Tangente", "t", graph_id="g", x_parameter="pa", **({"label": "term"} | tangent))
    s = make_object(ObjectKind.SECANT, "Sekante", "s", graph_id="g", x_value=-1.0, h=1.5, label="slope")
    steps = [
        play(*(make_animation(AnimationKind.CREATE, i, run_time=0.2) for i in ("ax", "g", "t", "s"))),
        play(make_animation(AnimationKind.SET_VALUE, "pa", "v", value=2.0, run_time=0.5)),
    ]
    return Scene(id="s", name="Beschriftung", objects=[axes, a, g, t, s], steps=steps)


@pytest.mark.parametrize(
    ("slope", "intercept", "decimals", "style", "text"),
    [
        (1.5, -0.25, 2, "term", "t(x) = 1.50x − 0.25"),
        (-2.0, 1.0, 1, "equation", "y = −2.0x + 1.0"),
        (0.0001, -0.0001, 2, "term", "t(x) = 0.00x + 0.00"),  # no "−0.00"
        (-0.75, 3.0, 2, "slope", "m = −0.75"),
        (2.5, 0.5, 0, "term", "t(x) = 2x + 0"),
    ],
)
def test_line_terms(slope, intercept, decimals, style, text) -> None:
    assert graphs.line_term("t", slope, intercept, decimals, style) == text
    namespace: dict = {}
    exec(STUDIO_TERM_SOURCE, namespace)  # the script writes exactly what the stage shows
    assert namespace["studio_term"]("t", slope, intercept, decimals, style) == text


def test_labels_follow_the_parameter_and_avoid_the_graph() -> None:
    scene = label_scene()
    tangent, secant = scene.objects[3], scene.objects[4]
    start = graphs.line_label(scene, tangent)
    assert start.text == "t(x) = 3.00x + 5.33" and (start.x, start.slope) == (-2.0, pytest.approx(3.0))
    assert start.side == 1  # the graph is concave at x = -2 (below the tangent), so the label goes above
    end = graphs.line_label(scene, tangent, {"a": 2.0})
    assert end.text == "t(x) = 3.00x − 5.33" and end.side == -1  # convex at x = 2: below
    assert graphs.line_label(scene, secant).text == "m = −0.75"
    assert graphs.line_label(scene, secant).x == pytest.approx(-0.25)  # between both points
    tangent.params.update(label="none")
    assert graphs.line_label(scene, tangent) is None
    tangent.params.update(label="equation", label_side="above")
    assert graphs.line_label(scene, tangent, {"a": 2.0}).side == 1
    assert not has_errors(validate_scene(scene))


def test_label_code() -> None:
    code = generate_script(make_project(label_scene()))
    assert 'studio_beside(Text(studio_term("t", slope, y0 - slope * x0, 2, "term"), font_size=24.0' in code
    assert "side = -1 if curve(x0 + 0.01) + curve(x0 - 0.01) > 2 * y0 else 1" in code
    assert 'studio_beside(Text("m = −0.75", font_size=24.0' in code  # the secant's numbers do not change
    assert "def studio_term(" in code and "def studio_beside(" in code
    compile(code, "labels.py", "exec")
    plain = generate_script(make_project(label_scene(label="none")))
    assert "tangente = always_redraw(tangente_build)" in plain and "studio_term(" not in plain.split("def tangente_build")[1].split("tangente = ")[0]


def test_live_point_labels_keep_two_decimals_like_the_video() -> None:
    assert graphs.point_label(1.5, -1.0) == "(1.5 | -1)"
    assert graphs.point_label(1.5, -1.0, live=True) == "(1.50 | -1.00)"


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_the_label_shows_the_current_term_in_manim(tmp_path) -> None:
    from manim import Text, tempconfig

    scene = label_scene()
    script = generate_script(make_project(scene))
    namespace: dict = {}
    exec(compile(script, "labels.py", "exec"), namespace)
    with tempconfig({"dry_run": True, "quality": "low_quality", "media_dir": str(tmp_path)}):
        rendered = namespace["Beschriftung"]()
        rendered.render()
    # become() copies the shape of the new label, not its .text, so check where the label is:
    # next to the tangent at x = 2, placed like studio_beside places it
    import numpy as np

    axes = next(m for m in rendered.mobjects if type(m).__name__ == "Axes")
    label = graphs.line_label(scene, scene.objects[3], {"a": 2.0})
    point = axes.c2p(label.x, label.y)
    direction = axes.c2p(label.x + 1, label.y + label.slope) - point
    normal = label.side * np.array([-direction[1], direction[0], 0.0]) / np.linalg.norm(direction)
    labels = [m for top in rendered.mobjects for m in top.get_family() if isinstance(m, Text)]
    expected = [point + (abs(normal[0]) * m.width / 2 + abs(normal[1]) * m.height / 2 + graphs.LINE_LABEL_BUFF) * normal for m in labels]
    assert any(np.allclose(m.get_center(), center, atol=1e-6) for m, center in zip(labels, expected))
