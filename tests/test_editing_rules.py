"""Tests for stage editing rules and default animations (pure model logic)."""

from __future__ import annotations

from manim_studio.model.animation_builder import allowed_for_objects, build_animations
from manim_studio.model.entities import Scene
from manim_studio.model.stage_edits import (
    MOVE,
    SCALE,
    check_edit,
    color_edit,
    move_edit,
    rotate_edit,
    scale_edit,
    set_move_target,
    set_rotation_angle,
    set_scale_factor,
    would_create,
)
from manim_studio.model.state import START
from manim_studio.model.types import AnimationKind, ObjectKind
from tests.helpers import make_animation, make_object, play, wait


def scene_with_move() -> Scene:
    circle = make_object(ObjectKind.CIRCLE, "Kreis", "c", 1.0, 1.0)
    axes = make_object(ObjectKind.AXES, "Achsen", "a")
    graph = make_object(ObjectKind.FUNCTION_GRAPH, "Graph", "g", axes_id="a")
    steps = [
        play(make_animation(AnimationKind.MOVE, "c", "m", x=3.0, y=0.0)),
        wait(1.0),
        play(make_animation(AnimationKind.FADE_OUT, "c")),
    ]
    return Scene(id="s", name="S", objects=[circle, axes, graph], steps=steps)


def test_start_edits_initial_values() -> None:
    scene = scene_with_move()
    assert check_edit(scene, START, ["c"], MOVE).allowed
    move_edit(START, ["c"], 0.5, -1.0)(scene)
    scale_edit(START, "c", 2.0)(scene)
    rotate_edit(START, "c", 30.0)(scene)
    circle = scene.object_by_id("c")
    assert (circle.x, circle.y, circle.params["radius"], circle.rotation) == (1.5, 0.0, 2.0, 30.0)


def test_step_edits_animation_targets() -> None:
    scene = scene_with_move()
    assert check_edit(scene, 0, ["c"], MOVE).allowed
    move_edit(0, ["c"], 1.0, 2.0)(scene)
    assert scene.steps[0].animations[0].params == {"x": 4.0, "y": 2.0}
    assert (scene.object_by_id("c").x, scene.object_by_id("c").y) == (1.0, 1.0)


def test_locked_cases() -> None:
    scene = scene_with_move()
    assert check_edit(scene, 0, ["c"], SCALE).allowed
    assert check_edit(scene, 2, ["c"], MOVE).allowed
    assert check_edit(scene, 1, ["c"], MOVE).reason == "wait_step"
    locked = check_edit(scene, START, ["g"], MOVE)
    assert not locked.allowed and locked.reason == "bound_graph" and locked.object_id == "g"
    assert check_edit(scene, START, [], MOVE).reason == "nothing_selected"


def test_dragging_in_a_step_records_new_animations() -> None:
    scene = scene_with_move()
    assert would_create(scene, 2, ["c"], MOVE) == ["c"]
    assert would_create(scene, 0, ["c"], MOVE) == []
    assert would_create(scene, START, ["c"], MOVE) == []
    move_edit(2, ["c"], -1.0, 0.5)(scene)
    scale_edit(2, "c", 2.0)(scene)
    rotate_edit(2, "c", 45.0)(scene)
    color_edit(2, ["c"], "fill_color", "#FF0000")(scene)
    kinds = {anim.kind: anim for anim in scene.steps[2].animations}
    assert kinds[AnimationKind.MOVE].params == {"x": 2.0, "y": 0.5}
    assert kinds[AnimationKind.SCALE].params == {"factor": 2.0}
    assert kinds[AnimationKind.ROTATE].params["angle"] == 45.0 and kinds[AnimationKind.ROTATE].params.get("pivot", "center") == "center"
    assert kinds[AnimationKind.CHANGE_COLOR].params == {"color": "#FF0000", "apply_to": "fill"}
    assert all(anim.run_time == 1.0 for anim in scene.steps[2].animations)


def test_recorded_animation_matches_step_duration() -> None:
    scene = scene_with_move()
    scene.steps[0].animations[0].run_time = 2.5
    scale_edit(0, "c", 1.5)(scene)
    assert scene.steps[0].animations[-1].run_time == 2.5


def test_absolute_step_values_and_color_merge() -> None:
    scene = scene_with_move()
    set_move_target(0, "c", -2.0, 1.0)(scene)
    set_rotation_angle(2, "c", 90.0)(scene)
    set_scale_factor(2, "c", 0.5)(scene)
    color_edit(2, ["c"], "stroke_color", "#00FF00")(scene)
    color_edit(2, ["c"], "fill_color", "#0000FF")(scene)
    assert scene.steps[0].animations[0].params == {"x": -2.0, "y": 1.0}
    color = [a for a in scene.steps[2].animations if a.kind == AnimationKind.CHANGE_COLOR]
    assert len(color) == 1 and color[0].params == {"color": "#0000FF", "apply_to": "both"}
    color_edit(START, ["c"], "fill_color", "#123456")(scene)
    assert scene.object_by_id("c").fill_color == "#123456"


def test_build_move_uses_current_position() -> None:
    scene = scene_with_move()
    anims = build_animations(scene, AnimationKind.MOVE, ["c"], 0)
    assert anims[0].params == {"x": 4.0, "y": 0.0}


def test_build_transform_from_two_selected_objects() -> None:
    scene = scene_with_move()
    scene.objects.append(make_object(ObjectKind.SQUARE, "Quadrat", "q"))
    anims = build_animations(scene, AnimationKind.TRANSFORM, ["c", "q"], START)
    assert len(anims) == 1 and anims[0].target_id == "c" and anims[0].params["target"] == "q"


def test_build_transform_prefers_hidden_target() -> None:
    scene = scene_with_move()
    hidden = make_object(ObjectKind.SQUARE, "Versteckt", "h")
    scene.objects.append(hidden)
    scene.steps.append(play(make_animation(AnimationKind.CREATE, "h")))
    anims = build_animations(scene, AnimationKind.TRANSFORM, ["c"], START)
    assert anims[0].params["target"] == "h"


def test_one_animation_per_selected_object() -> None:
    scene = scene_with_move()
    anims = build_animations(scene, AnimationKind.FADE_IN, ["c", "a"], START)
    assert [anim.target_id for anim in anims] == ["c", "a"]
    assert len({anim.id for anim in anims}) == 2


def test_raster_images_cannot_be_created() -> None:
    scene = Scene(id="s", name="S", objects=[make_object(ObjectKind.IMAGE, "Bild", "i", path="foto.png")])
    assert not allowed_for_objects(scene, AnimationKind.CREATE, ["i"])
    assert allowed_for_objects(scene, AnimationKind.FADE_IN, ["i"])
    assert not allowed_for_objects(scene, AnimationKind.FADE_IN, [])
