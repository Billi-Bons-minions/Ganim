"""Coordinates of objects in formulas: ``A.x``, ``A.y`` and ``dist(A, B)`` (numbers, positions, results)."""

from __future__ import annotations

import importlib.util
import math
import re

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model import graphs
from manim_studio.model.entities import Scene, Step
from manim_studio.model.playback import state_at_time
from manim_studio.model.state import parameter_values
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_animation, make_object, make_project, play

HAS_MANIM = importlib.util.find_spec("manim") is not None


def formula_scene() -> Scene:
    """A segment AB with its length as a live number and its midpoint M; B moves."""
    a = make_object(ObjectKind.DOT, "A", "a", -3.0, -1.0)
    b = make_object(ObjectKind.DOT, "B", "b", 1.0, 2.0)
    side = make_object(ObjectKind.LINE, "AB", "ab", attach="between", attach_start="a", attach_end="b")
    middle = make_object(ObjectKind.DOT, "M", "m", attach="formula", attach_x="(A.x + B.x)/2", attach_y="(A.y + B.y)/2")
    length = make_object(ObjectKind.DECIMAL_NUMBER, "Laenge", "l", 3.0, 3.0, formula="dist(A, B)", decimals=2)
    move = make_animation(AnimationKind.MOVE, "b", "mv", x=3.0, y=-2.0)
    move.rate_func = "linear"
    return Scene(id="s", name="Strecke", objects=[a, b, side, middle, length], steps=[play(move)])


def test_formulas_follow_the_objects() -> None:
    scene = formula_scene()
    assert not has_errors(validate_scene(scene))
    formula = graphs.number_formula(scene, scene.object_by_id("l"))
    assert graphs.uses_positions(formula) and set(graphs.position_users(scene, formula)) == {"a", "b"}
    states = state_at_time(scene, 0.5)
    b = states["b"]
    assert (states["m"].x, states["m"].y) == pytest.approx(((-3.0 + b.x) / 2, (-1.0 + b.y) / 2))
    values = parameter_values(scene, states)
    assert formula.evaluate(0.0, values) == pytest.approx(math.hypot(b.x + 3.0, b.y + 1.0))
    # unknown names and an own position are explained
    assert graphs.formula_error(scene, "dist(A, Q)").code == "unknown_object"
    scene.object_by_id("m").params["attach_x"] = "M.x + 1"
    assert any(issue.code == "attach_formula_self" for issue in validate_scene(scene))


def test_code() -> None:
    code = generate_script(make_project(formula_scene()))
    assert "np.sqrt((a.get_center()[0] - b.get_center()[0]) ** 2.0 + (a.get_center()[1] - b.get_center()[1]) ** 2.0)" in code
    assert "m.add_updater(lambda mob: mob.move_to([(a.get_center()[0] + b.get_center()[0]) / 2, (a.get_center()[1] + b.get_center()[1]) / 2, 0.0]), call_updater=True)" in code
    assert code.index("b = Dot(") < code.index("laenge = DecimalNumber(")  # the number reads B at once


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_frames_like_manim(tmp_path) -> None:
    """Length and midpoint in every frame like the stage."""
    from tests.test_manim_integration import run_manim

    scene = formula_scene()
    record = "\n".join(
        [
            "spur = []",
            "beobachter = Mobject()",
            "beobachter.add_updater(lambda m, dt: dt > 0 and spur.append((self.renderer.num_plays + self.last_t, laenge.get_value(), *m_dot_center())))",
            "m_dot_center = lambda: [float(v) for v in m.get_center()[:2]]",
            "self.add(beobachter)",
        ]
    )
    scene.steps.insert(0, Step(id="record", kind=StepKind.CODE, code=record, wait_time=0.0))
    scene.steps.append(Step(id="report", kind=StepKind.CODE, code="for frame in spur:\n    print('FRAME', *[round(float(v), 5) for v in frame])", wait_time=0.0))
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Strecke", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    frames = [[float(v) for v in match.split()] for match in re.findall(r"FRAME ([^\n]+)", result.stdout)]
    assert len(frames) > 10
    formula = graphs.number_formula(scene, scene.object_by_id("l"))
    for time, length, mx, my in frames:
        if 1e-6 < time < 1 - 1e-6:
            states = state_at_time(scene, time)
            assert length == pytest.approx(formula.evaluate(0.0, parameter_values(scene, states)), abs=2e-3), time
            assert (mx, my) == pytest.approx((states["m"].x, states["m"].y), abs=2e-3), time


def test_angles() -> None:
    a, b, c = (make_object(ObjectKind.DOT, name, key, x, y) for name, key, x, y in (("A", "a", 0.0, 0.0), ("B", "b", 4.0, 0.0), ("C", "c", 1.0, 3.0)))
    scene = Scene(id="s", name="S", objects=[a, b, c])
    values = graphs.initial_values(scene)
    total = graphs.parse_formula(scene, "angle(B, A, C) + angle(A, B, C) + angle(A, C, B)")
    assert total.evaluate(0.0, values) == pytest.approx(180.0)
    assert graphs.parse_formula(scene, "angle(B, A, C)").evaluate(0.0, values) == pytest.approx(math.degrees(math.atan2(3, 1)))
    # what the user types is limited, not what dist/angle become
    assert graphs.formula_error(scene, " + ".join(["angle(A, B, C)"] * 5)) is None


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_angle_like_manim(tmp_path) -> None:
    from tests.test_manim_integration import run_manim

    scene = formula_scene()
    scene.objects.append(make_object(ObjectKind.DOT, "D", "d", -2.0, 2.0))
    scene.objects.append(make_object(ObjectKind.DECIMAL_NUMBER, "Winkel", "w", -3.0, 3.0, formula="angle(B, A, D)", decimals=3))
    report = "print('ANGLE', round(float(winkel.get_value()), 4))"
    scene.steps.append(Step(id="report", kind=StepKind.CODE, code=report, wait_time=0.0))
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Strecke", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    from manim_studio.model.state import states_after

    states = states_after(scene, 0)
    ours = graphs.number_formula(scene, scene.object_by_id("w")).evaluate(0.0, parameter_values(scene, states))
    theirs = float(re.search(r"ANGLE (\S+)", result.stdout).group(1))
    assert ours == pytest.approx(theirs, abs=1e-3)
