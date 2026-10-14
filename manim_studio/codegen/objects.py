"""Code generation for scene objects."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Callable

from manim_studio.codegen.animations import STUDIO_MAP, STUDIO_PREPARE_MAP
from manim_studio.codegen.data_code import bar_chart_code, bar_label_lines, data_plot_code
from manim_studio.codegen.errors import CodegenError
from manim_studio.codegen.formatting import INDENT, assign, call, indent_lines
from manim_studio.codegen.graph_code import axis_label_lines, graph_object_code, renames
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
    STUDIO_ANGLE,
    STUDIO_OUTLINE,
    STUDIO_TABLE_CELLS,
    STUDIO_UNION,
    angle_code,
    boolean_code,
    brace_code,
    bullet_list_code,
    curve_call,
    group_code,
    highlight_code,
    network_code,
    trace_code,
    uses_union,
    vector_field_code,
)
from manim_studio.codegen.objects_extra import text as extra_text
from manim_studio.codegen.three_d_code import axes_3d_code, curve_3d_code, solid_code, surface_code, vector_3d_code
from manim_studio.model import graphs
from manim_studio.model.angles import ANGLE_LINE_KEYS, angle_lines
from manim_studio.model.assets import resolve_asset_path
from manim_studio.model.attach import ATTACH_BETWEEN, ATTACH_CORNERS, REDRAWN_MODES, attach_mode, connection_targets, corner_targets
from manim_studio.model.dashes import dash_settings, is_dashed
from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.fields import field_expressions
from manim_studio.model.geometry import param_float, polar_grid
from manim_studio.model.gradients import DEFAULT_DIRECTION, SHEEN_CODE, gradient_color, gradient_parts
from manim_studio.model.latex import colored_parts, colorize
from manim_studio.model.schema import is_vector_image_path
from manim_studio.model.tables import table_selection
from manim_studio.model.three_d import THREE_D_KINDS, is_3d
from manim_studio.model.traces import trace_target
from manim_studio.model.types import GRAPH_TOOL_KINDS, INVISIBLE_KINDS, ON_3D_AXES, UNADDED_KINDS, UNGROUPABLE, ObjectKind

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


def _math_tex(obj: SceneObject, scene=None) -> list[str]:
    latex = str(obj.params.get("latex", ""))
    if scene is not None:
        from manim_studio.model.latex_term import shown_latex

        latex = shown_latex(scene, obj) or latex  # "= result" with the start values
    kwargs = [("font_size", fmt_float(_p(obj, "font_size"))), ("color", py_color(obj.fill_color))]
    parts = colored_parts(obj.params)
    if parts:
        latex = colorize(latex, [(text, py_color(color).strip('"')) for text, color in parts])
        kwargs.append(("tex_template", COLOR_TEX))
    return call("MathTex", [py_str(latex, prefer_raw=True)], kwargs, 2)


#: Name and source of the LaTeX template with colors (``\textcolor``).
COLOR_TEX = "COLOR_TEX"
COLOR_TEX_SOURCE = """# LaTeX template that allows colored parts of formulas (\\textcolor)
COLOR_TEX = TexTemplate()
COLOR_TEX.add_to_preamble(r"\\usepackage{xcolor}")"""


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


def _grid_style(obj: SceneObject, opacity: float | None = None) -> str:
    return (
        f'{{"stroke_color": {py_color(obj.stroke_color)}, '
        f'"stroke_width": {fmt_float(obj.stroke_width)}, '
        f'"stroke_opacity": {fmt_float(obj.stroke_opacity if opacity is None else opacity)}}}'
    )


def _number_plane(obj: SceneObject) -> list[str]:
    # with a polar grid the square lines are hidden; the circles and rays come from polar_grid_line()
    opacity = 0.0 if polar_grid(obj) is not None else None
    numbers = obj.params.get("numbers", "none")
    kwargs = _axis_ranges(obj) + [("background_line_style", _grid_style(obj, opacity))]
    if numbers in ("real", "complex"):
        kwargs.append(("axis_config", '{"label_constructor": Text}'))  # numbers without LaTeX
    return call("ComplexPlane" if numbers == "complex" else "NumberPlane", [], kwargs, 2)


STUDIO_COMPLEX_LABELS = "studio_complex_labels"
STUDIO_COMPLEX_LABELS_SOURCE = '''def studio_complex_labels(plane, font_size=24):
    """The imaginary numbers of a complex plane (i, 2i, -i …), written with Text instead of LaTeX."""
    axis = plane.get_y_axis()
    places = axis.decimal_number_config.get("num_decimal_places", 0)
    labels = VGroup()
    for value in axis.get_tick_range():
        if abs(value) < 1e-9:
            continue
        number = f"{abs(value):,.{places}f}"
        text = ("-" if value < 0 else "") + ("i" if number == "1" else number + "i")
        labels.add(Text(text, font_size=font_size).next_to(plane.n2p(complex(0, value)), DR, buff=SMALL_BUFF))
    return labels'''


def plane_number_lines(obj: SceneObject, variable: str, helpers: set[str]) -> list[str]:
    """The numbers of a number plane (added after placing it, so they do not shift it)."""
    numbers = obj.params.get("numbers", "none")
    if numbers == "real":
        return [f"{variable}.add_coordinates()"]
    if numbers == "complex":
        helpers.add(STUDIO_COMPLEX_LABELS)
        return [f"{variable}.add_coordinates(*{variable}.get_x_axis().get_tick_range())", f"{variable}.add({STUDIO_COMPLEX_LABELS}({variable}))"]
    return []


def polar_grid_line(obj: SceneObject, variable: str) -> list[str]:
    """Circles and rays behind a number plane, around its origin and in its scale (``PolarPlane``)."""
    grid = polar_grid(obj)
    if grid is None:
        return []
    polar = call(
        "PolarPlane",
        [],
        [
            ("radius_max", fmt_float(grid.radius_max)),
            ("size", fmt_float(round(2 * grid.radius_max * grid.unit, 6))),
            ("radius_step", fmt_float(grid.radius_step)),
            ("azimuth_step", str(grid.divisions)),
            ("background_line_style", _grid_style(obj)),
            ("radius_config", '{"stroke_width": 0}'),
        ],
        2,
    )
    return [f"{variable}.add_to_back(", *(f"    {line}" for line in polar[:-1]), f"    {polar[-1]}.move_to({variable}.c2p(0, 0))", ")"]


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
}


def _constructor(obj: SceneObject) -> list[str]:
    """The Manim object; a dashed shape is its outline cut into dashes (``DashedVMobject``, without fill)."""
    if not is_dashed(obj):
        return _CONSTRUCTORS[obj.kind](obj)
    base = _CONSTRUCTORS[obj.kind](dataclasses.replace(obj, fill_opacity=0.0))
    if obj.kind == ObjectKind.SECTOR:
        base = [f"{STUDIO_OUTLINE}("] + indent_lines(base, 1) + [")"]
    count, ratio = dash_settings(obj)
    return ["DashedVMobject("] + indent_lines(base[:-1] + [base[-1] + ","], 1) + [f"{INDENT}num_dashes={fmt_int(count)},", f"{INDENT}dashed_ratio={fmt_float(ratio)},", ")"]


def connection_code(obj: SceneObject, start: str, end: str) -> str:
    """A line or arrow from the center of one object to the center of another (inside ``always_redraw``)."""
    points = [f"{start}.get_center()", f"{end}.get_center()"]
    style = [f"{key}={value}" for key, value in _line_style(obj)]
    if obj.kind == ObjectKind.DASHED_LINE:
        dashes = [f"dash_length={fmt_float(float(obj.params.get('dash_length', 0.15)))}", f"dashed_ratio={fmt_float(float(obj.params.get('dashed_ratio', 0.5)))}"]
        return f"DashedLine({', '.join(points + dashes + style)})"
    name = {ObjectKind.ARROW: "Arrow", ObjectKind.DOUBLE_ARROW: "DoubleArrow"}.get(obj.kind, "Line")
    buff = ["buff=0"] if name != "Line" else []
    return f"{name}({', '.join(points + buff + style)}){_gradient_chain(obj)}"


def corners_code(obj: SceneObject, corners: list[str]) -> str:
    """A polygon through the centers of objects (inside ``always_redraw``); dashed as DashedVMobject."""
    points = [f"{corner}.get_center()" for corner in corners]
    if is_dashed(obj):
        count, ratio = dash_settings(obj)
        plain = dataclasses.replace(obj, fill_opacity=0.0, params={**obj.params, "dashed": False})
        return f"DashedVMobject({corners_code(plain, corners)}, num_dashes={count}, dashed_ratio={fmt_float(ratio)}){_gradient_chain(obj)}"
    if obj.params.get("smooth") or not obj.params.get("closed", True):
        return f"{' '.join(curve_call(obj, points))}{_gradient_chain(obj)}"
    style = [f"{key}={value}" for key, value in _shape_style(obj)]
    return f"Polygon({', '.join(points + style)}){_gradient_chain(obj)}"


def _gradient_chain(obj: SceneObject) -> str:
    """A gradient inside ``always_redraw`` (the shape is built anew in every frame, unturned)."""
    fill, stroke = gradient_parts(obj)
    chain = ""
    if fill:
        chain += f".set_fill([{py_color(obj.fill_color)}, {py_color(gradient_color(obj))}])"
    if not (fill or stroke):
        return ""
    if stroke:
        chain += f".set_stroke([{py_color(obj.stroke_color)}, {py_color(gradient_color(obj))}])"
    direction = str(obj.params.get("gradient_direction", DEFAULT_DIRECTION))
    if direction != DEFAULT_DIRECTION and direction in SHEEN_CODE:
        chain += f".set_sheen_direction({SHEEN_CODE[direction]})"
    return chain


def _placement(obj: SceneObject, variable: str) -> list[str]:
    lines = [f"{variable}.move_to({py_point(obj.x, obj.y)})"]
    if round(obj.rotation, 6) != 0:
        lines.append(f"{variable}.rotate({py_degrees(obj.rotation)})")
    return lines


def _gradient_lines(obj: SceneObject, variable: str) -> list[str]:
    """Two-color fill or stroke; set before turning the object, so its direction turns with it."""
    if obj.kind == ObjectKind.TEXT:
        return []  # a text's letters get their colors in Text(gradient=…)
    if attach_mode(obj) in REDRAWN_MODES:
        return []  # part of the always_redraw shape (connection_code, corners_code)
    fill, stroke = gradient_parts(obj)
    lines = []
    if fill:
        lines.append(f"{variable}.set_fill([{py_color(obj.fill_color)}, {py_color(gradient_color(obj))}])")
    if stroke:
        lines.append(f"{variable}.set_stroke([{py_color(obj.stroke_color)}, {py_color(gradient_color(obj))}])")
    direction = str(obj.params.get("gradient_direction", DEFAULT_DIRECTION))
    if lines and direction != DEFAULT_DIRECTION and direction in SHEEN_CODE:
        lines.append(f"{variable}.set_sheen_direction({SHEEN_CODE[direction]})")
    return lines


def _post_style(obj: SceneObject, variable: str) -> list[str]:
    lines: list[str] = _gradient_lines(obj, variable)
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
        # parameters (ValueTrackers) and the camera are not mobjects and cannot be grouped
        member_ids = [m for m in obj.params.get("members", []) if m in names and (member := scene.object_by_id(m)) is not None and member.kind not in UNGROUPABLE]
        if not member_ids:
            raise CodegenError("group_empty", obj.name)
        return group_code(variable, [names[m] for m in member_ids]), False
    if obj.kind == ObjectKind.BRACE:
        target = obj.params.get("target")
        attached = target in names and target != obj.id
        return brace_code(obj, variable, names[target] if attached else None), not attached
    if obj.kind == ObjectKind.HIGHLIGHT:
        target = obj.params.get("target")
        if target not in names or target == obj.id:
            raise CodegenError("highlight_target_missing", obj.name)
        selection = table_selection(scene, obj)
        if selection is not None:
            # a cell, row or column of the table
            return highlight_code(obj, variable, f"{STUDIO_TABLE_CELLS}({names[str(target)]}, {selection[0]}, {selection[1]})"), False
        return highlight_code(obj, variable, names[str(target)]), False
    if obj.kind == ObjectKind.VECTOR_FIELD:
        expressions = field_expressions(scene, obj)
        if expressions is None:
            raise CodegenError("expression_invalid", obj.name)
        rename = renames(scene, names)
        x_code, y_code = (expression.to_numpy(rename) for expression in expressions)
        return vector_field_code(obj, variable, x_code, y_code, bool(graphs.parameter_users(scene, obj))), False
    if obj.kind == ObjectKind.TRACE:
        target = trace_target(scene, obj)
        if target is None or target.id not in names:
            raise CodegenError("trace_target_missing", obj.name)
        return trace_code(obj, variable, names[target.id]), False
    if obj.kind == ObjectKind.ANGLE:
        lines = angle_lines(scene, obj)
        if lines is None or any(line.id not in names for line in lines):
            raise CodegenError("angle_lines_missing", obj.name)
        return angle_code(obj, variable, names[lines[0].id], names[lines[1].id]), False
    if obj.kind == ObjectKind.ZOOM_LENS:
        return lens_code(obj, variable), False
    if obj.kind == ObjectKind.BOOLEAN_SHAPE:
        from manim_studio.model.booleans import leaves, operands

        if operands(scene, obj) is None or any(leaf.id not in names for leaf in leaves(scene, obj)):
            raise CodegenError("boolean_shapes_missing", obj.name)
        return boolean_code(scene, obj, variable, names), False
    return None


def lens_code(obj: SceneObject, variable: str) -> list[str]:
    """The zoomed camera of a ``ZoomedScene``: its frame is the lens, the display shows it magnified."""
    from manim_studio.model.lenses import lens_geometry

    lens = lens_geometry(obj)
    stroke = f"{py_color(obj.stroke_color)}, width={fmt_float(obj.stroke_width)}"
    return [
        f"{variable} = self.zoomed_camera.frame",
        f"{variable}.stretch_to_fit_width({fmt_float(lens.frame_width)}).stretch_to_fit_height({fmt_float(lens.frame_height)})",
        f"{variable}.move_to({py_point(obj.x, obj.y)}).set_stroke({stroke})",
        f"self.zoomed_display.stretch_to_fit_width({fmt_float(lens.display_width)}).stretch_to_fit_height({fmt_float(lens.display_height)})",
        f"self.zoomed_display.move_to({py_point(lens.display_x, lens.display_y)})",
        f"self.zoomed_display.display_frame.set_stroke({stroke})",
    ]


STUDIO_CAMERA = "studio_camera_frame"
STUDIO_CAMERA_SOURCE = '''def studio_camera_frame(scene):
    """A frame that steers the 3D camera like the camera frame of a 2D scene.

    Moving, scaling and rotating this (invisible) rectangle moves, zooms and
    rolls the camera. It is also available as ``self.camera.frame``.
    """
    camera = scene.renderer.camera
    if getattr(camera, "studio_frame", None) is not None:
        return camera.studio_frame
    frame = Rectangle(width=config.frame_width, height=config.frame_height, stroke_opacity=0, fill_opacity=0)

    def follow(_dt):
        right, left = frame.get_vertices()[0], frame.get_vertices()[1]
        camera.frame_center = frame.get_center()
        camera.set_zoom(config.frame_width / max(np.linalg.norm(right - left), 1e-6))
        camera.set_gamma(-angle_of_vector(right - left))

    scene.add(frame)
    scene.add_updater(follow)
    camera.studio_frame = camera.frame = frame
    return frame'''


def camera_code(obj: SceneObject, variable: str) -> list[str]:
    """Initial position, zoom and rotation of the camera frame."""
    lines = []
    if round(obj.x, 6) != 0 or round(obj.y, 6) != 0:
        lines.append(f"{variable}.move_to({py_point(obj.x, obj.y)})")
    width = float(obj.params.get("width", 0.0) or 0.0)
    if width > 0:
        lines.append(f"{variable}.set(width={fmt_float(width)})")
    if round(obj.rotation, 6) != 0:
        lines.append(f"{variable}.rotate({py_degrees(obj.rotation)})")
    return lines


def object_code(
    scene: Scene, obj: SceneObject, names: dict[str, str], base_dir: str | Path | None, helpers: set[str] | None = None
) -> list[str]:
    """Return the lines that create, place and style one object."""
    variable = names[obj.id]
    helpers = helpers if helpers is not None else set()
    try:
        special = _special_code(scene, obj, names) or graph_object_code(scene, obj, names, helpers)
        if obj.kind == ObjectKind.ANGLE:
            helpers.add(STUDIO_ANGLE)
        if obj.kind == ObjectKind.BOOLEAN_SHAPE and uses_union(scene, obj):
            helpers.add(STUDIO_UNION)
        if obj.kind == ObjectKind.HIGHLIGHT and table_selection(scene, obj) is not None:
            helpers.add(STUDIO_TABLE_CELLS)
        if obj.kind == ObjectKind.CAMERA:
            if is_3d(scene):
                # the 3D camera has no frame: a helper frame steers its center, zoom and roll
                helpers.add(STUDIO_CAMERA)
                return [f"{variable} = {STUDIO_CAMERA}(self)"] + camera_code(obj, variable)
            if round(obj.rotation, 6) != 0:
                raise CodegenError("camera_rotation_2d", obj.name)
            return camera_code(obj, variable)
        ends = connection_targets(scene, obj)
        if ends is not None:
            if any(end.id not in names for end in ends):
                raise CodegenError("attach_between_missing", obj.name)
            special = ([f"{variable} = always_redraw(lambda: {connection_code(obj, *(names[end.id] for end in ends))})"], False)
        elif attach_mode(obj) == ATTACH_BETWEEN:
            raise CodegenError("attach_between_missing", obj.name)
        corners = corner_targets(scene, obj)
        if corners is not None:
            if any(corner.id not in names for corner in corners):
                raise CodegenError("attach_corners_missing", obj.name)
            special = ([f"{variable} = always_redraw(lambda: {corners_code(obj, [names[corner.id] for corner in corners])})"], False)
        elif attach_mode(obj) == ATTACH_CORNERS:
            raise CodegenError("attach_corners_missing", obj.name)
        if special is not None:
            lines, place = special
        elif obj.kind == ObjectKind.AXES_3D:
            lines, place = assign(variable, axes_3d_code(obj)), True
        elif obj.kind == ObjectKind.NETWORK:
            lines, place = network_code(obj, variable), False
        elif obj.kind == ObjectKind.BULLET_LIST:
            lines, place = bullet_list_code(obj, variable), True
        elif obj.kind == ObjectKind.SOLID:
            lines, place = assign(variable, solid_code(scene, obj, names)), False
        elif obj.kind == ObjectKind.VECTOR_3D:
            lines, place = assign(variable, vector_3d_code(scene, obj, names)), False
        elif obj.kind in (ObjectKind.SURFACE, ObjectKind.CURVE_3D):
            rename = renames(scene, names)
            build = surface_code if obj.kind == ObjectKind.SURFACE else curve_3d_code
            expression_lines = build(scene, obj, names, rename)
            if graphs.parameter_users(scene, obj):
                expression_lines = ["always_redraw(", "    lambda: " + expression_lines[0]] + ["    " + line for line in expression_lines[1:]] + [")"]
            lines, place = assign(variable, expression_lines), False
        elif obj.kind == ObjectKind.DATA_PLOT:
            lines, place = assign(variable, data_plot_code(scene, obj, names)), False
        elif obj.kind == ObjectKind.BAR_CHART:
            lines, place = assign(variable, bar_chart_code(obj)) + bar_label_lines(obj, variable), True
        elif obj.kind == ObjectKind.MATH_TEX:
            if colored_parts(obj.params):
                helpers.add(COLOR_TEX)
            lines, place = assign(variable, _math_tex(obj, scene)), True
        elif obj.kind == ObjectKind.IMAGE:
            lines, place = assign(variable, image_code(obj, base_dir)), True
        else:
            lines, place = assign(variable, _constructor(obj)), True
            if is_dashed(obj) and obj.kind == ObjectKind.SECTOR:
                helpers.add(STUDIO_OUTLINE)
        lines += _post_style(obj, variable)
        if place:
            lines += _placement(obj, variable)
        if obj.kind == ObjectKind.AXES:
            lines += axis_label_lines(obj, variable)
        if obj.kind == ObjectKind.NUMBER_PLANE:
            lines += polar_grid_line(obj, variable)
            lines += plane_number_lines(obj, variable, helpers)
        parameter = scene.object_by_id(obj.params.get("parameter_id")) if obj.kind == ObjectKind.DECIMAL_NUMBER else None
        from manim_studio.model.latex_term import result_term

        term = result_term(scene, obj)
        if term is not None and (graphs.parameter_users(scene, obj) or graphs.uses_positions(term)):
            # recompute "= result" in every frame; become() keeps the formula where it is
            code = term.to_numpy(renames(scene, names), pad_variable=False)
            decimals = int(param_float(obj.params, "result_decimals", 2.0))
            source = py_str(str(obj.params.get("latex", "")) + " = ", prefer_raw=True)
            kwargs = f"font_size={fmt_float(_p(obj, 'font_size'))}, color={py_color(obj.fill_color)}"
            text = f'{source} + f"{{({code}):.{decimals}f}}"'
            lines.append(f"{variable}.add_updater(lambda mob: mob.become(MathTex({text}, {kwargs}).move_to(mob.get_center())), call_updater=True)")
        formula = graphs.number_formula(scene, obj)
        if formula is not None:
            # the number shows a formula of parameters, recomputed in every frame
            code = formula.to_numpy(renames(scene, names), pad_variable=False)
            lines.append(f"{variable}.add_updater(lambda mob: mob.set_value({code}), call_updater=True)")
        elif parameter is not None and parameter.kind == ObjectKind.PARAMETER and parameter.id in names:
            lines.append(f"{variable}.add_updater(lambda mob: mob.set_value({names[parameter.id]}.get_value()), call_updater=True)")
    except LiteralError as error:
        raise CodegenError("value_invalid", f"{obj.name}: {error}") from None
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, CodegenError):
            raise
        raise CodegenError("value_invalid", f"{obj.name}: {error}") from None
    from manim_studio.model.warps import warped_objects

    if obj.id in warped_objects(scene):
        # many short curves, so that the nonlinear map later bends the outlines smoothly
        helpers.add(STUDIO_MAP)
        lines.append(f"{STUDIO_PREPARE_MAP}({variable})")
    if is_3d(scene) and obj.kind not in UNADDED_KINDS and obj.kind not in THREE_D_KINDS:
        lines.append(f"self.renderer.camera.add_fixed_in_frame_mobjects({variable})")
    if obj.kind == ObjectKind.HIGHLIGHT and obj.params.get("style") == "background":
        # stays behind its target even when it appears later (new mobjects are drawn on top)
        target = scene.object_by_id(obj.params.get("target"))
        lines.append(f"{variable}.set_z_index({fmt_int((target.z_index if target is not None else obj.z_index) - 1)})")
    elif obj.z_index and obj.kind not in INVISIBLE_KINDS:
        lines.append(f"{variable}.set_z_index({fmt_int(obj.z_index)})")
    return lines


def dependencies(scene: Scene, obj: SceneObject) -> list[str]:
    """Return ids of objects that must be created before ``obj``."""
    result: list[str] = []
    if (obj.kind in (ObjectKind.FUNCTION_GRAPH, ObjectKind.DATA_PLOT) or obj.kind in ON_3D_AXES) and obj.params.get("axes_id"):
        result.append(str(obj.params.get("axes_id")))
    if obj.kind in GRAPH_TOOL_KINDS:
        for key in ("x_parameter",):
            if obj.params.get(key):
                result.append(str(obj.params.get(key)))
    if obj.kind in (ObjectKind.BRACE, ObjectKind.HIGHLIGHT, ObjectKind.TRACE) and obj.params.get("target"):
        result.append(str(obj.params.get("target")))
    if obj.kind == ObjectKind.ANGLE:
        result += [str(obj.params.get(key)) for key in ANGLE_LINE_KEYS if obj.params.get(key)]
    if obj.kind == ObjectKind.BOOLEAN_SHAPE:
        result += [str(obj.params.get(key)) for key in ("first_shape", "second_shape") if obj.params.get(key)]
    if obj.kind == ObjectKind.TOOL_LABEL and obj.params.get("tool_id"):
        result.append(str(obj.params.get("tool_id")))
    if obj.kind == ObjectKind.GROUP:
        result += [str(member) for member in obj.params.get("members", [])]
    if attach_mode(obj) == ATTACH_BETWEEN:
        result += [str(obj.params.get(key)) for key in ("attach_start", "attach_end") if obj.params.get(key)]
    if attach_mode(obj) == ATTACH_CORNERS:
        result += [str(corner) for corner in obj.params.get("attach_corners", []) or []]
    # a number or result that reads A.x, A.y or dist(A, B) is updated at once: A must exist
    from manim_studio.model.latex_term import result_term

    formula = graphs.number_formula(scene, obj) or result_term(scene, obj)
    if formula is not None:
        result += graphs.position_users(scene, formula)
    for key in ("graph_id", "other_graph_id"):
        if obj.params.get(key):
            result.append(str(obj.params.get(key)))
    return [dep for dep in result if scene.object_by_id(dep) is not None and dep != obj.id]


def creation_order(scene: Scene) -> list[SceneObject]:
    """Objects sorted so that every object comes after the ones it depends on.

    Parameters (value trackers) come first because terms of any object may use them.
    """
    remaining = [obj for obj in scene.objects if obj.kind == ObjectKind.PARAMETER]
    remaining += [obj for obj in scene.objects if obj.kind != ObjectKind.PARAMETER]
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
