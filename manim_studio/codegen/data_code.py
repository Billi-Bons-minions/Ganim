"""Code generation for data plots and bar charts."""

from __future__ import annotations

from manim_studio.codegen.errors import CodegenError
from manim_studio.codegen.formatting import INDENT, call
from manim_studio.codegen.literals import fmt_float, fmt_number, py_bool, py_color, py_range, py_str
from manim_studio.model import graphs
from manim_studio.model.data import bar_colors, bar_range, bar_values, data_points
from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.geometry import param_float

BAR_LABEL_SIZE = 24.0


def _list(values: list[str]) -> str:
    return "[" + ", ".join(values) + "]"


def data_plot_code(scene: Scene, obj: SceneObject, names: dict[str, str]) -> list[str]:
    """Dots and/or a line graph on axes, plus an optional regression curve."""
    axes = graphs.data_axes(scene, obj)
    points = data_points(obj)
    if axes is None or axes.id not in names:
        raise CodegenError("data_needs_axes", obj.name)
    if not points:
        raise CodegenError("data_empty", obj.name)
    axes_variable = names[axes.id]
    style = obj.params.get("display", "dots")
    radius = fmt_float(param_float(obj.params, "radius", 0.08))
    fill = py_color(obj.fill_color)
    stroke = py_color(obj.stroke_color)
    parts: list[str] = []
    if style in ("line", "both"):
        xs = _list([fmt_number(x) for x, _y in points])
        ys = _list([fmt_number(y) for _x, y in points])
        kwargs = [
            ("line_color", stroke),
            ("add_vertex_dots", py_bool(style == "both")),
            ("vertex_dot_radius", radius),
            ("vertex_dot_style", f'{{"color": {fill}}}'),
            ("stroke_width", fmt_float(obj.stroke_width)),
        ]
        parts.append("\n".join(call(f"{axes_variable}.plot_line_graph", [xs, ys], kwargs, 2)))
    else:
        pairs = _list([f"({fmt_number(x)}, {fmt_number(y)})" for x, y in points])
        parts.append(f"*[Dot({axes_variable}.c2p(x, y), radius={radius}, color={fill}) for x, y in {pairs}]")
    fit = graphs.data_fit(obj)
    if fit is not None:
        low, high = min(x for x, _y in points), max(x for x, _y in points)
        function = f"lambda x: {fit.code(fmt_float)}"
        kwargs = [("x_range", py_range(low, high)), ("color", stroke), ("stroke_width", fmt_float(obj.stroke_width))]
        parts.append("\n".join(call(f"{axes_variable}.plot", [function], kwargs, 2)))
    lines = ["VGroup("]
    for part in parts:
        part_lines = part.split("\n")
        lines += [f"{INDENT}{line}" for line in part_lines[:-1]] + [f"{INDENT}{part_lines[-1]},"]
    return lines + [")"]


def bar_chart_code(obj: SceneObject) -> list[str]:
    """Manim's ``BarChart`` with text labels (no LaTeX needed)."""
    bars = bar_values(obj)
    if not bars:
        raise CodegenError("data_empty", obj.name)
    y_min, y_max, y_step = bar_range(obj)
    kwargs = [
        ("values", _list([fmt_number(value) for _name, value in bars])),
        ("bar_names", _list([py_str(name) for name, _value in bars])),
        ("y_range", py_range(y_min, y_max, y_step)),
        ("x_length", fmt_float(param_float(obj.params, "x_length", 6.0))),
        ("y_length", fmt_float(param_float(obj.params, "y_length", 4.0))),
        ("bar_width", fmt_float(param_float(obj.params, "bar_width", 0.6))),
        ("bar_colors", _list([py_color(color) for color in bar_colors(obj)])),
        ("bar_fill_opacity", fmt_float(obj.fill_opacity)),
        ("bar_stroke_width", fmt_float(obj.stroke_width)),
        ("x_axis_config", f'{{"label_constructor": Text, "font_size": {fmt_float(BAR_LABEL_SIZE)}}}'),
        ("y_axis_config", '{"label_constructor": Text}'),
    ]
    return call("BarChart", [], kwargs, 2)


def bar_label_lines(obj: SceneObject, variable: str) -> list[str]:
    """Value labels above the bars."""
    if not obj.params.get("show_values"):
        return []
    return [f"{variable}.add({variable}.get_bar_labels(font_size={fmt_float(BAR_LABEL_SIZE)}, label_constructor=Text))"]
