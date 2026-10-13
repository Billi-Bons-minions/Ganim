"""Dashed shapes (Manim's ``DashedVMobject``) and the dashed line (``DashedLine``)."""

from __future__ import annotations

import importlib.util
import re

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model.dashes import DASHED_KINDS, dash_intervals, dash_polylines
from manim_studio.model.entities import Scene, Step
from manim_studio.model.schema import animation_allowed
from manim_studio.model.state import states_after
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_animation, make_object, make_project, play

HAS_MANIM = importlib.util.find_spec("manim") is not None


def dashed_scene() -> Scene:
    objects = [
        make_object(ObjectKind.CIRCLE, "Kreis", "k", -5.0, 2.0, radius=1.0, dashed=True),
        make_object(ObjectKind.SQUARE, "Quadrat", "q", -2.5, 2.0, side_length=1.8, dashed=True, num_dashes=12, dashed_ratio=0.6),
        make_object(ObjectKind.STAR, "Stern", "s", 0.0, 2.0, dashed=True, num_dashes=20),
        make_object(ObjectKind.ARC, "Bogen", "b", 2.5, 2.0, radius=1.0, start_angle=30.0, angle=200.0, dashed=True, num_dashes=7),
        make_object(ObjectKind.SECTOR, "Sektor", "t", 5.0, 2.0, radius=1.2, start_angle=10.0, angle=100.0, dashed=True, num_dashes=9),
        make_object(ObjectKind.POLYGON, "Vieleck", "v", -5.0, -1.5, points=[[-1, -0.5], [1, -0.8], [0.6, 0.9]], dashed=True, num_dashes=10),
        make_object(ObjectKind.REGULAR_POLYGON, "Sechseck", "r", -2.5, -1.5, n=6, radius=1.0, dashed=True),
        make_object(ObjectKind.ELLIPSE, "Ellipse", "e", 0.5, -1.5, width=2.6, height=1.2, dashed=True, num_dashes=18, dashed_ratio=0.3),
        make_object(ObjectKind.TRIANGLE, "Dreieck", "d", 3.5, -1.5, radius=1.0, dashed=True, num_dashes=6),
        make_object(ObjectKind.RECTANGLE, "Rechteck", "w", 5.5, -2.5, width=1.5, height=0.8, dashed=True, num_dashes=5),
        make_object(ObjectKind.DASHED_LINE, "Strichlinie", "l", 0.0, -3.3, length=5.0, dash_length=0.3, dashed_ratio=0.4),
    ]
    objects[0].rotation = 30.0
    objects[2].rotation = -15.0
    return Scene(id="s", name="Striche", objects=objects)


def test_dash_intervals_like_manim() -> None:
    # closed: as many gaps as dashes; open: starts and ends with a dash
    assert dash_intervals(4, 0.5, True) == pytest.approx([(0.0, 0.125), (0.25, 0.375), (0.5, 0.625), (0.75, 0.875)])
    open_dashes = dash_intervals(3, 0.6, False)
    assert open_dashes[0][0] == 0.0 and open_dashes[-1][1] == pytest.approx(1.0)
    assert sum(end - start for start, end in open_dashes) == pytest.approx(0.6)


def test_dashes_follow_the_outline() -> None:
    scene = dashed_scene()
    circle = scene.object_by_id("k")
    dashes = dash_polylines(scene, circle)
    assert len(dashes) == 15
    # Manim starts the circle on the right and goes counterclockwise
    assert dashes[0][0] == pytest.approx((1.0, 0.0), abs=1e-6) and dashes[0][-1][1] > 0


def test_rules() -> None:
    scene = dashed_scene()
    assert not has_errors(validate_scene(scene))
    circle = scene.object_by_id("k")
    # Manim would bend every dash into the other shape: no transforms
    assert not animation_allowed(AnimationKind.TRANSFORM, ObjectKind.CIRCLE, circle.params)
    assert animation_allowed(AnimationKind.TRANSFORM, ObjectKind.CIRCLE, {})
    assert animation_allowed(AnimationKind.CREATE, ObjectKind.CIRCLE, circle.params)
    # a dashed shape is no path and no part of a boolean shape
    dot = make_object(ObjectKind.DOT, "Punkt", "p")
    scene.objects.append(dot)
    scene.steps = [play(make_animation(AnimationKind.MOVE_ALONG_PATH, "p", "m", path="k"))]
    assert any(issue.code == "path_dashed" for issue in validate_scene(scene))
    from manim_studio.model.booleans import can_use

    assert not can_use(scene, "x", circle) and all(kind in DASHED_KINDS for kind in (ObjectKind.SECTOR, ObjectKind.STAR))


def test_code() -> None:
    code = generate_script(make_project(dashed_scene()))
    assert "kreis = DashedVMobject(" in code and "num_dashes=15," in code
    assert "num_dashes=12,\n            dashed_ratio=0.6," in code
    # only the outline: the shape inside has no fill
    start = code.index("stern = DashedVMobject(")
    assert "fill_opacity=0.0" in code[start : code.index("num_dashes", start)]


def test_import() -> None:
    from manim_studio.importer import import_script

    imported = import_script(generate_script(make_project(dashed_scene()))).project.scenes[0]
    circle = next(obj for obj in imported.objects if obj.kind == ObjectKind.CIRCLE)
    assert circle.params["dashed"] is True and circle.params["num_dashes"] == 15
    square = next(obj for obj in imported.objects if obj.kind == ObjectKind.SQUARE)
    assert square.params["num_dashes"] == 12 and square.params["dashed_ratio"] == pytest.approx(0.6)


def _stage_dash_ends(scene: Scene, obj, state) -> list[tuple[float, float, float, float]]:
    from manim_studio.ui.stage.drawing import PX, StageResources, build_drawing
    from manim_studio.ui.stage.drawing_extra import placement_transform

    drawing = build_drawing(scene, obj, state, StageResources())
    to_scene = placement_transform(("", "", state.x, state.y, state.rotation, state.scale, tuple(state.matrix)))
    ends = []
    for primitive in drawing.primitives:
        for polygon in to_scene.map(primitive.path).toSubpathPolygons():
            first, last = polygon[0], polygon[polygon.size() - 1]
            ends.append((first.x() / PX, -first.y() / PX, last.x() / PX, -last.y() / PX))
    return ends


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_dashes_like_manim(tmp_path, qapp) -> None:
    """Every dash starts and ends where Manim has it (after placing, turning and scaling)."""
    from tests.test_manim_integration import run_manim

    scene = dashed_scene()
    scene.steps = [play(make_animation(AnimationKind.SCALE, "q", "z", factor=1.3), make_animation(AnimationKind.ROTATE, "b", "r", angle=40.0))]
    names = {"k": "kreis", "q": "quadrat", "s": "stern", "b": "bogen", "t": "sektor", "v": "vieleck", "r": "sechseck", "e": "ellipse", "d": "dreieck", "w": "rechteck", "l": "strichlinie"}
    report = "\n".join(
        f"for dash in {name}.submobjects:\n    print('DASH {key}', *[round(float(v), 4) for v in (*dash.points[0][:2], *dash.points[-1][:2])])"
        for key, name in names.items()
    )
    scene.steps.append(Step(id="report", kind=StepKind.CODE, code=report, wait_time=0.0))
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Striche", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    theirs: dict[str, list[tuple[float, ...]]] = {}
    for key, *values in re.findall(r"DASH (\w) (\S+) (\S+) (\S+) (\S+)", result.stdout):
        theirs.setdefault(key, []).append(tuple(float(v) for v in values))
    states = states_after(scene, 0)
    for key in names:
        ours = _stage_dash_ends(scene, scene.object_by_id(key), states[key])
        assert len(ours) == len(theirs[key]), key
        for mine, manim in zip(ours, theirs[key]):
            assert mine == pytest.approx(manim, abs=0.03), key
