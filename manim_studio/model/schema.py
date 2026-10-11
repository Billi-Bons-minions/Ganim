"""Declarative description of object and animation parameters.

The schema drives the property panel, default values, stage scaling and
validation, so new parameters only need to be declared here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from manim_studio.model.types import AnimationKind, ObjectKind


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


def _font_size(default: float, key: str = "font_size") -> ParamSpec:
    return ParamSpec(key, ParamType.FLOAT, default, minimum=1.0, maximum=500.0, step=1.0, decimals=1, scalable=True)


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
        ),
        _AXES_STYLE,
        (("stroke_color", _WHITE), ("stroke_width", 2.0)),
    ),
    ObjectKind.NUMBER_PLANE: KindInfo(
        ObjectKind.NUMBER_PLANE,
        _range_params("x", -7.0, 7.0, 1.0, 14.0) + _range_params("y", -4.0, 4.0, 1.0, 8.0),
        frozenset({"stroke_color", "stroke_width", "stroke_opacity"}),
        (("stroke_color", "#29ABCA"), ("stroke_width", 2.0)),
    ),
    ObjectKind.FUNCTION_GRAPH: KindInfo(
        ObjectKind.FUNCTION_GRAPH,
        (
            ParamSpec("expression", ParamType.EXPRESSION, "sin(x)"),
            ParamSpec("x_min", ParamType.FLOAT, -5.0, minimum=-1000.0, maximum=1000.0, step=0.5),
            ParamSpec("x_max", ParamType.FLOAT, 5.0, minimum=-1000.0, maximum=1000.0, step=0.5),
            ParamSpec(
                "axes_id",
                ParamType.OBJECT_REF,
                None,
                ref_kinds=(ObjectKind.AXES, ObjectKind.NUMBER_PLANE),
                optional=True,
            ),
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
}

#: Shift directions offered for FadeIn/FadeOut.
SHIFT_CHOICES = ("none", "up", "down", "left", "right")
#: Which colors a color change affects.
COLOR_TARGET_CHOICES = ("both", "stroke", "fill")

ANIMATION_PARAMS: dict[AnimationKind, tuple[ParamSpec, ...]] = {
    AnimationKind.FADE_IN: (ParamSpec("shift", ParamType.CHOICE, "none", choices=SHIFT_CHOICES),),
    AnimationKind.FADE_OUT: (ParamSpec("shift", ParamType.CHOICE, "none", choices=SHIFT_CHOICES),),
    AnimationKind.TRANSFORM: (ParamSpec("target", ParamType.OBJECT_REF, None),),
    AnimationKind.REPLACEMENT_TRANSFORM: (ParamSpec("target", ParamType.OBJECT_REF, None),),
    AnimationKind.MOVE: (
        ParamSpec("x", ParamType.FLOAT, 0.0, minimum=-100.0, maximum=100.0, step=0.25),
        ParamSpec("y", ParamType.FLOAT, 0.0, minimum=-100.0, maximum=100.0, step=0.25),
    ),
    AnimationKind.SCALE: (ParamSpec("factor", ParamType.FLOAT, 1.5, minimum=0.01, maximum=100.0, step=0.1),),
    AnimationKind.ROTATE: (ParamSpec("angle", ParamType.FLOAT, 90.0, minimum=-3600.0, maximum=3600.0, step=15.0, decimals=1),),
    AnimationKind.CHANGE_COLOR: (
        ParamSpec("color", ParamType.COLOR, _YELLOW),
        ParamSpec("apply_to", ParamType.CHOICE, "both", choices=COLOR_TARGET_CHOICES),
    ),
    AnimationKind.INDICATE: (
        ParamSpec("color", ParamType.COLOR, _YELLOW),
        ParamSpec("scale_factor", ParamType.FLOAT, 1.2, minimum=0.1, maximum=10.0, step=0.1),
    ),
    AnimationKind.CIRCUMSCRIBE: (ParamSpec("color", ParamType.COLOR, _YELLOW),),
}

#: Manim's default rate function per animation where it differs from ``smooth``.
DEFAULT_RATE_FUNC: dict[AnimationKind, str] = {
    AnimationKind.WRITE: "linear",
    AnimationKind.INDICATE: "there_and_back",
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
    }
)


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


def animation_allowed(anim_kind: AnimationKind, obj_kind: ObjectKind, params: dict[str, Any]) -> bool:
    """Return ``True`` if the animation can be applied to the object."""
    if obj_kind == ObjectKind.GROUP and anim_kind in (AnimationKind.TRANSFORM, AnimationKind.REPLACEMENT_TRANSFORM):
        return False
    if anim_kind in _VECTOR_ONLY:
        return is_vector_object(obj_kind, params)
    return True
