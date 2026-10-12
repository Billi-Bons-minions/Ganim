"""Motion traces (TracedPath)."""

from __future__ import annotations

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model.state import states_after
from manim_studio.model.traces import trace_points, with_traces
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind
from manim_studio.model.validation import has_errors, validate_scene


def test_trace_records_the_path_of_its_target(window) -> None:
    controller = window.controller
    messages = []
    controller.statusMessage.connect(messages.append)
    window.editor.select_objects([])
    assert controller.add_object(ObjectKind.TRACE) is None and "Weg" in messages[-1]
    dot = controller.add_object(ObjectKind.DOT, -3.0, 0.0)
    trace = controller.add_object(ObjectKind.TRACE)
    scene = window.editor.scene()
    assert scene.object_by_id(trace).params["target"] == dot
    controller.add_step(StepKind.PLAY)
    controller.move_objects([dot], 4.0, 2.0)
    scene = window.editor.scene()
    points = trace_points(scene, scene.object_by_id(trace), 1.0)
    assert points[0] == pytest.approx((-3.0, 0.0), abs=1e-3) and points[-1] == pytest.approx((1.0, 2.0))
    assert trace_points(scene, scene.object_by_id(trace), 0.5)[-1][0] == pytest.approx(-1.0, abs=0.2)
    states = with_traces(scene, states_after(scene, 0), 1.0)
    assert len(states[trace].geometry) == 2 * len(points)
    assert not has_errors(validate_scene(scene))
    script = generate_script(window.document.project)
    assert "spur_1 = TracedPath(punkt_1.get_center, stroke_color=" in script
    controller.delete_objects([dot])
    assert window.editor.scene().objects == []


def test_trace_started_later_and_fading(window) -> None:
    controller = window.controller
    dot = controller.add_object(ObjectKind.DOT, 0.0, 0.0)
    window.editor.select_objects([dot])
    trace = controller.add_object(ObjectKind.TRACE, dissipating_time=0.5)
    controller.add_step(StepKind.PLAY)
    controller.move_objects([dot], 2.0, 0.0)
    window.editor.select_objects([trace])
    controller.add_animation(AnimationKind.FADE_IN, False)
    window.editor.select_objects([dot])
    controller.add_step(StepKind.PLAY)
    controller.move_objects([dot], 0.0, 2.0)
    scene = window.editor.scene()
    obj = scene.object_by_id(trace)
    # nothing recorded during the first move, then only the last half second
    assert trace_points(scene, obj, 1.0) == []
    points = trace_points(scene, obj, 3.0)
    assert points[0][1] == pytest.approx(1.0, abs=0.25) and points[-1] == pytest.approx((2.0, 2.0))
    script = generate_script(window.document.project)
    assert "self.add(spur_1)" in script and "FadeIn(spur_1" not in script and "dissipating_time=0.5" in script
    from manim_studio.model.schema import animation_allowed

    assert not animation_allowed(AnimationKind.MOVE, ObjectKind.TRACE, {}) and animation_allowed(AnimationKind.FADE_OUT, ObjectKind.TRACE, {})


def test_trace_ignores_the_jump_onto_a_path(window) -> None:
    controller = window.controller
    circle = controller.add_object(ObjectKind.CIRCLE, 2.0, 0.0, radius=2.0)
    dot = controller.add_object(ObjectKind.DOT, -5.0, 2.0)
    window.editor.select_objects([dot])
    trace = controller.add_object(ObjectKind.TRACE)
    controller.add_reference_animation(AnimationKind.MOVE_ALONG_PATH, dot, circle, False)
    scene = window.editor.scene()
    points = trace_points(scene, scene.object_by_id(trace), 1.0)
    assert points[0] == pytest.approx((4.0, 0.0), abs=0.05)


@pytest.mark.manim
def test_trace_can_fade_out_before_it_recorded_anything(tmp_path) -> None:
    """Fading out a TracedPath before its first frame crashed Manim (fuzz session 10100007)."""
    pytest.importorskip("manim")
    from manim_studio.model.entities import Scene
    from tests.helpers import make_animation, make_object, make_project, play
    from tests.test_manim_integration import run_manim

    dot = make_object(ObjectKind.DOT, "Punkt", "d", -2.0, 0.0)
    early = make_object(ObjectKind.TRACE, "Spur A", "a", target="d")
    late = make_object(ObjectKind.TRACE, "Spur B", "b", target="d")
    steps = [
        play(make_animation(AnimationKind.FADE_OUT, "a", "out-a")),
        play(make_animation(AnimationKind.FADE_IN, "b", "in-b")),
        play(make_animation(AnimationKind.FADE_OUT, "b", "out-b"), make_animation(AnimationKind.MOVE, "d", "m", x=2.0, y=1.0)),
    ]
    scene = Scene(id="s", name="Spuren", objects=[dot, early, late], steps=steps)
    assert not has_errors(validate_scene(scene))
    script = generate_script(make_project(scene))
    assert script.count(".update(0)") == 2
    result = run_manim(tmp_path, script, "Spuren", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
