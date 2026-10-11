"""Graphs, calculus, analysis, graph tools and parameters (model and code generation)."""

from __future__ import annotations

import math

import pytest

from manim_studio.codegen import CodegenOptions, generate_script
from manim_studio.model import graphs
from manim_studio.model.analysis import extrema, find_roots, inflection_points, intersections, zeros
from manim_studio.model.calculus import derivative
from manim_studio.model.entities import Scene
from manim_studio.model.expression import ExpressionError, check_expression, parse_expression
from manim_studio.model.playback import state_at_time
from manim_studio.model.stage_edits import VALUE, step_animation, value_edit
from manim_studio.model.state import START, parameter_values, states_after
from manim_studio.model.types import AnimationKind, ObjectKind
from manim_studio.model.validation import validate_scene
from tests.helpers import make_animation, make_object, make_project, play


def axes_scene(*objects) -> Scene:
    axes = make_object(ObjectKind.AXES, "Achsen", "ax")
    return Scene(id="s", name="Graphen", objects=[axes, *objects])


def graph(object_id: str = "g", expression: str = "x^3/3 - x", **params):
    return make_object(ObjectKind.FUNCTION_GRAPH, "Graph", object_id, expression=expression, axes_id="ax", **params)


# --- terms -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("ax^2", "a * x ** 2"),
        ("a sin(k x)", "a * np.sin(k * x)"),
        ("2ak", "2 * a * k + 0 * x"),
        ("xsin(x)", "x * np.sin(x)"),
    ],
)
def test_parameters_and_split_names(text: str, code: str) -> None:
    expression = parse_expression(text, parameters=("a", "k"))
    assert expression.to_numpy() == code
    assert expression.used_parameters() <= {"a", "k"}


def test_parameters_are_renamed_and_evaluated() -> None:
    expression = parse_expression("a x + b", parameters=("a", "b"))
    assert expression.to_numpy({"a": "a.get_value()", "b": "b.get_value()"}) == "a.get_value() * x + b.get_value()"
    assert expression.evaluate(2.0, {"a": 3.0, "b": 1.0}) == 7.0
    assert check_expression("a x") is not None
    with pytest.raises(ExpressionError):
        parse_expression("x + 1", variable="t")
    assert parse_expression("cos(t)", variable="t").to_numpy() == "np.cos(t)"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("sin(x)", "cos(x)"),
        ("x^3/3 - x", "x^2 - 1"),
        ("2x^2 + 3x - 1", "4*x + 3"),
        ("e^x", "e^x"),
        ("ln(x)", "1/x"),
        ("a x^2", "2*a*x"),
        ("3", "0"),
    ],
)
def test_symbolic_derivative(text: str, expected: str) -> None:
    assert derivative(parse_expression(text, parameters=("a",))).source == expected


@pytest.mark.parametrize("text", ["x*sin(x)", "exp(-x^2)", "(x+1)/(x-1)", "sqrt(x)", "tan(x)", "x^x", "2^x", "atan(x)^2"])
def test_derivative_matches_numerics(text: str) -> None:
    expression = parse_expression(text)
    first = derivative(expression)
    for x in (0.3, 0.9, 1.7):
        h = 1e-6
        numeric = (expression.evaluate(x + h) - expression.evaluate(x - h)) / (2 * h)
        assert first.evaluate(x) == pytest.approx(numeric, rel=1e-5, abs=1e-6)
        assert parse_expression(first.source).evaluate(x) == pytest.approx(first.evaluate(x))


# --- analysis ------------------------------------------------------------------------------


def test_roots_skip_poles_and_find_touching_zeros() -> None:
    assert find_roots(lambda x: 1 / x, -5, 5) == []
    assert find_roots(lambda x: x * x, -5, 5) == pytest.approx([0.0], abs=1e-6)
    assert [p.x for p in zeros(parse_expression("sin(x)"), -4, 4)] == pytest.approx([-math.pi, 0.0, math.pi], abs=1e-8)
    assert [p.x for p in zeros(parse_expression("tan(x)"), -2, 2)] == pytest.approx([0.0], abs=1e-8)


def test_extrema_inflection_and_intersections() -> None:
    cubic = parse_expression("x^3 - 3x")
    found = [(p.x, p.y, p.kind) for p in extrema(cubic, -5, 5)]
    assert found == [(-1.0, 2.0, "maximum"), (1.0, -2.0, "minimum")]
    assert [(p.x, p.kind) for p in inflection_points(cubic, -5, 5)] == [(0.0, "inflection")]
    assert extrema(parse_expression("x^3"), -5, 5) == []
    meet = intersections(parse_expression("x^2"), parse_expression("x + 2"), -5, 5)
    assert [(p.x, p.y) for p in meet] == [(-1.0, 1.0), (2.0, 4.0)]


# --- graphs ------------------------------------------------------------------------------------


def test_clipped_graph_splits_at_poles() -> None:
    scene = axes_scene(graph(expression="tan(x)"))
    segments = graphs.curve_points(scene, scene.object_by_id("g"))
    assert len(segments) == 3
    assert all(-3.0 - 1e-9 <= y <= 3.0 + 1e-9 for segment in segments for _x, y in segment)


def test_piecewise_and_derivative_graphs() -> None:
    piecewise = graph("p", curve="piecewise", pieces=[["x^2", "-5", "1"], ["x + 2", "1", "5"]], clip=False)
    derived = graph("d", curve="derivative", derive_from="p")
    scene = axes_scene(piecewise, derived)
    f = graphs.graph_function(scene, piecewise)
    assert (f(0.5), f(1.0), f(3.0)) == (0.25, 3.0, 5.0)
    assert len(graphs.curve_points(scene, piecewise)) == 2
    df = graphs.graph_function(scene, derived)
    assert (df(0.5), df(3.0)) == (1.0, 1.0)
    assert graphs.piece_breaks(graphs.function_pieces(scene, piecewise), -5, 5) == [1.0]
    loop = graph("l", curve="derivative", derive_from="l")
    assert graphs.function_pieces(axes_scene(loop), loop) is None


def test_parametric_and_polar_curves() -> None:
    circle = graph("c", curve="parametric", x_expression="cos(t)", y_expression="sin(t)")
    rose = graph("r", curve="polar", r_expression="2")
    scene = axes_scene(circle, rose)
    for obj, radius in ((circle, 1.0), (rose, 2.0)):
        points = [point for segment in graphs.curve_points(scene, obj) for point in segment]
        assert all(math.hypot(x, y) == pytest.approx(radius, abs=1e-9) for x, y in points)


def test_graph_tools_geometry() -> None:
    g = graph(clip=False)
    area = make_object(ObjectKind.GRAPH_AREA, "A", "a", graph_id="g", x_min=0.0, x_max=1.0)
    riemann = make_object(ObjectKind.RIEMANN, "R", "r", graph_id="g", x_min=0.0, x_max=1.0, dx=0.25, sample="right")
    tangent = make_object(ObjectKind.TANGENT, "T", "t", graph_id="g", x_value=2.0, width=2.0)
    point = make_object(ObjectKind.GRAPH_POINT, "P", "p", graph_id="g", x_value=3.0)
    markers = make_object(ObjectKind.GRAPH_MARKERS, "M", "m", graph_id="g", feature="extrema")
    scene = axes_scene(g, area, riemann, tangent, point, markers)
    assert graphs.area_value(scene, area) == pytest.approx(1 / 12 - 1 / 2, abs=1e-6)
    assert len(graphs.riemann_rectangles(scene, riemann)) == 4
    assert graphs.tangent_slope(scene, tangent) == pytest.approx(3.0)
    assert graphs.tangent_points(scene, tangent)[0] == pytest.approx((1.0, 2 / 3 - 3.0))
    assert graphs.graph_point(scene, point) == pytest.approx((3.0, 6.0))
    assert [(m.x, m.kind) for m in graphs.marker_points(scene, markers)] == [(-1.0, "maximum"), (1.0, "minimum")]
    assert all(graphs.is_bound(scene, obj) for obj in scene.objects[1:])
    assert graphs.point_label(1.2345, -0.004) == "(1.23 | 0)"


def test_area_follows_clipped_graph_edge() -> None:
    g = graph(expression="x^2")
    area = make_object(ObjectKind.GRAPH_AREA, "A", "a", graph_id="g", x_min=-3.0, x_max=3.0)
    scene = axes_scene(g, area)
    assert max(y for _x, y in graphs.area_polygon(scene, area)) == pytest.approx(3.0)


# --- parameters -------------------------------------------------------------------------------------


def parameter_scene() -> Scene:
    a = make_object(ObjectKind.PARAMETER, "a", "pa", symbol="a", value=1.0, minimum=0.0, maximum=4.0)
    g = graph(expression="a x^2", clip=False)
    point = make_object(ObjectKind.GRAPH_POINT, "P", "p", graph_id="g", x_parameter="pa")
    number = make_object(ObjectKind.DECIMAL_NUMBER, "Zahl", "n", parameter_id="pa")
    scene = axes_scene(a, g, point, number)
    scene.steps.append(play(make_animation(AnimationKind.SET_VALUE, "pa", "change", value=3.0)))
    return scene


def test_parameter_animation_changes_values_over_time() -> None:
    scene = parameter_scene()
    assert parameter_values(scene, states_after(scene, START)) == {"a": 1.0}
    assert parameter_values(scene, states_after(scene, 0)) == {"a": 3.0}
    middle = parameter_values(scene, state_at_time(scene, 0.5))["a"]
    assert 1.0 < middle < 3.0
    point = scene.object_by_id("p")
    assert graphs.graph_point(scene, point, {"a": 2.0}) == pytest.approx((2.0, 8.0))
    assert graphs.parameter_users(scene, point) == {"pa"}
    assert graphs.parameter_users(scene, scene.object_by_id("n")) == {"pa"}


def test_value_edit_sets_start_value_or_records() -> None:
    scene = parameter_scene()
    value_edit(START, "pa", 2.5)(scene)
    assert scene.object_by_id("pa").params["value"] == 2.5
    value_edit(0, "pa", 0.5)(scene)
    assert step_animation(scene, 0, "pa", VALUE).params["value"] == 0.5


def test_parameter_code_uses_value_trackers_and_always_redraw() -> None:
    code = generate_script(make_project(parameter_scene()), CodegenOptions())
    assert "a = ValueTracker(1.0)" in code
    assert code.index("a = ValueTracker") < code.index("achsen = Axes")
    assert "graph = always_redraw(" in code and "lambda x: a.get_value() * x ** 2," in code
    assert "def p_build():" in code and "p = always_redraw(p_build)" in code
    assert "zahl.add_updater(lambda number: number.set_value(a.get_value()))" in code
    assert "self.play(a.animate(run_time=1.0, rate_func=smooth).set_value(3.0))" in code
    assert "self.add(" in code and " a," not in code.split("self.add(")[1].split(")")[0]


def test_graph_tool_code() -> None:
    g = graph(expression="tan(x)")
    area = make_object(ObjectKind.GRAPH_AREA, "Fläche", "a", graph_id="g")
    tangent = make_object(ObjectKind.TANGENT, "Tangente", "t", graph_id="g", x_value=0.0)
    code = generate_script(make_project(axes_scene(g, area, tangent)), CodegenOptions())
    assert "def studio_plot(axes, function" in code
    assert "graph = studio_plot(" in code
    assert "flaeche = achsen.get_area(graph, x_range=(-1, 2)" in code
    assert "tangente = achsen.plot(" in code and "lambda x: 0.0 + 1.0 * (x - 0.0)," in code


def test_graph_validation() -> None:
    bad = graph("b", curve="piecewise", pieces=[])
    lonely = make_object(ObjectKind.TANGENT, "T", "t", graph_id="missing")
    parameter = make_object(ObjectKind.PARAMETER, "x", "px", symbol="x")
    codes = {issue.code for issue in validate_scene(axes_scene(bad, lonely, parameter))}
    assert {"pieces_empty", "graph_missing", "parameter_symbol_invalid"} <= codes
