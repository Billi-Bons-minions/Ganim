"""The way back: scripts that Manim Studio writes come back through the import (templates)."""

from __future__ import annotations

import importlib.util
import re

import pytest

from manim_studio.codegen import generate_script
from manim_studio.i18n import set_language
from manim_studio.importer import import_script
from manim_studio.model.entities import Project, Step
from manim_studio.model.types import ObjectKind, StepKind
from manim_studio.model.validation import has_errors, validate_scene

HAS_MANIM = importlib.util.find_spec("manim") is not None


def _round_trip(key: str):
    from manim_studio.templates import BUILTIN_TEMPLATES

    set_language("de")
    scene = next(template for template in BUILTIN_TEMPLATES if template.key == key).build()
    report = import_script(generate_script(Project(scenes=[scene])))
    return scene, report, report.project.scenes[0]


@pytest.mark.parametrize("key", ["secant", "parameter", "conics", "triangle", "venn"])
def test_templates_come_back_whole(key: str) -> None:
    original, report, scene = _round_trip(key)
    assert not report.skipped, report.skipped
    assert not has_errors(validate_scene(scene))
    # a tangent at a fixed point is written as a plain straight graph and comes back as one (same picture)
    kinds = sorted("function_graph" if obj.kind == ObjectKind.TANGENT and not obj.params.get("x_parameter") else obj.kind.value for obj in original.objects)
    assert sorted(obj.kind.value for obj in scene.objects) == kinds
    assert len(scene.steps) == len(original.steps)


def test_tools_that_follow_a_parameter() -> None:
    _original, report, scene = _round_trip("tangent")
    # only the separate value label is not read back yet
    assert all("beschriftung" in line for _number, line in report.skipped)
    tangent = next(obj for obj in scene.objects if obj.kind == ObjectKind.TANGENT)
    point = next(obj for obj in scene.objects if obj.kind == ObjectKind.GRAPH_POINT)
    parameter = next(obj for obj in scene.objects if obj.kind == ObjectKind.PARAMETER)
    graph = next(obj for obj in scene.objects if obj.kind == ObjectKind.FUNCTION_GRAPH)
    assert tangent.params["x_parameter"] == point.params["x_parameter"] == parameter.id
    assert tangent.params["graph_id"] == point.params["graph_id"] == graph.id and tangent.params["width"] == pytest.approx(2.5)
    secant = next(obj for obj in _round_trip("secant")[2].objects if obj.kind == ObjectKind.SECANT)
    assert secant.params["h_parameter"] and secant.params["show_triangle"]


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_round_trip_renders_the_same(tmp_path) -> None:
    """The scene read back renders in Manim and ends where the original ends."""
    from tests.test_manim_integration import run_manim

    original, _report, scene = _round_trip("tangent")
    report = "print('END', *[round(float(v), 4) for mob in (tangente_1, punkt_auf_graph_1) for v in mob.get_center()[:2]])"
    ends = []
    for current, folder in ((original, "original"), (scene, "imported")):
        current.steps.append(Step(id="report", kind=StepKind.CODE, code=report, wait_time=0.0))
        (tmp_path / folder).mkdir()
        result = run_manim(tmp_path / folder, generate_script(Project(scenes=[current])), "TangenteWandertAmGraphen", "--dry_run")
        assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
        ends.append([float(v) for v in re.search(r"END ([^\n]+)", result.stdout).group(1).split()])
    assert ends[0] == pytest.approx(ends[1], abs=1e-3)
