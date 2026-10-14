"""Numbers on the stage set like Manim's ``DecimalNumber`` (characters close together, signs in place)."""

from __future__ import annotations

import importlib.util
import re

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model.entities import Scene, Step
from manim_studio.model.state import states_after
from manim_studio.model.types import ObjectKind, StepKind
from tests.helpers import make_object, make_project

HAS_MANIM = importlib.util.find_spec("manim") is not None


def number_scene() -> Scene:
    objects = [
        make_object(ObjectKind.DECIMAL_NUMBER, "Zahl a", "a", -4.0, 2.0, value=3.14159, decimals=2),
        make_object(ObjectKind.DECIMAL_NUMBER, "Zahl b", "b", 2.0, 2.0, value=-12.5, decimals=1, font_size=72.0),
        make_object(ObjectKind.DECIMAL_NUMBER, "Zahl c", "c", -4.0, -1.0, value=7.0, decimals=0, show_sign=True),
        make_object(ObjectKind.DECIMAL_NUMBER, "Zahl d", "d", 2.0, -1.0, value=12345.25, decimals=3, font_size=36.0),
    ]
    return Scene(id="s", name="Zahlen", objects=objects)


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_numbers_like_manim(tmp_path, qapp) -> None:
    from manim_studio.ui.stage.drawing import PX, StageResources, build_drawing
    from tests.test_manim_integration import run_manim

    scene = number_scene()
    names = {"a": "zahl_a", "b": "zahl_b", "c": "zahl_c", "d": "zahl_d"}
    report = "\n".join(f"print('SIZE {key}', round(float({name}.width), 4), round(float({name}.height), 4))" for key, name in names.items())
    scene.steps.append(Step(id="report", kind=StepKind.CODE, code=report, wait_time=0.0))
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Zahlen", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    for key in names:
        width, height = (float(v) for v in re.search(rf"SIZE {key} (\S+) (\S+)", result.stdout).groups())
        bounds = build_drawing(scene, scene.object_by_id(key), states_after(scene, -1)[key], StageResources()).primitives[0].path.boundingRect()
        assert (bounds.width() / PX, bounds.height() / PX) == pytest.approx((width, height), rel=0.03, abs=0.02), key
