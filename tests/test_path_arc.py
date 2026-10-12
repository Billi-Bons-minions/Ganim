"""Move and Transform on an arc (Manim's ``path_arc``): model, stage and generated code."""

from __future__ import annotations

import cmath
import importlib.util
import math
import re

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model.entities import Scene, Step
from manim_studio.model.paths import arc_factor, arc_point, arc_polyline
from manim_studio.model.playback import state_at_time
from manim_studio.model.schema import animation_params
from manim_studio.model.state import states_after
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_animation, make_object, make_project, play

HAS_MANIM = importlib.util.find_spec("manim") is not None


def linear(anim):
    anim.rate_func = "linear"
    return anim


def arc_scene() -> Scene:
    """A dot moves on an arc, a square moves on an arc while growing, then turns into a bigger square on an arc."""
    dot = make_object(ObjectKind.DOT, "Punkt", "p", -3.0, -1.0)
    square = make_object(ObjectKind.SQUARE, "Quadrat", "q", -2.0, 2.0, side_length=1.0)
    goal = make_object(ObjectKind.SQUARE, "Ziel", "z", 3.0, 1.0, side_length=2.0)
    steps = [
        play(linear(make_animation(AnimationKind.MOVE, "p", "m1", x=3.0, y=-1.0, path_arc=120.0))),
        play(
            linear(make_animation(AnimationKind.MOVE, "q", "m2", x=1.0, y=2.0, path_arc=-90.0)),
            linear(make_animation(AnimationKind.SCALE, "q", "s2", factor=1.5)),
        ),
        play(linear(make_animation(AnimationKind.TRANSFORM, "q", "t3", target="z", path_arc=90.0))),
    ]
    return Scene(id="s", name="Bogen", objects=[dot, square, goal], steps=steps)


def test_params() -> None:
    for kind in (AnimationKind.MOVE, AnimationKind.TRANSFORM, AnimationKind.REPLACEMENT_TRANSFORM, AnimationKind.TRANSFORM_FROM_COPY):
        assert "path_arc" in [spec.key for spec in animation_params(kind)]
    # FadeTransform cross-fades, TransformMatchingShapes moves pieces: no arc for them
    for kind in (AnimationKind.FADE_TRANSFORM, AnimationKind.TRANSFORM_MATCHING):
        assert "path_arc" not in [spec.key for spec in animation_params(kind)]
    assert not has_errors(validate_scene(arc_scene()))


def test_arc_weight() -> None:
    # straight paths are the plain mix, the end of an arc is the target, half of 180° is the top of a half circle
    assert arc_factor(0.3, 0.0) == 0.3
    assert arc_factor(1.0, 120.0) == pytest.approx(1.0)
    assert arc_point((-1.0, 0.0), (1.0, 0.0), 0.5, 180.0) == pytest.approx((0.0, -1.0))
    assert arc_point((-1.0, 0.0), (1.0, 0.0), 0.5, -180.0) == pytest.approx((0.0, 1.0))
    # Swap keeps its quarter circle
    assert arc_point((0.0, 0.0), (2.0, 0.0), 0.5) == pytest.approx((1.0, 1 - math.sqrt(2)))
    line = arc_polyline((0.0, 0.0), (2.0, 0.0), 0.0)
    assert line == [(0.0, 0.0), (2.0, 0.0)]
    bow = arc_polyline((0.0, 0.0), (2.0, 0.0), 90.0)
    assert bow[0] == pytest.approx((0.0, 0.0)) and bow[-1] == pytest.approx((2.0, 0.0)) and min(y for _x, y in bow) < -0.4


def test_states_on_the_arc() -> None:
    scene = arc_scene()
    half = state_at_time(scene, 0.5)["p"]
    assert (half.x, half.y) == pytest.approx(arc_point((-3.0, -1.0), (3.0, -1.0), 0.5, 120.0))
    # a positive arc runs counterclockwise: from left to right it dips below the line
    assert half.y < -1.0
    assert (states_after(scene, 0)["p"].x, states_after(scene, 0)["p"].y) == pytest.approx((3.0, -1.0))
    # the transform's center travels on the arc, the outlines are mixed with turning weights
    morph = state_at_time(scene, 2.5)["q"]
    assert (morph.x, morph.y) == pytest.approx(arc_point((1.0, 2.0), (3.0, 1.0), 0.5, 90.0))
    assert morph.morph_weights is not None
    source, target = states_after(scene, 1)["q"], states_after(scene, 1)["z"]
    weight = arc_factor(0.5, 90.0)
    frame = morph.scale * cmath.exp(1j * math.radians(morph.rotation))
    assert morph.morph_weights[0] * frame == pytest.approx((1 - weight) * source.scale)
    assert morph.morph_weights[1] * frame == pytest.approx(weight * target.scale)
    # straight transforms keep the plain mix
    straight = arc_scene()
    straight.steps[2].animations[0].params["path_arc"] = 0.0
    assert state_at_time(straight, 2.5)["q"].morph_weights is None


def test_group_moves_rigidly_on_the_arc() -> None:
    a = make_object(ObjectKind.CIRCLE, "A", "a", -1.0, 0.0)
    b = make_object(ObjectKind.CIRCLE, "B", "b", 1.0, 0.0)
    group = make_object(ObjectKind.GROUP, "Gruppe", "g", members=["a", "b"])
    scene = Scene(id="s", name="G", objects=[a, b, group], steps=[play(linear(make_animation(AnimationKind.MOVE, "g", "m", x=0.0, y=4.0, path_arc=90.0)))])
    states = state_at_time(scene, 0.5)
    cx, cy = arc_point((0.0, 0.0), (0.0, 4.0), 0.5, 90.0)
    assert (states["a"].x, states["a"].y) == pytest.approx((cx - 1.0, cy))
    assert (states["b"].x, states["b"].y) == pytest.approx((cx + 1.0, cy))


def test_code() -> None:
    code = generate_script(make_project(arc_scene()))
    assert "punkt.animate(run_time=1.0, rate_func=linear, path_arc=120.0 * DEGREES).move_to([3.0, -1.0, 0.0])" in code
    # moving on an arc while scaling: the arc is only for the center (like the stage)
    assert '("arc_move", 0.0, 1.0, linear, ([1.0, 2.0, 0.0], -90.0 * DEGREES))' in code
    assert "Transform(quadrat, ziel, path_arc=90.0 * DEGREES, run_time=1.0, rate_func=linear)" in code
    copy = arc_scene()
    copy.steps[2].animations[0].kind = AnimationKind.TRANSFORM_FROM_COPY
    assert "ReplacementTransform(quadrat.copy(), ziel, path_arc=90.0 * DEGREES" in generate_script(make_project(copy))


def test_stage_morph_on_the_arc(qapp) -> None:
    """A shape that only moves on an arc stays the same shape; the weights mix the outlines in the moving frame."""
    from PySide6.QtGui import QPainterPath

    from manim_studio.ui.stage.drawing import Drawing, Primitive
    from manim_studio.ui.stage.effects import morph_path

    square = QPainterPath()
    square.addRect(-50, -50, 100, 100)
    drawing = Drawing([Primitive(path=square)], square.boundingRect())
    weight = arc_factor(0.4, 135.0)
    same = morph_path(drawing, drawing, 0.4, (1 - weight, weight))
    assert same.boundingRect().width() == pytest.approx(100, abs=0.5)
    # twice the size on the target: the mix (1 + w) turns and scales the square
    big = QPainterPath()
    big.addRect(-100, -100, 200, 200)
    grown = morph_path(drawing, Drawing([Primitive(path=big)], big.boundingRect()), 0.4, (1 - weight, weight))
    turn = 1 + weight
    corner = grown.toSubpathPolygons()[0][0]
    first = square.toSubpathPolygons()[0][0]
    expected = turn.conjugate() * complex(first.x(), first.y())
    assert (corner.x(), corner.y()) == pytest.approx((expected.real, expected.imag), abs=1.0)


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_arc_weight_like_manim() -> None:
    import numpy as np
    from manim.utils.paths import path_along_arc

    for arc in (90.0, -45.0, 180.0, 200.0, 0.3, 30.0):
        for alpha in (0.0, 0.3, 0.7, 1.0):
            theirs = path_along_arc(math.radians(arc))(np.array([1.0, 2.0, 0.0]), np.array([-3.0, 0.5, 0.0]), alpha)
            assert arc_point((1.0, 2.0), (-3.0, 0.5), alpha, arc) == pytest.approx((theirs[0], theirs[1]), abs=1e-9)


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_frames_like_manim(tmp_path) -> None:
    """Every frame of the rendered video puts the objects where the stage has them."""
    from tests.test_manim_integration import run_manim

    scene = arc_scene()
    record = "\n".join(
        [
            "spur = []",
            "beobachter = Mobject()",
            "beobachter.add_updater(lambda m, dt: dt > 0 and spur.append((self.renderer.num_plays + self.last_t, *punkt.get_center()[:2], *quadrat.get_center()[:2], quadrat.width, *quadrat.points[0][:2])))",
            "self.add(beobachter)",
            "start_quadrat, ziel_ecke = quadrat.points[0].copy(), ziel.points[0].copy()",
        ]
    )
    report = "\n".join(
        [
            "print('START', *[round(float(v), 6) for v in start_quadrat[:2]], *[round(float(v), 6) for v in ziel_ecke[:2]])",
            "for frame in spur:",
            "    print('FRAME', *[round(float(v), 6) for v in frame])",
        ]
    )
    scene.steps.insert(0, Step(id="record", kind=StepKind.CODE, code=record, wait_time=0.0))
    scene.steps.append(Step(id="report", kind=StepKind.CODE, code=report, wait_time=0.0))
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Bogen", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    frames = [tuple(float(v) for v in match.split()) for match in re.findall(r"FRAME ([^\n]+)", result.stdout)]
    start = [float(v) for v in re.search(r"START ([^\n]+)", result.stdout).group(1).split()]
    assert len(frames) > 30
    checked = 0
    for time, px, py, qx, qy, width, cx, cy in frames:
        if time <= 1e-6 or abs(time - round(time)) < 1e-6:
            continue  # the frames between the steps belong to both
        states = state_at_time(scene, time)
        dot, square = states["p"], states["q"]
        assert (px, py) == pytest.approx((dot.x, dot.y), abs=1e-3), time
        assert (qx, qy) == pytest.approx((square.x, square.y), abs=1e-3), time
        if time < 2.0:
            assert width == pytest.approx(square.scale, abs=1e-3), time
        else:
            # the corner Manim moves on its arc is where the stage's weights put it
            # (corners in the objects' own, unscaled coordinates; the weights carry the scales)
            local_source = complex(start[0] + 2.0, start[1] - 2.0)
            local_target = complex(start[2] - 3.0, start[3] - 1.0)
            frame = square.scale * cmath.exp(1j * math.radians(square.rotation))
            weights = square.morph_weights
            assert weights is not None
            expected = complex(square.x, square.y) + frame * (weights[0] * local_source + weights[1] * local_target)
            assert (cx, cy) == pytest.approx((expected.real, expected.imag), abs=1e-3), time
        checked += 1
    assert checked > 30


def test_import() -> None:
    from manim_studio.importer import import_script

    imported = import_script(generate_script(make_project(arc_scene()))).project.scenes[0]
    moves = [anim for step in imported.steps for anim in step.animations if anim.kind == AnimationKind.MOVE]
    transforms = [anim for step in imported.steps for anim in step.animations if anim.kind == AnimationKind.TRANSFORM]
    assert moves[0].params["path_arc"] == pytest.approx(120.0)
    assert transforms[0].params["path_arc"] == pytest.approx(90.0)
    source = "\n".join(
        [
            "from manim import *",
            "class S(Scene):",
            "    def construct(self):",
            "        a = Circle()",
            "        b = Square().shift(RIGHT * 2)",
            "        c = Dot()",
            "        self.add(a, c)",
            "        self.play(ClockwiseTransform(a, b))",
            "        self.play(c.animate(path_arc=PI / 2).move_to(UP))",
            "        self.play(c.animate(path_arc=PI).move_to(DOWN).rotate(PI))",
        ]
    )
    scene = import_script(source).project.scenes[0]
    anims = [anim for step in scene.steps for anim in step.animations]
    assert anims[0].kind == AnimationKind.TRANSFORM and anims[0].params["path_arc"] == pytest.approx(-180.0)
    assert anims[1].params["path_arc"] == pytest.approx(90.0)
    # next to a rotation the arc is the rotation's own
    assert anims[2].kind == AnimationKind.MOVE and anims[2].params["path_arc"] == 0.0


def test_outlines_pair_like_manim(qapp) -> None:
    """Circles start on the right and run counterclockwise, rectangles start upper right (Manim's point order).

    Transform pairs the points in this order: half way from a circle to a square around it,
    Manim's first point lies between (1, 0) and the corner (1, 1).
    """
    from manim_studio.ui.stage.drawing import PX, StageResources, build_drawing
    from manim_studio.ui.stage.effects import morph_path

    circle = make_object(ObjectKind.CIRCLE, "Kreis", "c", radius=1.0)
    square = make_object(ObjectKind.SQUARE, "Quadrat", "q", side_length=2.0)
    scene = Scene(id="s", name="S", objects=[circle, square])
    states = states_after(scene, -1)
    round_one = build_drawing(scene, circle, states["c"], StageResources())
    corner_one = build_drawing(scene, square, states["q"], StageResources())
    ring = round_one.primitives[0].path.toSubpathPolygons()[0]
    assert (ring[0].x(), ring[0].y()) == pytest.approx((PX, 0.0), abs=1e-6)
    assert ring[1].y() < 0  # upwards on the screen: counterclockwise
    box = corner_one.primitives[0].path.toSubpathPolygons()[0]
    assert [(p.x() / PX, -p.y() / PX) for p in box][:4] == [(1.0, 1.0), (-1.0, 1.0), (-1.0, -1.0), (1.0, -1.0)]
    half = morph_path(round_one, corner_one, 0.5).toSubpathPolygons()[0]
    assert (half[0].x() / PX, -half[0].y() / PX) == pytest.approx((1.0, 0.5), abs=1e-6)
