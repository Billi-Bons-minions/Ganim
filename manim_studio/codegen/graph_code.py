"""Code generation for function graphs, graph tools and parameters.

Objects whose shape depends on a parameter (a Manim ``ValueTracker``) are
wrapped in ``always_redraw`` so they follow the parameter while it is animated.
"""

from __future__ import annotations

import math

from manim_studio.codegen.errors import CodegenError
from manim_studio.codegen.formatting import INDENT, call
from manim_studio.codegen.literals import fmt_float, fmt_number, py_color, py_range, py_str
from manim_studio.model import graphs
from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.geometry import bound_axes, param_float
from manim_studio.model.graphs import Piece
from manim_studio.model.types import (
    CURVE_FUNCTION,
    CURVE_IMPLICIT,
    CURVE_PARAMETRIC,
    CURVE_PIECEWISE,
    CURVE_POLAR,
    FUNCTION_CURVES,
    GRAPH_TOOL_KINDS,
    ObjectKind,
)

#: Name of the helper function emitted into scripts that need clipped graphs.
STUDIO_PLOT = "studio_plot"
STUDIO_DASHED = "studio_dashed_line"
STUDIO_LINES = "studio_lines_to_point"
STUDIO_TERM = "studio_term"
STUDIO_BESIDE = "studio_beside"
POINT_LABEL_SIZE = 24.0
AXIS_LABEL_SIZE = 28.0
SMALL_BUFF = 0.1
MANIM_DIRECTIONS = {
    "up_right": "UR",
    "up": "UP",
    "right": "RIGHT",
    "down_right": "DR",
    "down": "DOWN",
    "down_left": "DL",
    "left": "LEFT",
    "up_left": "UL",
}

Kwargs = list[tuple[str, str]]


# --- parameters --------------------------------------------------------------------------


def renames(scene: Scene, names: dict[str, str]) -> dict[str, str]:
    """Map parameter symbols onto ``tracker.get_value()`` code."""
    symbols = set(graphs.parameter_symbols(scene))
    return {
        graphs.parameter_symbol(obj): f"{names[obj.id]}.get_value()"
        for obj in graphs.parameter_objects(scene)
        if graphs.parameter_symbol(obj) in symbols and obj.id in names
    }


def parameter_code(obj: SceneObject, variable: str) -> list[str]:
    """``a = ValueTracker(1.0)``."""
    return [f"{variable} = ValueTracker({fmt_float(param_float(obj.params, 'value', 0.0))})"]


def _graph_uses_parameters(scene: Scene, graph: SceneObject | None) -> bool:
    if graph is None or graph.kind != ObjectKind.FUNCTION_GRAPH:
        return False
    curve = graph.params.get("curve", CURVE_FUNCTION)
    if curve in FUNCTION_CURVES:
        pieces = graphs.function_pieces(scene, graph) or []
        return any(piece.expression.used_parameters() for piece in pieces)
    if curve == CURVE_IMPLICIT:
        expression = graphs.implicit_expression(scene, graph)
        # y is the second variable of f(x, y) = 0, not a parameter
        return expression is not None and bool(expression.used_parameters() - {"y"})
    keys = ("x_expression", "y_expression") if curve == CURVE_PARAMETRIC else ("r_expression",)
    expressions = [graphs.parse(scene, str(graph.params.get(key, "")), "t") for key in keys]
    return any(expression is not None and expression.used_parameters() for expression in expressions)


def is_dynamic(scene: Scene, obj: SceneObject) -> bool:
    """Return ``True`` if the object has to be redrawn while parameters change."""
    if obj.kind == ObjectKind.FUNCTION_GRAPH:
        return _graph_uses_parameters(scene, obj)
    if obj.kind not in GRAPH_TOOL_KINDS or obj.kind == ObjectKind.GRAPH_MARKERS:
        return False
    if any(scene.object_by_id(obj.params.get(key)) is not None for key in ("x_parameter", "h_parameter")):
        return True
    graph = scene.object_by_id(obj.params.get("graph_id"))
    other = scene.object_by_id(obj.params.get("other_graph_id")) if obj.params.get("mode") == "between" else None
    return _graph_uses_parameters(scene, graph) or _graph_uses_parameters(scene, other)


# --- function code -----------------------------------------------------------------------------


def _condition(piece: Piece, last: bool, variable: str = "x") -> str:
    parts = []
    if math.isfinite(piece.low):
        parts.append(f"{fmt_number(piece.low)} <=")
    parts.append(variable)
    if math.isfinite(piece.high):
        parts.append(f"{'<=' if last else '<'} {fmt_number(piece.high)}")
    return " ".join(parts)


def pieces_code(pieces: list[Piece], rename: dict[str, str]) -> str:
    """Body of ``lambda x: ...`` for (piecewise) functions."""
    if len(pieces) == 1 and not math.isfinite(pieces[0].low) and not math.isfinite(pieces[0].high):
        return pieces[0].expression.to_numpy(rename)
    code = "np.nan"
    for index in range(len(pieces) - 1, -1, -1):
        piece = pieces[index]
        branch = piece.expression.to_numpy(rename)
        condition = _condition(piece, index == len(pieces) - 1)
        nested = code if index == len(pieces) - 1 else f"({code})"
        code = f"{branch} if {condition} else {nested}"
    return code


def _function_pieces(scene: Scene, graph: SceneObject) -> list[Piece]:
    pieces = graphs.function_pieces(scene, graph)
    if pieces is None:
        raise CodegenError("expression_invalid", graph.name)
    return pieces


def _expression_code(scene: Scene, graph: SceneObject, key: str, rename: dict[str, str]) -> str:
    expression = graphs.parse(scene, str(graph.params.get(key, "")), "t")
    if expression is None:
        raise CodegenError("expression_invalid", graph.name)
    return expression.to_numpy(rename)


def _line_style(obj: SceneObject) -> Kwargs:
    return [
        ("color", py_color(obj.stroke_color)),
        ("stroke_width", fmt_float(obj.stroke_width)),
        ("stroke_opacity", fmt_float(obj.stroke_opacity)),
    ]


def _needs_studio_plot(scene: Scene, graph: SceneObject, pieces: list[Piece], dynamic: bool) -> bool:
    if graph.params.get("curve") == CURVE_PIECEWISE or len(pieces) > 1:
        return True
    limits = graphs.y_limits(scene, graph)
    if limits is None:
        return False
    if dynamic:
        return True
    function = graphs.graph_function(scene, graph)
    if function is None:
        return False
    low, high = graphs.x_range(graph)
    for index in range(401):
        y = function(low + (high - low) * index / 400)
        if not math.isfinite(y) or not limits[0] - 1e-9 <= y <= limits[1] + 1e-9:
            return True
    return False


def graph_constructor(scene: Scene, graph: SceneObject, names: dict[str, str], helpers: set[str]) -> list[str]:
    """The expression that creates a function graph (without ``always_redraw``)."""
    rename = renames(scene, names)
    curve = graph.params.get("curve", CURVE_FUNCTION)
    axes = bound_axes(scene, graph)
    axes_variable = names[axes.id] if axes is not None else None
    style = _line_style(graph)
    if curve in FUNCTION_CURVES:
        pieces = _function_pieces(scene, graph)
        function = f"lambda x: {pieces_code(pieces, rename)}"
        low, high = graphs.x_range(graph)
        if axes_variable is None:
            return call("FunctionGraph", [function], [("x_range", py_range(low, high))] + style, 2)
        if _needs_studio_plot(scene, graph, pieces, bool(_graph_uses_parameters(scene, graph))):
            helpers.add(STUDIO_PLOT)
            limits = graphs.y_limits(scene, graph)
            options: Kwargs = [("y_range", py_range(*limits) if limits else "None")]
            breaks = graphs.piece_breaks(pieces, low, high)
            if breaks:
                options.append(("breaks", "[" + ", ".join(fmt_number(value) for value in breaks) + "]"))
            return call(STUDIO_PLOT, [axes_variable, function, py_range(low, high)], options + style, 2)
        return call(f"{axes_variable}.plot", [function], [("x_range", py_range(low, high))] + style, 2)
    if curve == CURVE_IMPLICIT:
        expression = graphs.implicit_expression(scene, graph)
        if expression is None:
            raise CodegenError("expression_invalid", graph.name)
        function = f"lambda x, y: {expression.to_numpy(rename)}"
        if _graph_uses_parameters(scene, graph):
            # recomputed in every frame while the parameter moves: a coarser search is much faster
            style = [("max_quads", "500")] + list(style)
        if axes_variable is not None:
            return call(f"{axes_variable}.plot_implicit_curve", [function], style, 2)
        x0, x1, y0, y1 = graphs.implicit_range(scene, graph)
        return call("ImplicitFunction", [function], [("x_range", py_range(x0, x1)), ("y_range", py_range(y0, y1))] + style, 2)
    t_range = py_range(param_float(graph.params, "t_min", 0.0), param_float(graph.params, "t_max", math.tau))
    if curve == CURVE_PARAMETRIC:
        x_code = _expression_code(scene, graph, "x_expression", rename)
        y_code = _expression_code(scene, graph, "y_expression", rename)
        if axes_variable is not None:
            function = f"lambda t: np.array([{x_code}, {y_code}])"
            return call(f"{axes_variable}.plot_parametric_curve", [function], [("t_range", t_range)] + style, 2)
        function = f"lambda t: np.array([{x_code}, {y_code}, 0])"
        return call("ParametricFunction", [function], [("t_range", t_range)] + style, 2)
    if curve == CURVE_POLAR:
        r_code = _expression_code(scene, graph, "r_expression", rename)
        if axes_variable is not None:
            return call(f"{axes_variable}.plot_polar_graph", [f"lambda t: {r_code}"], [("theta_range", t_range)] + style, 2)
        function = f"lambda t: ({r_code}) * np.array([np.cos(t), np.sin(t), 0])"
        return call("ParametricFunction", [function], [("t_range", t_range)] + style, 2)
    raise CodegenError("value_invalid", graph.name)


# --- graph tools ---------------------------------------------------------------------------------


def _tool_parts(scene: Scene, obj: SceneObject, names: dict[str, str]) -> tuple[SceneObject, str, str]:
    graph = graphs.tool_graph(scene, obj)
    if graph is None or graph.id not in names:
        raise CodegenError("graph_missing", obj.name)
    axes = bound_axes(scene, graph)
    assert axes is not None
    if obj.kind != ObjectKind.GRAPH_LABEL and not graphs.is_function_curve(graph):
        raise CodegenError("graph_not_function", obj.name)
    return graph, names[graph.id], names[axes.id]


def _x_code(scene: Scene, obj: SceneObject, names: dict[str, str]) -> str:
    parameter = scene.object_by_id(obj.params.get("x_parameter"))
    if parameter is not None and parameter.kind == ObjectKind.PARAMETER and parameter.id in names:
        return f"{names[parameter.id]}.get_value()"
    return fmt_float(param_float(obj.params, "x_value", 0.0))


def area_code(scene: Scene, obj: SceneObject, names: dict[str, str]) -> list[str]:
    graph, graph_variable, axes_variable = _tool_parts(scene, obj, names)
    low, high = param_float(obj.params, "x_min", -1.0), param_float(obj.params, "x_max", 2.0)
    kwargs: Kwargs = [("x_range", f"({fmt_number(low)}, {fmt_number(high)})")]
    mode = obj.params.get("mode", "under")
    if mode == "between":
        other = scene.object_by_id(obj.params.get("other_graph_id"))
        if other is None or other.id not in names or not graphs.is_function_curve(other):
            raise CodegenError("other_graph_missing", obj.name)
        kwargs.append(("bounded_graph", names[other.id]))
    elif mode in ("above", "below"):
        axes = bound_axes(scene, graph)
        assert axes is not None
        edge = param_float(axes.params, "y_max" if mode == "above" else "y_min", 0.0)
        kwargs.append(("bounded_graph", f"{axes_variable}.plot(lambda x: {fmt_number(edge)} + 0 * x, x_range={py_range(low, high)})"))
    kwargs += [
        ("color", py_color(obj.fill_color)),
        ("opacity", fmt_float(obj.fill_opacity)),
        ("stroke_width", fmt_float(obj.stroke_width)),
    ]
    return call(f"{axes_variable}.get_area", [graph_variable], kwargs, 2)


def riemann_code(scene: Scene, obj: SceneObject, names: dict[str, str]) -> list[str]:
    _graph, graph_variable, axes_variable = _tool_parts(scene, obj, names)
    low, high = param_float(obj.params, "x_min", 0.0), param_float(obj.params, "x_max", 3.0)
    kwargs = [
        ("x_range", py_range(low, high)),
        ("dx", fmt_float(param_float(obj.params, "dx", 0.25))),
        ("input_sample_type", py_str(str(obj.params.get("sample", "left")))),
        ("color", py_color(obj.fill_color)),
        ("fill_opacity", fmt_float(obj.fill_opacity)),
        ("stroke_color", py_color(obj.stroke_color)),
        ("stroke_width", fmt_float(obj.stroke_width)),
        ("show_signed_area", "False"),
    ]
    return call(f"{axes_variable}.get_riemann_rectangles", [graph_variable], kwargs, 2)


def _slope_code(scene: Scene, graph: SceneObject, rename: dict[str, str]) -> str:
    from manim_studio.model.calculus import derivative

    pieces = [Piece(derivative(piece.expression), piece.low, piece.high) for piece in _function_pieces(scene, graph)]
    return pieces_code(pieces, rename)


def tangent_code(scene: Scene, obj: SceneObject, names: dict[str, str], variable: str, dynamic: bool) -> tuple[list[str], str]:
    """Return ``(definition lines, expression)`` of a tangent."""
    graph, _graph_variable, axes_variable = _tool_parts(scene, obj, names)
    half = param_float(obj.params, "width", 3.0) / 2
    style = _line_style(obj)
    labelled = obj.params.get("label", "none") in graphs.LINE_LABEL_STYLES
    if not dynamic:
        function_of_graph = graphs.graph_function(scene, graph)
        x0 = graphs.tool_x(scene, obj, None)
        y0 = function_of_graph(x0) if function_of_graph is not None else math.nan
        slope = graphs.tangent_slope(scene, obj)
        if slope is None or not math.isfinite(y0):
            raise CodegenError("tangent_undefined", obj.name)
        function = f"lambda x: {fmt_float(y0)} + {fmt_float(slope)} * (x - {fmt_float(x0)})"
        plot = call(f"{axes_variable}.plot", [function], [("x_range", py_range(x0 - half, x0 + half))] + style, 2)
        if not labelled:
            return [], "\n".join(plot)
        return [], "\n".join(["VGroup("] + [f"{INDENT}{line}" for line in plot[:-1]] + [f"{INDENT}{plot[-1]},", f"{INDENT}{_static_label(scene, obj, axes_variable)},", ")"])
    rename = renames(scene, names)
    function_code = pieces_code(_function_pieces(scene, graph), rename)
    if not labelled:
        lines = [
            "",
            f"def {variable}_build():",
            f"{INDENT}x0 = {_x_code(scene, obj, names)}",
            f"{INDENT}y0 = (lambda x: {function_code})(x0)",
            f"{INDENT}slope = (lambda x: {_slope_code(scene, graph, rename)})(x0)",
            f"{INDENT}return {axes_variable}.plot(",
            f"{INDENT * 2}lambda x: y0 + slope * (x - x0),",
            f"{INDENT * 2}x_range=[x0 - {fmt_float(half)}, x0 + {fmt_float(half)}],",
        ]
        lines += [f"{INDENT * 2}{key}={value}," for key, value in style]
        lines += [f"{INDENT})", ""]
        return lines, f"always_redraw({variable}_build)"
    lines = [
        "",
        f"def {variable}_build():",
        f"{INDENT}x0 = {_x_code(scene, obj, names)}",
        f"{INDENT}curve = lambda x: {function_code}",
        f"{INDENT}y0 = curve(x0)",
        f"{INDENT}slope = (lambda x: {_slope_code(scene, graph, rename)})(x0)",
        *_side_lines(obj, "x0", "y0"),
        f"{INDENT}return VGroup(",
        f"{INDENT * 2}{axes_variable}.plot(",
        f"{INDENT * 3}lambda x: y0 + slope * (x - x0),",
        f"{INDENT * 3}x_range=[x0 - {fmt_float(half)}, x0 + {fmt_float(half)}],",
    ]
    lines += [f"{INDENT * 3}{key}={value}," for key, value in style]
    lines += [f"{INDENT * 2}),", f"{INDENT * 2}{_live_label(obj, 't', axes_variable, 'x0', 'y0')},", f"{INDENT})", ""]
    return lines, f"always_redraw({variable}_build)"


def _label_text(obj: SceneObject, text_code: str) -> str:
    color = py_color(obj.stroke_color)
    return f"Text({text_code}, font_size={fmt_float(POINT_LABEL_SIZE)}, color={color}, fill_opacity={fmt_float(obj.stroke_opacity)})"


def _static_label(scene: Scene, obj: SceneObject, axes_variable: str) -> str:
    """The label of a tangent or secant whose numbers do not change."""
    label = graphs.line_label(scene, obj)
    if label is None:
        raise CodegenError("tangent_undefined" if obj.kind == ObjectKind.TANGENT else "secant_undefined", obj.name)
    numbers = ", ".join(fmt_float(value) for value in (label.x, label.y, label.slope))
    return f"{STUDIO_BESIDE}({_label_text(obj, py_str(label.text))}, {axes_variable}, {numbers}, {label.side})"


def _side_lines(obj: SceneObject, x_code: str, y_code: str) -> list[str]:
    """``side = …``: above or below the line; ``auto`` keeps the label off the graph (see ``graphs.label_side``)."""
    choice = str(obj.params.get("label_side", "auto"))
    if choice in ("above", "below"):
        return [f"{INDENT}side = {1 if choice == 'above' else -1}"]
    step = fmt_float(graphs.SIDE_STEP)
    return [f"{INDENT}side = -1 if curve({x_code} + {step}) + curve({x_code} - {step}) > 2 * {y_code} else 1  # keep off the graph"]


def _live_label(obj: SceneObject, name: str, axes_variable: str, x_code: str, y_code: str) -> str:
    """The label of a tangent or secant inside its build function (slope, x and y are variables there)."""
    decimals = int(param_float(obj.params, "decimals", 2.0))
    style = py_str(str(obj.params.get("label", "term")))
    text = f'{STUDIO_TERM}("{name}", slope, {y_code} - slope * {x_code}, {decimals}, {style})'
    return f"{STUDIO_BESIDE}({_label_text(obj, text)}, {axes_variable}, {x_code}, {y_code}, slope, side)"


def _h_code(scene: Scene, obj: SceneObject, names: dict[str, str]) -> str:
    parameter = scene.object_by_id(obj.params.get("h_parameter"))
    if parameter is not None and parameter.kind == ObjectKind.PARAMETER and parameter.id in names:
        return f"{names[parameter.id]}.get_value()"
    return fmt_float(param_float(obj.params, "h", 1.0))


def _secant_parts(axes_variable: str, obj: SceneObject, x0: str, y0: str, x1: str, y1: str, left: tuple[str, str], right: tuple[str, str]) -> list[str]:
    """The pieces of a secant: line, the two points and the dashed slope triangle."""
    color = py_color(obj.stroke_color)
    opacity = fmt_float(obj.stroke_opacity)

    def point(x: str, y: str) -> str:
        return f"{axes_variable}.c2p({x}, {y})"

    parts = [
        f"Line({point(*left)}, {point(*right)}, color={color}, stroke_width={fmt_float(obj.stroke_width)}, stroke_opacity={opacity})",
    ]
    radius = param_float(obj.params, "radius", 0.07)
    if radius > 0:
        parts += [f"Dot({point(x, y)}, radius={fmt_float(radius)}, color={color}, fill_opacity={opacity})" for x, y in ((x0, y0), (x1, y1))]
    if obj.params.get("show_triangle", True):
        legs = (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)))
        parts += [f"{STUDIO_DASHED}({point(*start)}, {point(*end)}, color={color}, stroke_width=2, stroke_opacity={opacity})" for start, end in legs]
    return parts


def secant_code(scene: Scene, obj: SceneObject, names: dict[str, str], variable: str, dynamic: bool) -> tuple[list[str], str]:
    """Return ``(definition lines, expression)`` of a secant through f(x0) and f(x0 + h)."""
    graph, _graph_variable, axes_variable = _tool_parts(scene, obj, names)
    extend = param_float(obj.params, "extend", 1.0)
    if not dynamic:
        found = graphs.secant(scene, obj)
        if found is None:
            raise CodegenError("secant_undefined", obj.name)
        (left_x, left_y), (right_x, right_y) = found.line
        numbers = [fmt_float(value) for value in (found.x0, found.y0, found.x1, found.y1)]
        parts = _secant_parts(axes_variable, obj, *numbers, (fmt_float(left_x), fmt_float(left_y)), (fmt_float(right_x), fmt_float(right_y)))
        if obj.params.get("label", "none") in graphs.LINE_LABEL_STYLES:
            parts.append(_static_label(scene, obj, axes_variable))
        return [], "\n".join(["VGroup("] + [f"{INDENT}{part}," for part in parts] + [")"])
    rename = renames(scene, names)
    function_code = pieces_code(_function_pieces(scene, graph), rename)
    parts = _secant_parts(axes_variable, obj, "x0", "y0", "x1", "y1", ("left", "y0 + slope * (left - x0)"), ("right", "y0 + slope * (right - x0)"))
    labelled = obj.params.get("label", "none") in graphs.LINE_LABEL_STYLES
    curve = "curve" if labelled else f"(lambda x: {function_code})"
    lines = [
        "",
        f"def {variable}_build():",
        f"{INDENT}x0 = {_x_code(scene, obj, names)}",
        f"{INDENT}dx = {_h_code(scene, obj, names)}",
        *([f"{INDENT}curve = lambda x: {function_code}"] if labelled else []),
        f"{INDENT}y0 = {curve}(x0)",
        f"{INDENT}if abs(dx) < {graphs.SECANT_MIN_H!r}:",
        f"{INDENT * 2}# h = 0: the secant has become the tangent",
        f"{INDENT * 2}x1, y1 = x0, y0",
        f"{INDENT * 2}slope = (lambda x: {_slope_code(scene, graph, rename)})(x0)",
        f"{INDENT}else:",
        f"{INDENT * 2}x1 = x0 + dx",
        f"{INDENT * 2}y1 = {curve}(x1)",
        f"{INDENT * 2}slope = (y1 - y0) / dx",
        f"{INDENT}left, right = min(x0, x1) - {fmt_float(extend)}, max(x0, x1) + {fmt_float(extend)}",
    ]
    if labelled:
        # the label sits between the two points, on the secant
        lines += _side_lines(obj, "(x0 + x1) / 2", "(y0 + y1) / 2")
        parts.append(_live_label(obj, "s", axes_variable, "(x0 + x1) / 2", "(y0 + y1) / 2"))
    lines.append(f"{INDENT}return VGroup(")
    lines += [f"{INDENT * 2}{part}," for part in parts]
    lines += [f"{INDENT})", ""]
    return lines, f"always_redraw({variable}_build)"


_DIRECTIONS = {(1.0, 1.0): "UR", (1.0, -1.0): "DR", (0.0, 1.0): "UP", (0.0, -1.0): "DOWN"}


def _point_parts(
    axes_variable: str, x_code: str, y_code: str, obj: SceneObject, label: str | None, direction: tuple[float, float] = (1.0, 1.0)
) -> list[str]:
    point = f"{axes_variable}.c2p({x_code}, {y_code})"
    color = py_color(obj.fill_color)
    radius = fmt_float(param_float(obj.params, "radius", 0.08))
    parts = []
    if obj.params.get("show_lines", True) and obj.kind == ObjectKind.GRAPH_POINT:
        parts.append(f"{STUDIO_LINES}({axes_variable}, {point}, color={color}, stroke_width=2)")
    parts.append(f"Dot({point}, radius={radius}, color={color})")
    if label is not None:
        buff = fmt_float(param_float(obj.params, "radius", 0.08) + SMALL_BUFF)
        parts.append(f"Text({label}, font_size={fmt_float(POINT_LABEL_SIZE)}, color={color}).next_to({point}, {_DIRECTIONS[direction]}, buff={buff})")
    return parts


def _group(parts: list[str]) -> str:
    if len(parts) == 1:
        return parts[0]
    return "VGroup(\n" + "".join(f"{INDENT}{part},\n" for part in parts) + ")"


def graph_point_code(scene: Scene, obj: SceneObject, names: dict[str, str], variable: str, dynamic: bool) -> tuple[list[str], str]:
    graph, _graph_variable, axes_variable = _tool_parts(scene, obj, names)
    show_label = bool(obj.params.get("show_label"))
    if not dynamic:
        point = graphs.graph_point(scene, obj)
        if point is None:
            raise CodegenError("point_undefined", obj.name)
        x0, y0 = point
        label = py_str(graphs.point_label(x0, y0)) if show_label else None
        return [], _group(_point_parts(axes_variable, fmt_float(x0), fmt_float(y0), obj, label))
    rename = renames(scene, names)
    function_code = pieces_code(_function_pieces(scene, graph), rename)
    label = 'f"({x0:.2f} | {y0:.2f})"' if show_label else None
    body = _group(_point_parts(axes_variable, "x0", "y0", obj, label)).split("\n")
    lines = [
        "",
        f"def {variable}_build():",
        f"{INDENT}x0 = {_x_code(scene, obj, names)}",
        f"{INDENT}y0 = (lambda x: {function_code})(x0)",
        f"{INDENT}return {body[0]}",
    ]
    lines += [f"{INDENT}{line}" for line in body[1:]]
    return lines + [""], f"always_redraw({variable}_build)"


def markers_code(scene: Scene, obj: SceneObject, names: dict[str, str]) -> str:
    _graph, _graph_variable, axes_variable = _tool_parts(scene, obj, names)
    if obj.params.get("feature") == "intersections":
        other = scene.object_by_id(obj.params.get("other_graph_id"))
        if other is None or not graphs.is_function_curve(other):
            raise CodegenError("other_graph_missing", obj.name)
    parts: list[str] = []
    for special in graphs.marker_points(scene, obj):
        label = py_str(graphs.point_label(special.x, special.y)) if obj.params.get("show_labels", True) else None
        direction = graphs.marker_label_direction(scene, obj, special)
        parts += _point_parts(axes_variable, fmt_float(special.x), fmt_float(special.y), obj, label, direction)
    if not parts:
        return "VGroup()"
    return "VGroup(\n" + "".join(f"{INDENT}{part},\n" for part in parts) + ")"


def label_code(scene: Scene, obj: SceneObject, names: dict[str, str]) -> list[str]:
    _graph, graph_variable, axes_variable = _tool_parts(scene, obj, names)
    text = str(obj.params.get("text", ""))
    size = fmt_float(param_float(obj.params, "font_size", 36.0))
    label = f"MathTex({py_str(text, prefer_raw=True)}, font_size={size})" if obj.params.get("use_latex") else f"Text({py_str(text)}, font_size={size})"
    kwargs = [
        ("label", label),
        ("x_val", fmt_float(param_float(obj.params, "x_value", 2.0))),
        ("direction", MANIM_DIRECTIONS.get(str(obj.params.get("direction", "up_right")), "UR")),
        ("color", py_color(obj.fill_color)),
    ]
    return call(f"{axes_variable}.get_graph_label", [graph_variable], kwargs, 2)


def axis_label_lines(obj: SceneObject, variable: str) -> list[str]:
    """``axes.add(axes.get_x_axis_label(...))`` for the labels set on a coordinate system."""
    lines = []
    for key, method in (("x_label", "get_x_axis_label"), ("y_label", "get_y_axis_label")):
        text = str(obj.params.get(key, "")).strip()
        if text:
            lines.append(f"{variable}.add({variable}.{method}(Text({py_str(text)}, font_size={fmt_float(AXIS_LABEL_SIZE)})))")
    return lines


# --- dispatch -----------------------------------------------------------------------------------------


def _wrap_dynamic(expression_lines: list[str], dynamic: bool) -> list[str]:
    if not dynamic:
        return expression_lines
    if len(expression_lines) == 1:
        return [f"always_redraw(lambda: {expression_lines[0]})"]
    return ["always_redraw(", f"{INDENT}lambda: {expression_lines[0]}"] + [f"{INDENT}{line}" for line in expression_lines[1:]] + [")"]


def graph_object_code(scene: Scene, obj: SceneObject, names: dict[str, str], helpers: set[str]) -> tuple[list[str], bool] | None:
    """Return ``(lines, needs_placement)`` for graphs, graph tools and parameters, else ``None``."""
    variable = names[obj.id]
    if obj.kind == ObjectKind.PARAMETER:
        return parameter_code(obj, variable), False
    if obj.kind == ObjectKind.FUNCTION_GRAPH:
        dynamic = is_dynamic(scene, obj)
        bound = bound_axes(scene, obj) is not None
        lines = _wrap_dynamic(graph_constructor(scene, obj, names, helpers), dynamic and bound)
        if dynamic and not bound:
            lines = _wrap_dynamic(_with_placement(graph_constructor(scene, obj, names, helpers), obj), True)
            return _assign(variable, lines), False
        return _assign(variable, lines), not bound
    if obj.kind not in GRAPH_TOOL_KINDS:
        return None
    lines, placement = _tool_code(scene, obj, names, variable)
    code = "\n".join(lines)
    if f"{STUDIO_LINES}(" in code:
        helpers.update((STUDIO_LINES, STUDIO_DASHED))
    for name in (STUDIO_DASHED, STUDIO_TERM, STUDIO_BESIDE):
        if f"{name}(" in code:
            helpers.add(name)
    return lines, placement


def _tool_code(scene: Scene, obj: SceneObject, names: dict[str, str], variable: str) -> tuple[list[str], bool]:
    dynamic = is_dynamic(scene, obj)
    if obj.kind in (ObjectKind.TANGENT, ObjectKind.SECANT):
        build = tangent_code if obj.kind == ObjectKind.TANGENT else secant_code
        definition, expression = build(scene, obj, names, variable, dynamic)
        return definition + _assign(variable, expression.split("\n")), False
    if obj.kind == ObjectKind.GRAPH_POINT:
        definition, expression = graph_point_code(scene, obj, names, variable, dynamic)
        return definition + _assign(variable, expression.split("\n")), False
    if obj.kind == ObjectKind.GRAPH_MARKERS:
        return _assign(variable, markers_code(scene, obj, names).split("\n")), False
    builders = {ObjectKind.GRAPH_AREA: area_code, ObjectKind.RIEMANN: riemann_code, ObjectKind.GRAPH_LABEL: label_code}
    return _assign(variable, _wrap_dynamic(builders[obj.kind](scene, obj, names), dynamic)), False


def _with_placement(lines: list[str], obj: SceneObject) -> list[str]:
    from manim_studio.codegen.literals import py_degrees, py_point

    suffix = f".move_to({py_point(obj.x, obj.y)})"
    if round(obj.rotation, 6) != 0:
        suffix += f".rotate({py_degrees(obj.rotation)})"
    return lines[:-1] + [lines[-1] + suffix]


def _assign(variable: str, lines: list[str]) -> list[str]:
    return [f"{variable} = {lines[0]}"] + lines[1:]


#: Dashed helper lines that may have length 0 (a point on an axis, a secant with
#: h = 0); Manim 0.19 fails on a ``DashedLine`` of length 0.
STUDIO_DASHED_SOURCE = '''def studio_dashed_line(start, end, **kwargs):
    """A DashedLine that may also have length 0 (it is then invisibly short)."""
    start, end = np.array(start, dtype=float), np.array(end, dtype=float)
    if np.linalg.norm(end - start) < 1e-6:
        end = start + np.array([1e-6, 0.0, 0.0])
    return DashedLine(start, end, **kwargs)'''

STUDIO_LINES_SOURCE = '''def studio_lines_to_point(axes, point, **kwargs):
    """Like axes.get_lines_to_point, but also for points on an axis."""
    return VGroup(*(studio_dashed_line(axis.get_projection(point), point, **kwargs) for axis in (axes.y_axis, axes.x_axis)))'''

#: Text of a tangent's or secant's label; ``graphs.line_term`` (stage) does the same.
STUDIO_TERM_SOURCE = '''def studio_term(name, slope, intercept, decimals, style):
    """Label of a tangent or secant, e.g. "t(x) = 1.50x − 0.25" (style "term"), "y = …" or "m = …"."""
    m, b = f"{abs(slope):.{decimals}f}", f"{abs(intercept):.{decimals}f}"
    m = ("−" if slope < 0 and float(m) != 0 else "") + m
    if style == "slope":
        return f"m = {m}"
    sign = "−" if intercept < 0 and float(b) != 0 else "+"
    left = "y" if style == "equation" else f"{name}(x)"
    return f"{left} = {m}x {sign} {b}"'''

#: Places such a label next to its line, like the stage does.
STUDIO_BESIDE_SOURCE = '''def studio_beside(label, axes, x, y, slope, side, buff=0.15):
    """Put a label next to the line through (x, y) with this slope: above it (side 1) or below (side -1)."""
    point = axes.c2p(x, y)
    direction = axes.c2p(x + 1, y + slope) - point
    normal = side * np.array([-direction[1], direction[0], 0.0]) / np.linalg.norm(direction)
    # move the label away from the line until its box only touches the line's parallel at distance buff
    distance = abs(normal[0]) * label.width / 2 + abs(normal[1]) * label.height / 2 + buff
    return label.move_to(point + distance * normal)'''

#: Source of the clipping plot helper, emitted once per script when needed.
STUDIO_PLOT_SOURCE = '''def studio_plot(axes, function, x_range, y_range=None, breaks=(), **kwargs):
    """Plot y = f(x) on axes, leaving out parts that are undefined or outside y_range.

    The pieces are joined into one curve so it can be animated and used for
    areas like a normal graph. ``breaks`` splits the curve (piecewise functions).
    """
    x_min, x_max = x_range[0], x_range[1]

    def inside(x):
        with np.errstate(all="ignore"):
            try:
                y = float(function(x))
            except (ArithmeticError, ValueError):
                return False
        if not np.isfinite(y):
            return False
        return y_range is None or y_range[0] - 1e-9 <= y <= y_range[1] + 1e-9

    def edge(good, bad):
        for _ in range(40):
            middle = (good + bad) / 2
            if inside(middle):
                good = middle
            else:
                bad = middle
        return good

    intervals = []
    bounds = [x_min] + [b for b in sorted(breaks) if x_min < b < x_max] + [x_max]
    for low, high in zip(bounds[:-1], bounds[1:]):
        if high < x_max:
            high -= 1e-9
        samples = np.linspace(low, high, 400)
        start = None
        previous = None
        for x in samples:
            if inside(x):
                if start is None:
                    start = x if previous is None else edge(x, previous)
            elif start is not None:
                intervals.append((start, edge(previous, x)))
                start = None
            previous = x
        if start is not None:
            end = high if inside(high) else edge(previous, high)
            intervals.append((start, end))
    pieces = [axes.plot(function, x_range=[a, b], **kwargs) for a, b in intervals if b - a > 1e-6]
    if not pieces:
        graph = axes.plot(lambda x: 0 * x, x_range=[x_min, x_max], **kwargs)
        return graph.set_stroke(opacity=0)
    graph = pieces[0]
    for piece in pieces[1:]:
        graph.append_points(piece.points)
    graph.t_min, graph.t_max = x_min, x_max
    graph.underlying_function = function
    return graph'''
