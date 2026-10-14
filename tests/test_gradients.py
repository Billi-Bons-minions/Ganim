"""Color gradients of shapes and lines (Manim's ``set_fill([a, b])``, ``set_stroke([a, b])``, sheen direction)."""

from __future__ import annotations

import importlib.util
import re

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model.entities import Scene
from manim_studio.model.gradients import gradient_line
from manim_studio.model.playback import state_at_time
from manim_studio.model.schema import KIND_INFO
from manim_studio.model.state import states_after
from manim_studio.model.types import AnimationKind, ObjectKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_animation, make_object, make_project, play

HAS_MANIM = importlib.util.find_spec("manim") is not None


def gradient_scene() -> Scene:
    square = make_object(ObjectKind.SQUARE, "Quadrat", "q", -4.0, 1.0, side_length=2.5, gradient="fill", gradient_color="#58C4DD")
    square.rotation = 30.0
    square.fill_opacity = 1.0
    circle = make_object(ObjectKind.CIRCLE, "Kreis", "k", 0.0, 1.0, radius=1.3, gradient="both", gradient_color="#FFFF00", gradient_direction="right")
    circle.fill_opacity = 0.8
    star = make_object(ObjectKind.STAR, "Stern", "s", 4.0, 1.0, gradient="fill", gradient_color="#FC6255", gradient_direction="down")
    line = make_object(ObjectKind.LINE, "Linie", "l", -2.0, -2.0, length=4.0, gradient="stroke", gradient_color="#FC6255", gradient_direction="ur")
    line.rotation = 20.0
    arc = make_object(ObjectKind.ARC, "Bogen", "a", 3.0, -2.0, radius=1.2, start_angle=30.0, angle=200.0, gradient="stroke", gradient_color="#FFFFFF")
    return Scene(id="s", name="Verlauf", objects=[square, circle, star, line, arc])


def test_params_and_states() -> None:
    assert {"gradient", "gradient_color", "gradient_direction"} <= {spec.key for spec in KIND_INFO[ObjectKind.CIRCLE].params}
    assert KIND_INFO[ObjectKind.LINE].param("gradient").choices == ("none", "stroke")
    assert KIND_INFO[ObjectKind.TEXT].param("gradient").choices == ("none", "letters")  # letter by letter
    assert KIND_INFO[ObjectKind.MATH_TEX].param("gradient") is None
    scene = gradient_scene()
    assert not has_errors(validate_scene(scene))
    states = states_after(scene, -1)
    assert (states["q"].fill_color2, states["q"].stroke_color2) == ("#58C4DD", "")
    assert (states["k"].fill_color2, states["k"].stroke_color2) == ("#FFFF00", "#FFFF00")
    assert (states["l"].fill_color2, states["l"].stroke_color2) == ("", "#FC6255")


def test_color_change_ends_the_gradient() -> None:
    scene = gradient_scene()
    scene.steps = [
        play(make_animation(AnimationKind.CHANGE_COLOR, "k", "c1", color="#FF0000", apply_to="fill")),
        play(make_animation(AnimationKind.TRANSFORM, "q", "t", target="s")),
    ]
    half = state_at_time(scene, 0.5)["k"]
    assert half.fill_color2 not in ("", "#FFFF00", "#FF0000")  # on its way, like Manim's stretched color list
    after = states_after(scene, 0)["k"]
    assert (after.fill_color, after.fill_color2, after.stroke_color2) == ("#FF0000", "", "#FFFF00")
    # a transform mixes the second colors too and takes the target's gradient
    assert state_at_time(scene, 1.5)["q"].fill_color2 not in ("", "#58C4DD", "#FC6255")
    assert states_after(scene, 1)["q"].fill_color2 == "#FC6255"


def test_gradient_line() -> None:
    # UL: from the lower right corner of the box to the upper left one
    assert gradient_line((1.0, 2.0), 2.0, 1.0, (-1.0, 1.0), 0.0) == ((3.0, 1.0), (-1.0, 3.0))
    # the direction turns with the object, the box is that of the turned object
    start, end = gradient_line((0.0, 0.0), 1.0, 1.0, (1.0, 0.0), 90.0)
    assert start == pytest.approx((0.0, -1.0)) and end == pytest.approx((0.0, 1.0))


def test_code() -> None:
    code = generate_script(make_project(gradient_scene()))
    assert 'quadrat.set_fill(["#FC6255", "#58C4DD"])' in code
    lines = code.splitlines()
    fill = next(i for i, line in enumerate(lines) if "quadrat.set_fill([" in line)
    turn = next(i for i, line in enumerate(lines) if "quadrat.rotate(" in line)
    assert fill < turn  # the direction must turn with the square
    assert "kreis.set_stroke([" in code and "kreis.set_sheen_direction(RIGHT)" in code
    assert "linie.set_stroke([" in code and "linie.set_sheen_direction(UR)" in code
    assert "quadrat.set_sheen_direction" not in code  # UL is Manim's default


def test_import() -> None:
    from manim_studio.importer import import_script

    imported = import_script(generate_script(make_project(gradient_scene()))).project.scenes[0]
    by_name = {obj.name: obj for obj in imported.objects}
    circle = next(obj for obj in imported.objects if obj.kind == ObjectKind.CIRCLE)
    assert circle.params["gradient"] == "both" and circle.params["gradient_color"] == "#FFFF00" and circle.params["gradient_direction"] == "right"
    square = next(obj for obj in imported.objects if obj.kind == ObjectKind.SQUARE)
    assert square.params["gradient"] == "fill" and square.params.get("gradient_direction", "ul") == "ul"
    assert by_name


def test_stage_paints_the_gradient(qapp) -> None:
    from PySide6.QtGui import QGradient

    from manim_studio.ui.stage.drawing import StageResources, build_drawing

    scene = gradient_scene()
    states = states_after(scene, -1)
    drawing = build_drawing(scene, scene.object_by_id("k"), states["k"], StageResources())
    primitive = drawing.primitives[0]
    assert primitive.brush.gradient() is not None and primitive.brush.gradient().type() == QGradient.Type.LinearGradient
    assert primitive.pen.brush().gradient() is not None
    plain = build_drawing(scene, scene.object_by_id("s"), states["s"], StageResources())
    assert plain.primitives[0].pen.brush().gradient() is None  # the star's outline stays one color


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_gradient_line_like_manim(tmp_path, qapp) -> None:
    """Where the gradient starts and ends: Manim's get_gradient_start_and_end_points vs. the stage's drawing."""
    from manim_studio.model.entities import Step
    from manim_studio.model.types import StepKind
    from manim_studio.ui.stage.drawing import StageResources, build_drawing
    from manim_studio.ui.stage.gradients import gradient_points
    from tests.test_manim_integration import run_manim

    scene = gradient_scene()
    scene.steps = [
        play(make_animation(AnimationKind.ROTATE, "k", "r", angle=45.0)),
        play(make_animation(AnimationKind.SCALE, "s", "z", factor=1.5)),
    ]
    names = {"q": "quadrat", "k": "kreis", "s": "stern", "l": "linie", "a": "bogen"}
    report = "\n".join(
        f"print('LINE {key}', *[round(float(v), 4) for point in {name}.get_gradient_start_and_end_points() for v in point[:2]])" for key, name in names.items()
    )
    scene.steps.append(Step(id="report", kind=StepKind.CODE, code=report, wait_time=0.0))
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Verlauf", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    states = states_after(scene, 1)
    for key, *values in re.findall(r"LINE (\w) (\S+) (\S+) (\S+) (\S+)", result.stdout):
        obj = scene.object_by_id(key)
        drawing = build_drawing(scene, obj, states[key], StageResources())
        start, end = gradient_points(drawing.primitives, obj, states[key])
        assert (*start, *end) == pytest.approx([float(v) for v in values], abs=0.02), key
