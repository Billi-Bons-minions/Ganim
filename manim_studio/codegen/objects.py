"""Code generation for scene objects."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from manim_studio.codegen.errors import CodegenError
from manim_studio.codegen.formatting import assign, call
from manim_studio.codegen.literals import (
    LiteralError,
    fmt_float,
    fmt_int,
    py_bool,
    py_color,
    py_degrees,
    py_point,
    py_range,
    py_str,
)
from manim_studio.codegen.objects_extra import (
    EXTRA_CONSTRUCTORS,
    brace_code,
    group_code,
)
from manim_studio.codegen.objects_extra import text as extra_text
from manim_studio.model.assets import resolve_asset_path
from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.expression import ExpressionError, parse_expression
from manim_studio.model.geometry import bound_axes
from manim_studio.model.schema import is_vector_image_path
from manim_studio.model.types import ObjectKind

Kwargs = list[tuple[str, str]]

AXIS_LABEL_FONT_SIZE = 24.0


def _p(obj: SceneObject, key: str) -> float:
    return float(obj.params[key])


def _shape_style(obj: SceneObject) -> Kwargs:
    return [
        ("stroke_color", py_color(obj.stroke_color)),
        ("stroke_width", fmt_float(obj.stroke_width)),
        ("stroke_opacity", fmt_float(obj.stroke_opacity)),
        ("fill_color", py_color(obj.fill_color)),
        ("fill_opacity", fmt_float(obj.fill_opacity)),
    ]


def _line_style(obj: SceneObject) -> Kwargs:
    return [
        ("color", py_color(obj.stroke_color)),
        ("stroke_width", fmt_float(obj.stroke_width)),
        ("stroke_opacity", fmt_float(obj.stroke_opacity)),
    ]


def _horizontal_points(length: float) -> list[str]:
    half = length / 2
    return [py_point(-half, 0.0), py_point(half, 0.0)]


def _circle(obj: SceneObject) -> list[str]:
    return call("Circle", [], [("radius", fmt_float(_p(obj, "radius")))] + _shape_style(obj), 2)


def _square(obj: SceneObject) -> list[str]:
    return call("Square", [], [("side_length", fmt_float(_p(obj, "side_length")))] + _shape_style(obj), 2)


def _rectangle(obj: SceneObject) -> list[str]:
    size = [("width", fmt_float(_p(obj, "width"))), ("height", fmt_float(_p(obj, "height")))]
    return call("Rectangle", [], size + _shape_style(obj), 2)


def _triangle(obj: SceneObject) -> list[str]:
    return call("Triangle", [], [("radius", fmt_float(_p(obj, "radius")))] + _shape_style(obj), 2)


def _ellipse(obj: SceneObject) -> list[str]:
    size = [("width", fmt_float(_p(obj, "width"))), ("height", fmt_float(_p(obj, "height")))]
    return call("Ellipse", [], size + _shape_style(obj), 2)


def _line(obj: SceneObject) -> list[str]:
    return call("Line", _horizontal_points(_p(obj, "length")), _line_style(obj), 2)


def _arrow(obj: SceneObject) -> list[str]:
    return call("Arrow", _horizontal_points(_p(obj, "length")), [("buff", "0")] + _line_style(obj), 2)


def _dot(obj: SceneObject) -> list[str]:
    kwargs = [
        ("radius", fmt_float(_p(obj, "radius"))),
        ("color", py_color(obj.fill_color)),
        ("fill_opacity", fmt_float(obj.fill_opacity)),
    ]
    return call("Dot", [], kwargs, 2)


def _text(obj: SceneObject) -> list[str]:
    kwargs = [
        ("font_size", fmt_float(_p(obj, "font_size"))),
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
    return call("Text", [py_str(str(obj.params.get("text", "")))], kwargs, 2)


def _math_tex(obj: SceneObject) -> list[str]:
    latex = str(obj.params.get("latex", ""))
    kwargs = [("font_size", fmt_float(_p(obj, "font_size"))), ("color", py_color(obj.fill_color))]
    return call("MathTex", [py_str(latex, prefer_raw=True)], kwargs, 2)


def _axis_ranges(obj: SceneObject) -> Kwargs:
    return [
        ("x_range", py_range(_p(obj, "x_min"), _p(obj, "x_max"), _p(obj, "x_step"))),
        ("y_range", py_range(_p(obj, "y_min"), _p(obj, "y_max"), _p(obj, "y_step"))),
        ("x_length", fmt_float(_p(obj, "x_length"))),
        ("y_length", fmt_float(_p(obj, "y_length"))),
    ]


def _axes(obj: SceneObject) -> list[str]:
    config = [f'"color": {py_color(obj.stroke_color)}', f'"stroke_width": {fmt_float(obj.stroke_width)}']
    if obj.params.get("show_numbers"):
        config += ['"include_numbers": True', '"label_constructor": Text', f'"font_size": {fmt_float(AXIS_LABEL_FONT_SIZE)}']
    kwargs = _axis_ranges(obj) + [
        ("tips", py_bool(obj.params.get("tips", True))),
        ("axis_config", "{" + ", ".join(config) + "}"),
    ]
    return call("Axes", [], kwargs, 2)


def _number_plane(obj: SceneObject) -> list[str]:
    style = (
        f'{{"stroke_color": {py_color(obj.stroke_color)}, '
        f'"stroke_width": {fmt_float(obj.stroke_width)}, '
        f'"stroke_opacity": {fmt_float(obj.stroke_opacity)}}}'
    )
    return call("NumberPlane", [], _axis_ranges(obj) + [("background_line_style", style)], 2)


def function_lambda(obj: SceneObject) -> str:
    """Return the ``lambda x: ...`` code of a function graph."""
    try:
        expression = parse_expression(str(obj.params.get("expression", "")))
    except ExpressionError as error:
        raise CodegenError("expression_invalid", f"{obj.name}: {error.code} {error.detail}".strip()) from None
    return f"lambda x: {expression.to_numpy()}"


def _graph_kwargs(obj: SceneObject) -> Kwargs:
    return [("x_range", py_range(_p(obj, "x_min"), _p(obj, "x_max")))] + _line_style(obj)


def _function_graph(obj: SceneObject) -> list[str]:
    return call("FunctionGraph", [function_lambda(obj)], _graph_kwargs(obj), 2)


def bound_graph_code(obj: SceneObject, axes_variable: str) -> list[str]:
    """Return ``axes.plot(...)`` for a graph attached to a coordinate system."""
    return call(f"{axes_variable}.plot", [function_lambda(obj)], _graph_kwargs(obj), 2)


def _image_path(obj: SceneObject, base_dir: str | Path | None) -> str:
    path = str(obj.params.get("path", ""))
    if not path:
        raise CodegenError("image_missing_path", obj.name)
    return resolve_asset_path(path, base_dir).as_posix()


def image_code(obj: SceneObject, base_dir: str | Path | None) -> list[str]:
    """Return the constructor of an image object (SVG or raster)."""
    path = _image_path(obj, base_dir)
    height = fmt_float(_p(obj, "height"))
    if is_vector_image_path(path):
        return call("SVGMobject", [py_str(path, prefer_raw=True)], [("height", height)], 2)
    return call("ImageMobject", [py_str(path, prefer_raw=True)], [], 2)


_CONSTRUCTORS: dict[ObjectKind, Callable[[SceneObject], list[str]]] = {
    **EXTRA_CONSTRUCTORS,
    ObjectKind.CIRCLE: _circle,
    ObjectKind.SQUARE: _square,
    ObjectKind.RECTANGLE: _rectangle,
    ObjectKind.TRIANGLE: _triangle,
    ObjectKind.ELLIPSE: _ellipse,
    ObjectKind.LINE: _line,
    ObjectKind.ARROW: _arrow,
    ObjectKind.DOT: _dot,
    ObjectKind.TEXT: extra_text,
    ObjectKind.MATH_TEX: _math_tex,
    ObjectKind.AXES: _axes,
    ObjectKind.NUMBER_PLANE: _number_plane,
    ObjectKind.FUNCTION_GRAPH: _function_graph,
}


def _placement(obj: SceneObject, variable: str) -> list[str]:
    lines = [f"{variable}.move_to({py_point(obj.x, obj.y)})"]
    if round(obj.rotation, 6) != 0:
        lines.append(f"{variable}.rotate({py_degrees(obj.rotation)})")
    return lines


def _post_style(obj: SceneObject, variable: str) -> list[str]:
    lines: list[str] = []
    if obj.kind == ObjectKind.MATRIX:
        lines.append(f"{variable}.set_color({py_color(obj.fill_color)})")
    if obj.kind in (ObjectKind.TEX, ObjectKind.MATRIX, ObjectKind.DECIMAL_NUMBER) and float(obj.fill_opacity) != 1.0:
        lines.append(f"{variable}.set_fill(opacity={fmt_float(obj.fill_opacity)})")
    if obj.kind == ObjectKind.MATH_TEX and float(obj.fill_opacity) != 1.0:
        lines.append(f"{variable}.set_fill(opacity={fmt_float(obj.fill_opacity)})")
    if obj.kind == ObjectKind.IMAGE:
        if not is_vector_image_path(str(obj.params.get("path", ""))):
            lines.append(f"{variable}.height = {fmt_float(_p(obj, 'height'))}")
        if float(obj.params.get("opacity", 1.0)) != 1.0:
            lines.append(f"{variable}.set_opacity({fmt_float(float(obj.params['opacity']))})")
    return lines


def _special_code(scene: Scene, obj: SceneObject, names: dict[str, str]) -> tuple[list[str], bool] | None:
    """Code for objects that depend on others; returns ``(lines, needs_placement)``."""
    variable = names[obj.id]
    if obj.kind == ObjectKind.GROUP:
        member_ids = [m for m in obj.params.get("members", []) if m in names]
        if not member_ids:
            raise CodegenError("group_empty", obj.name)
        return group_code(variable, [names[m] for m in member_ids]), False
    if obj.kind == ObjectKind.BRACE:
        target = obj.params.get("target")
        attached = target in names and target != obj.id
        return brace_code(obj, variable, names[target] if attached else None), not attached
    return None


def object_code(scene: Scene, obj: SceneObject, names: dict[str, str], base_dir: str | Path | None) -> list[str]:
    """Return the lines that create, place and style one object."""
    variable = names[obj.id]
    try:
        special = _special_code(scene, obj, names)
        axes = bound_axes(scene, obj) if obj.kind == ObjectKind.FUNCTION_GRAPH else None
        if special is not None:
            lines, place = special
        elif axes is not None:
            lines, place = assign(variable, bound_graph_code(obj, names[axes.id])), False
        elif obj.kind == ObjectKind.IMAGE:
            lines, place = assign(variable, image_code(obj, base_dir)), True
        else:
            lines, place = assign(variable, _CONSTRUCTORS[obj.kind](obj)), True
        lines += _post_style(obj, variable)
        if place:
            lines += _placement(obj, variable)
    except LiteralError as error:
        raise CodegenError("value_invalid", f"{obj.name}: {error}") from None
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, CodegenError):
            raise
        raise CodegenError("value_invalid", f"{obj.name}: {error}") from None
    if obj.z_index and obj.kind != ObjectKind.GROUP:
        lines.append(f"{variable}.set_z_index({fmt_int(obj.z_index)})")
    return lines


def dependencies(scene: Scene, obj: SceneObject) -> list[str]:
    """Return ids of objects that must be created before ``obj``."""
    result: list[str] = []
    if obj.kind == ObjectKind.FUNCTION_GRAPH and bound_axes(scene, obj) is not None:
        result.append(str(obj.params.get("axes_id")))
    if obj.kind == ObjectKind.BRACE and obj.params.get("target"):
        result.append(str(obj.params.get("target")))
    if obj.kind == ObjectKind.GROUP:
        result += [str(member) for member in obj.params.get("members", [])]
    for key in ("graph_id", "other_graph_id"):
        if obj.params.get(key):
            result.append(str(obj.params.get(key)))
    return [dep for dep in result if scene.object_by_id(dep) is not None and dep != obj.id]


def creation_order(scene: Scene) -> list[SceneObject]:
    """Objects sorted so that every object comes after the ones it depends on."""
    remaining = list(scene.objects)
    done: set[str] = set()
    ordered: list[SceneObject] = []
    while remaining:
        progress = False
        for obj in list(remaining):
            if all(dep in done for dep in dependencies(scene, obj)):
                ordered.append(obj)
                done.add(obj.id)
                remaining.remove(obj)
                progress = True
        if not progress:
            raise CodegenError("dependency_cycle", ", ".join(obj.name for obj in remaining))
    return ordered
