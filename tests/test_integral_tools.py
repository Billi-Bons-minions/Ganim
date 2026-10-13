"""Graph tools on the integral function F(x) = C + ∫ f(t) dt (point, tangent, secant, area, Riemann, markers, labels)."""

from __future__ import annotations

import importlib.util
import math
import re

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model import graphs
from manim_studio.model.entities import Scene, Step
from manim_studio.model.tool_labels import tool_label
from manim_studio.model.types import ObjectKind, StepKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_object, make_project

HAS_MANIM = importlib.util.find_spec("manim") is not None


def integral_scene() -> Scene:
    """f(x) = x² − 1 and F(x) = x³/3 − x with tools on F."""
    axes = make_object(ObjectKind.AXES, "Achsen", "ax", x_min=-3.0, x_max=3.0, y_min=-3.0, y_max=3.0, x_length=6.0, y_length=6.0)
    f = make_object(ObjectKind.FUNCTION_GRAPH, "f", "f", expression="x^2 - 1", axes_id="ax", x_min=-2.5, x_max=2.5)
    big_f = make_object(ObjectKind.FUNCTION_GRAPH, "F", "F", curve="antiderivative", derive_from="f", integral_from=0.0, integral_constant=0.0, axes_id="ax", x_min=-2.5, x_max=2.5)
    point = make_object(ObjectKind.GRAPH_POINT, "Punkt", "p", graph_id="F", x_value=1.5, show_lines=False, show_label=False)
    tangent = make_object(ObjectKind.TANGENT, "Tangente", "t", graph_id="F", x_value=2.0, width=2.0)
    secant = make_object(ObjectKind.SECANT, "Sekante", "s", graph_id="F", x_value=-2.0, h=1.0)
    area = make_object(ObjectKind.GRAPH_AREA, "Flaeche", "a", graph_id="F", x_min=0.0, x_max=1.5)
    riemann = make_object(ObjectKind.RIEMANN, "Riemann", "r", graph_id="F", x_min=-2.0, x_max=-0.5, dx=0.5)
    extrema = make_object(ObjectKind.GRAPH_MARKERS, "Extrema", "e", graph_id="F", feature="extrema", show_labels=False)
    zeros = make_object(ObjectKind.GRAPH_MARKERS, "Nullstellen", "z", graph_id="F", feature="zeros", show_labels=False)
    inflection = make_object(ObjectKind.GRAPH_MARKERS, "Wendepunkte", "w", graph_id="F", feature="inflection", show_labels=False)
    meet = make_object(ObjectKind.GRAPH_MARKERS, "Schnitt", "m", graph_id="F", feature="intersections", other_graph_id="f", show_labels=False)
    label = make_object(ObjectKind.TOOL_LABEL, "Steigung", "l", tool_id="t", content="slope")
    return Scene(id="s", name="Integral", objects=[axes, f, big_f, point, tangent, secant, area, riemann, extrema, zeros, inflection, meet, label])


def big_f(x: float) -> float:
    return x**3 / 3 - x


def test_tools_compute_on_the_integral_function() -> None:
    scene = integral_scene()
    assert not has_errors(validate_scene(scene))
    assert graphs.is_tool_graph(scene.object_by_id("F")) and graphs.graph_point(scene, scene.object_by_id("p")) == pytest.approx((1.5, big_f(1.5)), abs=1e-4)
    # the slope of F is f
    (x0, y0), (x1, y1) = graphs.tangent_points(scene, scene.object_by_id("t"))
    assert (y1 - y0) / (x1 - x0) == pytest.approx(3.0, abs=1e-6) and (y0 + y1) / 2 == pytest.approx(big_f(2.0), abs=1e-4)
    found = graphs.secant(scene, scene.object_by_id("s"))
    assert found.slope == pytest.approx(big_f(-1.0) - big_f(-2.0), abs=1e-4)
    assert graphs.area_value(scene, scene.object_by_id("a")) == pytest.approx(1.5**4 / 12 - 1.5**2 / 2, abs=1e-3)
    tops = [rect[2][1] for rect in graphs.riemann_rectangles(scene, scene.object_by_id("r"))]
    assert tops == pytest.approx([big_f(x) for x in (-2.0, -1.5, -1.0)], abs=1e-4)
    # extrema of F where f changes sign, zeros of F, the inflection point at the minimum of f
    extrema = graphs.marker_points(scene, scene.object_by_id("e"))
    assert [(round(p.x, 4), p.kind) for p in extrema] == [(-1.0, "maximum"), (1.0, "minimum")]
    assert [round(p.x, 4) for p in graphs.marker_points(scene, scene.object_by_id("z"))] == [round(-math.sqrt(3), 4), 0.0, round(math.sqrt(3), 4)]
    assert [round(p.x, 4) for p in graphs.marker_points(scene, scene.object_by_id("w"))] == [0.0]
    meet = graphs.marker_points(scene, scene.object_by_id("m"))
    assert meet and all(abs(big_f(p.x) - (p.x**2 - 1)) < 1e-4 for p in meet)
    assert tool_label(scene, scene.object_by_id("l")).text == "m = 3.00"
    table = graphs.value_table(scene, scene.object_by_id("F"))
    assert table[1][table[0].index("2")] == "0.67"


def test_code_uses_the_integral() -> None:
    code = generate_script(make_project(integral_scene()))
    assert "studio_integral(" in code and "def studio_integral" in code
    assert "achsen.get_riemann_rectangles(" in code and "achsen.get_area(" in code


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_tools_like_manim(tmp_path) -> None:
    """Point, tangent, Riemann rectangles and markers on F lie where the stage has them."""
    from tests.test_manim_integration import run_manim

    scene = integral_scene()
    report = "\n".join(
        [
            "def c(p):",
            "    return ' '.join(str(round(float(v), 4)) for v in achsen.p2c(p)[:2])",
            "print('POINT', c(punkt.get_center()))",
            "print('TANGENT', c(tangente.get_start()), c(tangente.get_end()))",
            "for rect in riemann:",
            "    print('RECT', c(rect.get_top()), c(rect.get_bottom()))",
            "for dot in extrema:",
            "    print('EXTREMUM', c(dot.get_center()))",
        ]
    )
    scene.steps.append(Step(id="report", kind=StepKind.CODE, code=report, wait_time=0.0))
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Integral", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    out = result.stdout
    point = [float(v) for v in re.search(r"POINT (\S+) (\S+)", out).groups()]
    assert point == pytest.approx(graphs.graph_point(scene, scene.object_by_id("p")), abs=2e-3)
    tangent = [float(v) for v in re.search(r"TANGENT (\S+) (\S+) (\S+) (\S+)", out).groups()]
    assert tangent == pytest.approx([v for p in graphs.tangent_points(scene, scene.object_by_id("t")) for v in p], abs=2e-3)
    # a rectangle below the x-axis has its value at the bottom
    heights = [float(top) if abs(float(bottom)) < 1e-3 else float(bottom) for _x, top, _x2, bottom in re.findall(r"RECT (\S+) (\S+) (\S+) (\S+)", out)]
    ours = graphs.riemann_rectangles(scene, scene.object_by_id("r"))
    assert heights == pytest.approx([rect[2][1] for rect in ours], abs=2e-3)
    dots = [tuple(float(v) for v in match) for match in re.findall(r"EXTREMUM (\S+) (\S+)", out)]
    assert [v for dot in dots for v in dot] == pytest.approx([v for p in graphs.marker_points(scene, scene.object_by_id("e")) for v in (p.x, p.y)], abs=2e-3)
