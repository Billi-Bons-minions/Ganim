"""Nonlinear maps: ApplyComplexFunction and ApplyPointwiseFunction on the stage and in the script."""

from __future__ import annotations

import importlib.util
import math

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model.entities import Scene
from manim_studio.model.expression import ExpressionError, evaluate_complex, parse_complex
from manim_studio.model.schema import animation_allowed
from manim_studio.model.state import states_after
from manim_studio.model.types import AnimationKind, ObjectKind
from manim_studio.model.validation import has_errors, validate_scene
from manim_studio.model.warps import COMPLEX, POINTWISE, map_function, warp_point, warp_polyline
from tests.helpers import make_animation, make_object, make_project, play

HAS_MANIM = importlib.util.find_spec("manim") is not None


def test_complex_terms() -> None:
    assert evaluate_complex(parse_complex("z^2"), 1 + 1j) == pytest.approx(2j)
    assert evaluate_complex(parse_complex("e^(iz)"), math.pi) == pytest.approx(-1)
    assert evaluate_complex(parse_complex("2iz + 1"), 1j) == pytest.approx(-1)
    assert evaluate_complex(parse_complex("(z - 1)/(z + 1)"), 1j) == pytest.approx(1j)
    with pytest.raises(ExpressionError) as error:
        parse_complex("floor(z)")
    assert error.value.code == "not_complex"
    # where the map is undefined the point stays; far points are pulled back
    inverse = map_function(COMPLEX, ("1/z",))
    assert inverse(0.0, 0.0) == (0.0, 0.0) and inverse(2.0, 0.0) == pytest.approx((0.5, 0.0))
    assert math.hypot(*inverse(1e-9, 0.0)) == pytest.approx(1000.0)
    # points travel on straight lines (Manim never uses the arc ApplyComplexFunction defines)
    assert warp_point((COMPLEX, ("iz",), 0.5), 1.0, 0.0) == pytest.approx((0.5, 0.5))
    assert warp_point((POINTWISE, ("x + y", "y"), 0.5), 1.0, 2.0) == pytest.approx((2.0, 2.0))


def test_long_lines_bend() -> None:
    line = warp_polyline(((COMPLEX, ("z^2",), 1.0),), [(-1.0, 1.0), (1.0, 1.0)])
    # y = 1 becomes the parabola u = x^2 - 1, v = 2x: its vertex lies at (-1, 0)
    assert len(line) > 30 and min(u for u, _v in line) == pytest.approx(-1.0, abs=1e-6)


def test_state_rules_and_code() -> None:
    plane = make_object(ObjectKind.NUMBER_PLANE, "Ebene", "pl", x_min=-3, x_max=3, y_min=-2, y_max=2, x_length=6, y_length=4)
    circle = make_object(ObjectKind.CIRCLE, "Kreis", "c", 1.0, 0.0, radius=0.5)
    steps = [
        play(make_animation(AnimationKind.APPLY_COMPLEX, "pl", "w1", function="exp(z)"), make_animation(AnimationKind.APPLY_POINTWISE, "c", "w2", x_function="x^2", y_function="y")),
    ]
    scene = Scene(id="s", name="Abbildung", objects=[plane, circle], steps=steps)
    assert states_after(scene, 0)["pl"].warps == ((COMPLEX, ("exp(z)",), 1.0),)
    assert not has_errors(validate_scene(scene))
    code = generate_script(make_project(scene))
    assert "studio_prepare_map(ebene)" in code and "studio_prepare_map(kreis)" in code
    assert "ApplyComplexFunction(lambda z: studio_map_complex(lambda z: np.exp(z), z), ebene" in code
    assert "ApplyPointwiseFunction(lambda p: studio_map_point(lambda x, y: (x ** 2, y), p), kreis" in code
    assert "def studio_map_point(function, point):" in code
    # after a map the object keeps its shape where it is: moving it is refused
    scene.steps.append(play(make_animation(AnimationKind.MOVE, "c", "m", x=2.0, y=0.0)))
    assert "warp_then_move" in {issue.code for issue in validate_scene(scene)}
    assert not animation_allowed(AnimationKind.APPLY_COMPLEX, ObjectKind.MATH_TEX, {})
    assert animation_allowed(AnimationKind.APPLY_COMPLEX, ObjectKind.TEXT, {})


def test_stage_bends_the_outline(qapp) -> None:
    from manim_studio.ui.stage.drawing import PX, StageResources, build_drawing

    line = make_object(ObjectKind.LINE, "Linie", "l", 0.0, 1.0, length=2.0)
    scene = Scene(id="s", name="S", objects=[line], steps=[play(make_animation(AnimationKind.APPLY_COMPLEX, "l", "w", function="z^2"))])
    states = states_after(scene, 0)
    path = build_drawing(scene, line, states["l"], StageResources()).primitives[0].path
    rect = path.boundingRect()
    # the segment from -1+i to 1+i becomes the parabola from -2i to 2i through -1
    state = states["l"]
    left, right = state.x + rect.left() / PX, state.x + rect.right() / PX
    top, bottom = state.y - rect.top() / PX, state.y - rect.bottom() / PX
    assert (left, right, bottom, top) == pytest.approx((-1.0, 0.0, -2.0, 2.0), abs=0.02)


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
@pytest.mark.parametrize("function", ["iz", "z^2", "exp(z) / 2", "(1 + i) z"])
def test_points_travel_like_manim(function: str) -> None:
    import numpy as np
    from manim import ApplyComplexFunction, Polygon, linear

    from manim_studio.codegen.animations import STUDIO_MAP_SOURCE

    namespace: dict = {"np": np}
    exec(STUDIO_MAP_SOURCE, namespace)  # noqa: S102 - our own helper source
    code = parse_complex(function).to_numpy({"i": "1j"}, pad_variable=False)
    manim_function = eval(f"lambda z: studio_map_complex(lambda z: {code}, z)", namespace)  # noqa: S307 - generated from a validated term
    corners = [(0.5, 0.2), (1.2, 0.4), (0.8, 1.1)]
    polygon = Polygon(*[np.array([x, y, 0.0]) for x, y in corners])
    # Manim maps the anchors of the Bézier curves exactly (the handles follow the tangent of the map)
    anchors = [index for index in range(len(polygon.points)) if index % 4 in (0, 3)]
    start = [tuple(polygon.points[index][:2]) for index in anchors]
    animation = ApplyComplexFunction(manim_function, polygon, rate_func=linear)
    animation.begin()
    for alpha in (0.3, 0.7, 1.0):
        animation.interpolate(alpha)
        ours = [warp_point((COMPLEX, (function,), alpha), x, y) for x, y in start]
        theirs = [polygon.points[index][:2] for index in anchors]
        assert [value for point in ours for value in point] == pytest.approx([value for point in theirs for value in point], abs=1e-6)


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_maps_render(tmp_path) -> None:
    from tests.test_manim_integration import run_manim

    plane = make_object(ObjectKind.NUMBER_PLANE, "Ebene", "pl", x_min=-3, x_max=3, y_min=-2, y_max=2, x_length=6, y_length=4)
    axes = make_object(ObjectKind.AXES, "Achsen", "ax", show_numbers=True, x_min=-2, x_max=2, y_min=-2, y_max=2, x_length=4, y_length=4)
    shapes = [
        make_object(ObjectKind.CIRCLE, "Kreis", "c", 1.0, 0.0, radius=0.5),
        make_object(ObjectKind.TEXT, "Text", "t", 0.0, -1.0, text="w = f(z)"),
        make_object(ObjectKind.ARROW, "Pfeil", "a", 0.0, 1.0),
        make_object(ObjectKind.STAR, "Stern", "s", -1.5, 1.0),
        make_object(ObjectKind.FUNCTION_GRAPH, "f", "f", expression="sin(x)", x_min=-2.0, x_max=2.0),
    ]
    steps = [
        play(make_animation(AnimationKind.CREATE, "pl", run_time=0.2), make_animation(AnimationKind.CREATE, "ax", run_time=0.2), *(make_animation(AnimationKind.FADE_IN, s.id, run_time=0.2) for s in shapes)),
        play(make_animation(AnimationKind.APPLY_COMPLEX, "pl", "w1", function="1/z", run_time=0.3), make_animation(AnimationKind.APPLY_COMPLEX, "ax", "w2", function="iz", run_time=0.3)),
        play(make_animation(AnimationKind.APPLY_POINTWISE, "c", "w3", run_time=0.3), make_animation(AnimationKind.APPLY_POINTWISE, "t", "w3t", run_time=0.3), make_animation(AnimationKind.APPLY_COMPLEX, "a", "w4", function="exp(z)", run_time=0.3)),
        play(make_animation(AnimationKind.APPLY_COMPLEX, "s", "w5", function="log(z)", run_time=0.3), make_animation(AnimationKind.APPLY_POINTWISE, "f", "w6", x_function="x", y_function="y / 2", run_time=0.3)),
        play(make_animation(AnimationKind.INDICATE, "pl", run_time=0.2), make_animation(AnimationKind.FADE_OUT, "t", run_time=0.2)),
    ]
    scene = Scene(id="s", name="Abbildungen", objects=[plane, axes, *shapes], steps=steps)
    assert not has_errors(validate_scene(scene)), [issue.code for issue in validate_scene(scene)]
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Abbildungen", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
@pytest.mark.parametrize("numbers, step", [("real", 1.0), ("complex", 1.0), ("real", 0.5), ("complex", 0.5)])
def test_plane_numbers_like_manim(qapp, numbers: str, step: float) -> None:
    import numpy as np
    from manim import ComplexPlane, NumberPlane, Text

    from manim_studio.codegen.literals import fmt_number
    from manim_studio.codegen.objects import STUDIO_COMPLEX_LABELS_SOURCE
    from manim_studio.ui.stage.drawing import PX, StageResources, build_drawing

    value = float(fmt_number(step)) if "." in fmt_number(step) else int(step)
    cls = ComplexPlane if numbers == "complex" else NumberPlane
    plane = cls(x_range=[-3, 3, value], y_range=[-2, 2, value], x_length=6, y_length=4, axis_config={"label_constructor": Text})
    if numbers == "complex":
        namespace: dict = {}
        exec("from manim import *\n" + STUDIO_COMPLEX_LABELS_SOURCE, namespace)  # noqa: S102 - our own helper source
        plane.add_coordinates(*plane.get_x_axis().get_tick_range())
        labels = [*plane.coordinate_labels, *namespace["studio_complex_labels"](plane)]
    else:
        plane.add_coordinates()
        labels = [*plane.x_axis.numbers, *plane.y_axis.numbers]
    points = np.concatenate([label.get_all_points() for label in labels])
    manim_box = (points[:, 0].min(), points[:, 1].min(), points[:, 0].max(), points[:, 1].max())
    obj = make_object(ObjectKind.NUMBER_PLANE, "P", "p", numbers=numbers, x_min=-3, x_max=3, y_min=-2, y_max=2, x_length=6, y_length=4, x_step=step, y_step=step)
    scene = Scene(id="s", name="S", objects=[obj])
    drawing = build_drawing(scene, obj, states_after(scene, -1)["p"], StageResources())
    rect = drawing.primitives[-1].path.boundingRect()
    stage_box = (rect.left() / PX, -rect.bottom() / PX, rect.right() / PX, -rect.top() / PX)
    assert stage_box == pytest.approx(manim_box, abs=0.03)
