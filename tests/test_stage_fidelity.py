"""Details of the stage that must agree with Manim: default text font and ticks of axes."""

from __future__ import annotations

import importlib.util

import pytest

from manim_studio.model.geometry import tick_values

HAS_MANIM = importlib.util.find_spec("manim") is not None


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
@pytest.mark.parametrize("tip", [False, True])
@pytest.mark.parametrize("low, high, step", [(-5, 5, 1), (-3, 3, 0.5), (1, 5, 1), (0.5, 4, 1), (-6, -1, 2), (-2.5, 3.2, 1), (0, 10, 2.5), (-1, 1, 1)])
def test_ticks_like_manim(low: float, high: float, step: float, tip: bool) -> None:
    from manim import NumberLine

    line = NumberLine(x_range=[low, high, step], include_tip=tip)
    assert tick_values(low, high, step, tip) == pytest.approx(list(line.get_tick_range()))


def test_last_tick_is_left_out_under_a_tip() -> None:
    assert tick_values(-5, 5, 1, True) == [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4]
    assert tick_values(-5, 5, 1, False)[-1] == 5


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_stage_text_is_as_wide_as_manims(qapp) -> None:
    """Without ``font=`` Manim's Text uses Pango's default (a serif font), not the interface font."""
    from manim import Text

    from manim_studio.model.types import ObjectKind
    from manim_studio.ui.stage.drawing import PX, text_font, text_path
    from tests.helpers import make_object

    sample = "Hamburgefonts A = 1.50"
    obj = make_object(ObjectKind.TEXT, "T", "t", text=sample, font_size=48.0)
    bounds = text_path(sample, text_font(obj, 48.0)).boundingRect()
    manim_text = Text(sample, font_size=48.0)
    assert bounds.width() / PX == pytest.approx(manim_text.width, rel=0.02)
    assert bounds.height() / PX == pytest.approx(manim_text.height, rel=0.05)


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
@pytest.mark.parametrize("x, y, y_max", [(0.0, -0.3, 2.0), (0.0, 0.0, 3.0), (-3.0, -1.0, 2.0), (3.5, 0.5, 3.0)])
def test_axis_labels_like_manim(tmp_path, qapp, x: float, y: float, y_max: float) -> None:
    """``get_x_axis_label``/``get_y_axis_label``: next to the axis tip, pushed back onto the screen."""
    import re

    from manim_studio.codegen import generate_script
    from manim_studio.model.entities import Scene, Step
    from manim_studio.model.state import states_after
    from manim_studio.model.types import ObjectKind, StepKind
    from manim_studio.ui.stage.drawing import PX, StageResources, build_drawing
    from tests.helpers import make_object, make_project
    from tests.test_manim_integration import run_manim

    axes = make_object(ObjectKind.AXES, "Achsen", "ax", x, y, x_min=-3.0, x_max=3.0, y_min=-2.0, y_max=y_max, x_length=10.0, y_length=6.0, x_label="x", y_label="y")
    code = "for label in achsen.submobjects[-2:]:\n    print('LABEL', round(float(label.get_center()[0]), 4), round(float(label.get_center()[1]), 4))"
    scene = Scene(id="s", name="Achsen", objects=[axes], steps=[Step(id="code", kind=StepKind.CODE, code=code)])
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Achsen", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    manim_centers = [(float(a), float(b)) for a, b in re.findall(r"LABEL (\\S+) (\\S+)", result.stdout)]
    drawing = build_drawing(scene, axes, states_after(scene, -1)["ax"], StageResources())
    stage_centers = [(x + p.path.boundingRect().center().x() / PX, y - p.path.boundingRect().center().y() / PX) for p in drawing.primitives[-2:]]
    for ours, theirs in zip(stage_centers, manim_centers):
        assert ours == pytest.approx(theirs, abs=0.03)
