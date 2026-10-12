"""Edge cases found by randomized editing sessions (fuzzing the controller)."""

from __future__ import annotations

from manim_studio.codegen import generate_script
from manim_studio.model import operations as ops
from manim_studio.model.stage_edits import MOVE, check_edit
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind
from manim_studio.model.validation import has_errors, validate_scene


def test_graph_tool_brings_its_axes_and_graph(window) -> None:
    controller = window.controller
    messages = []
    controller.statusMessage.connect(messages.append)
    tangent = controller.add_object(ObjectKind.TANGENT, 1.0, -1.0)
    scene = window.editor.scene()
    kinds = [obj.kind for obj in scene.objects]
    assert kinds == [ObjectKind.AXES, ObjectKind.FUNCTION_GRAPH, ObjectKind.TANGENT]
    assert not has_errors(validate_scene(scene))
    assert "automatisch" in messages[-1]
    assert window.editor.selected_objects == [tangent]
    generate_script(window.document.project)
    window.document.undo_stack.undo()
    assert window.editor.scene().objects == []


def test_existing_hosts_are_reused(window) -> None:
    controller = window.controller
    axes = controller.add_object(ObjectKind.AXES, 0.0, 0.0)
    graph = controller.add_object(ObjectKind.FUNCTION_GRAPH)
    area = controller.add_object(ObjectKind.GRAPH_AREA)
    data = controller.add_object(ObjectKind.DATA_PLOT)
    scene = window.editor.scene()
    assert len(scene.objects) == 4
    assert scene.object_by_id(area).params["graph_id"] == graph
    assert scene.object_by_id(data).params["axes_id"] == axes
    surface = controller.add_object(ObjectKind.SURFACE)
    curve = controller.add_object(ObjectKind.CURVE_3D)
    scene = window.editor.scene()
    axes_3d = [obj for obj in scene.objects if obj.kind == ObjectKind.AXES_3D]
    assert len(axes_3d) == 1
    assert scene.object_by_id(surface).params["axes_id"] == scene.object_by_id(curve).params["axes_id"] == axes_3d[0].id
    assert not has_errors(validate_scene(scene))


def test_inspector_survives_a_stale_selection(window) -> None:
    controller = window.controller
    first = controller.add_object(ObjectKind.CIRCLE, -1.0, 0.0)
    second = controller.add_object(ObjectKind.SQUARE, 1.0, 0.0)
    window.editor.select_objects([first, second])
    # remove one object behind the editor's back: the inspector refreshes before the selection is cleaned
    window.document.edit_scene("x", window.editor.scene_id, lambda s: ops.remove_objects(s, [second]), None)
    window.properties.refresh()
    assert window.properties._key[0] in ("object", "objects")


def test_recording_refuses_animations_an_object_cannot_have(window) -> None:
    controller = window.controller
    parameter = controller.add_object(ObjectKind.PARAMETER)
    circle = controller.add_object(ObjectKind.CIRCLE)
    controller.add_step(StepKind.PLAY)
    scene = window.editor.scene()
    cursor = window.editor.cursor
    assert check_edit(scene, cursor, [parameter], MOVE).reason == "not_animatable"
    controller.move_objects([parameter], 1.0, 0.0)
    assert window.editor.scene().steps[cursor].animations == []
    controller.move_objects([circle], 1.0, 0.0)
    assert [anim.kind for anim in window.editor.scene().steps[cursor].animations] == [AnimationKind.MOVE]


def test_reference_animations_check_their_partner(window) -> None:
    controller = window.controller
    parameter = controller.add_object(ObjectKind.PARAMETER)
    circle = controller.add_object(ObjectKind.CIRCLE)
    square = controller.add_object(ObjectKind.SQUARE, 2.0, 0.0)
    controller.add_reference_animation(AnimationKind.TRANSFORM, parameter, circle, False)
    controller.add_reference_animation(AnimationKind.SWAP, circle, parameter, False)
    assert window.editor.scene().steps == []
    controller.add_reference_animation(AnimationKind.TRANSFORM, circle, square, False)
    assert [anim.kind for step in window.editor.scene().steps for anim in step.animations] == [AnimationKind.TRANSFORM]


def test_deleting_a_host_deletes_what_depends_on_it(window) -> None:
    controller = window.controller
    messages = []
    controller.statusMessage.connect(messages.append)
    controller.add_object(ObjectKind.TANGENT)
    scene = window.editor.scene()
    axes, graph, tangent = (obj.id for obj in scene.objects)
    derivative = controller.add_derivative(graph)
    marker = controller.add_graph_tool(ObjectKind.GRAPH_MARKERS, derivative, feature="zeros")
    controller.add_object(ObjectKind.CIRCLE, 3.0, 0.0)
    window.editor.select_objects([tangent, marker])
    controller.add_animation(AnimationKind.FADE_IN, False)
    controller.delete_objects([graph])
    scene = window.editor.scene()
    assert [obj.kind for obj in scene.objects] == [ObjectKind.AXES, ObjectKind.CIRCLE]
    assert all(not step.animations for step in scene.steps)
    assert "Tangente" in messages[-1]
    assert not has_errors(validate_scene(scene))
    window.document.undo_stack.undo()
    assert len(window.editor.scene().objects) == 6


def test_transform_and_effect_on_one_object_get_separate_steps(window) -> None:
    from manim_studio.model.factory import create_animation

    controller = window.controller
    messages = []
    controller.statusMessage.connect(messages.append)
    circle = controller.add_object(ObjectKind.CIRCLE)
    square = controller.add_object(ObjectKind.SQUARE, 2.0, 0.0)
    controller.add_reference_animation(AnimationKind.TRANSFORM, circle, square, False)
    window.editor.select_objects([circle])
    controller.add_animation(AnimationKind.INDICATE, True)
    steps = window.editor.scene().steps
    assert [[anim.kind for anim in step.animations] for step in steps] == [[AnimationKind.TRANSFORM], [AnimationKind.INDICATE]]
    assert "eigenen Schritt" in messages[-1]
    # a project built elsewhere with the conflict is reported before rendering
    scene = window.editor.scene()
    scene.steps[0].animations.append(create_animation(AnimationKind.FADE_IN, circle))
    assert "transform_conflict" in {issue.code for issue in validate_scene(scene)}


def test_simultaneous_conflict_rules() -> None:
    from manim_studio.codegen.animations import COMBINABLE
    from manim_studio.model.factory import create_animation
    from manim_studio.model.types import COMBINABLE_EFFECTS, simultaneous_conflicts, transform_conflicts

    def anims(*items):
        return [create_animation(kind, target, **params) for kind, target, params in items]

    assert set(COMBINABLE) == COMBINABLE_EFFECTS
    assert simultaneous_conflicts(anims((AnimationKind.MOVE, "a", {}), (AnimationKind.SCALE, "a", {}), (AnimationKind.FADE_IN, "a", {}))) == set()
    assert simultaneous_conflicts(anims((AnimationKind.FADE_IN, "a", {}), (AnimationKind.INDICATE, "a", {}))) == set()
    assert simultaneous_conflicts(anims((AnimationKind.MOVE, "a", {}), (AnimationKind.FLASH, "a", {}), (AnimationKind.CIRCUMSCRIBE, "a", {}))) == set()
    assert simultaneous_conflicts(anims((AnimationKind.CREATE, "a", {}), (AnimationKind.WIGGLE, "a", {}))) == {"a"}
    two_targets = anims((AnimationKind.REPLACEMENT_TRANSFORM, "a", {"target": "b"}), (AnimationKind.FADE_TRANSFORM, "a", {"target": "c"}))
    assert transform_conflicts(two_targets) == {"a"}
    assert simultaneous_conflicts(anims((AnimationKind.TRANSFORM, "a", {"target": "b"}), (AnimationKind.FADE_IN, "b", {}))) == {"b"}
    assert simultaneous_conflicts(anims((AnimationKind.SWAP, "a", {"partner": "b"}), (AnimationKind.MOVE, "b", {}))) == {"b"}


def test_groups_skip_parameters(window) -> None:
    controller = window.controller
    parameter = controller.add_object(ObjectKind.PARAMETER)
    circle = controller.add_object(ObjectKind.CIRCLE)
    window.editor.select_objects([parameter, circle])
    controller.group_selection()
    assert all(obj.kind != ObjectKind.GROUP for obj in window.editor.scene().objects)


def test_toolbars_fold_on_small_screens(window, qapp) -> None:
    window.resize(1280, 800)
    qapp.processEvents()
    assert window.arrange_tools.is_compact() and window.timeline.step_buttons.is_compact()
    assert window.main_split.sizes()[0] >= 150, window.main_split.sizes()
    menu = window.arrange_tools.compact.menu()
    assert window.act_group in menu.actions() and len([a for a in menu.actions() if not a.isSeparator()]) >= 10
    assert window.timeline.visible_add_step_button() is window.timeline.compact_add_step_button
    window.resize(2200, 1000)
    qapp.processEvents()
    assert not window.arrange_tools.is_compact() and window.timeline.visible_add_step_button() is window.timeline.add_step_button
