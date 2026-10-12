"""Declarative description of object and animation parameters.

The schema drives the property panel, default values, stage scaling and
validation, so new parameters only need to be declared here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from manim_studio.model.data import DATA_STYLES, REGRESSIONS
from manim_studio.model.types import (
    CAMERA_ANIMATIONS,
    CURVE_DERIVATIVE,
    CURVE_FUNCTION,
    CURVE_IMPLICIT,
    CURVE_PARAMETRIC,
    CURVE_PIECEWISE,
    CURVE_POLAR,
    CURVES,
    FUNCTION_CURVES,
    HIGHLIGHT_STYLES,
    MOTION_ANIMATIONS,
    TRANSFORM_ANIMATIONS,
    AnimationKind,
    ObjectKind,
)


class ParamType(str, Enum):
    """Editor type of a parameter."""

    FLOAT = "float"
    INT = "int"
    BOOL = "bool"
    STRING = "string"
    TEXT = "text"
    LATEX = "latex"
    EXPRESSION = "expression"
    COLOR = "color"
    CHOICE = "choice"
    FILE = "file"
    OBJECT_REF = "object_ref"
    FONT = "font"
    POINTS = "points"
    TABLE = "table"
    WORD_COLORS = "word_colors"
    PIECES = "pieces"
    DATA = "data"
    BARS = "bars"


@dataclass(frozen=True)
class ParamSpec:
    """Description of one editable parameter."""

    key: str
    type: ParamType
    default: Any
    minimum: float | None = None
    maximum: float | None = None
    step: float = 0.1
    decimals: int = 2
    choices: tuple[str, ...] = ()
    scalable: bool = False
    ref_kinds: tuple[ObjectKind, ...] = ()
    optional: bool = False
    visible_when: tuple[str, tuple[Any, ...]] | None = None
    variable: str = "x"
    #: Further names a term may use (e.g. ``y`` for surfaces z = f(x, y)).
    extra_names: tuple[str, ...] = ()

    def is_visible(self, params: dict[str, Any], defaults: dict[str, Any] | None = None) -> bool:
        """Return ``True`` if the parameter applies with the given other values."""
        if self.visible_when is None:
            return True
        key, allowed = self.visible_when
        value = params.get(key, (defaults or {}).get(key))
        return value in allowed


#: Style attributes stored directly on :class:`SceneObject`.
STYLE_FIELDS = ("stroke_color", "stroke_width", "stroke_opacity", "fill_color", "fill_opacity")

_SHAPE_STYLE = frozenset(STYLE_FIELDS)
_LINE_STYLE = frozenset({"stroke_color", "stroke_width", "stroke_opacity"})
_TEXT_STYLE = frozenset({"fill_color", "fill_opacity"})
_AXES_STYLE = frozenset({"stroke_color", "stroke_width"})


@dataclass(frozen=True)
class KindInfo:
    """Static information about one object kind."""

    kind: ObjectKind
    params: tuple[ParamSpec, ...]
    style: frozenset[str]
    default_style: tuple[tuple[str, Any], ...] = ()

    def param(self, key: str) -> ParamSpec | None:
        """Return the spec of a parameter or ``None``."""
        for spec in self.params:
            if spec.key == key:
                return spec
        return None


def _length(key: str, default: float, minimum: float = 0.01) -> ParamSpec:
    return ParamSpec(key, ParamType.FLOAT, default, minimum=minimum, maximum=100.0, scalable=True)


def _range_params(prefix: str, low: float, high: float, step: float, length: float) -> tuple[ParamSpec, ...]:
    return (
        ParamSpec(f"{prefix}_min", ParamType.FLOAT, low, minimum=-1000.0, maximum=1000.0, step=1.0),
        ParamSpec(f"{prefix}_max", ParamType.FLOAT, high, minimum=-1000.0, maximum=1000.0, step=1.0),
        ParamSpec(f"{prefix}_step", ParamType.FLOAT, step, minimum=0.01, maximum=1000.0, step=0.5),
        _length(f"{prefix}_length", length, minimum=0.1),
    )


ALIGNMENTS = ("left", "center", "right")
CODE_LANGUAGES = ("python", "javascript", "typescript", "java", "c", "cpp", "csharp", "rust", "go", "html", "css", "bash", "json", "sql", "latex")


#: Areas: below the graph (to the x-axis), between two graphs, or up/down to the edge of the axes.
AREA_MODES = ("under", "between", "above", "below")
MARKER_FEATURES = ("zeros", "extrema", "inflection", "intersections")
LABEL_DIRECTIONS = ("up_right", "up", "right", "down_right", "down", "down_left", "left", "up_left")
_GRAPH_REF = ParamSpec("graph_id", ParamType.OBJECT_REF, None, ref_kinds=(ObjectKind.FUNCTION_GRAPH,))


def _font_size(default: float, key: str = "font_size") -> ParamSpec:
    return ParamSpec(key, ParamType.FLOAT, default, minimum=1.0, maximum=500.0, step=1.0, decimals=1, scalable=True)


#: Bullets of a list: dot, dash, numbers, letters or nothing.
BULLET_CHOICES = ("dot", "dash", "number", "letter", "none")

_WHITE = "#FFFFFF"
_YELLOW = "#F7D96F"

KIND_INFO: dict[ObjectKind, KindInfo] = {
    ObjectKind.CIRCLE: KindInfo(ObjectKind.CIRCLE, (_length("radius", 1.0),), _SHAPE_STYLE),
    ObjectKind.SQUARE: KindInfo(
        ObjectKind.SQUARE,
        (_length("side_length", 2.0),),
        _SHAPE_STYLE,
        (("stroke_color", "#FC6255"), ("fill_color", "#FC6255")),
    ),
    ObjectKind.RECTANGLE: KindInfo(
        ObjectKind.RECTANGLE,
        (_length("width", 4.0), _length("height", 2.0)),
        _SHAPE_STYLE,
        (("stroke_color", "#83C167"), ("fill_color", "#83C167")),
    ),
    ObjectKind.TRIANGLE: KindInfo(
        ObjectKind.TRIANGLE,
        (_length("radius", 1.0),),
        _SHAPE_STYLE,
        (("stroke_color", _YELLOW), ("fill_color", _YELLOW)),
    ),
    ObjectKind.ELLIPSE: KindInfo(
        ObjectKind.ELLIPSE,
        (_length("width", 3.0), _length("height", 1.5)),
        _SHAPE_STYLE,
        (("stroke_color", "#D147BD"), ("fill_color", "#D147BD")),
    ),
    ObjectKind.LINE: KindInfo(
        ObjectKind.LINE, (_length("length", 3.0),), _LINE_STYLE, (("stroke_color", _WHITE),)
    ),
    ObjectKind.ARROW: KindInfo(
        ObjectKind.ARROW, (_length("length", 3.0),), _LINE_STYLE, (("stroke_color", _WHITE),)
    ),
    ObjectKind.DOT: KindInfo(
        ObjectKind.DOT,
        (_length("radius", 0.08, minimum=0.005),),
        _TEXT_STYLE,
        (("fill_color", _WHITE), ("fill_opacity", 1.0)),
    ),
    ObjectKind.TEXT: KindInfo(
        ObjectKind.TEXT,
        (
            ParamSpec("text", ParamType.TEXT, "Text"),
            _font_size(48.0),
            ParamSpec("font", ParamType.FONT, ""),
            ParamSpec("bold", ParamType.BOOL, False),
            ParamSpec("italic", ParamType.BOOL, False),
            ParamSpec("alignment", ParamType.CHOICE, "left", choices=ALIGNMENTS),
            ParamSpec("line_spacing", ParamType.FLOAT, 0.0, minimum=0.0, maximum=5.0, step=0.1),
            ParamSpec("colored_words", ParamType.WORD_COLORS, []),
        ),
        _TEXT_STYLE,
        (("fill_color", _WHITE), ("fill_opacity", 1.0)),
    ),
    ObjectKind.MATH_TEX: KindInfo(
        ObjectKind.MATH_TEX,
        (
            ParamSpec("latex", ParamType.LATEX, r"e^{i\pi} + 1 = 0"),
            ParamSpec("font_size", ParamType.FLOAT, 48.0, minimum=1.0, maximum=500.0, step=1.0, decimals=1, scalable=True),
            ParamSpec("colored_parts", ParamType.WORD_COLORS, []),
        ),
        _TEXT_STYLE,
        (("fill_color", _WHITE), ("fill_opacity", 1.0)),
    ),
    ObjectKind.AXES: KindInfo(
        ObjectKind.AXES,
        _range_params("x", -5.0, 5.0, 1.0, 10.0)
        + _range_params("y", -3.0, 3.0, 1.0, 6.0)
        + (
            ParamSpec("show_numbers", ParamType.BOOL, False),
            ParamSpec("tips", ParamType.BOOL, True),
            ParamSpec("x_label", ParamType.STRING, ""),
            ParamSpec("y_label", ParamType.STRING, ""),
        ),
        _AXES_STYLE,
        (("stroke_color", _WHITE), ("stroke_width", 2.0)),
    ),
    ObjectKind.NUMBER_PLANE: KindInfo(
        ObjectKind.NUMBER_PLANE,
        _range_params("x", -7.0, 7.0, 1.0, 14.0)
        + _range_params("y", -4.0, 4.0, 1.0, 8.0)
        + (
            ParamSpec("grid", ParamType.CHOICE, "cartesian", choices=("cartesian", "polar")),
            ParamSpec("azimuth_divisions", ParamType.INT, 12, minimum=2, maximum=72, visible_when=("grid", ("polar",))),
        ),
        frozenset({"stroke_color", "stroke_width", "stroke_opacity"}),
        (("stroke_color", "#29ABCA"), ("stroke_width", 2.0)),
    ),
    ObjectKind.FUNCTION_GRAPH: KindInfo(
        ObjectKind.FUNCTION_GRAPH,
        (
            ParamSpec("curve", ParamType.CHOICE, CURVE_FUNCTION, choices=CURVES),
            ParamSpec("expression", ParamType.EXPRESSION, "sin(x)", visible_when=("curve", (CURVE_FUNCTION,))),
            ParamSpec(
                "derive_from",
                ParamType.OBJECT_REF,
                None,
                ref_kinds=(ObjectKind.FUNCTION_GRAPH,),
                visible_when=("curve", (CURVE_DERIVATIVE,)),
            ),
            ParamSpec("derive_order", ParamType.CHOICE, "1", choices=("1", "2"), visible_when=("curve", (CURVE_DERIVATIVE,))),
            ParamSpec("pieces", ParamType.PIECES, [["x^2", "-5", "1"], ["2 - x", "1", "5"]], visible_when=("curve", (CURVE_PIECEWISE,))),
            ParamSpec("x_expression", ParamType.EXPRESSION, "2cos(t)", visible_when=("curve", (CURVE_PARAMETRIC,)), variable="t"),
            ParamSpec("y_expression", ParamType.EXPRESSION, "sin(2t)", visible_when=("curve", (CURVE_PARAMETRIC,)), variable="t"),
            ParamSpec("r_expression", ParamType.EXPRESSION, "2sin(3t)", visible_when=("curve", (CURVE_POLAR,)), variable="t"),
            ParamSpec("implicit_expression", ParamType.EXPRESSION, "x^2 + y^2 - 4", visible_when=("curve", (CURVE_IMPLICIT,)), extra_names=("y",)),
            ParamSpec("x_min", ParamType.FLOAT, -5.0, minimum=-1000.0, maximum=1000.0, step=0.5, visible_when=("curve", FUNCTION_CURVES)),
            ParamSpec("x_max", ParamType.FLOAT, 5.0, minimum=-1000.0, maximum=1000.0, step=0.5, visible_when=("curve", FUNCTION_CURVES)),
            ParamSpec("t_min", ParamType.FLOAT, 0.0, minimum=-1000.0, maximum=1000.0, step=0.5, visible_when=("curve", (CURVE_PARAMETRIC, CURVE_POLAR))),
            ParamSpec("t_max", ParamType.FLOAT, 6.2832, minimum=-1000.0, maximum=1000.0, step=0.5, decimals=4, visible_when=("curve", (CURVE_PARAMETRIC, CURVE_POLAR))),
            ParamSpec(
                "axes_id",
                ParamType.OBJECT_REF,
                None,
                ref_kinds=(ObjectKind.AXES, ObjectKind.NUMBER_PLANE),
                optional=True,
            ),
            ParamSpec("clip", ParamType.BOOL, True, visible_when=("curve", FUNCTION_CURVES)),
        ),
        _LINE_STYLE,
        (("stroke_color", _YELLOW),),
    ),
    ObjectKind.IMAGE: KindInfo(
        ObjectKind.IMAGE,
        (
            ParamSpec("path", ParamType.FILE, ""),
            _length("height", 2.0),
            ParamSpec("opacity", ParamType.FLOAT, 1.0, minimum=0.0, maximum=1.0, step=0.05),
        ),
        frozenset(),
    ),
    ObjectKind.NUMBER_LINE: KindInfo(
        ObjectKind.NUMBER_LINE,
        (
            ParamSpec("x_min", ParamType.FLOAT, -5.0, minimum=-1000.0, maximum=1000.0, step=1.0),
            ParamSpec("x_max", ParamType.FLOAT, 5.0, minimum=-1000.0, maximum=1000.0, step=1.0),
            ParamSpec("x_step", ParamType.FLOAT, 1.0, minimum=0.01, maximum=1000.0, step=0.5),
            _length("length", 10.0, minimum=0.1),
            ParamSpec("show_numbers", ParamType.BOOL, True),
            ParamSpec("tips", ParamType.BOOL, False),
        ),
        _AXES_STYLE,
        (("stroke_color", _WHITE), ("stroke_width", 2.0)),
    ),
    ObjectKind.VECTOR: KindInfo(ObjectKind.VECTOR, (_length("length", 2.0),), _LINE_STYLE, (("stroke_color", _YELLOW),)),
    ObjectKind.DOUBLE_ARROW: KindInfo(
        ObjectKind.DOUBLE_ARROW, (_length("length", 3.0),), _LINE_STYLE, (("stroke_color", _WHITE),)
    ),
    ObjectKind.CURVED_ARROW: KindInfo(
        ObjectKind.CURVED_ARROW,
        (
            _length("length", 3.0),
            ParamSpec("angle", ParamType.FLOAT, 60.0, minimum=-330.0, maximum=330.0, step=15.0, decimals=1),
            ParamSpec("tips_at", ParamType.CHOICE, "end", choices=("end", "both", "none")),
        ),
        _LINE_STYLE,
        (("stroke_color", _WHITE),),
    ),
    ObjectKind.DASHED_LINE: KindInfo(
        ObjectKind.DASHED_LINE,
        (
            _length("length", 3.0),
            ParamSpec("dash_length", ParamType.FLOAT, 0.15, minimum=0.02, maximum=5.0, step=0.05, scalable=True),
            ParamSpec("dashed_ratio", ParamType.FLOAT, 0.5, minimum=0.05, maximum=0.95, step=0.05),
        ),
        _LINE_STYLE,
        (("stroke_color", _WHITE),),
    ),
    ObjectKind.HIGHLIGHT: KindInfo(
        ObjectKind.HIGHLIGHT,
        (
            ParamSpec("target", ParamType.OBJECT_REF, None),
            ParamSpec("style", ParamType.CHOICE, "frame", choices=HIGHLIGHT_STYLES),
            ParamSpec("buff", ParamType.FLOAT, 0.15, minimum=0.0, maximum=3.0, step=0.05),
            ParamSpec("corner_radius", ParamType.FLOAT, 0.1, minimum=0.0, maximum=2.0, step=0.05, visible_when=("style", ("frame",))),
            ParamSpec("opacity", ParamType.FLOAT, 0.75, minimum=0.0, maximum=1.0, step=0.05, visible_when=("style", ("background",))),
        ),
        _SHAPE_STYLE,
        (("stroke_color", "#F7D96F"), ("fill_color", "#000000"), ("fill_opacity", 0.0), ("stroke_width", 4.0)),
    ),
    ObjectKind.ANGLE: KindInfo(
        ObjectKind.ANGLE,
        (
            ParamSpec("first_line", ParamType.OBJECT_REF, None),
            ParamSpec("second_line", ParamType.OBJECT_REF, None),
            ParamSpec("radius", ParamType.FLOAT, 0.6, minimum=0.05, maximum=10.0, step=0.1),
            ParamSpec("right_angle", ParamType.BOOL, False),
            ParamSpec("flip_first", ParamType.BOOL, False),
            ParamSpec("flip_second", ParamType.BOOL, False),
            ParamSpec("reflex", ParamType.BOOL, False),
            ParamSpec("label", ParamType.CHOICE, "none", choices=("none", "symbol", "degrees")),
            ParamSpec("symbol", ParamType.STRING, "α", visible_when=("label", ("symbol",))),
            ParamSpec("decimals", ParamType.INT, 0, minimum=0, maximum=4, visible_when=("label", ("degrees",))),
            _font_size(32.0, key="label_size"),
        ),
        _LINE_STYLE,
        (("stroke_color", "#F7D96F"),),
    ),
    ObjectKind.NETWORK: KindInfo(
        ObjectKind.NETWORK,
        (
            ParamSpec("vertices", ParamType.TEXT, "A, B, C, D"),
            ParamSpec("edges", ParamType.TEXT, "A-B\nB-C\nC-D\nD-A\nA-C"),
            ParamSpec("directed", ParamType.BOOL, False),
            ParamSpec("layout", ParamType.CHOICE, "circular", choices=("circular", "spring", "kamada_kawai", "shell", "spiral", "tree")),
            ParamSpec("seed", ParamType.INT, 1, minimum=0, maximum=9999, visible_when=("layout", ("spring",))),
            ParamSpec("layout_scale", ParamType.FLOAT, 2.0, minimum=0.2, maximum=20.0, step=0.1, scalable=True),
            ParamSpec("radius", ParamType.FLOAT, 0.3, minimum=0.02, maximum=5.0, step=0.05, scalable=True),
            ParamSpec("labels", ParamType.BOOL, True),
            _font_size(28.0, key="label_size"),
            ParamSpec("label_color", ParamType.COLOR, "#000000", visible_when=("labels", (True,))),
        ),
        _SHAPE_STYLE,
        (("stroke_color", _WHITE), ("stroke_width", 3.0), ("fill_color", "#58C4DD"), ("fill_opacity", 1.0)),
    ),
    ObjectKind.BULLET_LIST: KindInfo(
        ObjectKind.BULLET_LIST,
        (
            ParamSpec("items", ParamType.TEXT, "1\n2\n3"),
            ParamSpec("bullet", ParamType.CHOICE, "dot", choices=BULLET_CHOICES),
            _font_size(36.0),
            ParamSpec("font", ParamType.FONT, ""),
            ParamSpec("bold", ParamType.BOOL, False),
            ParamSpec("buff", ParamType.FLOAT, 0.25, minimum=0.0, maximum=5.0, step=0.05, scalable=True),
        ),
        _TEXT_STYLE,
        (("fill_color", _WHITE), ("fill_opacity", 1.0)),
    ),
    ObjectKind.SOLID: KindInfo(
        ObjectKind.SOLID,
        (
            ParamSpec("axes_id", ParamType.OBJECT_REF, None),
            ParamSpec(
                "shape",
                ParamType.CHOICE,
                "sphere",
                choices=("sphere", "cube", "prism", "cone", "cylinder", "torus", "tetrahedron", "octahedron", "icosahedron", "dodecahedron"),
            ),
            ParamSpec("center_x", ParamType.FLOAT, 0.0, minimum=-1000.0, maximum=1000.0, step=0.5),
            ParamSpec("center_y", ParamType.FLOAT, 0.0, minimum=-1000.0, maximum=1000.0, step=0.5),
            ParamSpec("center_z", ParamType.FLOAT, 0.0, minimum=-1000.0, maximum=1000.0, step=0.5),
            ParamSpec("radius", ParamType.FLOAT, 1.0, minimum=0.05, maximum=50.0, step=0.1, visible_when=("shape", ("sphere", "cone", "cylinder", "torus"))),
            ParamSpec("minor_radius", ParamType.FLOAT, 0.3, minimum=0.01, maximum=50.0, step=0.05, visible_when=("shape", ("torus",))),
            ParamSpec(
                "side", ParamType.FLOAT, 2.0, minimum=0.05, maximum=50.0, step=0.1, visible_when=("shape", ("cube", "tetrahedron", "octahedron", "icosahedron", "dodecahedron"))
            ),
            ParamSpec("width", ParamType.FLOAT, 3.0, minimum=0.05, maximum=50.0, step=0.1, visible_when=("shape", ("prism",))),
            ParamSpec("depth", ParamType.FLOAT, 2.0, minimum=0.05, maximum=50.0, step=0.1, visible_when=("shape", ("prism",))),
            ParamSpec("height", ParamType.FLOAT, 2.0, minimum=0.05, maximum=50.0, step=0.1, visible_when=("shape", ("prism", "cone", "cylinder"))),
            ParamSpec("resolution", ParamType.INT, 16, minimum=4, maximum=48, visible_when=("shape", ("sphere", "cone", "cylinder", "torus"))),
            ParamSpec("show_vertices", ParamType.BOOL, False, visible_when=("shape", ("tetrahedron", "octahedron", "icosahedron", "dodecahedron"))),
        ),
        _SHAPE_STYLE,
        (("stroke_color", "#29ABCA"), ("fill_color", "#58C4DD"), ("fill_opacity", 0.75), ("stroke_width", 0.5)),
    ),
    ObjectKind.VECTOR_3D: KindInfo(
        ObjectKind.VECTOR_3D,
        (
            ParamSpec("axes_id", ParamType.OBJECT_REF, None, ref_kinds=(ObjectKind.AXES_3D,)),
            ParamSpec("element", ParamType.CHOICE, "arrow", choices=("arrow", "line", "point")),
            ParamSpec("from_x", ParamType.FLOAT, 0.0, minimum=-1000.0, maximum=1000.0, step=0.5, visible_when=("element", ("arrow", "line"))),
            ParamSpec("from_y", ParamType.FLOAT, 0.0, minimum=-1000.0, maximum=1000.0, step=0.5, visible_when=("element", ("arrow", "line"))),
            ParamSpec("from_z", ParamType.FLOAT, 0.0, minimum=-1000.0, maximum=1000.0, step=0.5, visible_when=("element", ("arrow", "line"))),
            ParamSpec("to_x", ParamType.FLOAT, 2.0, minimum=-1000.0, maximum=1000.0, step=0.5),
            ParamSpec("to_y", ParamType.FLOAT, 1.0, minimum=-1000.0, maximum=1000.0, step=0.5),
            ParamSpec("to_z", ParamType.FLOAT, 2.0, minimum=-1000.0, maximum=1000.0, step=0.5),
            ParamSpec("radius", ParamType.FLOAT, 0.08, minimum=0.01, maximum=5.0, step=0.02, visible_when=("element", ("point",))),
        ),
        _LINE_STYLE,
        (("stroke_color", "#FC6255"), ("fill_color", "#FC6255"), ("stroke_width", 4.0)),
    ),
    ObjectKind.VECTOR_FIELD: KindInfo(
        ObjectKind.VECTOR_FIELD,
        (
            ParamSpec("x_expression", ParamType.EXPRESSION, "-y", extra_names=("y",)),
            ParamSpec("y_expression", ParamType.EXPRESSION, "x", extra_names=("y",)),
            ParamSpec("display", ParamType.CHOICE, "arrows", choices=("arrows", "stream")),
            ParamSpec("x_min", ParamType.FLOAT, -7.0, minimum=-100.0, maximum=100.0, step=0.5),
            ParamSpec("x_max", ParamType.FLOAT, 7.0, minimum=-100.0, maximum=100.0, step=0.5),
            ParamSpec("y_min", ParamType.FLOAT, -4.0, minimum=-100.0, maximum=100.0, step=0.5),
            ParamSpec("y_max", ParamType.FLOAT, 4.0, minimum=-100.0, maximum=100.0, step=0.5),
            ParamSpec("step", ParamType.FLOAT, 0.5, minimum=0.1, maximum=10.0, step=0.1),
            ParamSpec("colored", ParamType.BOOL, True),
            ParamSpec("max_color", ParamType.FLOAT, 2.0, minimum=0.01, maximum=1000.0, step=0.5, visible_when=("colored", (True,))),
            ParamSpec("virtual_time", ParamType.FLOAT, 3.0, minimum=0.1, maximum=20.0, step=0.5, visible_when=("display", ("stream",))),
            ParamSpec("flow", ParamType.BOOL, True, visible_when=("display", ("stream",))),
            ParamSpec("flow_speed", ParamType.FLOAT, 1.0, minimum=0.1, maximum=10.0, step=0.1, visible_when=("display", ("stream",))),
        ),
        _LINE_STYLE,
        (("stroke_color", "#58C4DD"), ("stroke_width", 2.0)),
    ),
    ObjectKind.TRACE: KindInfo(
        ObjectKind.TRACE,
        (
            ParamSpec("target", ParamType.OBJECT_REF, None),
            ParamSpec("dissipating_time", ParamType.FLOAT, 0.0, minimum=0.0, maximum=60.0, step=0.25),
        ),
        _LINE_STYLE,
        (("stroke_color", "#F7D96F"), ("stroke_width", 3.0)),
    ),
    ObjectKind.BRACE: KindInfo(
        ObjectKind.BRACE,
        (
            ParamSpec("target", ParamType.OBJECT_REF, None, optional=True),
            ParamSpec("direction", ParamType.CHOICE, "down", choices=("down", "up", "left", "right")),
            ParamSpec("label", ParamType.STRING, ""),
            _font_size(36.0, key="label_size"),
            _length("width", 3.0),
            ParamSpec("buff", ParamType.FLOAT, 0.2, minimum=0.0, maximum=5.0, step=0.05),
        ),
        _TEXT_STYLE,
        (("fill_color", _WHITE), ("fill_opacity", 1.0)),
    ),
    ObjectKind.POLYGON: KindInfo(
        ObjectKind.POLYGON,
        (ParamSpec("points", ParamType.POINTS, [[-1.5, -1.0], [1.5, -1.0], [2.0, 0.8], [0.0, 1.6], [-2.0, 0.8]], scalable=True),),
        _SHAPE_STYLE,
        (("stroke_color", "#83C167"), ("fill_color", "#83C167")),
    ),
    ObjectKind.REGULAR_POLYGON: KindInfo(
        ObjectKind.REGULAR_POLYGON,
        (ParamSpec("n", ParamType.INT, 6, minimum=3, maximum=40), _length("radius", 1.0)),
        _SHAPE_STYLE,
        (("stroke_color", "#5CD0B3"), ("fill_color", "#5CD0B3")),
    ),
    ObjectKind.STAR: KindInfo(
        ObjectKind.STAR,
        (ParamSpec("n", ParamType.INT, 5, minimum=3, maximum=40), _length("outer_radius", 1.2), _length("inner_radius", 0.5)),
        _SHAPE_STYLE,
        (("stroke_color", _YELLOW), ("fill_color", _YELLOW), ("fill_opacity", 0.6)),
    ),
    ObjectKind.ARC: KindInfo(
        ObjectKind.ARC,
        (
            _length("radius", 1.5),
            ParamSpec("start_angle", ParamType.FLOAT, 0.0, minimum=-360.0, maximum=360.0, step=15.0, decimals=1),
            ParamSpec("angle", ParamType.FLOAT, 120.0, minimum=-360.0, maximum=360.0, step=15.0, decimals=1),
        ),
        _LINE_STYLE,
        (("stroke_color", _WHITE),),
    ),
    ObjectKind.SECTOR: KindInfo(
        ObjectKind.SECTOR,
        (
            _length("radius", 1.5),
            ParamSpec("start_angle", ParamType.FLOAT, 0.0, minimum=-360.0, maximum=360.0, step=15.0, decimals=1),
            ParamSpec("angle", ParamType.FLOAT, 90.0, minimum=-360.0, maximum=360.0, step=15.0, decimals=1),
        ),
        _SHAPE_STYLE,
        (("stroke_color", "#F0AC5F"), ("fill_color", "#F0AC5F"), ("fill_opacity", 0.6)),
    ),
    ObjectKind.ANNULUS: KindInfo(
        ObjectKind.ANNULUS,
        (_length("inner_radius", 0.7), _length("outer_radius", 1.3)),
        _SHAPE_STYLE,
        (("stroke_color", "#9A72AC"), ("fill_color", "#9A72AC"), ("fill_opacity", 0.6), ("stroke_width", 0.0)),
    ),
    ObjectKind.DECIMAL_NUMBER: KindInfo(
        ObjectKind.DECIMAL_NUMBER,
        (
            ParamSpec("value", ParamType.FLOAT, 0.0, minimum=-1e9, maximum=1e9, step=1.0, decimals=4),
            ParamSpec("decimals", ParamType.INT, 2, minimum=0, maximum=10),
            _font_size(48.0),
            ParamSpec("show_sign", ParamType.BOOL, False),
            ParamSpec("unit", ParamType.STRING, ""),
            ParamSpec("parameter_id", ParamType.OBJECT_REF, None, ref_kinds=(ObjectKind.PARAMETER,), optional=True),
            # a formula of parameters, e.g. a^2/2; when set it is shown instead of the value or parameter
            ParamSpec("formula", ParamType.EXPRESSION, ""),
        ),
        _TEXT_STYLE,
        (("fill_color", _WHITE), ("fill_opacity", 1.0)),
    ),
    ObjectKind.TABLE: KindInfo(
        ObjectKind.TABLE,
        (
            ParamSpec("rows", ParamType.TABLE, [["x", "f(x)"], ["1", "1"], ["2", "4"], ["3", "9"]]),
            _font_size(32.0),
            ParamSpec("outer_lines", ParamType.BOOL, True),
            ParamSpec("h_buff", ParamType.FLOAT, 1.0, minimum=0.05, maximum=10.0, step=0.1, scalable=True),
            ParamSpec("v_buff", ParamType.FLOAT, 0.5, minimum=0.05, maximum=10.0, step=0.1, scalable=True),
        ),
        frozenset({"stroke_color", "stroke_width", "fill_color"}),
        (("stroke_color", _WHITE), ("stroke_width", 2.0), ("fill_color", _WHITE)),
    ),
    ObjectKind.MATRIX: KindInfo(
        ObjectKind.MATRIX,
        (
            ParamSpec("rows", ParamType.TABLE, [["1", "0"], ["0", "1"]]),
            ParamSpec("h_buff", ParamType.FLOAT, 1.3, minimum=0.05, maximum=10.0, step=0.1, scalable=True),
            ParamSpec("v_buff", ParamType.FLOAT, 0.8, minimum=0.05, maximum=10.0, step=0.1, scalable=True),
        ),
        _TEXT_STYLE,
        (("fill_color", _WHITE), ("fill_opacity", 1.0)),
    ),
    ObjectKind.CODE: KindInfo(
        ObjectKind.CODE,
        (
            ParamSpec("code", ParamType.TEXT, "def quadrat(x):\n    return x ** 2"),
            ParamSpec("language", ParamType.CHOICE, "python", choices=CODE_LANGUAGES),
            _font_size(24.0),
            ParamSpec("line_numbers", ParamType.BOOL, True),
            ParamSpec("background", ParamType.CHOICE, "rectangle", choices=("rectangle", "window")),
        ),
        frozenset(),
    ),
    ObjectKind.TEX: KindInfo(
        ObjectKind.TEX,
        (ParamSpec("tex", ParamType.LATEX, r"Der Satz $a^2 + b^2 = c^2$"), _font_size(48.0)),
        _TEXT_STYLE,
        (("fill_color", _WHITE), ("fill_opacity", 1.0)),
    ),
    ObjectKind.MARKUP_TEXT: KindInfo(
        ObjectKind.MARKUP_TEXT,
        (
            ParamSpec("markup", ParamType.TEXT, '<b>Fett</b>, <i>kursiv</i> und <span fgcolor="#FC6255">rot</span>'),
            _font_size(48.0),
            ParamSpec("font", ParamType.FONT, ""),
        ),
        _TEXT_STYLE,
        (("fill_color", _WHITE), ("fill_opacity", 1.0)),
    ),
    ObjectKind.GROUP: KindInfo(ObjectKind.GROUP, (), frozenset()),
    ObjectKind.GRAPH_AREA: KindInfo(
        ObjectKind.GRAPH_AREA,
        (
            _GRAPH_REF,
            ParamSpec("mode", ParamType.CHOICE, "under", choices=AREA_MODES),
            ParamSpec("other_graph_id", ParamType.OBJECT_REF, None, ref_kinds=(ObjectKind.FUNCTION_GRAPH,), visible_when=("mode", ("between",))),
            ParamSpec("x_min", ParamType.FLOAT, -1.0, minimum=-1000.0, maximum=1000.0, step=0.5),
            ParamSpec("x_max", ParamType.FLOAT, 2.0, minimum=-1000.0, maximum=1000.0, step=0.5),
        ),
        frozenset({"fill_color", "fill_opacity"}),
        (("fill_color", "#58C4DD"), ("fill_opacity", 0.5), ("stroke_width", 0.0)),
    ),
    ObjectKind.RIEMANN: KindInfo(
        ObjectKind.RIEMANN,
        (
            _GRAPH_REF,
            ParamSpec("x_min", ParamType.FLOAT, 0.0, minimum=-1000.0, maximum=1000.0, step=0.5),
            ParamSpec("x_max", ParamType.FLOAT, 3.0, minimum=-1000.0, maximum=1000.0, step=0.5),
            ParamSpec("dx", ParamType.FLOAT, 0.25, minimum=0.01, maximum=100.0, step=0.05),
            ParamSpec("sample", ParamType.CHOICE, "left", choices=("left", "center", "right")),
        ),
        _SHAPE_STYLE,
        (("stroke_color", "#000000"), ("stroke_width", 1.0), ("fill_color", "#58C4DD"), ("fill_opacity", 0.7)),
    ),
    ObjectKind.TANGENT: KindInfo(
        ObjectKind.TANGENT,
        (
            _GRAPH_REF,
            ParamSpec("x_value", ParamType.FLOAT, 1.0, minimum=-1000.0, maximum=1000.0, step=0.25, decimals=3),
            ParamSpec("x_parameter", ParamType.OBJECT_REF, None, ref_kinds=(ObjectKind.PARAMETER,), optional=True),
            ParamSpec("width", ParamType.FLOAT, 3.0, minimum=0.05, maximum=1000.0, step=0.5),
            ParamSpec("label", ParamType.CHOICE, "none", choices=("none", "term", "equation", "slope")),
            ParamSpec("label_side", ParamType.CHOICE, "auto", choices=("auto", "above", "below"), visible_when=("label", ("term", "equation", "slope"))),
            ParamSpec("decimals", ParamType.INT, 2, minimum=0, maximum=4, visible_when=("label", ("term", "equation", "slope"))),
        ),
        _LINE_STYLE,
        (("stroke_color", "#FF862F"), ("stroke_width", 3.0)),
    ),
    ObjectKind.SECANT: KindInfo(
        ObjectKind.SECANT,
        (
            _GRAPH_REF,
            ParamSpec("x_value", ParamType.FLOAT, 1.0, minimum=-1000.0, maximum=1000.0, step=0.25, decimals=3),
            ParamSpec("x_parameter", ParamType.OBJECT_REF, None, ref_kinds=(ObjectKind.PARAMETER,), optional=True),
            ParamSpec("h", ParamType.FLOAT, 1.0, minimum=-1000.0, maximum=1000.0, step=0.1, decimals=3),
            ParamSpec("h_parameter", ParamType.OBJECT_REF, None, ref_kinds=(ObjectKind.PARAMETER,), optional=True),
            ParamSpec("extend", ParamType.FLOAT, 1.0, minimum=0.0, maximum=1000.0, step=0.25),
            ParamSpec("show_triangle", ParamType.BOOL, True),
            ParamSpec("radius", ParamType.FLOAT, 0.07, minimum=0.0, maximum=1.0, step=0.01),
            ParamSpec("label", ParamType.CHOICE, "none", choices=("none", "term", "equation", "slope")),
            ParamSpec("label_side", ParamType.CHOICE, "auto", choices=("auto", "above", "below"), visible_when=("label", ("term", "equation", "slope"))),
            ParamSpec("decimals", ParamType.INT, 2, minimum=0, maximum=4, visible_when=("label", ("term", "equation", "slope"))),
        ),
        _LINE_STYLE,
        (("stroke_color", "#9CDCEB"), ("stroke_width", 3.0)),
    ),
    ObjectKind.GRAPH_POINT: KindInfo(
        ObjectKind.GRAPH_POINT,
        (
            _GRAPH_REF,
            ParamSpec("x_value", ParamType.FLOAT, 1.0, minimum=-1000.0, maximum=1000.0, step=0.25, decimals=3),
            ParamSpec("x_parameter", ParamType.OBJECT_REF, None, ref_kinds=(ObjectKind.PARAMETER,), optional=True),
            ParamSpec("show_lines", ParamType.BOOL, True),
            ParamSpec("show_label", ParamType.BOOL, False),
            _length("radius", 0.08, minimum=0.005),
        ),
        _TEXT_STYLE,
        (("fill_color", "#FC6255"), ("fill_opacity", 1.0)),
    ),
    ObjectKind.GRAPH_MARKERS: KindInfo(
        ObjectKind.GRAPH_MARKERS,
        (
            _GRAPH_REF,
            ParamSpec("feature", ParamType.CHOICE, "zeros", choices=MARKER_FEATURES),
            ParamSpec("other_graph_id", ParamType.OBJECT_REF, None, ref_kinds=(ObjectKind.FUNCTION_GRAPH,), visible_when=("feature", ("intersections",))),
            ParamSpec("show_labels", ParamType.BOOL, True),
            _length("radius", 0.08, minimum=0.005),
        ),
        _TEXT_STYLE,
        (("fill_color", "#FC6255"), ("fill_opacity", 1.0)),
    ),
    ObjectKind.GRAPH_LABEL: KindInfo(
        ObjectKind.GRAPH_LABEL,
        (
            _GRAPH_REF,
            ParamSpec("text", ParamType.STRING, "f(x)"),
            ParamSpec("use_latex", ParamType.BOOL, False),
            ParamSpec("x_value", ParamType.FLOAT, 2.0, minimum=-1000.0, maximum=1000.0, step=0.25, decimals=3),
            ParamSpec("direction", ParamType.CHOICE, "up_right", choices=LABEL_DIRECTIONS),
            _font_size(36.0),
        ),
        _TEXT_STYLE,
        (("fill_color", _YELLOW), ("fill_opacity", 1.0)),
    ),
    ObjectKind.DATA_PLOT: KindInfo(
        ObjectKind.DATA_PLOT,
        (
            ParamSpec("axes_id", ParamType.OBJECT_REF, None, ref_kinds=(ObjectKind.AXES, ObjectKind.NUMBER_PLANE)),
            ParamSpec(
                "data",
                ParamType.DATA,
                [[-4.0, -1.8], [-3.0, -1.1], [-2.0, -0.9], [-1.0, 0.2], [0.0, 0.4], [1.0, 1.3], [2.0, 1.4], [3.0, 2.4], [4.0, 2.6]],
            ),
            ParamSpec("display", ParamType.CHOICE, "dots", choices=DATA_STYLES),
            ParamSpec("regression", ParamType.CHOICE, "none", choices=REGRESSIONS),
            _length("radius", 0.08, minimum=0.005),
        ),
        frozenset({"stroke_color", "stroke_width", "fill_color"}),
        (("stroke_color", _YELLOW), ("stroke_width", 3.0), ("fill_color", "#58C4DD"), ("fill_opacity", 1.0)),
    ),
    ObjectKind.BAR_CHART: KindInfo(
        ObjectKind.BAR_CHART,
        (
            ParamSpec("bars", ParamType.BARS, [["A", "3"], ["B", "5"], ["C", "2"], ["D", "4"]]),
            ParamSpec("colors", ParamType.CHOICE, "palette", choices=("palette", "single")),
            ParamSpec("show_values", ParamType.BOOL, False),
            ParamSpec("y_max", ParamType.FLOAT, 0.0, minimum=0.0, maximum=1e9, step=1.0),
            ParamSpec("y_step", ParamType.FLOAT, 0.0, minimum=0.0, maximum=1e9, step=0.5),
            _length("x_length", 6.0, minimum=0.5),
            _length("y_length", 4.0, minimum=0.5),
            ParamSpec("bar_width", ParamType.FLOAT, 0.6, minimum=0.05, maximum=1.0, step=0.05),
        ),
        frozenset({"fill_color", "fill_opacity", "stroke_width"}),
        (("fill_color", "#58C4DD"), ("fill_opacity", 0.7), ("stroke_width", 3.0)),
    ),
    ObjectKind.CAMERA: KindInfo(
        ObjectKind.CAMERA,
        (
            ParamSpec("width", ParamType.FLOAT, 0.0, minimum=0.0, maximum=1000.0, step=0.5, decimals=3),
            ParamSpec("phi", ParamType.FLOAT, 70.0, minimum=0.0, maximum=180.0, step=5.0, decimals=1),
            ParamSpec("theta", ParamType.FLOAT, -45.0, minimum=-360.0, maximum=360.0, step=5.0, decimals=1),
        ),
        frozenset(),
    ),
    ObjectKind.AXES_3D: KindInfo(
        ObjectKind.AXES_3D,
        _range_params("x", -4.0, 4.0, 1.0, 6.0) + _range_params("y", -4.0, 4.0, 1.0, 6.0) + _range_params("z", -3.0, 3.0, 1.0, 4.0),
        _AXES_STYLE,
        (("stroke_color", _WHITE), ("stroke_width", 2.0)),
    ),
    ObjectKind.SURFACE: KindInfo(
        ObjectKind.SURFACE,
        (
            ParamSpec("axes_id", ParamType.OBJECT_REF, None, ref_kinds=(ObjectKind.AXES_3D,)),
            ParamSpec("expression", ParamType.EXPRESSION, "sin(x) cos(y)", extra_names=("y",)),
            ParamSpec("x_min", ParamType.FLOAT, -3.0, minimum=-1000.0, maximum=1000.0, step=0.5),
            ParamSpec("x_max", ParamType.FLOAT, 3.0, minimum=-1000.0, maximum=1000.0, step=0.5),
            ParamSpec("y_min", ParamType.FLOAT, -3.0, minimum=-1000.0, maximum=1000.0, step=0.5),
            ParamSpec("y_max", ParamType.FLOAT, 3.0, minimum=-1000.0, maximum=1000.0, step=0.5),
            ParamSpec("resolution", ParamType.INT, 24, minimum=4, maximum=64),
        ),
        frozenset({"stroke_color", "stroke_width", "fill_color", "fill_opacity"}),
        (("stroke_color", "#29ABCA"), ("stroke_width", 0.5), ("fill_color", "#58C4DD"), ("fill_opacity", 0.75)),
    ),
    ObjectKind.CURVE_3D: KindInfo(
        ObjectKind.CURVE_3D,
        (
            ParamSpec("axes_id", ParamType.OBJECT_REF, None, ref_kinds=(ObjectKind.AXES_3D,)),
            ParamSpec("x_expression", ParamType.EXPRESSION, "2cos(t)", variable="t"),
            ParamSpec("y_expression", ParamType.EXPRESSION, "2sin(t)", variable="t"),
            ParamSpec("z_expression", ParamType.EXPRESSION, "t/4", variable="t"),
            ParamSpec("t_min", ParamType.FLOAT, -6.2832, minimum=-1000.0, maximum=1000.0, step=0.5, decimals=4),
            ParamSpec("t_max", ParamType.FLOAT, 6.2832, minimum=-1000.0, maximum=1000.0, step=0.5, decimals=4),
        ),
        _LINE_STYLE,
        (("stroke_color", _YELLOW), ("stroke_width", 4.0)),
    ),
    ObjectKind.PARAMETER: KindInfo(
        ObjectKind.PARAMETER,
        (
            ParamSpec("symbol", ParamType.STRING, "a"),
            ParamSpec("value", ParamType.FLOAT, 1.0, minimum=-1e6, maximum=1e6, step=0.1, decimals=3),
            ParamSpec("minimum", ParamType.FLOAT, -5.0, minimum=-1e6, maximum=1e6, step=1.0, decimals=3),
            ParamSpec("maximum", ParamType.FLOAT, 5.0, minimum=-1e6, maximum=1e6, step=1.0, decimals=3),
        ),
        frozenset(),
    ),
}

#: Shift directions offered for FadeIn/FadeOut.
SHIFT_CHOICES = ("none", "up", "down", "left", "right")
#: Which colors a color change affects.
COLOR_TARGET_CHOICES = ("both", "stroke", "fill")

#: Edges an object can grow from.
EDGE_CHOICES = ("down", "up", "left", "right")
#: What "highlight vertices/edges" does: recolor for good, light up briefly, or flash.
NETWORK_PART_EFFECTS = ("color", "indicate", "flash")

ANIMATION_PARAMS: dict[AnimationKind, tuple[ParamSpec, ...]] = {
    AnimationKind.FADE_IN: (
        ParamSpec("shift", ParamType.CHOICE, "none", choices=SHIFT_CHOICES),
        ParamSpec("scale", ParamType.FLOAT, 1.0, minimum=0.05, maximum=10.0, step=0.1),
    ),
    AnimationKind.FADE_OUT: (
        ParamSpec("shift", ParamType.CHOICE, "none", choices=SHIFT_CHOICES),
        ParamSpec("scale", ParamType.FLOAT, 1.0, minimum=0.05, maximum=10.0, step=0.1),
    ),
    AnimationKind.GROW_FROM_EDGE: (ParamSpec("edge", ParamType.CHOICE, "down", choices=EDGE_CHOICES),),
    AnimationKind.TRANSFORM_FROM_COPY: (ParamSpec("target", ParamType.OBJECT_REF, None),),
    AnimationKind.PASSING_FLASH: (
        ParamSpec("color", ParamType.COLOR, _YELLOW),
        ParamSpec("time_width", ParamType.FLOAT, 0.3, minimum=0.05, maximum=1.0, step=0.05),
    ),
    AnimationKind.BROADCAST: (ParamSpec("rings", ParamType.INT, 5, minimum=1, maximum=20, step=1),),
    AnimationKind.APPLY_MATRIX: (
        ParamSpec("m11", ParamType.FLOAT, 1.0, minimum=-20.0, maximum=20.0, step=0.25),
        ParamSpec("m12", ParamType.FLOAT, 1.0, minimum=-20.0, maximum=20.0, step=0.25),
        ParamSpec("m21", ParamType.FLOAT, 0.0, minimum=-20.0, maximum=20.0, step=0.25),
        ParamSpec("m22", ParamType.FLOAT, 1.0, minimum=-20.0, maximum=20.0, step=0.25),
    ),
    AnimationKind.NETWORK_PARTS: (
        ParamSpec("parts", ParamType.STRING, "A, A-B, B"),
        ParamSpec("effect", ParamType.CHOICE, "color", choices=NETWORK_PART_EFFECTS),
        ParamSpec("color", ParamType.COLOR, _YELLOW),
    ),
    AnimationKind.ONE_BY_ONE: (
        ParamSpec("lag_ratio", ParamType.FLOAT, 0.6, minimum=0.05, maximum=1.0, step=0.05),
        ParamSpec("shift", ParamType.CHOICE, "up", choices=SHIFT_CHOICES),
    ),
    AnimationKind.TRANSFORM: (ParamSpec("target", ParamType.OBJECT_REF, None),),
    AnimationKind.REPLACEMENT_TRANSFORM: (ParamSpec("target", ParamType.OBJECT_REF, None),),
    AnimationKind.MOVE: (
        ParamSpec("x", ParamType.FLOAT, 0.0, minimum=-100.0, maximum=100.0, step=0.25),
        ParamSpec("y", ParamType.FLOAT, 0.0, minimum=-100.0, maximum=100.0, step=0.25),
    ),
    AnimationKind.SCALE: (ParamSpec("factor", ParamType.FLOAT, 1.5, minimum=0.01, maximum=100.0, step=0.1),),
    AnimationKind.ROTATE: (
        ParamSpec("angle", ParamType.FLOAT, 90.0, minimum=-3600.0, maximum=3600.0, step=15.0, decimals=1),
        ParamSpec("pivot", ParamType.CHOICE, "center", choices=("center", "point")),
        ParamSpec("pivot_x", ParamType.FLOAT, 0.0, minimum=-100.0, maximum=100.0, step=0.25, visible_when=("pivot", ("point",))),
        ParamSpec("pivot_y", ParamType.FLOAT, 0.0, minimum=-100.0, maximum=100.0, step=0.25, visible_when=("pivot", ("point",))),
    ),
    AnimationKind.CHANGE_COLOR: (
        ParamSpec("color", ParamType.COLOR, _YELLOW),
        ParamSpec("apply_to", ParamType.CHOICE, "both", choices=COLOR_TARGET_CHOICES),
    ),
    AnimationKind.INDICATE: (
        ParamSpec("color", ParamType.COLOR, _YELLOW),
        ParamSpec("scale_factor", ParamType.FLOAT, 1.2, minimum=0.1, maximum=10.0, step=0.1),
    ),
    AnimationKind.CIRCUMSCRIBE: (ParamSpec("color", ParamType.COLOR, _YELLOW),),
    AnimationKind.SET_VALUE: (ParamSpec("value", ParamType.FLOAT, 2.0, minimum=-1e9, maximum=1e9, step=0.5, decimals=3),),
    AnimationKind.FADE_TRANSFORM: (ParamSpec("target", ParamType.OBJECT_REF, None),),
    AnimationKind.TRANSFORM_MATCHING: (ParamSpec("target", ParamType.OBJECT_REF, None),),
    AnimationKind.MOVE_ALONG_PATH: (ParamSpec("path", ParamType.OBJECT_REF, None),),
    AnimationKind.SWAP: (ParamSpec("partner", ParamType.OBJECT_REF, None),),
    AnimationKind.FLASH: (ParamSpec("color", ParamType.COLOR, _YELLOW),),
    AnimationKind.APPLY_WAVE: (ParamSpec("amplitude", ParamType.FLOAT, 0.2, minimum=0.01, maximum=5.0, step=0.05),),
    AnimationKind.ORBIT: (
        ParamSpec("phi", ParamType.FLOAT, 60.0, minimum=0.0, maximum=180.0, step=5.0, decimals=1),
        ParamSpec("theta", ParamType.FLOAT, 30.0, minimum=-3600.0, maximum=3600.0, step=15.0, decimals=1),
    ),
}

#: Manim's default rate function per animation where it differs from ``smooth``.
DEFAULT_RATE_FUNC: dict[AnimationKind, str] = {
    AnimationKind.WRITE: "linear",
    AnimationKind.INDICATE: "there_and_back",
    AnimationKind.ADD_LETTERS: "linear",
    AnimationKind.MOVE_ALONG_PATH: "linear",
    AnimationKind.WIGGLE: "linear",
    AnimationKind.APPLY_WAVE: "linear",
    AnimationKind.UNWRITE: "linear",
    AnimationKind.TYPE_WITH_CURSOR: "linear",
    AnimationKind.PASSING_FLASH: "linear",
}

#: Animations that require a vector object (not a raster image).
_VECTOR_ONLY = frozenset(
    {
        AnimationKind.CREATE,
        AnimationKind.WRITE,
        AnimationKind.DRAW_BORDER_THEN_FILL,
        AnimationKind.UNCREATE,
        AnimationKind.CHANGE_COLOR,
        AnimationKind.TRANSFORM,
        AnimationKind.REPLACEMENT_TRANSFORM,
        AnimationKind.FADE_TRANSFORM,
        AnimationKind.TRANSFORM_MATCHING,
        AnimationKind.SPIN_IN,
        AnimationKind.APPLY_WAVE,
        AnimationKind.UNWRITE,
        AnimationKind.TRANSFORM_FROM_COPY,
        AnimationKind.PASSING_FLASH,
    }
)
#: Objects a linear map (``ApplyMatrix``) can deform. Objects that Manim redraws in every
#: frame (highlights, graph tools, angles ...) would lose the deformation, so they are left out.
MATRIX_KINDS = frozenset(
    {
        ObjectKind.CIRCLE,
        ObjectKind.SQUARE,
        ObjectKind.RECTANGLE,
        ObjectKind.TRIANGLE,
        ObjectKind.ELLIPSE,
        ObjectKind.LINE,
        ObjectKind.ARROW,
        ObjectKind.DOT,
        ObjectKind.VECTOR,
        ObjectKind.DOUBLE_ARROW,
        ObjectKind.DASHED_LINE,
        ObjectKind.CURVED_ARROW,
        ObjectKind.POLYGON,
        ObjectKind.REGULAR_POLYGON,
        ObjectKind.STAR,
        ObjectKind.ARC,
        ObjectKind.SECTOR,
        ObjectKind.ANNULUS,
        ObjectKind.NUMBER_PLANE,
        ObjectKind.TEXT,
        ObjectKind.MATH_TEX,
        ObjectKind.TEX,
    }
)
#: Arrow kinds that ``GrowArrow`` supports.
ARROW_KINDS = frozenset({ObjectKind.ARROW, ObjectKind.VECTOR, ObjectKind.DOUBLE_ARROW})


def kind_info(kind: ObjectKind) -> KindInfo:
    """Return the static description of an object kind."""
    return KIND_INFO[kind]


def animation_params(kind: AnimationKind) -> tuple[ParamSpec, ...]:
    """Return the parameter specs of an animation kind."""
    return ANIMATION_PARAMS.get(kind, ())


def default_params(specs: tuple[ParamSpec, ...]) -> dict[str, Any]:
    """Return a dict with the default value of every spec."""
    return {spec.key: spec.default for spec in specs}


def is_vector_image_path(path: str) -> bool:
    """Return ``True`` if an image path points to an SVG file."""
    return path.lower().endswith(".svg")


def is_vector_object(kind: ObjectKind, params: dict[str, Any]) -> bool:
    """Return ``True`` if the object becomes a Manim ``VMobject``."""
    if kind != ObjectKind.IMAGE:
        return True
    return is_vector_image_path(str(params.get("path", "")))


#: Animations a highlight cannot have: it is redrawn around its target in every frame.
_NOT_FOR_HIGHLIGHTS = (
    frozenset({AnimationKind.MOVE, AnimationKind.SCALE, AnimationKind.ROTATE, AnimationKind.CHANGE_COLOR, AnimationKind.SET_VALUE, AnimationKind.ORBIT})
    | TRANSFORM_ANIMATIONS
    | MOTION_ANIMATIONS
)


#: Animations that would fight with the updater of a coupled object (it sets the position itself).
_NOT_FOR_COUPLED = frozenset({AnimationKind.MOVE, AnimationKind.APPLY_MATRIX}) | MOTION_ANIMATIONS | TRANSFORM_ANIMATIONS


def animation_allowed(anim_kind: AnimationKind, obj_kind: ObjectKind, params: dict[str, Any]) -> bool:
    """Return ``True`` if the animation can be applied to the object."""
    if anim_kind in _NOT_FOR_COUPLED and params.get("attach") in ("follow", "formula"):
        from manim_studio.model.attach import ATTACHABLE_KINDS

        if obj_kind in ATTACHABLE_KINDS:
            return False
    if obj_kind in (ObjectKind.HIGHLIGHT, ObjectKind.ANGLE, ObjectKind.VECTOR_FIELD) and anim_kind in _NOT_FOR_HIGHLIGHTS:
        return False
    if obj_kind in (ObjectKind.SOLID, ObjectKind.VECTOR_3D) and anim_kind in (
        {AnimationKind.MOVE, AnimationKind.ROTATE, AnimationKind.SET_VALUE, AnimationKind.ORBIT} | TRANSFORM_ANIMATIONS | MOTION_ANIMATIONS
    ):
        return False  # solids are placed by their 3D axes
    if obj_kind == ObjectKind.TRACE:
        # a trace starts recording when it appears and can be faded out
        return anim_kind in (AnimationKind.FADE_IN, AnimationKind.FADE_OUT)
    if obj_kind == ObjectKind.GROUP and anim_kind in (AnimationKind.TRANSFORM, AnimationKind.REPLACEMENT_TRANSFORM):
        return False
    if anim_kind == AnimationKind.SET_VALUE:
        if obj_kind == ObjectKind.DECIMAL_NUMBER and (params.get("parameter_id") or str(params.get("formula", "")).strip()):
            return False  # its updater shows the parameter or formula and would undo the change
        return obj_kind in (ObjectKind.PARAMETER, ObjectKind.DECIMAL_NUMBER)
    if obj_kind == ObjectKind.PARAMETER:
        return False
    if obj_kind == ObjectKind.CAMERA:
        return anim_kind in CAMERA_ANIMATIONS
    if anim_kind == AnimationKind.ORBIT:
        return False
    if anim_kind in (AnimationKind.ADD_LETTERS, AnimationKind.TYPE_WITH_CURSOR):
        return obj_kind == ObjectKind.TEXT
    if anim_kind == AnimationKind.NETWORK_PARTS:
        return obj_kind == ObjectKind.NETWORK
    if anim_kind == AnimationKind.APPLY_MATRIX:
        return obj_kind in MATRIX_KINDS
    if anim_kind == AnimationKind.ONE_BY_ONE:
        return obj_kind in (ObjectKind.BULLET_LIST, ObjectKind.GROUP)
    if anim_kind == AnimationKind.GROW_ARROW:
        return obj_kind in ARROW_KINDS  # GrowArrow needs Arrow.scale(scale_tips=...), CurvedArrow has no such method
    if anim_kind in _VECTOR_ONLY:
        return is_vector_object(obj_kind, params)
    return True
