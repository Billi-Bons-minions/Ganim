"""Numbers that show a formula of parameters, e.g. a²/2, live while the parameters change."""

from __future__ import annotations

import importlib.util

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model import graphs
from manim_studio.model.entities import Scene
from manim_studio.model.schema import animation_allowed
from manim_studio.model.types import AnimationKind, ObjectKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_animation, make_object, make_project, play

HAS_MANIM = importlib.util.find_spec("manim") is not None


def formula_scene(formula: str = "a^2/2") -> Scene:
    a = make_object(ObjectKind.PARAMETER, "a", "pa", symbol="a", value=1.0, minimum=0.0, maximum=5.0)
    number = make_object(ObjectKind.DECIMAL_NUMBER, "Zahl", "n", formula=formula)
    steps = [play(make_animation(AnimationKind.FADE_IN, "n")), play(make_animation(AnimationKind.SET_VALUE, "pa", "v", value=3.0))]
    return Scene(id="s", name="Formel", objects=[a, number], steps=steps)


def test_number_shows_its_formula() -> None:
    scene = formula_scene()
    number = scene.object_by_id("n")
    assert graphs.number_value(scene, number, None, 0.0) == pytest.approx(0.5)
    assert graphs.number_value(scene, number, {"a": 3.0}, 0.0) == pytest.approx(4.5)
    assert graphs.parameter_users(scene, number) == {"pa"}
    assert not has_errors(validate_scene(scene))
    # it follows the formula, so "change value" would be undone by its updater
    assert not animation_allowed(AnimationKind.SET_VALUE, ObjectKind.DECIMAL_NUMBER, number.params)
    assert animation_allowed(AnimationKind.SET_VALUE, ObjectKind.DECIMAL_NUMBER, {})


@pytest.mark.parametrize(("formula", "code"), [("2x + a", "number_formula_only_parameters"), ("a +* 2", "expression_invalid")])
def test_bad_formulas_are_reported(formula, code) -> None:
    assert code in {issue.code for issue in validate_scene(formula_scene(formula))}


def test_formula_code_and_conflict() -> None:
    code = generate_script(make_project(formula_scene("sin(a) + 1")))
    line = next(line for line in code.splitlines() if "zahl.add_updater" in line)
    assert "mob.set_value(" in line and "np.sin(a.get_value())" in line and "call_updater=True" in line
    clash = formula_scene()
    clash.steps = [play(make_animation(AnimationKind.FADE_IN, "n"), make_animation(AnimationKind.SET_VALUE, "pa", "v", value=3.0))]
    assert "parameter_conflict" in {issue.code for issue in validate_scene(clash)}


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_formula_number_in_manim(tmp_path) -> None:
    from manim import DecimalNumber, tempconfig

    namespace: dict = {}
    exec(compile(generate_script(make_project(formula_scene())), "formel.py", "exec"), namespace)
    with tempconfig({"dry_run": True, "quality": "low_quality", "media_dir": str(tmp_path)}):
        scene = namespace["Formel"]()
        scene.render()
    number = next(m for top in scene.mobjects for m in top.get_family() if isinstance(m, DecimalNumber))
    assert number.get_value() == pytest.approx(4.5)  # a went to 3, a²/2 = 4.5
