"""Integral functions F(x) = C + ∫ f(t) dt from a to x (Manim: plot_antiderivative_graph)."""

from __future__ import annotations

import importlib.util
import math

import pytest

from manim_studio.codegen import generate_script
from manim_studio.codegen.graph_code import STUDIO_INTEGRAL_SOURCE
from manim_studio.model import graphs
from manim_studio.model.entities import Scene
from manim_studio.model.operations import dependent_objects
from manim_studio.model.types import AnimationKind, ObjectKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_animation, make_object, make_project, play

HAS_MANIM = importlib.util.find_spec("manim") is not None


def integral_scene(expression: str = "2x", **params) -> Scene:
    axes = make_object(ObjectKind.AXES, "Achsen", "ax", x_min=-3.0, x_max=3.0, y_min=-3.0, y_max=9.0)
    k = make_object(ObjectKind.PARAMETER, "k", "pk", symbol="k", value=1.0, minimum=0.0, maximum=3.0)
    f = make_object(ObjectKind.FUNCTION_GRAPH, "f", "f", expression=expression, axes_id="ax", x_min=-3.0, x_max=3.0)
    big_f = make_object(ObjectKind.FUNCTION_GRAPH, "F", "F", curve="antiderivative", derive_from="f", axes_id="ax", x_min=-3.0, x_max=3.0, **params)
    steps = [play(make_animation(AnimationKind.CREATE, "ax"), make_animation(AnimationKind.CREATE, "f"), make_animation(AnimationKind.CREATE, "F"))]
    return Scene(id="s", name="Integral", objects=[axes, k, f, big_f], steps=steps)


def test_integral_function_values() -> None:
    scene = integral_scene()
    big_f = graphs.antiderivative_function(scene, scene.object_by_id("F"))
    for x in (-2.0, 0.0, 1.5, 3.0):
        assert big_f(x) == pytest.approx(x * x, abs=1e-4)  # ∫ 2t dt from 0 to x = x²
    shifted = integral_scene(integral_from=1.0, integral_constant=2.0)
    assert graphs.antiderivative_function(shifted, shifted.object_by_id("F"))(2.0) == pytest.approx(2.0 + 4.0 - 1.0, abs=1e-4)
    with_parameter = integral_scene("k cos(x)")
    big_f = graphs.antiderivative_function(with_parameter, with_parameter.object_by_id("F"), {"k": 2.0})
    assert big_f(1.0) == pytest.approx(2 * math.sin(1.0), abs=1e-4)
    assert graphs.curve_points(scene, scene.object_by_id("F"))  # drawn on the stage
    assert not has_errors(validate_scene(scene))
    assert "F" in dependent_objects(scene, ["f"])  # deleting f takes its integral function along


def test_integral_function_problems() -> None:
    scene = integral_scene()
    scene.object_by_id("F").params["derive_from"] = None
    assert "derive_source_missing" in {issue.code for issue in validate_scene(scene)}


def test_script_integral_matches_the_stage() -> None:
    import numpy as np

    namespace = {"np": np}
    exec(STUDIO_INTEGRAL_SOURCE, namespace)
    integral = namespace["studio_integral"]
    assert integral(lambda x: 2 * x, 0.0, 3.0) == pytest.approx(9.0, abs=1e-9)
    # piecewise terms only work on single numbers: the helper falls back to a loop
    step = lambda x: 1.0 if x < 1 else 3.0  # noqa: E731
    assert integral(step, 0.0, 2.0) == pytest.approx(4.0, abs=0.02)
    code = generate_script(make_project(integral_scene()))
    assert "studio_plot(" in code and "lambda x: 0.0 + studio_integral(lambda x: 2 * x, 0.0, x)" in code


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_integral_function_in_manim(tmp_path) -> None:
    from manim import tempconfig

    scene = integral_scene("k cos(x)")
    scene.steps.append(play(make_animation(AnimationKind.SET_VALUE, "pk", "v", value=2.0, run_time=0.3)))
    namespace: dict = {}
    exec(compile(generate_script(make_project(scene)), "integral.py", "exec"), namespace)
    with tempconfig({"dry_run": True, "quality": "low_quality", "media_dir": str(tmp_path)}):
        rendered = namespace["Integral"]()
        rendered.render()
    axes = next(m for m in rendered.mobjects if type(m).__name__ == "Axes")
    expected = graphs.antiderivative_function(scene, scene.object_by_id("F"), {"k": 2.0})
    # the redrawn F after k = 2: every point of the curve lies on 2 sin(x)
    curves = [m for m in rendered.mobjects if m is not axes and len(m.points) > 50]
    on_f = [
        max(abs(axes.p2c(point)[1] - expected(axes.p2c(point)[0])) for point in curve.points[::7])
        for curve in curves
    ]
    assert min(on_f) < 0.01
