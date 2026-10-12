"""Function values of graphs in formulas: ``f(a)`` in numbers, results and position formulas."""

from __future__ import annotations

import importlib.util
import re

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model.entities import Scene, Step
from manim_studio.model.expression import ExpressionError, parse_expression
from manim_studio.model.graphs import formula_error, formula_functions, number_value, parameter_users, parse_formula
from manim_studio.model.state import states_after
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_animation, make_object, make_project, play

HAS_MANIM = importlib.util.find_spec("manim") is not None


def graph_scene() -> Scene:
    a = make_object(ObjectKind.PARAMETER, "a", "pa", symbol="a", value=1.0, minimum=-5.0, maximum=5.0)
    k = make_object(ObjectKind.PARAMETER, "k", "pk", symbol="k", value=2.0, minimum=-5.0, maximum=5.0)
    axes = make_object(ObjectKind.AXES, "Achsen", "ax")
    f = make_object(ObjectKind.FUNCTION_GRAPH, "f", "f", expression="k x^2 / 2", axes_id="ax")
    g = make_object(ObjectKind.FUNCTION_GRAPH, "g", "g", curve="derivative", derive_from="f", axes_id="ax")
    piecewise = make_object(ObjectKind.FUNCTION_GRAPH, "p", "pw", curve="piecewise", axes_id="ax")
    unnamed = make_object(ObjectKind.FUNCTION_GRAPH, "Funktionsgraph 1", "u", expression="x", axes_id="ax")
    return Scene(id="s", name="S", objects=[a, k, axes, f, g, piecewise, unnamed])


def test_calls_are_replaced_by_the_term() -> None:
    f = parse_expression("x^2 / 2")
    expression = parse_expression("f(a) + 2f(1) + af(2)", "x", ("a",), {"f": f})
    assert expression.evaluate(0.0, {"a": 3.0}) == pytest.approx(4.5 + 1.0 + 6.0)
    assert expression.used_parameters() == {"a"}
    code = expression.to_numpy({"a": "a.get_value()"}, pad_variable=False)
    assert "f(" not in code and "a.get_value()" in code
    assert eval(code, {"np": __import__("numpy"), "a": type("T", (), {"get_value": lambda self: 3.0})()}) == pytest.approx(11.5)  # noqa: S307 - generated code
    nested = parse_expression("f(f(a))", "x", ("a",), {"f": f})
    assert nested.evaluate(0.0, {"a": 2.0}) == pytest.approx(2.0)
    with pytest.raises(ExpressionError) as error:
        parse_expression("h(a)", "x", ("a",), {"f": f})
    assert error.value.code == "unknown_function"
    # a parameter wins over a graph of the same name: f(a) is then f·a
    assert parse_expression("f(a)", "x", ("a", "f"), {"f": f}).evaluate(0.0, {"a": 3.0, "f": 2.0}) == pytest.approx(6.0)


def test_which_graphs_formulas_can_call() -> None:
    scene = graph_scene()
    functions = formula_functions(scene)
    assert sorted(functions) == ["f", "g"]  # p is piecewise, "Funktionsgraph 1" is no name
    assert parse_formula(scene, "f(a)").evaluate(0.0, {"a": 3.0, "k": 2.0}) == pytest.approx(9.0)
    assert parse_formula(scene, "g(a)").evaluate(0.0, {"a": 3.0, "k": 2.0}) == pytest.approx(6.0)  # f'(x) = k x
    assert formula_error(scene, "p(a)").code == "graph_not_callable"
    assert formula_error(scene, "f(x)").code == "only_parameters"
    assert formula_error(scene, "q(a)").code == "unknown_graph"


def test_number_shows_a_graph_value_live() -> None:
    scene = graph_scene()
    number = make_object(ObjectKind.DECIMAL_NUMBER, "Zahl", "n", formula="f(a)")
    scene.objects.append(number)
    # f(a) depends on a and on k (the parameter inside f)
    assert parameter_users(scene, number) == {"pa", "pk"}
    assert number_value(scene, number, {"a": 1.0, "k": 2.0}, 0.0) == pytest.approx(1.0)
    scene.steps = [play(make_animation(AnimationKind.SET_VALUE, "pa", "set", value=3.0))]
    states = states_after(scene, 0)
    from manim_studio.model.state import parameter_values

    assert number_value(scene, number, parameter_values(scene, states), 0.0) == pytest.approx(9.0)
    assert not has_errors(validate_scene(scene))
    number.params["formula"] = "p(a)"
    assert any(issue.code == "expression_invalid" for issue in validate_scene(scene))


def test_result_formula_and_position_formula_use_graph_values() -> None:
    from manim_studio.model.attach import formula_position
    from manim_studio.model.latex_term import shown_latex

    scene = graph_scene()
    formula = make_object(ObjectKind.MATH_TEX, "Formel", "m", latex=r"f(2) + \frac{g(1)}{2}", show_result=True)
    dot = make_object(ObjectKind.DOT, "Punkt", "d", attach="formula", attach_x="a", attach_y="f(a)")
    scene.objects += [formula, dot]
    assert shown_latex(scene, formula) == r"f(2) + \frac{g(1)}{2} = 5.00"
    assert formula_position(scene, dot, {"a": 1.5, "k": 2.0}) == pytest.approx((1.5, 2.25))
    assert not has_errors(validate_scene(scene))


def test_code_inlines_the_graph_term() -> None:
    scene = graph_scene()
    scene.objects.append(make_object(ObjectKind.DECIMAL_NUMBER, "Zahl", "n", formula="f(a) + g(1)"))
    code = generate_script(make_project(scene))
    line = next(line for line in code.splitlines() if "set_value(" in line and "zahl" in line)
    assert "a.get_value()" in line and "k.get_value()" in line and "f(" not in line.split("set_value", 1)[1]


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_graph_values_render_like_the_stage(tmp_path) -> None:
    from manim_studio.model.attach import formula_position
    from manim_studio.model.state import parameter_values
    from tests.test_manim_integration import run_manim

    scene = graph_scene()
    scene.objects.remove(scene.object_by_id("pw"))
    number = make_object(ObjectKind.DECIMAL_NUMBER, "Zahl", "n", 0.0, 3.0, formula="f(a) + g(1)")
    dot = make_object(ObjectKind.DOT, "Punkt", "d", attach="formula", attach_x="a", attach_y="f(a) / 4")
    scene.objects += [number, dot]
    scene.steps = [
        play(make_animation(AnimationKind.FADE_IN, "n"), make_animation(AnimationKind.FADE_IN, "d")),
        play(make_animation(AnimationKind.SET_VALUE, "pa", "a", value=-2.5), make_animation(AnimationKind.SET_VALUE, "pk", "k", value=1.5)),
        Step(id="code", kind=StepKind.CODE, code="print('VALUE', round(zahl.get_value(), 4), *[round(float(v), 4) for v in punkt.get_center()[:2]])"),
    ]
    assert not has_errors(validate_scene(scene)), [issue.code for issue in validate_scene(scene)]
    result = run_manim(tmp_path, generate_script(make_project(scene)), "S", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    value, x, y = (float(v) for v in re.search(r"VALUE (\S+) (\S+) (\S+)", result.stdout).groups())
    values = parameter_values(scene, states_after(scene, 1))
    assert value == pytest.approx(number_value(scene, number, values, 0.0), abs=1e-4)
    assert value == pytest.approx(1.5 * 6.25 / 2 + 1.5)
    assert (x, y) == pytest.approx(formula_position(scene, dot, values), abs=1e-4)


def test_issue_messages_explain_term_errors(qapp) -> None:
    from manim_studio.i18n import set_language
    from manim_studio.ui.dialogs.messages import issue_text

    set_language("de")
    scene = graph_scene()
    scene.objects.append(make_object(ObjectKind.DECIMAL_NUMBER, "Zahl", "n", formula="q(a)"))
    issue = next(issue for issue in validate_scene(scene) if issue.code == "expression_invalid")
    text = issue_text(scene, issue)
    assert "Unbekannte Funktion „q“" in text and "benenne den Graphen" in text and "unknown" not in text
