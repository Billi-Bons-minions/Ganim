"""Moving and turning 3D solids (move_to and Rotate) and Manim's shading on the stage."""

from __future__ import annotations

import importlib.util
import re

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model.entities import Scene, Step
from manim_studio.model.playback import state_at_time
from manim_studio.model.state import states_after
from manim_studio.model.three_d import face_shading, solid_axes_center, solid_faces
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_animation, make_object, make_project, play

HAS_MANIM = importlib.util.find_spec("manim") is not None


def solid_scene(shape: str = "cube") -> Scene:
    axes = make_object(ObjectKind.AXES_3D, "Achsen", "ax")
    solid = make_object(ObjectKind.SOLID, "Koerper", "k", axes_id="ax", shape=shape, side=1.5, radius=0.8, height=1.6, resolution=6)
    steps = [
        play(make_animation(AnimationKind.ROTATE_3D, "k", "turn", angle=30.0, axis="x")),
        play(make_animation(AnimationKind.MOVE_3D, "k", "move", x=2.0, y=1.0, z=1.0)),
        play(make_animation(AnimationKind.ROTATE_3D, "k", "turn2", angle=45.0, axis="z")),
    ]
    return Scene(id="s", name="Koerper", objects=[axes, solid], steps=steps)


def test_moves_and_turns() -> None:
    scene = solid_scene()
    solid = scene.object_by_id("k")
    assert not has_errors(validate_scene(scene))
    # move_to puts the center of the bounding box onto the point; turning keeps it there
    assert solid_axes_center(scene, solid, states_after(scene, 1)["k"]) == pytest.approx((2.0, 1.0, 1.0))
    assert solid_axes_center(scene, solid, states_after(scene, 2)["k"]) == pytest.approx((2.0, 1.0, 1.0), abs=1e-9)
    # half way through the first turn the cube is turned by 15 degrees
    half = state_at_time(scene, 0.5)["k"]
    assert half.orientation != states_after(scene, 0)["k"].orientation
    # other animations are refused for solids
    from manim_studio.model.schema import animation_allowed

    assert animation_allowed(AnimationKind.MOVE_3D, ObjectKind.SOLID, {}) and not animation_allowed(AnimationKind.MOVE_3D, ObjectKind.CIRCLE, {})


def test_code() -> None:
    code = generate_script(make_project(solid_scene()))
    assert "Rotate(koerper, angle=30.0 * DEGREES, axis=RIGHT" in code
    assert "ApplyMethod(koerper.move_to, achsen.c2p(2.0, 1.0, 1.0)" in code
    assert "Rotate(koerper, angle=45.0 * DEGREES, axis=OUT" in code


def test_default_target_is_beside_the_solid() -> None:
    from manim_studio.model.animation_builder import build_animations

    scene = solid_scene()
    built = build_animations(scene, AnimationKind.MOVE_3D, ["k"], 1)
    assert (built[0].params["x"], built[0].params["y"], built[0].params["z"]) == pytest.approx((3.0, 1.0, 1.0))


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
@pytest.mark.parametrize("shape", ["cube", "cone", "tetrahedron"])
def test_faces_and_shading_like_manim(tmp_path, shape: str) -> None:
    """After moving and turning, Manim's faces lie where the stage draws them and are shaded alike."""
    from tests.test_manim_integration import run_manim

    scene = solid_scene(shape)
    code = "\n".join(
        [
            "from manim.mobject.three_d.three_d_utils import get_3d_vmob_start_corner, get_3d_vmob_start_corner_unit_normal",
            "from manim.utils.color.core import get_shaded_rgb",
            # the faces only (a polyhedron also has small spheres at its corners, hidden here)
            "source = koerper.faces if hasattr(koerper, 'faces') else koerper",
            "faces = [f for f in source.family_members_with_points() if getattr(f, 'shade_in_3d', False) and len(f.points) >= 12]",
            "for f in faces:",
            "    light = get_shaded_rgb(np.zeros(3), get_3d_vmob_start_corner(f), get_3d_vmob_start_corner_unit_normal(f), np.array([-7.0, -9.0, 10.0]))[0]",
            "    print('FACE', *[round(float(v), 4) for v in f.points[0]], round(float(light), 4))",
        ]
    )
    scene.steps.append(Step(id="code", kind=StepKind.CODE, code=code))
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Koerper", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    theirs = [tuple(float(v) for v in match) for match in re.findall(r"FACE (\S+) (\S+) (\S+) (\S+)", result.stdout)]
    state = states_after(scene, 2)["k"]
    ours = [(*points[0], face_shading(points)[2]) for _corners, points in solid_faces(scene, scene.object_by_id("k"), state=state) if points]
    assert len(ours) == len(theirs)
    for a, b in zip(sorted(ours), sorted(theirs)):
        assert a == pytest.approx(b, abs=2e-3)
