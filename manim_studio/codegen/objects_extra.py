"""Code generation for the additional object kinds (lines, shapes, text, data)."""

from __future__ import annotations

from typing import Callable

from manim_studio.codegen.formatting import call
from manim_studio.codegen.literals import (
    fmt_float,
    fmt_int,
    py_bool,
    py_color,
    py_degrees,
    py_point,
    py_range,
    py_str,
)
from manim_studio.model.entities import SceneObject
from manim_studio.model.types import ObjectKind

Kwargs = list[tuple[str, str]]

DIRECTIONS = {"down": "DOWN", "up": "UP", "left": "LEFT", "right": "RIGHT"}
NUMBER_LABEL_SIZE = 24.0


def _f(obj: SceneObject, key: str, default: float = 0.0) -> float:
    return float(obj.params.get(key, default))


def shape_style(obj: SceneObject) -> Kwargs:
    """Stroke and fill keyword arguments of a filled shape."""
    return [
        ("stroke_color", py_color(obj.stroke_color)),
        ("stroke_width", fmt_float(obj.stroke_width)),
        ("stroke_opacity", fmt_float(obj.stroke_opacity)),
        ("fill_color", py_color(obj.fill_color)),
        ("fill_opacity", fmt_float(obj.fill_opacity)),
    ]


def line_style(obj: SceneObject) -> Kwargs:
    """Keyword arguments of a line-like object."""
    return [
        ("color", py_color(obj.stroke_color)),
        ("stroke_width", fmt_float(obj.stroke_width)),
        ("stroke_opacity", fmt_float(obj.stroke_opacity)),
    ]


def _endpoints(obj: SceneObject) -> list[str]:
    half = _f(obj, "length", 3.0) / 2
    return [py_point(-half, 0.0), py_point(half, 0.0)]


def number_line(obj: SceneObject) -> list[str]:
    kwargs = [
        ("x_range", py_range(_f(obj, "x_min", -5.0), _f(obj, "x_max", 5.0), _f(obj, "x_step", 1.0))),
        ("length", fmt_float(_f(obj, "length", 10.0))),
        ("include_tip", py_bool(obj.params.get("tips", False))),
        ("include_numbers", py_bool(obj.params.get("show_numbers", True))),
    ]
    if obj.params.get("show_numbers", True):
        kwargs += [("label_constructor", "Text"), ("font_size", fmt_float(NUMBER_LABEL_SIZE))]
    kwargs += [("color", py_color(obj.stroke_color)), ("stroke_width", fmt_float(obj.stroke_width))]
    return call("NumberLine", [], kwargs, 2)


def vector(obj: SceneObject) -> list[str]:
    return call("Vector", [py_point(_f(obj, "length", 2.0), 0.0)], line_style(obj), 2)


def double_arrow(obj: SceneObject) -> list[str]:
    return call("DoubleArrow", _endpoints(obj), [("buff", "0")] + line_style(obj), 2)


def dashed_line(obj: SceneObject) -> list[str]:
    kwargs = [("dash_length", fmt_float(_f(obj, "dash_length", 0.15))), ("dashed_ratio", fmt_float(_f(obj, "dashed_ratio", 0.5)))]
    return call("DashedLine", _endpoints(obj), kwargs + line_style(obj), 2)


def polygon(obj: SceneObject) -> list[str]:
    points = [py_point(float(x), float(y)) for x, y in obj.params.get("points", [])]
    return call("Polygon", points, shape_style(obj), 2)


def regular_polygon(obj: SceneObject) -> list[str]:
    kwargs = [("n", fmt_int(int(obj.params.get("n", 6)))), ("radius", fmt_float(_f(obj, "radius", 1.0)))]
    return call("RegularPolygon", [], kwargs + shape_style(obj), 2)


def star(obj: SceneObject) -> list[str]:
    kwargs = [
        ("n", fmt_int(int(obj.params.get("n", 5)))),
        ("outer_radius", fmt_float(_f(obj, "outer_radius", 1.2))),
        ("inner_radius", fmt_float(_f(obj, "inner_radius", 0.5))),
    ]
    return call("Star", [], kwargs + shape_style(obj), 2)


def _angles(obj: SceneObject) -> Kwargs:
    return [
        ("start_angle", py_degrees(_f(obj, "start_angle", 0.0))),
        ("angle", py_degrees(_f(obj, "angle", 90.0))),
    ]


def arc(obj: SceneObject) -> list[str]:
    return call("Arc", [], [("radius", fmt_float(_f(obj, "radius", 1.5)))] + _angles(obj) + line_style(obj), 2)


def sector(obj: SceneObject) -> list[str]:
    return call("Sector", [], [("radius", fmt_float(_f(obj, "radius", 1.5)))] + _angles(obj) + shape_style(obj), 2)


def annulus(obj: SceneObject) -> list[str]:
    kwargs = [("inner_radius", fmt_float(_f(obj, "inner_radius", 0.7))), ("outer_radius", fmt_float(_f(obj, "outer_radius", 1.3)))]
    return call("Annulus", [], kwargs + shape_style(obj), 2)


def decimal_number(obj: SceneObject) -> list[str]:
    kwargs = [
        ("num_decimal_places", fmt_int(int(obj.params.get("decimals", 2)))),
        ("mob_class", "Text"),
        ("font_size", fmt_float(_f(obj, "font_size", 48.0))),
        ("color", py_color(obj.fill_color)),
    ]
    if obj.params.get("show_sign"):
        kwargs.append(("include_sign", "True"))
    unit = str(obj.params.get("unit", "")).strip()
    if unit:
        kwargs.append(("unit", py_str(unit)))
    return call("DecimalNumber", [fmt_float(_f(obj, "value", 0.0))], kwargs, 2)


def _rows(obj: SceneObject) -> list[list[str]]:
    rows = [[str(cell) for cell in row] for row in obj.params.get("rows", []) if isinstance(row, list)]
    width = max((len(row) for row in rows), default=0)
    return [row + [""] * (width - len(row)) for row in rows]


def _rows_literal(rows: list[list[str]]) -> str:
    return "[" + ", ".join("[" + ", ".join(py_str(cell) for cell in row) + "]" for row in rows) + "]"


def table(obj: SceneObject) -> list[str]:
    element = f'{{"font_size": {fmt_float(_f(obj, "font_size", 32.0))}, "color": {py_color(obj.fill_color)}}}'
    lines = f'{{"stroke_color": {py_color(obj.stroke_color)}, "stroke_width": {fmt_float(obj.stroke_width)}}}'
    kwargs = [
        ("include_outer_lines", py_bool(obj.params.get("outer_lines", True))),
        ("h_buff", fmt_float(_f(obj, "h_buff", 1.0))),
        ("v_buff", fmt_float(_f(obj, "v_buff", 0.5))),
        ("element_to_mobject_config", element),
        ("line_config", lines),
    ]
    return call("Table", [_rows_literal(_rows(obj))], kwargs, 2)


def matrix(obj: SceneObject) -> list[str]:
    kwargs = [("h_buff", fmt_float(_f(obj, "h_buff", 1.3))), ("v_buff", fmt_float(_f(obj, "v_buff", 0.8)))]
    return call("Matrix", [_rows_literal(_rows(obj))], kwargs, 2)


def code_block(obj: SceneObject) -> list[str]:
    kwargs = [
        ("code_string", py_str(str(obj.params.get("code", "")))),
        ("language", py_str(str(obj.params.get("language", "python")))),
        ("add_line_numbers", py_bool(obj.params.get("line_numbers", True))),
        ("background", py_str(str(obj.params.get("background", "rectangle")))),
        ("paragraph_config", f'{{"font_size": {fmt_float(_f(obj, "font_size", 24.0))}}}'),
    ]
    return call("Code", [], kwargs, 2)


def tex(obj: SceneObject) -> list[str]:
    kwargs = [("font_size", fmt_float(_f(obj, "font_size", 48.0))), ("color", py_color(obj.fill_color))]
    return call("Tex", [py_str(str(obj.params.get("tex", "")), prefer_raw=True)], kwargs, 2)


def markup_text(obj: SceneObject) -> list[str]:
    kwargs = [
        ("font_size", fmt_float(_f(obj, "font_size", 48.0))),
        ("color", py_color(obj.fill_color)),
        ("fill_opacity", fmt_float(obj.fill_opacity)),
    ]
    font = str(obj.params.get("font", "")).strip()
    if font:
        kwargs.append(("font", py_str(font)))
    return call("MarkupText", [py_str(str(obj.params.get("markup", "")))], kwargs, 2)


def text(obj: SceneObject) -> list[str]:
    """``Text`` (or ``Paragraph`` for aligned multi-line text) with all options."""
    content = str(obj.params.get("text", ""))
    kwargs: Kwargs = [
        ("font_size", fmt_float(_f(obj, "font_size", 48.0))),
        ("color", py_color(obj.fill_color)),
        ("fill_opacity", fmt_float(obj.fill_opacity)),
    ]
    font = str(obj.params.get("font", "")).strip()
    if font:
        kwargs.append(("font", py_str(font)))
    if obj.params.get("bold"):
        kwargs.append(("weight", "BOLD"))
    if obj.params.get("italic"):
        kwargs.append(("slant", "ITALIC"))
    spacing = _f(obj, "line_spacing", 0.0)
    if spacing > 0:
        kwargs.append(("line_spacing", fmt_float(spacing)))
    words = [(str(word), str(color)) for word, color in obj.params.get("colored_words", []) or [] if str(word)]
    if words:
        kwargs.append(("t2c", "{" + ", ".join(f"{py_str(word)}: {py_color(color)}" for word, color in words) + "}"))
    lines = content.split("\n")
    alignment = str(obj.params.get("alignment", "left"))
    if len(lines) > 1 and alignment in ("center", "right"):
        return call("Paragraph", [py_str(line) for line in lines], [("alignment", py_str(alignment))] + kwargs, 2)
    return call("Text", [py_str(content)], kwargs, 2)


def brace_code(obj: SceneObject, variable: str, target_variable: str | None) -> list[str]:
    """A brace (around a target or a free width) plus an optional text label."""
    direction = DIRECTIONS.get(str(obj.params.get("direction", "down")), "DOWN")
    color = py_color(obj.fill_color)
    if target_variable is not None:
        subject = target_variable
    else:
        half = _f(obj, "width", 3.0) / 2
        if direction in ("LEFT", "RIGHT"):
            subject = f"Line({py_point(0.0, -half)}, {py_point(0.0, half)})"
        else:
            subject = f"Line({py_point(-half, 0.0)}, {py_point(half, 0.0)})"
    brace = f"Brace({subject}, direction={direction}, buff={fmt_float(_f(obj, 'buff', 0.2))}, color={color})"
    lines = [f"{variable} = VGroup({brace})"]
    label = str(obj.params.get("label", "")).strip()
    if label:
        size = fmt_float(_f(obj, "label_size", 36.0))
        lines.append(f"{variable}.add(Text({py_str(label)}, font_size={size}, color={color}).next_to({variable}[0], {direction}, buff=0.15))")
    if float(obj.fill_opacity) != 1.0:
        lines.append(f"{variable}.set_fill(opacity={fmt_float(obj.fill_opacity)})")
    return lines


def highlight_code(obj: SceneObject, variable: str, target_variable: str) -> list[str]:
    """Frame, background, underline or cross that is redrawn around its target in every frame."""
    style = obj.params.get("style", "frame")
    buff = fmt_float(_f(obj, "buff", 0.15))
    stroke = f"stroke_width={fmt_float(obj.stroke_width)}, stroke_opacity={fmt_float(obj.stroke_opacity)}"
    if style == "background":
        shape = f"BackgroundRectangle({target_variable}, color={py_color(obj.fill_color)}, fill_opacity={fmt_float(_f(obj, 'opacity', 0.75))}, buff={buff})"
    elif style == "underline":
        shape = f"Underline({target_variable}, buff={buff}, color={py_color(obj.stroke_color)}, {stroke})"
    elif style == "cross":
        shape = f"Cross({target_variable}, stroke_color={py_color(obj.stroke_color)}, {stroke})"
    else:
        shape = (
            f"SurroundingRectangle({target_variable}, buff={buff}, corner_radius={fmt_float(_f(obj, 'corner_radius', 0.0))}, "
            f"color={py_color(obj.stroke_color)}, {stroke}, fill_color={py_color(obj.fill_color)}, fill_opacity={fmt_float(obj.fill_opacity)})"
        )
    return [f"{variable} = always_redraw(lambda: {shape})"]


STUDIO_ANGLE = "studio_angle"
STUDIO_ANGLE_SOURCE = '''def studio_angle(line_1, line_2, radius=0.5, quadrant=(1, 1), other_angle=False, right=False, label="", decimals=-1, font_size=32, **style):
    """Angle mark between two lines with an optional label (used with always_redraw)."""
    try:
        if right:
            mark = RightAngle(line_1, line_2, length=radius, quadrant=quadrant, **style)
        else:
            mark = Angle(line_1, line_2, radius=radius, quadrant=quadrant, other_angle=other_angle, **style)
        value = Angle(line_1, line_2, quadrant=quadrant, other_angle=other_angle).get_value(degrees=True)
        spot = Angle(line_1, line_2, radius=radius + 0.3, quadrant=quadrant, other_angle=other_angle)
    except ValueError:  # the lines do not meet
        return VGroup()
    group = VGroup(mark)
    if decimals >= 0:
        label = f"{abs(value):.{decimals}f}°"
    if label and spot.has_points():
        group.add(Text(label, font_size=font_size, color=mark.get_color()).move_to(spot.point_from_proportion(0.5)))
    return group'''


def angle_code(obj: SceneObject, variable: str, first: str, second: str) -> list[str]:
    """An angle mark that is recomputed from its two lines in every frame."""
    quadrant = f"({-1 if obj.params.get('flip_first') else 1}, {-1 if obj.params.get('flip_second') else 1})"
    arguments = [first, second, f"radius={fmt_float(_f(obj, 'radius', 0.6))}", f"quadrant={quadrant}"]
    if obj.params.get("reflex"):
        arguments.append("other_angle=True")
    if obj.params.get("right_angle"):
        arguments.append("right=True")
    label = obj.params.get("label", "none")
    if label == "symbol" and str(obj.params.get("symbol", "")).strip():
        arguments.append(f"label={py_str(str(obj.params.get('symbol', '')).strip())}")
    elif label == "degrees":
        arguments.append(f"decimals={max(0, int(obj.params.get('decimals', 0)))}")
    if label != "none":
        arguments.append(f"font_size={fmt_float(_f(obj, 'label_size', 32.0))}")
    arguments += [f"color={py_color(obj.stroke_color)}", f"stroke_width={fmt_float(obj.stroke_width)}", f"stroke_opacity={fmt_float(obj.stroke_opacity)}"]
    return [f"{variable} = always_redraw(lambda: {STUDIO_ANGLE}({', '.join(arguments)}))"]


def group_code(variable: str, member_variables: list[str]) -> list[str]:
    """``VGroup`` of existing objects."""
    return [f"{variable} = VGroup({', '.join(member_variables)})"]


EXTRA_CONSTRUCTORS: dict[ObjectKind, Callable[[SceneObject], list[str]]] = {
    ObjectKind.NUMBER_LINE: number_line,
    ObjectKind.VECTOR: vector,
    ObjectKind.DOUBLE_ARROW: double_arrow,
    ObjectKind.DASHED_LINE: dashed_line,
    ObjectKind.POLYGON: polygon,
    ObjectKind.REGULAR_POLYGON: regular_polygon,
    ObjectKind.STAR: star,
    ObjectKind.ARC: arc,
    ObjectKind.SECTOR: sector,
    ObjectKind.ANNULUS: annulus,
    ObjectKind.DECIMAL_NUMBER: decimal_number,
    ObjectKind.TABLE: table,
    ObjectKind.MATRIX: matrix,
    ObjectKind.CODE: code_block,
    ObjectKind.TEX: tex,
    ObjectKind.MARKUP_TEXT: markup_text,
}
