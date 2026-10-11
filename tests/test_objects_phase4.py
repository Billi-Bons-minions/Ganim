"""Groups, layer order, aligning, vertex/endpoint editing and number terms (pure model logic)."""

from __future__ import annotations

import math

import pytest

from manim_studio.codegen import CodegenOptions, generate_script
from manim_studio.model import groups
from manim_studio.model import operations as ops
from manim_studio.model.arrange import (
    ALIGN_HCENTER,
    ALIGN_LEFT,
    ALIGN_TOP,
    DISTRIBUTE_H,
    FRAME_BOX,
    arrange_deltas,
    drawing_order,
    move_layer,
)
from manim_studio.model.entities import Scene
from manim_studio.model.expression import evaluate_number
from manim_studio.model.stage_edits import move_each_edit, move_edit
from manim_studio.model.state import START, states_after
from manim_studio.model.types import AnimationKind, ObjectKind
from manim_studio.model.validation import validate_scene
from tests.helpers import make_animation, make_object, make_project, play


def three_objects() -> Scene:
    objects = [
        make_object(ObjectKind.CIRCLE, "A", "a", -2.0, 0.0),
        make_object(ObjectKind.SQUARE, "B", "b", 0.0, 1.0),
        make_object(ObjectKind.DOT, "C", "c", 3.0, -1.0),
    ]
    return Scene(id="s", name="S", objects=objects, steps=[])


# --- groups ---------------------------------------------------------------------------


def test_group_and_ungroup_keep_animations() -> None:
    scene = three_objects()
    group_id = ops.group_objects(scene, ["a", "b"], "G")
    assert groups.members(scene, group_id) == ["a", "b"]
    assert groups.top_level(scene, "a") == group_id
    scene.steps.append(play(make_animation(AnimationKind.FADE_IN, group_id, "fade")))
    members = ops.ungroup(scene, group_id)
    assert members == ["a", "b"]
    assert scene.object_by_id(group_id) is None
    assert sorted(anim.target_id for anim in scene.steps[0].animations) == ["a", "b"]


def test_nested_groups_and_leaves() -> None:
    scene = three_objects()
    inner = ops.group_objects(scene, ["a", "b"], "Inner")
    outer = ops.group_objects(scene, [inner, "c"], "Outer")
    assert groups.leaves(scene, outer) == ["a", "b", "c"]
    assert groups.ancestors(scene, "a") == [inner, outer]
    assert groups.nesting_depth(scene, outer) == 2


def test_group_move_moves_members_and_updates_center() -> None:
    scene = three_objects()
    group_id = ops.group_objects(scene, ["a", "b"], "G")
    scene.steps.append(play(make_animation(AnimationKind.MOVE, "a", "solo", x=-4.0, y=0.0)))
    scene.steps.append(play(make_animation(AnimationKind.FADE_IN, "c", "f")))
    move_edit(1, [group_id], 1.0, 0.5)(scene)
    after = states_after(scene, 1)
    assert after["a"].x == pytest.approx(-3.0) and after["a"].y == pytest.approx(0.5)
    assert after["b"].x == pytest.approx(1.0) and after["b"].y == pytest.approx(1.5)


def test_group_start_edits_move_all_members() -> None:
    scene = three_objects()
    group_id = ops.group_objects(scene, ["a", "b"], "G")
    move_edit(START, [group_id], 1.0, 1.0)(scene)
    assert (scene.object_by_id("a").x, scene.object_by_id("b").y) == (-1.0, 2.0)


def test_group_code_creates_members_first() -> None:
    scene = three_objects()
    ops.group_objects(scene, ["a", "b"], "Gruppe")
    code = generate_script(make_project(scene), CodegenOptions())
    assert "gruppe = VGroup(a, b)" in code
    assert code.index("a = Circle") < code.index("gruppe = VGroup")


# --- layers ---------------------------------------------------------------------------------


def test_move_layer_places_object_next_to_reference() -> None:
    scene = three_objects()
    assert drawing_order(scene) == ["a", "b", "c"]
    move_layer(scene, "c", None, "a")
    assert drawing_order(scene) == ["c", "a", "b"]
    scene.object_by_id("b").z_index = 5
    move_layer(scene, "a", "b", None)
    assert drawing_order(scene) == ["c", "b", "a"]
    assert scene.object_by_id("a").z_index == 5


def test_move_layer_moves_groups_as_a_block() -> None:
    scene = three_objects()
    group_id = ops.group_objects(scene, ["a", "b"], "G")
    move_layer(scene, group_id, "c", None)
    assert drawing_order(scene) == ["c", "a", "b"]


# --- align and distribute -----------------------------------------------------------------------


def test_align_to_common_box_and_single_object_to_frame() -> None:
    boxes = {"a": (-3.0, -1.0, -1.0, 1.0), "b": (0.0, 0.0, 4.0, 2.0)}
    assert arrange_deltas(boxes, ALIGN_LEFT) == {"a": (0.0, 0.0), "b": (-3.0, 0.0)}
    assert arrange_deltas(boxes, ALIGN_TOP) == {"a": (0.0, 1.0), "b": (0.0, 0.0)}
    centered = arrange_deltas(boxes, ALIGN_HCENTER)
    assert centered == {"a": (2.5, 0.0), "b": (-1.5, 0.0)}
    single = arrange_deltas({"a": (-1.0, -1.0, 1.0, 1.0)}, ALIGN_LEFT)
    assert single["a"][0] == pytest.approx(FRAME_BOX[0] + 1.0)


def test_distribute_makes_equal_gaps() -> None:
    boxes = {"a": (-5.0, 0.0, -4.0, 1.0), "b": (-1.0, 0.0, 1.0, 1.0), "c": (3.0, 0.0, 5.0, 1.0)}
    deltas = arrange_deltas(boxes, DISTRIBUTE_H)
    moved = {key: (box[0] + deltas[key][0], box[2] + deltas[key][0]) for key, box in boxes.items()}
    assert moved["b"][0] - moved["a"][1] == pytest.approx(moved["c"][0] - moved["b"][1])
    assert deltas["a"] == (0.0, 0.0) and deltas["c"] == (0.0, 0.0)
    assert arrange_deltas({"a": boxes["a"], "b": boxes["b"]}, DISTRIBUTE_H) == {}


def test_move_each_records_one_move_per_object() -> None:
    scene = three_objects()
    scene.steps.append(play(make_animation(AnimationKind.FADE_IN, "c", "f")))
    move_each_edit(0, {"a": (1.0, 0.0), "b": (0.0, -1.0), "c": (0.0, 0.0)})(scene)
    moves = {anim.target_id: (anim.params["x"], anim.params["y"]) for anim in scene.steps[0].animations if anim.kind == AnimationKind.MOVE}
    assert moves == {"a": (-1.0, 0.0), "b": (0.0, 0.0)}


# --- vertices and endpoints -------------------------------------------------------------------------


def absolute_vertices(obj) -> list[tuple[float, float]]:
    points = obj.params["points"]
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    angle = math.radians(obj.rotation)
    result = []
    for x, y in points:
        dx, dy = x - cx, y - cy
        result.append((obj.x + dx * math.cos(angle) - dy * math.sin(angle), obj.y + dx * math.sin(angle) + dy * math.cos(angle)))
    return result


def test_moving_a_vertex_keeps_the_others_in_place() -> None:
    polygon = make_object(ObjectKind.POLYGON, "P", "p", 1.0, -0.5, points=[[-1.0, -1.0], [1.0, -1.0], [0.0, 1.0]])
    polygon.rotation = 30.0
    scene = Scene(id="s", name="S", objects=[polygon])
    before = absolute_vertices(polygon)
    ops.set_polygon_point(scene, "p", 2, 2.0, 3.0)
    after = absolute_vertices(polygon)
    for index in (0, 1):
        assert after[index] == pytest.approx(before[index], abs=1e-4)
    ops.insert_polygon_point(scene, "p", 1, 0.0, -2.0)
    assert len(polygon.params["points"]) == 4
    assert absolute_vertices(polygon)[0] == pytest.approx(before[0], abs=1e-4)
    ops.remove_polygon_point(scene, "p", 1)
    with pytest.raises(ops.ModelError):
        ops.remove_polygon_point(scene, "p", 0)


def test_line_endpoint_editing() -> None:
    line = make_object(ObjectKind.ARROW, "L", "l", 0.0, 0.0, length=4.0)
    scene = Scene(id="s", name="S", objects=[line])
    ops.set_line_endpoint(scene, "l", 1, 2.0, 2.0)
    start, end = ops.line_endpoints(line)
    assert start == pytest.approx((-2.0, 0.0), abs=1e-5) and end == pytest.approx((2.0, 2.0), abs=1e-5)
    assert line.params["length"] == pytest.approx(math.hypot(4.0, 2.0), abs=1e-4)
    with pytest.raises(ops.ModelError):
        ops.set_line_endpoint(scene, "l", 1, -2.0, 0.0)


# --- terms and validation ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [("pi/2", math.pi / 2), ("1,5", 1.5), ("2*3", 6.0), ("-0.25", -0.25), ("sqrt(2)", math.sqrt(2)), ("2x", None), ("1/0", None), ("", None), ("abc", None)],
)
def test_evaluate_number(text: str, expected: float | None) -> None:
    value = evaluate_number(text)
    assert value == pytest.approx(expected) if expected is not None else value is None


def test_validation_of_new_kinds() -> None:
    polygon = make_object(ObjectKind.POLYGON, "P", "p", points=[[0, 0], [1, 0]])
    star = make_object(ObjectKind.STAR, "S", "st", inner_radius=2.0, outer_radius=1.0)
    tex = make_object(ObjectKind.TEX, "T", "t", tex="Hallo")
    group = make_object(ObjectKind.GROUP, "G", "g", members=[])
    scene = Scene(id="s", name="S", objects=[polygon, star, tex, group])
    codes = {issue.code for issue in validate_scene(scene, latex_available=False)}
    assert {"polygon_points", "radii_invalid", "latex_unavailable", "group_empty"} <= codes
