"""Vector fields (arrows and stream lines)."""

from __future__ import annotations

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model import operations as ops
from manim_studio.model.fields import field_arrows, magnitude_color, stream_lines
from manim_studio.model.types import ObjectKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_object


def test_arrows_follow_manim() -> None:
    from manim_studio.model.entities import Scene

    field = make_object(ObjectKind.VECTOR_FIELD, "Feld", "f", x_min=-1.0, x_max=1.0, y_min=-1.0, y_max=1.0, step=1.0)
    scene = Scene(id="s", name="S", objects=[field])
    arrows = field_arrows(scene, field)
    assert len(arrows) == 9
    right = next(arrow for arrow in arrows if (arrow.x, arrow.y) == (1.0, 0.0))
    # (-y, x) at (1, 0) is (0, 1); length 0.45 * sigmoid(1)
    assert (right.dx, right.dy) == pytest.approx((0.0, 0.45 / (1 + 2.718281828 ** -1)), abs=1e-6)
    assert magnitude_color(field, 0.0) == "#236B8E" and magnitude_color(field, 5.0) == "#FC6255"
    lines = stream_lines(scene, make_object(ObjectKind.VECTOR_FIELD, "S", "g", x_min=-1.0, x_max=1.0, y_min=-1.0, y_max=1.0, step=1.0, display="stream"))
    assert len(lines) == 9 and all(len(line) >= 2 for line in lines)


def test_vector_field_in_the_app(window) -> None:
    controller = window.controller
    field = controller.add_object(ObjectKind.VECTOR_FIELD, 0.0, 0.0)
    parameter = controller.add_object(ObjectKind.PARAMETER, symbol="a")
    window.document.edit_scene("p", window.editor.scene_id, lambda s: ops.set_object_param(s, field, "x_expression", "-a y"), None)
    scene = window.editor.scene()
    assert not has_errors(validate_scene(scene))
    script = generate_script(window.document.project)
    assert "def vektorfeld_1_function(pos):" in script and "always_redraw(lambda: ArrowVectorField(vektorfeld_1_function" in script
    assert "a.get_value()" in script and parameter
    window.document.edit_scene("p", window.editor.scene_id, lambda s: ops.set_object_param(s, field, "display", "stream"), None)
    window.refresh_stage()
    field_object = window.editor.scene().object_by_id(field)
    # integrating stream lines is slow, so the stage reuses the result
    assert stream_lines(window.editor.scene(), field_object) is stream_lines(window.editor.scene(), field_object)
    assert "start_animation(warm_up=True" in generate_script(window.document.project)
    window.document.edit_scene("p", window.editor.scene_id, lambda s: ops.set_object_param(s, field, "y_expression", "x +"), None)
    assert "expression_invalid" in {issue.code for issue in validate_scene(window.editor.scene())}
