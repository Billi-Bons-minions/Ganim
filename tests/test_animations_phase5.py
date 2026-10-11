"""New animations, camera and colored formulas (model and code generation)."""

from __future__ import annotations

import math

import pytest

from manim_studio.codegen import CodegenOptions, generate_script
from manim_studio.model.animation_builder import build_animations, reference_candidates
from manim_studio.model.entities import Scene
from manim_studio.model.latex import colorize
from manim_studio.model.paths import arc_point, path_polyline, point_at
from manim_studio.model.playback import state_at_time
from manim_studio.model.state import START, states_after, visible_at_start
from manim_studio.model.types import AnimationKind, ObjectKind
from manim_studio.model.validation import validate_scene
from tests.helpers import make_animation, make_object, make_project, play


def motion_scene() -> Scene:
    objects = [
        make_object(ObjectKind.CIRCLE, "Kreis", "c", -3.0, 0.0, radius=0.5),
        make_object(ObjectKind.SQUARE, "Quadrat", "q", 3.0, 0.0),
        make_object(ObjectKind.CIRCLE, "Bahn", "path", 0.0, 0.0, radius=2.0),
    ]
    steps = [
        play(make_animation(AnimationKind.SWAP, "c", "swap", partner="q")),
        play(make_animation(AnimationKind.MOVE_ALONG_PATH, "q", "along", path="path")),
    ]
    return Scene(id="s", name="S", objects=objects, steps=steps)


def test_swap_and_move_along_path_states() -> None:
    scene = motion_scene()
    after_swap = states_after(scene, 0)
    assert (after_swap["c"].x, after_swap["q"].x) == (3.0, -3.0)
    middle = state_at_time(scene, 0.5)
    assert middle["c"].y != 0.0 and middle["q"].y != 0.0
    end = states_after(scene, 1)
    assert (end["q"].x, end["q"].y) == pytest.approx((2.0, 0.0))
    halfway = state_at_time(scene, 1.5)
    assert math.hypot(halfway["q"].x, halfway["q"].y) == pytest.approx(2.0, abs=0.01)
    assert visible_at_start(scene, scene.object_by_id("q")) and visible_at_start(scene, scene.object_by_id("path"))


def test_path_helpers() -> None:
    scene = motion_scene()
    outline = path_polyline(scene, states_after(scene, START), "path")
    assert outline[0] == pytest.approx((2.0, 0.0)) and outline[-1] == pytest.approx((2.0, 0.0))
    assert point_at([(0.0, 0.0), (2.0, 0.0), (2.0, 2.0)], 0.75) == pytest.approx((2.0, 1.0))
    assert arc_point((0.0, 0.0), (2.0, 0.0), 0.5, 90.0) == pytest.approx((1.0, 1.0 - math.sqrt(2)))
    start, end = (0.0, 0.0), (2.0, 0.0)
    assert arc_point(start, end, 0.0) == pytest.approx(start) and arc_point(start, end, 1.0) == pytest.approx(end)


def test_reference_animation_defaults_and_validation() -> None:
    scene = motion_scene()
    candidates = [obj.id for obj in reference_candidates(scene, AnimationKind.MOVE_ALONG_PATH, "c")]
    assert candidates == ["q", "path"]
    swap = build_animations(scene, AnimationKind.SWAP, ["c", "q"], START)[0]
    assert swap.params == {"partner": "q"}
    scene.steps.append(play(make_animation(AnimationKind.MOVE_ALONG_PATH, "c", "bad", path=None)))
    assert "path_missing" in {issue.code for issue in validate_scene(scene)}


def test_new_animation_code() -> None:
    scene = motion_scene()
    scene.steps.append(play(make_animation(AnimationKind.FLASH, "c", "f", color="#FC6255"), make_animation(AnimationKind.WIGGLE, "q", "w")))
    code = generate_script(make_project(scene), CodegenOptions())
    assert "Swap(kreis, quadrat, run_time=1.0" in code
    assert "MoveAlongPath(quadrat, bahn, run_time=1.0, rate_func=linear)" in code
    assert 'Flash(kreis, color="#FC6255"' in code and "Wiggle(quadrat" in code


def test_camera_code() -> None:
    camera = make_object(ObjectKind.CAMERA, "Kamera", "cam", 1.0, 0.0, width=10.0)
    dot = make_object(ObjectKind.DOT, "Punkt", "d")
    scene = Scene(id="s", name="Kamerafahrt", objects=[camera, dot], steps=[play(make_animation(AnimationKind.MOVE, "cam", "m", x=2.0, y=1.0))])
    code = generate_script(make_project(scene), CodegenOptions())
    assert "class Kamerafahrt(MovingCameraScene):" in code
    assert "self.camera.frame.move_to([1.0, 0.0, 0.0])" in code and "self.camera.frame.set(width=10.0)" in code
    assert "self.add(punkt)" in code
    assert "self.play(self.camera.frame.animate(run_time=1.0, rate_func=smooth).move_to([2.0, 1.0, 0.0]))" in code
    second = make_object(ObjectKind.CAMERA, "Kamera 2", "cam2")
    scene.objects.append(second)
    assert "camera_duplicate" in {issue.code for issue in validate_scene(scene)}


def test_colored_formula_parts() -> None:
    assert colorize(r"\frac{a}{b} + a^2 = \alpha", [("a", "#fc6255")]) == r"\frac{\textcolor[HTML]{FC6255}{a}}{b} + \textcolor[HTML]{FC6255}{a}^2 = \alpha"
    assert colorize("x + 2x", [("x", "#111111"), ("2x", "#222222")]) == r"\textcolor[HTML]{111111}{x} + \textcolor[HTML]{222222}{2x}"
    formula = make_object(ObjectKind.MATH_TEX, "Formel", "f", latex="a^2", colored_parts=[["a", "#FC6255"]])
    code = generate_script(make_project(Scene(id="s", name="S", objects=[formula])), CodegenOptions())
    assert "COLOR_TEX = TexTemplate()" in code and "tex_template=COLOR_TEX" in code
