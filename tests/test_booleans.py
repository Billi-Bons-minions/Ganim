"""Boolean shapes (union, intersection, difference, exclusion): model, stage, code and rendering."""

from __future__ import annotations

import importlib.util
import math
import re

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model import operations as ops
from manim_studio.model.booleans import can_use, leaves, operands, result_bounds, start_bounds
from manim_studio.model.entities import Scene, Step
from manim_studio.model.schema import animation_allowed
from manim_studio.model.stage_edits import MOVE, check_edit
from manim_studio.model.state import states_after
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_animation, make_object, make_project, play

HAS_MANIM = importlib.util.find_spec("manim") is not None


def boolean(object_id: str, operation: str, first: str, second: str):
    return make_object(ObjectKind.BOOLEAN_SHAPE, object_id.upper(), object_id, operation=operation, first_shape=first, second_shape=second)


def two_circles(operation: str = "intersection") -> Scene:
    a = make_object(ObjectKind.CIRCLE, "A", "a", -0.5, 0.0, radius=1.0)
    b = make_object(ObjectKind.CIRCLE, "B", "b", 0.5, 0.0, radius=1.0)
    return Scene(id="s", name="S", objects=[a, b, boolean("u", operation, "a", "b")])


def test_bounds_of_each_operation() -> None:
    lens = start_bounds(two_circles("intersection"), two_circles().object_by_id("u"))
    # the lens between two unit circles 1 apart: x from -0.5 to 0.5, y up to sqrt(3)/2
    assert lens == pytest.approx((-0.5, -math.sqrt(3) / 2, 0.5, math.sqrt(3) / 2), abs=2e-3)
    for operation in ("union", "exclusion"):
        scene = two_circles(operation)
        assert start_bounds(scene, scene.object_by_id("u")) == pytest.approx((-1.5, -1.0, 1.5, 1.0), abs=2e-3)
    scene = two_circles("difference")
    left, bottom, right, top = start_bounds(scene, scene.object_by_id("u"))
    assert (left, right, top) == pytest.approx((-1.5, 0.0, 1.0), abs=2e-3)  # A without B ends where B's outline crosses A's
    # disjoint circles: the intersection is empty
    scene.object_by_id("b").x = 5.0
    scene.object_by_id("u").params["operation"] = "intersection"
    assert start_bounds(scene, scene.object_by_id("u")) is None
    assert {issue.code for issue in validate_scene(scene)} >= {"boolean_empty"} and not has_errors(validate_scene(scene))


def test_operands_cycles_and_nesting() -> None:
    scene = two_circles("union")
    c = make_object(ObjectKind.SQUARE, "C", "c", 0.0, -1.0, side_length=1.0)
    scene.objects += [c, boolean("v", "difference", "u", "c")]
    assert [leaf.id for leaf in leaves(scene, scene.object_by_id("v"))] == ["a", "b", "c"]
    # u may not use v (v is built from u), text is no closed shape
    assert not can_use(scene, "u", scene.object_by_id("v")) and can_use(scene, "v", scene.object_by_id("c"))
    text = make_object(ObjectKind.TEXT, "T", "t", text="Hi")
    scene.objects.append(text)
    assert not can_use(scene, "u", text)
    scene.object_by_id("u").params["second_shape"] = "v"
    assert operands(scene, scene.object_by_id("u")) is None
    assert "boolean_shapes_missing" in {issue.code for issue in validate_scene(scene)}
    scene.object_by_id("u").params["second_shape"] = "a"
    assert operands(scene, scene.object_by_id("u")) is None  # the same shape twice


def test_boolean_shape_follows_its_shapes() -> None:
    scene = two_circles("intersection")
    scene.steps = [play(make_animation(AnimationKind.MOVE, "b", "m", x=0.5, y=1.0))]
    before, after = states_after(scene, -1)["u"], states_after(scene, 0)["u"]
    assert (before.x, before.y) == pytest.approx((0.0, 0.0), abs=1e-3)
    # the lens of circles at (-0.5, 0) and (0.5, 1): symmetric around the midpoint of the centers
    assert (after.x, after.y) == pytest.approx((0.0, 0.5), abs=5e-3)
    assert after.parts[1][2:4] == pytest.approx((0.5, 1.0))
    # moving or turning the boolean shape itself is not possible
    assert not animation_allowed(AnimationKind.MOVE, ObjectKind.BOOLEAN_SHAPE, {})
    assert not animation_allowed(AnimationKind.CHANGE_COLOR, ObjectKind.BOOLEAN_SHAPE, {})
    assert animation_allowed(AnimationKind.FADE_IN, ObjectKind.BOOLEAN_SHAPE, {})
    assert animation_allowed(AnimationKind.INDICATE, ObjectKind.BOOLEAN_SHAPE, {})


def test_deleting_a_shape_deletes_the_boolean_shapes() -> None:
    scene = two_circles("union")
    c = make_object(ObjectKind.SQUARE, "C", "c", 0.0, -1.0)
    scene.objects += [c, boolean("v", "difference", "u", "c")]
    ops.remove_objects(scene, ["a"])
    assert [obj.id for obj in scene.objects] == ["b", "c"]


def test_boolean_code() -> None:
    scene = two_circles("union")
    c = make_object(ObjectKind.SQUARE, "C", "c", 0.0, -1.0, side_length=1.0)
    scene.objects += [c, boolean("v", "intersection", "u", "c")]
    scene.steps = [play(make_animation(AnimationKind.CREATE, "v"))]
    code = generate_script(make_project(scene))
    assert "def studio_union(first, second, **style):" in code
    assert "u = always_redraw(lambda: studio_union(a, b, stroke_color=" in code
    # a nested boolean shape repeats the inner operation (the inner one may not be on screen)
    assert "v = always_redraw(lambda: Intersection(studio_union(a, b), c, stroke_color=" in code
    scene.object_by_id("u").params["operation"] = "exclusion"
    scene.object_by_id("v").params["operation"] = "difference"
    code = generate_script(make_project(scene))
    assert "studio_union" not in code and "Difference(Exclusion(a, b), c, " in code


def test_placement_transform_matches_the_stage_items(qapp) -> None:
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QGraphicsRectItem

    from manim_studio.ui.stage.drawing import pt
    from manim_studio.ui.stage.drawing_extra import placement_transform
    from manim_studio.ui.stage.view import local_matrix

    for placement in (("a", "a", 1.0, -2.0, 30.0, 1.5, (1.0, 0.0, 0.0, 1.0)), ("a", "a", -0.5, 0.7, -70.0, 0.8, (1.0, 1.0, 0.0, 1.0)), ("a", "a", 0.0, 0.0, 15.0, 1.0, (0.5, -0.3, 0.8, 1.2))):
        _id, _shape, x, y, rotation, scale, matrix = placement
        item = QGraphicsRectItem()
        item.setPos(pt(x, y))
        item.setRotation(-rotation)
        item.setScale(scale)
        item.setTransform(local_matrix(matrix, rotation))
        ours = placement_transform(placement)
        for point in (QPointF(30, -12), QPointF(-80, 45), QPointF(0, 0)):
            theirs = item.sceneTransform().map(point)
            mapped = ours.map(point)
            assert (mapped.x(), mapped.y()) == pytest.approx((theirs.x(), theirs.y()), abs=1e-6)


def test_stage_draws_the_result(qapp) -> None:
    from manim_studio.ui.stage.drawing import PX, StageResources, build_drawing

    scene = two_circles("difference")
    states = states_after(scene, -1)
    drawing = build_drawing(scene, scene.object_by_id("u"), states["u"], StageResources())
    path = drawing.primitives[0].path
    bounds = result_bounds(scene, scene.object_by_id("u"), states["u"].parts)
    rect = path.boundingRect()
    # drawn around the state's position (the center of the result)
    assert rect.width() / PX == pytest.approx(bounds[2] - bounds[0], abs=0.01)
    assert rect.height() / PX == pytest.approx(bounds[3] - bounds[1], abs=0.01)
    assert rect.center().x() == pytest.approx(0.0, abs=1.0) and rect.center().y() == pytest.approx(0.0, abs=1.0)
    # a point inside A but outside B is filled, one inside both is not
    from PySide6.QtCore import QPointF

    center_x = states["u"].x
    assert path.contains(QPointF((-1.2 - center_x) * PX, 0.0)) and not path.contains(QPointF((0.0 - center_x) * PX, 0.0))


def test_boolean_shapes_from_the_library(window) -> None:
    controller = window.controller
    created = controller.add_object(ObjectKind.BOOLEAN_SHAPE)
    scene = window.editor.scene()
    shape = scene.object_by_id(created)
    first, second = (scene.object_by_id(shape.params[key]) for key in ("first_shape", "second_shape"))
    assert first.kind == second.kind == ObjectKind.CIRCLE and first.x < second.x
    assert not has_errors(validate_scene(scene))
    # two selected shapes are combined
    square = controller.add_object(ObjectKind.SQUARE, 3.0, 0.0)
    star = controller.add_object(ObjectKind.STAR, 3.5, 0.5)
    window.editor.select_objects([square, star])
    combined = window.editor.scene().object_by_id(controller.add_object(ObjectKind.BOOLEAN_SHAPE))
    assert (combined.params["first_shape"], combined.params["second_shape"]) == (square, star)
    # it cannot be moved on the stage, and deleting a shape deletes it
    assert not check_edit(window.editor.scene(), -1, [combined.id], MOVE).allowed
    window.document.edit_scene("x", window.editor.scene_id, lambda s: ops.remove_objects(s, [star]), None)
    assert window.editor.scene().object_by_id(combined.id) is None


def test_boolean_shapes_round_trip_through_the_importer() -> None:
    from manim_studio.importer import import_script

    scene = two_circles("union")
    c = make_object(ObjectKind.SQUARE, "C", "c", 0.0, -1.0, side_length=1.0)
    scene.objects += [c, boolean("v", "difference", "u", "c")]
    scene.steps = [play(make_animation(AnimationKind.FADE_IN, "v"))]
    imported = import_script(generate_script(make_project(scene))).project.scenes[0]
    inner, outer = (obj for obj in imported.objects if obj.kind == ObjectKind.BOOLEAN_SHAPE)
    assert (inner.params["operation"], outer.params["operation"]) == ("union", "difference")
    assert outer.params["first_shape"] == inner.id
    assert operands(imported, outer) is not None and not has_errors(validate_scene(imported))


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_bounds_and_centers_match_manim(tmp_path) -> None:
    from tests.test_manim_integration import run_manim

    a = make_object(ObjectKind.SECTOR, "A", "a", -3.0, 1.0, radius=1.6, start_angle=10.0, angle=120.0)
    b = make_object(ObjectKind.TRIANGLE, "B", "b", -2.4, 0.8, radius=1.0)
    c = make_object(ObjectKind.STAR, "C", "c", 2.0, 1.0, outer_radius=1.5, inner_radius=0.6)
    d = make_object(ObjectKind.REGULAR_POLYGON, "D", "d", 2.8, 0.6, n=4, radius=1.0)
    d.rotation = 25.0
    e = make_object(ObjectKind.ANNULUS, "E", "e", 0.0, -2.0, inner_radius=0.5, outer_radius=1.2)
    f = make_object(ObjectKind.RECTANGLE, "F", "f", 0.9, -1.6, width=1.4, height=0.8)
    shapes = [a, b, c, d, e, f]
    results = [boolean("u", "union", "a", "b"), boolean("i", "intersection", "c", "d"), boolean("ex", "exclusion", "e", "f"), boolean("n", "difference", "u", "f")]
    steps = [
        play(make_animation(AnimationKind.MOVE, "f", "m", x=0.4, y=-1.2)),
        play(make_animation(AnimationKind.APPLY_MATRIX, "d", "mx", m11=1.0, m12=0.5, m21=0.0, m22=1.0)),
    ]
    lines = [f"print('BOUNDS', '{r.id}', *[round(float(v), 4) for v in ({r.id}.get_center()[0], {r.id}.get_center()[1], {r.id}.width, {r.id}.height)])" for r in results]
    steps.append(Step(id="code", kind=StepKind.CODE, code="\n".join(lines)))
    scene = Scene(id="s", name="Mengen", objects=[*shapes, *results], steps=steps)
    assert not has_errors(validate_scene(scene)), [issue.code for issue in validate_scene(scene)]
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Mengen", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    printed = {match[0]: tuple(float(v) for v in match[1:]) for match in re.findall(r"BOUNDS (\w+) (\S+) (\S+) (\S+) (\S+)", result.stdout)}
    states = states_after(scene, 1)
    for shape in results:
        left, bottom, right, top = result_bounds(scene, shape, states[shape.id].parts)
        x, y, width, height = printed[shape.id]
        # Manim measures the Bézier handles too; polygons and circles agree within a few hundredths
        assert ((left + right) / 2, (bottom + top) / 2) == pytest.approx((x, y), abs=0.03), shape.id
        assert (right - left, top - bottom) == pytest.approx((width, height), abs=0.06), shape.id


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_boolean_shapes_with_every_animation_render(tmp_path) -> None:
    from manim_studio.model.types import ENTRANCE_ANIMATIONS, EXIT_ANIMATIONS
    from tests.test_manim_integration import run_manim

    a = make_object(ObjectKind.CIRCLE, "A", "a", -3.5, 0.0, radius=1.0)
    b = make_object(ObjectKind.SECTOR, "B", "b", -2.8, 0.2, radius=1.4)
    c = make_object(ObjectKind.POLYGON, "C", "c", 3.0, 0.0)
    d = make_object(ObjectKind.ELLIPSE, "D", "d", 3.6, 0.5)
    results = [boolean("u", "union", "a", "b"), boolean("i", "intersection", "c", "d"), boolean("x", "exclusion", "u", "d"), boolean("f", "difference", "c", "a")]
    allowed = [kind for kind in AnimationKind if animation_allowed(kind, ObjectKind.BOOLEAN_SHAPE, {})]
    entrances = [kind for kind in allowed if kind in ENTRANCE_ANIMATIONS]
    exits = [kind for kind in allowed if kind in EXIT_ANIMATIONS]
    others = [kind for kind in allowed if kind not in ENTRANCE_ANIMATIONS and kind not in EXIT_ANIMATIONS]
    ids = [r.id for r in results]
    steps = []
    for index, kind in enumerate(entrances):
        target = ids[index % 4]
        steps += [play(make_animation(kind, target, f"in{index}", run_time=0.1)), play(make_animation(AnimationKind.FADE_OUT, target, f"out{index}", run_time=0.1))]
    steps.append(play(*(make_animation(AnimationKind.FADE_IN, target, f"show-{target}", run_time=0.1) for target in ids)))
    steps += [play(make_animation(kind, ids[index % 4], f"o{index}", run_time=0.1)) for index, kind in enumerate(others)]
    # the shapes move, turn and change while the boolean shapes follow them
    steps.append(play(make_animation(AnimationKind.MOVE, "a", "ma", x=-1.0, y=1.0, run_time=0.2), make_animation(AnimationKind.ROTATE, "c", "rc", angle=90.0, run_time=0.2)))
    steps.append(play(make_animation(AnimationKind.SCALE, "d", "sd", factor=0.3, run_time=0.2)))
    steps.append(play(make_animation(AnimationKind.TRANSFORM, "b", "tb", target="d", run_time=0.2)))
    for index, kind in enumerate(exits):
        steps += [play(make_animation(kind, "x", f"x{index}", run_time=0.1)), play(make_animation(AnimationKind.FADE_IN, "x", f"back{index}", run_time=0.1))]
    scene = Scene(id="s", name="Mengen", objects=[a, b, c, d, *results], steps=steps)
    assert len(entrances) >= 5 and len(exits) >= 3 and len(others) >= 3
    assert not has_errors(validate_scene(scene)), [issue.code for issue in validate_scene(scene)]
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Mengen", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
@pytest.mark.parametrize("n", [3, 4, 5, 6, 8])
def test_regular_polygon_outlines_start_like_manim(n: int) -> None:
    """Motion paths along a regular polygon start at Manim's first corner (0° for even n, 90° for odd n)."""
    from manim import RegularPolygon

    from manim_studio.model.booleans import local_contours
    from manim_studio.model.paths import local_outline

    polygon = make_object(ObjectKind.REGULAR_POLYGON, "P", "p", n=n, radius=1.0)
    corners = [tuple(vertex[:2]) for vertex in RegularPolygon(n=n).get_vertices()]
    outline = local_outline(Scene(id="s", name="S"), polygon)
    assert outline[0] == pytest.approx(corners[0], abs=1e-9)
    assert [value for point in outline[:-1] for value in point] == pytest.approx([value for point in corners for value in point], abs=1e-9)
    # the boolean outlines are centered on the bounding box like Manim's move_to
    xs, ys = [x for x, _ in corners], [y for _, y in corners]
    shifted = [(x - (min(xs) + max(xs)) / 2, y - (min(ys) + max(ys)) / 2) for x, y in corners]
    assert [value for point in local_contours(polygon)[0] for value in point] == pytest.approx([value for point in shifted for value in point], abs=1e-9)
