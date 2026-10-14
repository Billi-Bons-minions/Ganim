"""“Name as label”: a text with the object's name that follows the object."""

from __future__ import annotations

import pytest

from manim_studio.model.attach import follow_target
from manim_studio.model.playback import state_at_time
from manim_studio.model.types import AnimationKind, ObjectKind


def test_label_follows_its_dot(window) -> None:
    controller = window.controller
    dot = controller.add_object(ObjectKind.DOT, 1.0, -1.0, name="P")
    label_id = controller.add_name_label(dot)
    scene = window.editor.scene()
    label = scene.object_by_id(label_id)
    assert label.kind == ObjectKind.TEXT and label.params["text"] == scene.object_by_id(dot).name
    assert follow_target(scene, label).id == dot and label.x > 1.0 and label.y > -1.0
    # the label moves with the dot
    window.editor.select_objects([dot])
    controller.add_animation(AnimationKind.MOVE, False)
    move = scene.steps[-1].animations[0]
    move.params.update(x=3.0, y=1.0)
    states = state_at_time(scene, 1.0)
    assert states[label_id].x - states[dot].x == pytest.approx(label.x - 1.0)
    window.refresh_code()
    assert "add_updater(lambda mob: mob.move_to(p_1.get_center() +" in window.code.editor.toPlainText()
