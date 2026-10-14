"""Dashed function graphs: DashedVMobject around the graph, tools keep using the curve (``.curve``)."""

from __future__ import annotations

import importlib.util
import re

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model import graphs
from manim_studio.model.dashes import graph_dashes, is_dashed_graph
from manim_studio.model.entities import Scene, Step
from manim_studio.model.schema import animation_allowed
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_animation, make_object, make_project, play

HAS_MANIM = importlib.util.find_spec("manim") is not None


def graph_scene() -> Scene:
    axes = make_object(ObjectKind.AXES, "Achsen", "ax", x_min=-4.0, x_max=4.0, y_min=-2.0, y_max=2.0, x_length=8.0, y_length=4.0)
    sine = make_object(ObjectKind.FUNCTION_GRAPH, "f", "f", expression="sin(x)", axes_id="ax", x_min=-4.0, x_max=4.0, dashed=True)
    # pieces with a jump: the dashes run over both pieces, the gap does not count
    steps = make_object(ObjectKind.FUNCTION_GRAPH, "g", "g", curve="piecewise", pieces=[["0.5x - 1", "-4", "0"], ["1.5 - 0.5x", "0", "4"]], axes_id="ax", dashed=True, num_dashes=12, dashed_ratio=0.6)
    circle = make_object(ObjectKind.FUNCTION_GRAPH, "k", "k", curve="parametric", x_expression="1.5cos(t)", y_expression="1.5sin(t)", axes_id="ax", dashed=True, num_dashes=20)
    rose = make_object(ObjectKind.FUNCTION_GRAPH, "r", "r", curve="polar", r_expression="1.5sin(2t)", t_min=0.0, t_max=3.1416, axes_id="ax", dashed=True, num_dashes=16)
    area = make_object(ObjectKind.GRAPH_AREA, "Flaeche", "a", graph_id="f", x_min=0.0, x_max=3.0)
    riemann = make_object(ObjectKind.RIEMANN, "Riemann", "s", graph_id="f", x_min=-3.0, x_max=-1.0, dx=0.5)
    label = make_object(ObjectKind.GRAPH_LABEL, "Beschriftung", "b", graph_id="f", text="f", x_value=2.0)
    point = make_object(ObjectKind.GRAPH_POINT, "Punkt", "p", graph_id="f", x_value=1.0)
    dot = make_object(ObjectKind.DOT, "Laeufer", "d")
    scene = Scene(id="s", name="Gestrichelt", objects=[axes, sine, steps, circle, rose, area, riemann, label, point, dot])
    scene.steps = [play(make_animation(AnimationKind.CREATE, "f", "c")), play(make_animation(AnimationKind.MOVE_ALONG_PATH, "d", "m", path="f"))]
    return scene


def test_rules_and_model() -> None:
    scene = graph_scene()
    assert not has_errors(validate_scene(scene)), [issue.code for issue in validate_scene(scene)]
    sine = scene.object_by_id("f")
    assert is_dashed_graph(sine) and not is_dashed_graph(make_object(ObjectKind.FUNCTION_GRAPH, "i", "i", curve="implicit", dashed=True))
    assert not animation_allowed(AnimationKind.TRANSFORM, ObjectKind.FUNCTION_GRAPH, sine.params)
    dashes = graph_dashes(sine, graphs.graph_scene_segments(scene, sine))
    assert len(dashes) == 40  # the default for graphs
    # an open curve starts and ends with a dash
    start = graphs.graph_scene_segments(scene, sine)[0][0]
    assert dashes[0][0] == pytest.approx(start) and dashes[-1][-1] == pytest.approx(graphs.graph_scene_segments(scene, sine)[0][-1])


def test_code_keeps_the_curve_for_tools() -> None:
    code = generate_script(make_project(graph_scene()))
    assert "f = studio_dashed_graph(" in code and "def studio_dashed_graph" in code
    assert "achsen.get_area(\n            f.curve," in code or "achsen.get_area(f.curve" in code
    assert "get_riemann_rectangles(\n            f.curve," in code or "get_riemann_rectangles(f.curve" in code
    assert "get_graph_label(f.curve" in code or "get_graph_label(\n            f.curve" in code
    assert "MoveAlongPath(laeufer, f.curve" in code
    assert "Create(f," in code


def _stage_dash_ends(scene: Scene, key: str) -> list[tuple[float, float, float, float]]:
    obj = scene.object_by_id(key)
    dashes = graph_dashes(obj, graphs.graph_scene_segments(scene, obj))
    return [(*dash[0], *dash[-1]) for dash in dashes]


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_dashes_like_manim(tmp_path) -> None:
    """Every dash of the graphs starts and ends where Manim has it; the tools render on the curve."""
    from tests.test_manim_integration import run_manim

    scene = graph_scene()
    report = "\n".join(
        f"for dash in {name}.submobjects:\n    print('DASH {key}', *[round(float(v), 4) for v in (*dash.points[0][:2], *dash.points[-1][:2])])"
        for key, name in {"f": "f", "g": "g", "k": "k", "r": "r"}.items()
    )
    scene.steps.append(Step(id="report", kind=StepKind.CODE, code=report, wait_time=0.0))
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Gestrichelt", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    theirs: dict[str, list[tuple[float, ...]]] = {}
    for key, *values in re.findall(r"DASH (\w) (\S+) (\S+) (\S+) (\S+)", result.stdout):
        theirs.setdefault(key, []).append(tuple(float(v) for v in values))
    for key in ("f", "g", "k", "r"):
        ours = _stage_dash_ends(scene, key)
        assert len(ours) == len(theirs[key]), key
        for mine, manim in zip(ours, theirs[key]):
            assert mine == pytest.approx(manim, abs=0.03), key


def test_import_round_trip() -> None:
    from manim_studio.importer import import_script

    report = import_script(generate_script(make_project(graph_scene())))
    scene = report.project.scenes[0]
    by_name = {obj.name: obj for obj in scene.objects}
    assert by_name["f"].params["dashed"] is True and by_name["f"].params["num_dashes"] == 40
    assert by_name["k"].params["dashed"] is True and by_name["k"].params["num_dashes"] == 20  # (piecewise graphs are not imported)
    area = next(obj for obj in scene.objects if obj.kind == ObjectKind.GRAPH_AREA)
    assert area.params["graph_id"] == by_name["f"].id
    path = [anim for step in scene.steps for anim in step.animations if anim.kind == AnimationKind.MOVE_ALONG_PATH]
    assert path and path[0].params["path"] == by_name["f"].id
