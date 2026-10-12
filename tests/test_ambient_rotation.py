"""The 3D camera keeps turning: begin_ambient_camera_rotation across steps and pauses."""

from __future__ import annotations

import importlib.util
import re

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model.entities import Scene, Step
from manim_studio.model.playback import state_at_time
from manim_studio.model.state import states_after
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_animation, make_object, make_project, play, wait

HAS_MANIM = importlib.util.find_spec("manim") is not None


def turning_scene() -> Scene:
    axes = make_object(ObjectKind.AXES_3D, "Achsen", "ax")
    camera = make_object(ObjectKind.CAMERA, "Kamera", "cam", phi=70.0, theta=-45.0)
    solid = make_object(ObjectKind.SOLID, "Kugel", "k", axes_id="ax")
    steps = [
        play(make_animation(AnimationKind.AMBIENT_ROTATION, "cam", "turn", rate=20.0, run_time=2.0)),
        wait(3.0, "w1"),
        play(make_animation(AnimationKind.FADE_IN, "k", "in", run_time=1.0)),
        play(make_animation(AnimationKind.AMBIENT_ROTATION, "cam", "stop", rate=0.0, run_time=1.0)),
        wait(1.0, "w2"),
    ]
    return Scene(id="s", name="Drehung", objects=[axes, camera, solid], steps=steps)


def test_camera_angle_over_time() -> None:
    scene = turning_scene()
    assert not has_errors(validate_scene(scene)), [issue.code for issue in validate_scene(scene)]
    thetas = [states_after(scene, index)["cam"].theta for index in range(len(scene.steps))]
    # 20 °/s: 2 s, 3 s of waiting and 1 s of fading; then stopped
    assert thetas == pytest.approx([-5.0, 55.0, 75.0, 75.0, 75.0])
    assert state_at_time(scene, 3.5)["cam"].theta == pytest.approx(-45.0 + 20.0 * 3.5)
    assert states_after(scene, 4)["cam"].phi == pytest.approx(70.0)


def test_code_and_rules() -> None:
    scene = turning_scene()
    scene.steps.insert(2, play(make_animation(AnimationKind.AMBIENT_ROTATION, "cam", "faster", rate=40.0, about="theta", run_time=0.5)))
    code = generate_script(make_project(scene))
    assert code.count('self.begin_ambient_camera_rotation(rate=20.0 * DEGREES, about="theta")') == 1
    # a new speed stops the old rotation first (two would add up); stopping is a stop only
    assert code.count('self.stop_ambient_camera_rotation(about="theta")') == 2
    assert 'self.begin_ambient_camera_rotation(rate=40.0 * DEGREES, about="theta")' in code
    assert "self.wait(2.0)" in code and "self.wait(0.5)" in code
    # orbiting while the camera turns on its own is refused
    scene.steps.insert(1, play(make_animation(AnimationKind.ORBIT, "cam", "orbit", phi=60.0, theta=0.0)))
    assert "orbit_during_ambient" in {issue.code for issue in validate_scene(scene)}
    # only the camera turns like this
    from manim_studio.model.schema import animation_allowed

    assert animation_allowed(AnimationKind.AMBIENT_ROTATION, ObjectKind.CAMERA, {})
    assert not any(animation_allowed(AnimationKind.AMBIENT_ROTATION, kind, {}) for kind in ObjectKind if kind != ObjectKind.CAMERA)
    # and it needs a 3D scene
    flat = Scene(id="f", name="F", objects=[make_object(ObjectKind.CAMERA, "Kamera", "cam")], steps=[play(make_animation(AnimationKind.AMBIENT_ROTATION, "cam", "t"))])
    assert "orbit_needs_3d" in {issue.code for issue in validate_scene(flat)}


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_camera_turns_like_manim(tmp_path) -> None:
    from tests.test_manim_integration import run_manim

    scene = turning_scene()
    scene.steps.insert(4, Step(id="code", kind=StepKind.CODE, code="print('THETA', self.camera.get_theta() / DEGREES)"))
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Drehung")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    theta = float(re.search(r"THETA (\S+)", result.stdout).group(1))
    # Manim's first frame of every play/wait has dt = 0, so each of the three steps turns 1/fps seconds less
    # (at 15 fps 1.3°, at 60 fps 0.3° per step); the stage does not know the frame rate and ignores it
    assert theta == pytest.approx(states_after(scene, 3)["cam"].theta - 3 * 20.0 / 15, abs=0.05)
