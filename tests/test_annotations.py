"""Highlights (frame, background, underline, cross) attached to another object."""

from __future__ import annotations

from manim_studio.codegen import generate_script
from manim_studio.model import operations as ops
from manim_studio.model.arrange import drawing_order
from manim_studio.model.stage_edits import MOVE, check_edit
from manim_studio.model.state import states_after
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind
from manim_studio.model.validation import has_errors, validate_scene


def test_highlight_needs_and_follows_its_target(window) -> None:
    controller = window.controller
    messages = []
    controller.statusMessage.connect(messages.append)
    window.editor.select_objects([])
    assert controller.add_object(ObjectKind.HIGHLIGHT) is None and "Wähle zuerst" in messages[-1]
    text = controller.add_object(ObjectKind.TEXT, -2.0, 1.0)
    frame = controller.add_object(ObjectKind.HIGHLIGHT)
    scene = window.editor.scene()
    assert scene.object_by_id(frame).params["target"] == text
    assert drawing_order(scene).index(frame) > drawing_order(scene).index(text)
    # a background goes behind its target
    window.editor.select_objects([text])
    back = controller.add_object(ObjectKind.HIGHLIGHT)
    window.document.edit_scene("style", window.editor.scene_id, lambda s: ops.set_object_param(s, back, "style", "background"), None)
    scene = window.editor.scene()
    assert drawing_order(scene).index(back) < drawing_order(scene).index(text)
    # the highlight moves with its target and cannot be moved itself
    window.editor.select_objects([text])
    controller.add_step(StepKind.PLAY)
    controller.move_objects([text], 3.0, -1.0)
    scene = window.editor.scene()
    states = states_after(scene, 0)
    assert (states[frame].x, states[frame].y) == (states[text].x, states[text].y) == (1.0, 0.0)
    assert check_edit(scene, 0, [frame], MOVE).reason == "attached"
    assert not has_errors(validate_scene(scene))
    script = generate_script(window.document.project)
    assert "always_redraw(lambda: SurroundingRectangle(text_1" in script and "BackgroundRectangle(text_1" in script
    # deleting the target removes its highlights
    controller.delete_objects([text])
    assert window.editor.scene().objects == []


def test_highlight_animations_are_limited() -> None:
    from manim_studio.model.schema import animation_allowed

    assert animation_allowed(AnimationKind.CREATE, ObjectKind.HIGHLIGHT, {})
    assert animation_allowed(AnimationKind.FADE_OUT, ObjectKind.HIGHLIGHT, {})
    assert animation_allowed(AnimationKind.INDICATE, ObjectKind.HIGHLIGHT, {})
    for kind in (AnimationKind.MOVE, AnimationKind.CHANGE_COLOR, AnimationKind.TRANSFORM, AnimationKind.SWAP):
        assert not animation_allowed(kind, ObjectKind.HIGHLIGHT, {})
