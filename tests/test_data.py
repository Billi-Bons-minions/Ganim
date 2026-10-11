"""Data points, regression and bar charts."""

from __future__ import annotations

import pytest

from manim_studio.codegen import CodegenOptions, generate_script
from manim_studio.model import graphs
from manim_studio.model.data import bar_range, color_gradient, data_points, nice_step, parse_table_text, regression
from manim_studio.model.entities import Scene
from manim_studio.model.types import ObjectKind
from manim_studio.model.validation import validate_scene
from tests.helpers import make_object, make_project


def test_regressions_recover_exact_curves() -> None:
    line = regression([(0, 1), (1, 3), (2, 5)], "linear")
    assert line.coefficients == pytest.approx((2.0, 1.0)) and line.r_squared == pytest.approx(1.0)
    parabola = regression([(x, 2 * x * x - x + 3) for x in range(-2, 3)], "quadratic")
    assert parabola.coefficients == pytest.approx((2.0, -1.0, 3.0))
    growth = regression([(x, 3 * 2.718281828 ** (0.5 * x)) for x in range(4)], "exponential")
    assert growth.coefficients == pytest.approx((3.0, 0.5), rel=1e-6)
    assert regression([(0, 1)], "linear") is None
    assert regression([(0, -1), (1, 2)], "exponential") is None
    assert line.text() == "y = 2x + 1"


def test_csv_parsing_handles_headers_semicolons_and_decimal_commas() -> None:
    assert parse_table_text("x;y\n1;2,5\n2;3,5\n") == [[1.0, 2.5], [2.0, 3.5]]
    assert parse_table_text("t,s\n0,0\n1,4.9\n") == [[0.0, 0.0], [1.0, 4.9]]
    assert parse_table_text("1\t2\n3\t4") == [[1.0, 2.0], [3.0, 4.0]]


def test_bar_range_and_colors() -> None:
    chart = make_object(ObjectKind.BAR_CHART, "B", "b", bars=[["A", "3"], ["B", "5.5"], ["C", "-2"]])
    assert bar_range(chart) == (-2.0, 6.0, 2.0)
    chart.params["y_max"] = 10.0
    assert bar_range(chart)[1] == 10.0
    assert nice_step(7.5) == 2.0 and nice_step(0.9) == 0.2
    assert color_gradient(["#000000", "#FFFFFF"], 3) == ["#000000", "#808080", "#FFFFFF"]
    assert color_gradient(["#FF0000"], 2) == ["#FF0000", "#FF0000"]


def test_data_plot_model_and_code() -> None:
    axes = make_object(ObjectKind.AXES, "Achsen", "ax")
    plot = make_object(ObjectKind.DATA_PLOT, "Messwerte", "d", axes_id="ax", data=[[0, 1], [1, 3], [2, 5], ["x", 1]], regression="linear", display="both")
    chart = make_object(ObjectKind.BAR_CHART, "Balken", "b", 3.0, 0.0, show_values=True)
    scene = Scene(id="s", name="Daten", objects=[axes, plot, chart])
    assert data_points(plot) == [(0.0, 1.0), (1.0, 3.0), (2.0, 5.0)]
    assert graphs.is_bound(scene, plot) and not graphs.is_bound(scene, chart)
    code = generate_script(make_project(scene), CodegenOptions())
    assert "achsen.plot_line_graph(" in code and "lambda x: 2.0 * x + 1.0" in code
    assert "balken = BarChart(" in code and '"label_constructor": Text' in code
    assert "balken.add(balken.get_bar_labels(font_size=24.0, label_constructor=Text))" in code
    assert code.index("balken.add(") < code.index("balken.move_to(")


def test_data_validation() -> None:
    lonely = make_object(ObjectKind.DATA_PLOT, "D", "d", data=[])
    empty_chart = make_object(ObjectKind.BAR_CHART, "B", "b", bars=[["A", "x"]])
    codes = {issue.code for issue in validate_scene(Scene(id="s", name="S", objects=[lonely, empty_chart]))}
    assert {"data_needs_axes", "data_empty"} <= codes
