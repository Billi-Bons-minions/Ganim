"""Angle marks between two lines."""

from __future__ import annotations

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model.angles import angle_geometry
from manim_studio.model.state import states_after
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind
from manim_studio.model.validation import has_errors, validate_scene


def test_angle_between_two_lines(window) -> None:
    controller = window.controller
    messages = []
    controller.statusMessage.connect(messages.append)
    assert controller.add_object(ObjectKind.ANGLE) is None and "zwei Linien" in messages[-1]
    first = controller.add_object(ObjectKind.LINE, 0.0, 0.0)
    second = controller.add_object(ObjectKind.ARROW, 0.0, 0.0)
    window.document.edit_scene("r", window.editor.scene_id, lambda s: setattr(s.object_by_id(second), "rotation", 60.0), None)
    window.editor.select_objects([first, second])
    angle = controller.add_object(ObjectKind.ANGLE)
    scene = window.editor.scene()
    mark = scene.object_by_id(angle)
    assert (mark.params["first_line"], mark.params["second_line"]) == (first, second)
    states = states_after(scene, -1)
    assert states[angle].geometry == pytest.approx((0.0, 60.0))
    assert not has_errors(validate_scene(scene))
    # the other side and the reflex angle
    # Manim measures counter-clockwise from the first to the second line
    mark.params["flip_first"] = True
    assert angle_geometry(scene, mark, states).value == pytest.approx(240.0)
    mark.params["reflex"] = True
    assert angle_geometry(scene, mark, states).sweep == pytest.approx(-120.0)
    mark.params.update(flip_first=False, reflex=False, label="degrees")
    # the mark follows a rotating line
    window.editor.select_objects([second])
    controller.add_animation(AnimationKind.ROTATE, False)
    rotate = window.editor.scene().steps[0].animations[0]
    window.document.edit_scene("a", window.editor.scene_id, lambda s: s.steps[0].animations[0].params.update(angle=30.0), None)
    assert states_after(window.editor.scene(), 0)[angle].geometry == pytest.approx((0.0, 90.0))
    assert rotate.kind == AnimationKind.ROTATE
    script = generate_script(window.document.project)
    assert "always_redraw(lambda: studio_angle(linie_1, pfeil_1, radius=0.6, quadrant=(1, 1), decimals=0" in script
    assert "def studio_angle(" in script
    # deleting one line removes the mark
    controller.delete_objects([first])
    assert all(obj.kind != ObjectKind.ANGLE for obj in window.editor.scene().objects)


def test_parallel_lines_only_warn(window) -> None:
    controller = window.controller
    a = controller.add_object(ObjectKind.LINE, 0.0, 0.0)
    b = controller.add_object(ObjectKind.LINE, 0.0, 1.0)
    window.editor.select_objects([a, b])
    controller.add_object(ObjectKind.ANGLE)
    issues = validate_scene(window.editor.scene())
    assert "angle_parallel" in {issue.code for issue in issues} and not has_errors(issues)
    controller.add_step(StepKind.PLAY)
