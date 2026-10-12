"""Coupled objects (Manim updaters): follow an object or a formula with parameters."""

from __future__ import annotations

import math

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model import operations as ops
from manim_studio.model.attach import can_follow, set_attach_mode
from manim_studio.model.entities import Scene
from manim_studio.model.playback import state_at_time
from manim_studio.model.schema import animation_allowed
from manim_studio.model.stage_edits import check_edit
from manim_studio.model.state import START, states_after
from manim_studio.model.types import AnimationKind, ObjectKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_animation, make_object, make_project, play


def _scene() -> Scene:
    dot = make_object(ObjectKind.DOT, "Punkt", "d", -4.0, 1.0)
    label = make_object(ObjectKind.TEXT, "P", "l", -4.0, 1.6, text="P", attach="follow", attach_target="d")
    angle = make_object(ObjectKind.PARAMETER, "w", "w", symbol="w", value=0.0, minimum=0.0, maximum=7.0)
    orbiter = make_object(ObjectKind.DOT, "Q", "q", attach="formula", attach_x="2 cos(w)", attach_y="2 sin(w)")
    tag = make_object(ObjectKind.TEXT, "Q-Text", "t", 2.4, 0.0, text="Q", attach="follow", attach_target="q")
    return Scene(
        id="s",
        name="S",
        objects=[dot, label, angle, orbiter, tag],
        steps=[
            play(make_animation(AnimationKind.MOVE, "d", "m", x=4.0, y=-2.0), make_animation(AnimationKind.SET_VALUE, "w", "v", value=math.pi)),
        ],
    )


def test_followers_and_formulas_on_the_stage() -> None:
    scene = _scene()
    assert not has_errors(validate_scene(scene))
    start = states_after(scene, START)
    assert (start["q"].x, start["q"].y) == pytest.approx((2.0, 0.0))
    assert (start["t"].x, start["t"].y) == pytest.approx((2.4, 0.0))  # placed next to Q's start position
    end = states_after(scene, 0)
    assert (end["l"].x, end["l"].y) == pytest.approx((4.0, -1.4))
    assert (end["q"].x, end["q"].y) == pytest.approx((-2.0, 0.0), abs=1e-6)
    assert (end["t"].x, end["t"].y) == pytest.approx((-1.6, 0.0), abs=1e-6)  # a follower of a follower
    halfway = state_at_time(scene, 0.5)
    assert halfway["l"].x == pytest.approx(halfway["d"].x) and halfway["l"].y == pytest.approx(halfway["d"].y + 0.6)
    assert math.hypot(halfway["q"].x, halfway["q"].y) == pytest.approx(2.0)


def test_code_uses_updaters() -> None:
    code = generate_script(make_project(_scene()))
    assert "p.add_updater(lambda m: m.move_to(punkt.get_center() + np.array([0.0, 0.6, 0.0])), call_updater=True)" in code
    assert "q.add_updater(lambda m: m.move_to([2 * np.cos(w.get_value()), 2 * np.sin(w.get_value()), 0.0]), call_updater=True)" in code
    assert "q_text.add_updater(lambda m: m.move_to(q.get_center() + np.array([0.4, 0.0, 0.0])), call_updater=True)" in code


def test_rules_for_coupled_objects() -> None:
    scene = _scene()
    label = scene.object_by_id("l")
    assert not animation_allowed(AnimationKind.MOVE, label.kind, label.params)
    assert not animation_allowed(AnimationKind.TRANSFORM, label.kind, label.params)
    assert animation_allowed(AnimationKind.ROTATE, label.kind, label.params)
    assert check_edit(scene, START, ["l"], "move").allowed  # at the start: changes the distance
    assert check_edit(scene, 0, ["l"], "move").reason == "coupled"
    assert check_edit(scene, START, ["q"], "move").reason == "coupled"
    assert not can_follow(scene, "d", scene.object_by_id("l"))  # would be a circle
    scene.object_by_id("d").params.update(attach="follow", attach_target="l")
    assert "attach_cycle" in {issue.code for issue in validate_scene(scene)}
    scene.object_by_id("d").params.update(attach="none")
    scene.object_by_id("q").params["attach_x"] = "x + 1"
    assert "attach_only_parameters" in {issue.code for issue in validate_scene(scene)}


def test_switching_on_keeps_things_in_place_and_deleting_the_target_detaches() -> None:
    scene = _scene()
    dot = make_object(ObjectKind.DOT, "Neu", "n", 1.5, -0.5)
    scene.objects.append(dot)
    set_attach_mode(scene, "n", "formula")
    assert (dot.params["attach_x"], dot.params["attach_y"]) == ("1.5", "-0.5")
    scene.objects.append(make_object(ObjectKind.SQUARE, "Box", "b", 1.0, -1.0))
    dot.params.pop("attach_target", None)
    set_attach_mode(scene, "n", "follow")
    assert dot.params["attach_target"] == "b"  # the nearest object
    ops.remove_objects(scene, ["b"])
    assert dot.params["attach_target"] is None and "attach_target_missing" in {issue.code for issue in validate_scene(scene)}
