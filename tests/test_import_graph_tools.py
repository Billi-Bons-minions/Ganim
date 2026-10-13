"""Importing graph tools from Manim scripts (methods of axes and points on graphs)."""

from __future__ import annotations

import importlib.util
import math
import shutil

import pytest

from manim_studio.codegen import generate_script
from manim_studio.importer import import_script
from manim_studio.model.types import ObjectKind
from manim_studio.model.validation import has_errors, validate_scene

HAS_MANIM = importlib.util.find_spec("manim") is not None

SCRIPT = """
from manim import *


class Analysis(Scene):
    def construct(self):
        ax = Axes(x_range=[-3, 3, 1], y_range=[-3, 3, 1], x_length=6, y_length=6)
        f = ax.plot(lambda x: x**2 - 1, x_range=[-2.5, 2.5], color=YELLOW)
        df = ax.plot_derivative_graph(f, color=GREEN)
        F = ax.plot_antiderivative_graph(f, y_intercept=1, color=RED)
        area = ax.get_area(f, x_range=(0, 1.5), color=BLUE, opacity=0.4)
        between = ax.get_area(f, x_range=[-1, 1], bounded_graph=df)
        rects = ax.get_riemann_rectangles(f, x_range=[-2, 0], dx=0.5, input_sample_type="right", color=BLUE, fill_opacity=0.6)
        secant = ax.get_secant_slope_group(1, f, dx=0.5, secant_line_color=RED)
        label = ax.get_graph_label(f, label="x^2 - 1", x_val=2, direction=UR)
        dot = Dot(ax.i2gp(1.5, f), color=RED)
        curve = ax.plot_parametric_curve(lambda t: np.array([np.cos(t), np.sin(2 * t), 0]), t_range=[0, TAU])
        rose = ax.plot_polar_graph(lambda theta: 2 * np.sin(3 * theta), theta_range=[0, PI])
        self.add(ax, f)
        self.play(Create(df), Create(F))
        self.play(FadeIn(area), FadeIn(rects), Create(secant), Write(label), FadeIn(dot), Create(curve), Create(rose), FadeIn(between))
"""


def imported():
    report = import_script(SCRIPT)
    return report, report.project.scenes[0]


def test_graph_tools_are_imported() -> None:
    report, scene = imported()
    assert not report.skipped, report.skipped
    by_name = {obj.name: obj for obj in scene.objects}
    f = by_name["f"]
    assert by_name["df"].params["curve"] == "derivative" and by_name["df"].params["derive_from"] == f.id
    big_f = by_name["F"]
    assert big_f.params["curve"] == "antiderivative" and big_f.params["integral_from"] == 0.0 and big_f.params["integral_constant"] == 1.0
    assert (big_f.params["x_min"], big_f.params["x_max"]) == (-2.5, 2.5)  # like the graph it comes from
    area = by_name["area"]
    assert area.kind == ObjectKind.GRAPH_AREA and (area.params["x_min"], area.params["x_max"]) == (0.0, 1.5) and area.fill_opacity == 0.4
    between = by_name["between"]
    assert between.params["mode"] == "between" and between.params["other_graph_id"] == by_name["df"].id
    rects = by_name["rects"]
    assert rects.kind == ObjectKind.RIEMANN and rects.params["dx"] == 0.5 and rects.params["sample"] == "right" and rects.fill_opacity == 0.6
    secant = by_name["secant"]
    assert secant.kind == ObjectKind.SECANT and secant.params["x_value"] == 1.0 and secant.params["h"] == 0.5
    label = by_name["label"]
    assert label.kind == ObjectKind.GRAPH_LABEL and label.params["text"] == "x^2 - 1" and label.params["use_latex"] and label.params["x_value"] == 2.0
    dot = by_name["dot"]
    assert dot.kind == ObjectKind.GRAPH_POINT and dot.params["graph_id"] == f.id and dot.params["x_value"] == 1.5
    curve = by_name["curve"]
    assert curve.params["curve"] == "parametric" and (curve.params["x_expression"], curve.params["y_expression"]) == ("cos(t)", "sin(2 * t)")
    assert curve.params["t_max"] == pytest.approx(math.tau)
    rose = by_name["rose"]
    assert rose.params["curve"] == "polar" and rose.params["r_expression"] == "2 * sin(3 * t)" and rose.params["t_max"] == pytest.approx(math.pi)


def test_imported_scene_is_valid_and_generates() -> None:
    _report, scene = imported()
    assert not has_errors(validate_scene(scene)), [issue.code for issue in validate_scene(scene)]
    from manim_studio.model.entities import Project

    code = generate_script(Project(scenes=[scene]))
    assert "get_riemann_rectangles(" in code and "studio_integral(" in code


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
@pytest.mark.skipif(shutil.which("latex") is None or shutil.which("dvisvgm") is None, reason="LaTeX is not installed (the graph label is MathTex)")
def test_imported_scene_renders(tmp_path) -> None:
    from manim_studio.model.entities import Project
    from tests.test_manim_integration import run_manim

    _report, scene = imported()
    result = run_manim(tmp_path, generate_script(Project(scenes=[scene])), "Analysis", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
