"""Curved arrows: geometry like Manim's CurvedArrow, code, size and rendering."""

from __future__ import annotations

import importlib.util
import math

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model.curved import curved_parts, curved_size
from manim_studio.model.entities import Scene
from manim_studio.model.types import AnimationKind, ObjectKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_animation, make_object, make_project, play

HAS_MANIM = importlib.util.find_spec("manim") is not None


def arrow(tips: str = "end", angle: float = 60.0, length: float = 3.0, object_id: str = "b"):
    return make_object(ObjectKind.CURVED_ARROW, "Bogen", object_id, length=length, angle=angle, tips_at=tips)


def test_curved_arrow_geometry() -> None:
    parts = curved_parts(arrow("none", 60.0))
    start, end = parts.shaft[0], parts.shaft[-1]
    assert start == pytest.approx((-1.5, 0.0)) and end == pytest.approx((1.5, 0.0)) and not parts.tips
    # a positive angle bends the arc below the chord (like Manim); the sagitta is (L/2) tan(angle/4)
    lowest = min(y for _x, y in parts.shaft)
    assert lowest == pytest.approx(-1.5 * math.tan(math.radians(15)), abs=1e-3)
    assert max(y for _x, y in curved_parts(arrow("none", -60.0)).shaft) == pytest.approx(-lowest, abs=1e-3)
    single = curved_parts(arrow("end"))
    assert len(single.tips) == 1 and single.tips[0][0] == pytest.approx((1.5, 0.0))
    double = curved_parts(arrow("both"))
    assert len(double.tips) == 2 and double.tips[1][0] == pytest.approx((-1.5, 0.0))
    straight = curved_parts(arrow("end", 0.0))
    assert all(abs(y) < 1e-9 for _x, y in straight.shaft)
    width, height = curved_size(arrow("none", 180.0))
    assert (width, height) == pytest.approx((3.0, 1.5), abs=1e-3)  # a half circle


def test_curved_arrow_code() -> None:
    objects = [arrow("end", object_id="a"), arrow("both", -90.0, object_id="b"), arrow("none", 120.0, object_id="c")]
    objects[1].rotation = 30.0
    scene = Scene(id="s", name="S", objects=objects, steps=[play(*(make_animation(AnimationKind.CREATE, o.id) for o in objects))])
    code = generate_script(make_project(scene))
    assert "CurvedArrow(\n            [-1.5, 0.0, 0.0],\n            [1.5, 0.0, 0.0],\n            angle=60.0 * DEGREES," in code
    assert "CurvedDoubleArrow(" in code and "angle=-90.0 * DEGREES" in code and "ArcBetweenPoints(" in code
    assert not has_errors(validate_scene(scene))


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
@pytest.mark.parametrize("tips", ["none", "end", "both"])
@pytest.mark.parametrize("angle", [60.0, -100.0, 250.0, 0.0])
def test_curved_arrow_matches_manim(tips: str, angle: float) -> None:
    import numpy as np
    from manim import DEGREES, ArcBetweenPoints, CurvedArrow, CurvedDoubleArrow

    cls = {"none": ArcBetweenPoints, "end": CurvedArrow, "both": CurvedDoubleArrow}[tips]
    mobject = cls(np.array([-1.5, 0.0, 0.0]), np.array([1.5, 0.0, 0.0]), angle=angle * DEGREES)
    parts = curved_parts(arrow(tips, angle))
    # the very same Bézier points (the tips are submobjects, so mobject.points is the arc alone)
    assert [value for point in parts.shaft for value in point] == pytest.approx([value for point in mobject.points for value in point[:2]], abs=1e-6)
    manim_tips = [mobject.tip] if tips == "end" else [mobject.tip, mobject.start_tip] if tips == "both" else []
    assert len(parts.tips) == len(manim_tips)
    for ours, theirs in zip(parts.tips, manim_tips):
        vertices = [tuple(vertex[:2]) for vertex in theirs.get_vertices()]
        assert [value for point in ours for value in point] == pytest.approx([value for point in vertices for value in point], abs=1e-6)
    # the bounding box (used by move_to) agrees, so the stage and the video are centered alike
    width, height = curved_size(arrow(tips, angle))
    assert (width, height) == pytest.approx((mobject.width, mobject.height), abs=1e-6)


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_curved_arrows_with_every_animation_render(tmp_path) -> None:
    from manim_studio.model.schema import animation_allowed
    from manim_studio.model.types import ENTRANCE_ANIMATIONS, EXIT_ANIMATIONS, MOTION_ANIMATIONS, TRANSFORM_ANIMATIONS
    from tests.test_manim_integration import run_manim

    arrows = [arrow(tips, angle, object_id=f"b{i}") for i, (tips, angle) in enumerate((("end", 60.0), ("both", -120.0), ("none", 200.0)))]
    for index, obj in enumerate(arrows):
        obj.x, obj.y = -4.0 + 4.0 * index, 1.0
    circle = make_object(ObjectKind.CIRCLE, "Kreis", "k", 0.0, -2.0)
    from manim_studio.model.schema import WARP_ANIMATIONS

    skipped = TRANSFORM_ANIMATIONS | MOTION_ANIMATIONS | WARP_ANIMATIONS  # maps fix the shape in place (see test_warps.py)
    allowed = [kind for kind in AnimationKind if animation_allowed(kind, ObjectKind.CURVED_ARROW, {}) and kind not in skipped]
    entrances = [kind for kind in allowed if kind in ENTRANCE_ANIMATIONS]
    exits = [kind for kind in allowed if kind in EXIT_ANIMATIONS]
    others = [kind for kind in allowed if kind not in ENTRANCE_ANIMATIONS and kind not in EXIT_ANIMATIONS]
    ids = [obj.id for obj in arrows]
    steps = []
    for index, kind in enumerate(entrances):
        target = ids[index % 3]
        steps += [play(make_animation(kind, target, f"in{index}", run_time=0.1)), play(make_animation(AnimationKind.FADE_OUT, target, f"out{index}", run_time=0.1))]
    steps.append(play(*(make_animation(AnimationKind.FADE_IN, target, f"show-{target}", run_time=0.1) for target in ids)))
    steps += [play(make_animation(kind, ids[index % 3], f"o{index}", run_time=0.1)) for index, kind in enumerate(others)]
    steps.append(play(make_animation(AnimationKind.TRANSFORM, "b0", "t1", run_time=0.1, target="k")))
    steps.append(play(make_animation(AnimationKind.REPLACEMENT_TRANSFORM, "b1", "t2", run_time=0.1, target="b2")))
    for index, kind in enumerate(exits):
        steps += [play(make_animation(kind, "b2", f"x{index}", run_time=0.1)), play(make_animation(AnimationKind.FADE_IN, "b2", f"back{index}", run_time=0.1))]
    scene = Scene(id="s", name="Boegen", objects=[*arrows, circle], steps=steps)
    assert len(entrances) >= 5 and len(exits) >= 3 and len(others) >= 8
    assert not has_errors(validate_scene(scene)), [issue.code for issue in validate_scene(scene)]
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Boegen", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]


def test_curved_arrows_round_trip_through_the_importer() -> None:
    from manim_studio.importer import import_script

    objects = [arrow("end", 60.0, object_id="a"), arrow("both", -90.0, 2.0, object_id="b"), arrow("none", 120.0, object_id="c")]
    objects[0].x, objects[0].y, objects[1].rotation, objects[2].x = 1.0, 2.0, 30.0, -3.0
    scene = Scene(id="s", name="S", objects=objects, steps=[play(*(make_animation(AnimationKind.CREATE, o.id) for o in objects))])
    imported = import_script(generate_script(make_project(scene))).project.scenes[0].objects
    assert [(o.kind, o.params["tips_at"], o.params["angle"], o.params["length"]) for o in imported] == [
        (ObjectKind.CURVED_ARROW, "end", 60.0, 3.0),
        (ObjectKind.CURVED_ARROW, "both", -90.0, 2.0),
        (ObjectKind.CURVED_ARROW, "none", 120.0, 3.0),
    ]
    assert [(round(o.x, 6), round(o.y, 6), round(o.rotation, 6)) for o in imported] == [(1.0, 2.0, 0.0), (0.0, 0.0, 30.0), (-3.0, 0.0, 0.0)]
    # written by hand: the chord from (0, 0) to (2, 0); the object sits at the center of the box around the arc
    hand = import_script("from manim import *\n\nclass H(Scene):\n    def construct(self):\n        b = CurvedArrow(ORIGIN, 2 * RIGHT)\n        self.add(b)\n")
    obj = hand.project.scenes[0].objects[0]
    assert obj.params["angle"] == pytest.approx(45.0) and obj.x == pytest.approx(1.0) and obj.y < 0
