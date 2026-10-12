"""Formulas that compute their result (= …), also with parameters (user request)."""

from __future__ import annotations

import importlib.util
import shutil

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model.entities import Scene
from manim_studio.model.latex_term import latex_to_term, shown_latex
from manim_studio.model.types import AnimationKind, ObjectKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_animation, make_object, make_project, play

CAN_RENDER = importlib.util.find_spec("manim") is not None and shutil.which("latex") is not None


def result_scene(latex: str = r"\frac{a^2}{2} + 3") -> Scene:
    a = make_object(ObjectKind.PARAMETER, "a", "pa", symbol="a", value=1.0, minimum=0.0, maximum=5.0)
    formula = make_object(ObjectKind.MATH_TEX, "Formel", "f", latex=latex, show_result=True)
    steps = [play(make_animation(AnimationKind.WRITE, "f")), play(make_animation(AnimationKind.SET_VALUE, "pa", "v", value=4.0, run_time=0.3))]
    return Scene(id="s", name="Ergebnis", objects=[a, formula], steps=steps)


@pytest.mark.parametrize(
    ("latex", "value"),
    [(r"3 \cdot 4 + 2", 14.0), (r"\frac{1}{4} + \sqrt{9}", 3.25), (r"2^{3} \div 4", 2.0), (r"\sin(\pi/2) + \left(1 + 1\right)", 3.0)],
)
def test_latex_terms(latex, value) -> None:
    scene = result_scene(latex)
    assert shown_latex(scene, scene.object_by_id("f")) == f"{latex} = {value:.2f}"


def test_result_follows_the_parameter() -> None:
    scene = result_scene()
    formula = scene.object_by_id("f")
    assert shown_latex(scene, formula) == r"\frac{a^2}{2} + 3 = 3.50"
    assert shown_latex(scene, formula, {"a": 4.0}) == r"\frac{a^2}{2} + 3 = 11.00"
    assert not has_errors(validate_scene(scene))
    assert latex_to_term(r"\frac{a}{2}") == "((a)/(2))"
    code = generate_script(make_project(scene))
    assert r'MathTex(r"\frac{a^2}{2} + 3 = 3.50"' in code
    assert r'mob.become(MathTex(r"\frac{a^2}{2} + 3 = " + f"{(a.get_value() ** 2.0 / 2 + 3):.2f}"' in code


@pytest.mark.parametrize("latex", [r"x^2 + 1", r"a^2 + b^2 = c^2", r"\int_0^1 t\,dt"])
def test_formulas_that_cannot_be_computed(latex) -> None:
    assert "formula_not_computable" in {issue.code for issue in validate_scene(result_scene(latex))}


@pytest.mark.manim
@pytest.mark.skipif(not CAN_RENDER, reason="needs Manim and LaTeX")
def test_result_in_manim(tmp_path) -> None:
    from tests.test_manim_integration import run_manim

    result = run_manim(tmp_path, generate_script(make_project(result_scene())), "Ergebnis", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
