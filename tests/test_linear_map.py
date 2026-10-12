"""Linear maps (Manim's ApplyMatrix): state, stage, code and import."""

from __future__ import annotations

import math

import pytest

from manim_studio.codegen import generate_script
from manim_studio.importer import import_script
from manim_studio.model.entities import Scene
from manim_studio.model.playback import state_at_time
from manim_studio.model.schema import animation_allowed
from manim_studio.model.state import ObjectState, apply_matrix, states_after
from manim_studio.model.types import AnimationKind, ObjectKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_animation, make_object, make_project, play

SHEAR = {"m11": 1.0, "m12": 1.0, "m21": 0.0, "m22": 1.0}


def _drawn(state: ObjectState, local: tuple[float, float]) -> tuple[float, float]:
    """Where the state draws a point of the shape (center + R · s · M · local)."""
    m11, m12, m21, m22 = state.matrix
    x, y = m11 * local[0] + m12 * local[1], m21 * local[0] + m22 * local[1]
    t = math.radians(state.rotation)
    return state.x + state.scale * (math.cos(t) * x - math.sin(t) * y), state.y + state.scale * (math.sin(t) * x + math.cos(t) * y)


def test_the_map_acts_on_every_point_around_the_origin() -> None:
    start = ObjectState("o", "o", True, 1.0, 2.0, 30.0, 1.5, "#FFFFFF", "#FFFFFF")
    after = apply_matrix(start, (1.0, 1.0, 0.0, 1.0), 1.0)
    for local in ((0.7, -0.3), (0.0, 1.0), (-1.0, 0.25)):
        x, y = _drawn(start, local)
        assert _drawn(after, local) == pytest.approx((x + y, y))
    halfway = apply_matrix(start, (1.0, 1.0, 0.0, 1.0), 0.5)
    x, y = _drawn(start, (0.7, -0.3))
    assert _drawn(halfway, (0.7, -0.3)) == pytest.approx((x + 0.5 * y, y))  # points move on straight lines


def test_steps_and_playback() -> None:
    square = make_object(ObjectKind.SQUARE, "Quadrat", "q", 2.0, 1.0)
    scene = Scene(
        id="s",
        name="S",
        objects=[square],
        steps=[play(make_animation(AnimationKind.APPLY_MATRIX, "q", "m", **SHEAR)), play(make_animation(AnimationKind.ROTATE, "q", "r", angle=90.0), step_id="r")],
    )
    assert not has_errors(validate_scene(scene))
    sheared = states_after(scene, 0)["q"]
    assert (sheared.x, sheared.y) == pytest.approx((3.0, 1.0)) and sheared.matrix == pytest.approx((1.0, 1.0, 0.0, 1.0))
    turned = states_after(scene, 1)["q"]
    assert turned.rotation == pytest.approx(90.0) and turned.matrix == pytest.approx(sheared.matrix)  # turning keeps the shear
    assert state_at_time(scene, 0.5)["q"].matrix[1] == pytest.approx(0.5)


def test_only_shapes_that_keep_the_deformation() -> None:
    assert animation_allowed(AnimationKind.APPLY_MATRIX, ObjectKind.NUMBER_PLANE, {})
    assert animation_allowed(AnimationKind.APPLY_MATRIX, ObjectKind.VECTOR, {})
    for kind in (ObjectKind.HIGHLIGHT, ObjectKind.GRAPH_POINT, ObjectKind.CAMERA, ObjectKind.PARAMETER, ObjectKind.IMAGE, ObjectKind.SURFACE):
        assert not animation_allowed(AnimationKind.APPLY_MATRIX, kind, {})


def test_code_and_import() -> None:
    plane = make_object(ObjectKind.NUMBER_PLANE, "Ebene", "e")
    scene = Scene(id="s", name="S", objects=[plane], steps=[play(make_animation(AnimationKind.APPLY_MATRIX, "e", "m", m11=0.0, m12=-1.0, m21=1.0, m22=0.0))])
    code = generate_script(make_project(scene))
    assert "ApplyMatrix([[0.0, -1.0], [1.0, 0.0]], ebene, run_time=1.0, rate_func=smooth)" in code
    report = import_script(code)
    imported = [anim for step in report.project.scenes[0].steps for anim in step.animations]
    assert [(anim.kind, anim.params) for anim in imported] == [(AnimationKind.APPLY_MATRIX, {"m11": 0.0, "m12": -1.0, "m21": 1.0, "m22": 0.0})]


def test_stage_draws_the_map_inside_the_rotation(qapp) -> None:
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QGraphicsRectItem

    from manim_studio.ui.stage.view import local_matrix

    for rotation in (0.0, 30.0, 90.0, -45.0):
        item = QGraphicsRectItem(0, 0, 1, 1)
        item.setRotation(-rotation)
        item.setTransform(local_matrix((1.0, 1.0, 0.0, 1.0), rotation))
        point = item.mapToScene(QPointF(0.7, 0.2))  # stage y points down
        state = ObjectState("o", "o", True, 0.0, 0.0, rotation, 1.0, "#FFFFFF", "#FFFFFF", matrix=(1.0, 1.0, 0.0, 1.0))
        assert (point.x(), -point.y()) == pytest.approx(_drawn(state, (0.7, -0.2)))
