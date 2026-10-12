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
