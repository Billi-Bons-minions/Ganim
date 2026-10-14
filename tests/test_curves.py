"""Smooth curves and open lines through points (``set_points_smoothly``, ``set_points_as_corners``)."""

from __future__ import annotations

import importlib.util
import re

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model.curves import curve_cubics, smooth_handles
from manim_studio.model.entities import Scene, Step
from manim_studio.model.state import states_after
from manim_studio.model.types import ObjectKind, StepKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_object, make_project

HAS_MANIM = importlib.util.find_spec("manim") is not None


def curve_scene() -> Scene:
    wave = make_object(ObjectKind.POLYGON, "Welle", "w", -3.0, 1.5, smooth=True, closed=False, points=[[-2, 0], [-1, 1.2], [0, -0.4], [1, 0.9], [2, 0]])
    blob = make_object(ObjectKind.POLYGON, "Klecks", "k", 3.0, 1.0, smooth=True, points=[[0, 0], [2, 0.5], [1.5, 2], [-0.5, 1.5]])
    blob.fill_opacity = 0.5
    zigzag = make_object(ObjectKind.POLYGON, "Zickzack", "z", -3.0, -2.0, closed=False, points=[[-2, 0], [-1, 1], [0, 0], [1, 1], [2, 0]])
    dashed = make_object(ObjectKind.POLYGON, "Gestrichelt", "g", 3.0, -2.0, smooth=True, closed=False, dashed=True, num_dashes=12, points=[[-1.5, 0], [0, 1], [1.5, -0.5]])
    return Scene(id="s", name="Kurven", objects=[wave, blob, zigzag, dashed])


def test_rules_and_code() -> None:
    scene = curve_scene()
    assert not has_errors(validate_scene(scene))
    code = generate_script(make_project(scene))
    assert ".set_points_smoothly([[-2.0, 0.0, 0.0], [-1.0, 1.2, 0.0]" in code
    assert ".set_points_as_corners([" in code
    # a closed smooth curve runs back to its start
    assert ".set_points_smoothly([[0.0, 0.0, 0.0], [2.0, 0.5, 0.0], [1.5, 2.0, 0.0], [-0.5, 1.5, 0.0], [0.0, 0.0, 0.0]])" in code
    from manim_studio.model.booleans import can_use

    assert not can_use(scene, "x", scene.object_by_id("w"))
    from manim_studio.importer import import_script

    imported = {obj.name: obj for obj in import_script(code).project.scenes[0].objects}
    assert imported["welle"].params["smooth"] and not imported["welle"].params["closed"] and len(imported["welle"].params["points"]) == 5
    assert imported["klecks"].params["closed"] and len(imported["klecks"].params["points"]) == 4
    assert not imported["zickzack"].params["smooth"] and not imported["zickzack"].params["closed"]


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_handles_like_manim() -> None:
    import numpy as np
    from manim.utils.bezier import get_smooth_cubic_bezier_handle_points

    for points, closed in (([(0, 0), (1, 2), (3, 1), (4, 3), (6, 0)], False), ([(0, 0), (2, 1), (1, 3), (-1, 2)], True), ([(0, 0), (1, 1), (2, 0)], False)):
        anchors = np.array([[x, y, 0.0] for x, y in points + (points[:1] if closed else [])])
        first, second = get_smooth_cubic_bezier_handle_points(anchors)
        ours = smooth_handles(points, closed)
        assert [v for h1, h2 in ours for v in (*h1, *h2)] == pytest.approx([v for a, b in zip(first, second) for v in (*a[:2], *b[:2])], abs=1e-9)


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_curves_like_manim(tmp_path, qapp) -> None:
    """The Bézier points the stage draws lie where Manim has them (after move_to); the dashes too."""
    from manim_studio.ui.stage.drawing import PX, StageResources, build_drawing
    from manim_studio.ui.stage.drawing_extra import placement_transform
    from tests.test_manim_integration import run_manim

    scene = curve_scene()
    report = "\n".join(
        [f"print('POINTS {key}', *[round(float(v), 4) for p in {name}.points for v in p[:2]])" for key, name in (("w", "welle"), ("k", "klecks"), ("z", "zickzack"))]
        + ["for dash in gestrichelt.submobjects:\n    print('DASH', *[round(float(v), 4) for v in (*dash.points[0][:2], *dash.points[-1][:2])])"]
    )
    scene.steps.append(Step(id="report", kind=StepKind.CODE, code=report, wait_time=0.0))
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Kurven", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    states = states_after(scene, -1)
    for key in ("w", "k", "z"):
        theirs = [float(v) for v in re.search(rf"POINTS {key} ([^\n]+)", result.stdout).group(1).split()]
        obj = scene.object_by_id(key)
        drawing = build_drawing(scene, obj, states[key], StageResources())
        to_scene = placement_transform(("", "", obj.x, obj.y, 0.0, 1.0, (1.0, 0.0, 0.0, 1.0)))
        path = to_scene.map(drawing.primitives[0].path)
        ours = []
        for index in range(path.elementCount()):
            element = path.elementAt(index)
            ours.append((element.x / PX, -element.y / PX))
        # Manim keeps 4 points per curve (start, handle, handle, end); Qt shares the ends
        cubics = curve_cubics([(float(x), float(y)) for x, y in obj.params["points"]], bool(obj.params.get("smooth")), obj.params.get("closed", True))
        expected = [v for cubic in cubics for point in cubic for v in point]
        assert len(theirs) == len(expected), key
        shift = (ours[0][0] - cubics[0][0][0], ours[0][1] - cubics[0][0][1])
        moved = [v + shift[i % 2] for i, v in enumerate(expected)]
        assert moved == pytest.approx(theirs, abs=2e-3), key
    dashes = [tuple(float(v) for v in match.split()) for match in re.findall(r"DASH ([^\n]+)", result.stdout)]
    dashed = scene.object_by_id("g")
    drawing = build_drawing(scene, dashed, states["g"], StageResources())
    to_scene = placement_transform(("", "", dashed.x, dashed.y, 0.0, 1.0, (1.0, 0.0, 0.0, 1.0)))
    ours = []
    for primitive in drawing.primitives:
        polygon = to_scene.map(primitive.path).toSubpathPolygons()[0]
        ours.append((polygon[0].x() / PX, -polygon[0].y() / PX, polygon[polygon.size() - 1].x() / PX, -polygon[polygon.size() - 1].y() / PX))
    assert len(ours) == len(dashes)
    for mine, manim in zip(ours, dashes):
        assert mine == pytest.approx(manim, abs=0.03)


def test_smooth_curve_through_objects() -> None:
    dots = [make_object(ObjectKind.DOT, name, key, x, y) for name, key, x, y in (("A", "a", -2.0, 0.0), ("B", "b", 0.0, 2.0), ("C", "c", 2.0, 0.0))]
    curve = make_object(ObjectKind.POLYGON, "Bogen", "k", attach="corners", attach_corners=["a", "b", "c"], smooth=True)
    scene = Scene(id="s", name="S", objects=[*dots, curve])
    assert not has_errors(validate_scene(scene))
    code = generate_script(make_project(scene))
    line = next(line for line in code.splitlines() if line.strip().startswith("bogen = always_redraw"))
    assert ".set_points_smoothly([a.get_center(), b.get_center(), c.get_center(), a.get_center()])" in line


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_gradient_on_a_smooth_curve(tmp_path, qapp) -> None:
    """The gradient spans the box of the anchors, like Manim's get_gradient_start_and_end_points."""
    from manim_studio.ui.stage.drawing import StageResources, build_drawing
    from manim_studio.ui.stage.gradients import gradient_points
    from tests.test_manim_integration import run_manim

    scene = curve_scene()
    blob = scene.object_by_id("k")
    blob.params.update(gradient="fill", gradient_color="#FC6255", gradient_direction="up")
    scene.steps.append(Step(id="report", kind=StepKind.CODE, code="print('LINE', *[round(float(v), 4) for p in klecks.get_gradient_start_and_end_points() for v in p[:2]])", wait_time=0.0))
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Kurven", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    theirs = [float(v) for v in re.search(r"LINE (\S+) (\S+) (\S+) (\S+)", result.stdout).groups()]
    state = states_after(scene, -1)["k"]
    start, end = gradient_points(build_drawing(scene, blob, state, StageResources()).primitives, blob, state)
    assert [*start, *end] == pytest.approx(theirs, abs=0.01)
