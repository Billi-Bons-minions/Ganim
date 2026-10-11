"""Tests for state computation, operations, validation and serialization."""

from __future__ import annotations

import pytest

from manim_studio.model import operations as ops
from manim_studio.model.entities import Scene
from manim_studio.model.factory import clone_scene, create_project, unique_name
from manim_studio.model.geometry import axes_layout
from manim_studio.model.graphs import bound_anchor
from manim_studio.model.serialization import (
    ProjectFormatError,
    dumps_project,
    load_project,
    loads_project,
    project_to_dict,
    save_project,
)
from manim_studio.model.state import START, states_after, visible_at_start
from manim_studio.model.types import AnimationKind, ObjectKind, Visibility
from manim_studio.model.validation import ERROR, WARNING, has_errors, validate_scene
from tests.helpers import acceptance_scene, make_animation, make_object, make_project, play, wait

# --- state ----------------------------------------------------------------------


def test_states_follow_the_timeline() -> None:
    scene = acceptance_scene()
    start = states_after(scene, START)
    assert not start["c1"].visible and not start["s1"].visible and not start["t1"].visible
    after_create = states_after(scene, 0)
    assert after_create["c1"].visible and after_create["c1"].shape_id == "c1"
    after_transform = states_after(scene, 1)
    assert after_transform["c1"].shape_id == "s1"
    assert after_transform["c1"].stroke_color == "#FC6255"
    assert not after_transform["s1"].visible
    assert states_after(scene, 2)["t1"].visible


def test_modifiers_change_the_state() -> None:
    circle = make_object(ObjectKind.CIRCLE, "K", "c", 1.0, 1.0)
    scene = Scene(id="s", name="S", objects=[circle], steps=[
        play(
            make_animation(AnimationKind.MOVE, "c", "m", x=3.0, y=-1.0),
            make_animation(AnimationKind.SCALE, "c", "s", factor=2.0),
            make_animation(AnimationKind.ROTATE, "c", "r", angle=30.0),
            make_animation(AnimationKind.CHANGE_COLOR, "c", "k", color="#00FF00", apply_to="fill"),
        ),
        wait(1.0),
        play(make_animation(AnimationKind.FADE_OUT, "c")),
    ])
    state = states_after(scene, 1)
    assert (state["c"].x, state["c"].y, state["c"].scale, state["c"].rotation) == (3.0, -1.0, 2.0, 30.0)
    assert state["c"].fill_color == "#00FF00" and state["c"].stroke_color == circle.stroke_color
    assert not states_after(scene, 2)["c"].visible


def test_returning_rate_function_keeps_state() -> None:
    move = make_animation(AnimationKind.MOVE, "c", x=5.0, y=5.0)
    move.rate_func = "there_and_back"
    scene = Scene(id="s", name="S", objects=[make_object(ObjectKind.CIRCLE, "K", "c")], steps=[play(move)])
    assert (states_after(scene, 0)["c"].x, states_after(scene, 0)["c"].y) == (0.0, 0.0)


def test_replacement_transform_swaps_visibility() -> None:
    scene = Scene(id="s", name="S", objects=[
        make_object(ObjectKind.CIRCLE, "A", "a"), make_object(ObjectKind.SQUARE, "B", "b"),
    ], steps=[play(make_animation(AnimationKind.REPLACEMENT_TRANSFORM, "a", target="b"))])
    assert visible_at_start(scene, scene.objects[0]) and not visible_at_start(scene, scene.objects[1])
    state = states_after(scene, 0)
    assert not state["a"].visible and state["b"].visible


def test_explicit_visibility_overrides_auto() -> None:
    obj = make_object(ObjectKind.DOT, "P", "p")
    scene = Scene(id="s", name="S", objects=[obj], steps=[play(make_animation(AnimationKind.FADE_IN, "p"))])
    assert not visible_at_start(scene, obj)
    obj.visibility = Visibility.SHOWN
    assert visible_at_start(scene, obj)


def test_bound_graph_anchor_uses_axes() -> None:
    axes = make_object(ObjectKind.AXES, "A", "a", 2.0, 1.0, tips=False)
    graph = make_object(ObjectKind.FUNCTION_GRAPH, "G", "g", 9.0, 9.0, expression="x", axes_id="a")
    scene = Scene(id="s", name="S", objects=[axes, graph])
    x, y = bound_anchor(scene, graph)
    assert x == pytest.approx(2.0) and y == pytest.approx(1.0)


def test_axes_layout_matches_manim_bounding_box() -> None:
    axes = make_object(ObjectKind.AXES, "A", "a", x_min=0.0, x_max=10.0, y_min=0.0, y_max=6.0)
    layout = axes_layout(axes)
    assert layout.offset == pytest.approx((-0.0875, -0.0875))
    assert layout.to_local(5.0, 3.0) == pytest.approx((0.0875, 0.0875))


# --- operations -----------------------------------------------------------------


def test_remove_object_removes_its_animations_and_references() -> None:
    scene = acceptance_scene()
    graph = make_object(ObjectKind.FUNCTION_GRAPH, "G", "g", axes_id="s1")
    scene.objects.append(graph)
    ops.remove_objects(scene, ["s1"])
    assert [anim.kind for step in scene.steps for anim in step.animations] == [AnimationKind.CREATE, AnimationKind.WRITE]
    assert graph.params["axes_id"] is None


def test_scale_and_rotate_objects() -> None:
    scene = Scene(id="s", name="S", objects=[make_object(ObjectKind.RECTANGLE, "R", "r", width=4.0, height=2.0)])
    ops.scale_object(scene, "r", 0.5)
    assert scene.objects[0].params == {"width": 2.0, "height": 1.0}
    ops.rotate_object(scene, "r", 270.0)
    assert scene.objects[0].rotation == -90.0


def test_step_operations() -> None:
    scene = acceptance_scene()
    first_id = scene.steps[0].id
    copy_id = ops.duplicate_step(scene, first_id)
    assert scene.step_index(copy_id) == 1
    assert scene.steps[1].animations[0].id != scene.steps[0].animations[0].id
    ops.move_step(scene, copy_id, 3)
    assert scene.step_index(copy_id) == 3
    ops.reorder_steps(scene, list(reversed([s.id for s in scene.steps])))
    assert scene.steps[0].id == copy_id
    with pytest.raises(ops.ModelError):
        ops.reorder_steps(scene, [copy_id])


def test_paste_objects_creates_new_ids_and_names() -> None:
    scene = acceptance_scene()
    new_ids = ops.paste_objects(scene, [scene.objects[0]], 0.5, -0.5)
    pasted = scene.object_by_id(new_ids[0])
    assert pasted is not None and pasted.id != "c1"
    assert pasted.name == "Kreis 2" and (pasted.x, pasted.y) == (-2.5, -0.5)


def test_scene_operations() -> None:
    project = create_project("Szene 1")
    first = project.scenes[0].id
    second = ops.duplicate_scene(project, first, "Szene 2")
    assert [s.name for s in project.scenes] == ["Szene 1", "Szene 2"]
    ops.remove_scene(project, first)
    with pytest.raises(ops.ModelError):
        ops.remove_scene(project, second)


def test_clone_scene_remaps_references() -> None:
    clone = clone_scene(acceptance_scene(), "Kopie")
    ids = {obj.id for obj in clone.objects}
    transform = clone.steps[1].animations[0]
    assert transform.target_id in ids and transform.params["target"] in ids
    assert "c1" not in ids


def test_unique_name() -> None:
    assert unique_name(["Kreis 1", "Kreis 2"], "Kreis") == "Kreis 3"
    assert unique_name(["Kreis 1"], "Kreis 1") == "Kreis 2"


# --- validation -------------------------------------------------------------------


def test_validation_reports_problems() -> None:
    scene = Scene(id="s", name="S", objects=[
        make_object(ObjectKind.FUNCTION_GRAPH, "G", "g", expression="y"),
        make_object(ObjectKind.MATH_TEX, "F", "f"),
        make_object(ObjectKind.IMAGE, "I", "i", path="/does/not/exist.png"),
    ], steps=[play(step_id="empty"), play(make_animation(AnimationKind.TRANSFORM, "f", target="f"))])
    issues = validate_scene(scene, latex_available=False)
    codes = {(issue.severity, issue.code) for issue in issues}
    assert (ERROR, "expression_invalid") in codes
    assert (ERROR, "latex_unavailable") in codes
    assert (ERROR, "image_not_found") in codes
    assert (WARNING, "step_empty") in codes
    assert (ERROR, "transform_target_self") in codes
    assert has_errors(issues)


def test_valid_scene_has_no_errors() -> None:
    assert not has_errors(validate_scene(acceptance_scene()))


# --- serialization ----------------------------------------------------------------


def test_project_round_trip_is_identical(tmp_path) -> None:
    project = make_project(acceptance_scene())
    project.scenes[0].objects[0].params["radius"] = 1.2345678
    project.render.format = "gif"
    path = tmp_path / "projekt.msproj"
    save_project(project, path)
    loaded = load_project(path)
    assert loaded == project
    assert project_to_dict(loaded) == project_to_dict(project)
    assert dumps_project(loaded) == dumps_project(project)


@pytest.mark.parametrize("text", ["", "{}", '{"format": "other"}', "[1, 2]", '{"format": "manim-studio-project", "scenes": []}'])
def test_invalid_project_files_are_rejected(text: str) -> None:
    with pytest.raises(ProjectFormatError):
        loads_project(text)
