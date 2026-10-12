"""Enumerations and constant tables shared by the whole application."""

from __future__ import annotations

from enum import Enum


class ObjectKind(str, Enum):
    """All object types that can be placed on the stage."""

    CIRCLE = "circle"
    SQUARE = "square"
    RECTANGLE = "rectangle"
    TRIANGLE = "triangle"
    ELLIPSE = "ellipse"
    LINE = "line"
    ARROW = "arrow"
    DOT = "dot"
    TEXT = "text"
    MATH_TEX = "math_tex"
    AXES = "axes"
    NUMBER_PLANE = "number_plane"
    FUNCTION_GRAPH = "function_graph"
    IMAGE = "image"
    NUMBER_LINE = "number_line"
    VECTOR = "vector"
    DOUBLE_ARROW = "double_arrow"
    DASHED_LINE = "dashed_line"
    BRACE = "brace"
    POLYGON = "polygon"
    REGULAR_POLYGON = "regular_polygon"
    STAR = "star"
    ARC = "arc"
    SECTOR = "sector"
    ANNULUS = "annulus"
    DECIMAL_NUMBER = "decimal_number"
    TABLE = "table"
    MATRIX = "matrix"
    CODE = "code"
    TEX = "tex"
    MARKUP_TEXT = "markup_text"
    GROUP = "group"
    GRAPH_AREA = "graph_area"
    RIEMANN = "riemann"
    TANGENT = "tangent"
    GRAPH_POINT = "graph_point"
    GRAPH_MARKERS = "graph_markers"
    GRAPH_LABEL = "graph_label"
    PARAMETER = "parameter"
    DATA_PLOT = "data_plot"
    BAR_CHART = "bar_chart"
    CAMERA = "camera"
    AXES_3D = "axes_3d"
    SURFACE = "surface"
    CURVE_3D = "curve_3d"
    HIGHLIGHT = "highlight"
    ANGLE = "angle"
    TRACE = "trace"
    VECTOR_FIELD = "vector_field"
    SOLID = "solid"
    BULLET_LIST = "bullet_list"
    NETWORK = "network"


class AnimationKind(str, Enum):
    """All supported animations."""

    CREATE = "create"
    WRITE = "write"
    DRAW_BORDER_THEN_FILL = "draw_border_then_fill"
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    GROW_FROM_CENTER = "grow_from_center"
    TRANSFORM = "transform"
    REPLACEMENT_TRANSFORM = "replacement_transform"
    MOVE = "move"
    SCALE = "scale"
    ROTATE = "rotate"
    CHANGE_COLOR = "change_color"
    INDICATE = "indicate"
    CIRCUMSCRIBE = "circumscribe"
    UNCREATE = "uncreate"
    SET_VALUE = "set_value"
    SPIN_IN = "spin_in"
    ADD_LETTERS = "add_letters"
    GROW_ARROW = "grow_arrow"
    SHRINK_TO_CENTER = "shrink_to_center"
    FLASH = "flash"
    WIGGLE = "wiggle"
    APPLY_WAVE = "apply_wave"
    FOCUS_ON = "focus_on"
    FADE_TRANSFORM = "fade_transform"
    TRANSFORM_MATCHING = "transform_matching"
    MOVE_ALONG_PATH = "move_along_path"
    SWAP = "swap"
    ORBIT = "orbit"
    GROW_FROM_EDGE = "grow_from_edge"
    TYPE_WITH_CURSOR = "type_with_cursor"
    UNWRITE = "unwrite"
    TRANSFORM_FROM_COPY = "transform_from_copy"
    PASSING_FLASH = "passing_flash"
    BROADCAST = "broadcast"
    ONE_BY_ONE = "one_by_one"
    NETWORK_PARTS = "network_parts"
    APPLY_MATRIX = "apply_matrix"


class StepKind(str, Enum):
    """A timeline step either plays animations or waits."""

    PLAY = "play"
    WAIT = "wait"
    CODE = "code"


class Visibility(str, Enum):
    """Whether an object is on screen when the scene starts."""

    AUTO = "auto"
    SHOWN = "shown"
    HIDDEN = "hidden"


#: Animations that bring an object onto the screen.
ENTRANCE_ANIMATIONS = frozenset(
    {
        AnimationKind.CREATE,
        AnimationKind.WRITE,
        AnimationKind.DRAW_BORDER_THEN_FILL,
        AnimationKind.FADE_IN,
        AnimationKind.GROW_FROM_CENTER,
        AnimationKind.SPIN_IN,
        AnimationKind.ADD_LETTERS,
        AnimationKind.GROW_ARROW,
        AnimationKind.GROW_FROM_EDGE,
        AnimationKind.TYPE_WITH_CURSOR,
        AnimationKind.ONE_BY_ONE,
    }
)

#: Animations that remove an object from the screen.
EXIT_ANIMATIONS = frozenset({AnimationKind.FADE_OUT, AnimationKind.UNCREATE, AnimationKind.SHRINK_TO_CENTER, AnimationKind.UNWRITE})

#: Transforms after which the target object takes the place of the source.
REPLACING_TRANSFORMS = frozenset({AnimationKind.REPLACEMENT_TRANSFORM, AnimationKind.FADE_TRANSFORM, AnimationKind.TRANSFORM_MATCHING})

#: Animations that morph one object into another object (a copy of the source for TransformFromCopy).
TRANSFORM_ANIMATIONS = frozenset({AnimationKind.TRANSFORM, AnimationKind.TRANSFORM_FROM_COPY}) | REPLACING_TRANSFORMS

#: Animations that move an object along a path or swap two objects.
MOTION_ANIMATIONS = frozenset({AnimationKind.MOVE_ALONG_PATH, AnimationKind.SWAP})

#: Animations with a second object: parameter key that names it.
REFERENCE_PARAMS = {
    **{
        kind: "target"
        for kind in (
            AnimationKind.TRANSFORM,
            AnimationKind.REPLACEMENT_TRANSFORM,
            AnimationKind.FADE_TRANSFORM,
            AnimationKind.TRANSFORM_MATCHING,
            AnimationKind.TRANSFORM_FROM_COPY,
        )
    },
    AnimationKind.MOVE_ALONG_PATH: "path",
    AnimationKind.SWAP: "partner",
}

#: Animations generated with Manim's ``.animate`` syntax (can be merged per object).
MODIFIER_ANIMATIONS = frozenset(
    {AnimationKind.MOVE, AnimationKind.SCALE, AnimationKind.ROTATE, AnimationKind.CHANGE_COLOR}
)

#: Effects that can run together with movements of the same object (but not with a transform of it).
COMBINABLE_EFFECTS = frozenset(
    {
        AnimationKind.CREATE,
        AnimationKind.WRITE,
        AnimationKind.DRAW_BORDER_THEN_FILL,
        AnimationKind.UNCREATE,
        AnimationKind.FADE_IN,
        AnimationKind.FADE_OUT,
        AnimationKind.GROW_FROM_CENTER,
        AnimationKind.INDICATE,
    }
)


#: Highlights that draw extra shapes but leave the object itself untouched.
DETACHED_EFFECTS = frozenset(
    {AnimationKind.FLASH, AnimationKind.CIRCUMSCRIBE, AnimationKind.FOCUS_ON, AnimationKind.PASSING_FLASH, AnimationKind.BROADCAST}
)


def pivot_of(anim) -> tuple[float, float] | None:
    """The point a rotation turns around (``None`` = the object's own center)."""
    if anim.kind != AnimationKind.ROTATE or anim.params.get("pivot") != "point":
        return None
    return float(anim.params.get("pivot_x", 0.0)), float(anim.params.get("pivot_y", 0.0))


def _participants(animations) -> dict[str, list[AnimationKind]]:
    by_object: dict[str, list[AnimationKind]] = {}
    for anim in animations:
        if anim.kind in DETACHED_EFFECTS or anim.kind == AnimationKind.ORBIT:
            continue
        # a rotation around another point cannot be merged with other movements
        by_object.setdefault(anim.target_id, []).append(AnimationKind.MOVE_ALONG_PATH if pivot_of(anim) else anim.kind)
        if anim.kind in TRANSFORM_ANIMATIONS and anim.params.get("target"):
            by_object.setdefault(str(anim.params["target"]), []).append(anim.kind)
        if anim.kind == AnimationKind.SWAP and anim.params.get("partner"):
            by_object.setdefault(str(anim.params["partner"]), []).append(anim.kind)
    return by_object


def simultaneous_conflicts(animations) -> set[str]:
    """Objects with animations that Manim cannot play at the same time.

    Several animations of one object only work together if all of them are
    movements/colors or visibility effects (they are merged into one animation).
    """
    combinable = MODIFIER_ANIMATIONS | COMBINABLE_EFFECTS
    return {object_id for object_id, kinds in _participants(animations).items() if len(kinds) > 1 and not all(kind in combinable for kind in kinds)}


def transform_conflicts(animations) -> set[str]:
    """The conflicting objects that take part in a transform (reported with their own message)."""
    by_object = _participants(animations)
    return {object_id for object_id in simultaneous_conflicts(animations) if any(kind in TRANSFORM_ANIMATIONS for kind in by_object[object_id])}


#: Animations that only draw attention and do not change the final state.
EMPHASIS_ANIMATIONS = frozenset(
    {
        AnimationKind.INDICATE,
        AnimationKind.CIRCUMSCRIBE,
        AnimationKind.FLASH,
        AnimationKind.WIGGLE,
        AnimationKind.APPLY_WAVE,
        AnimationKind.FOCUS_ON,
        AnimationKind.PASSING_FLASH,
        AnimationKind.BROADCAST,
    }
)

#: Rate function name -> Python expression valid after ``from manim import *``.
RATE_FUNCTIONS: dict[str, str] = {
    "linear": "linear",
    "smooth": "smooth",
    "rush_into": "rush_into",
    "rush_from": "rush_from",
    "slow_into": "slow_into",
    "double_smooth": "double_smooth",
    "there_and_back": "there_and_back",
    "there_and_back_with_pause": "there_and_back_with_pause",
    "running_start": "running_start",
    "wiggle": "wiggle",
    "lingering": "lingering",
    "ease_in_sine": "rate_functions.ease_in_sine",
    "ease_out_sine": "rate_functions.ease_out_sine",
    "ease_in_out_sine": "rate_functions.ease_in_out_sine",
    "ease_in_quad": "rate_functions.ease_in_quad",
    "ease_out_quad": "rate_functions.ease_out_quad",
    "ease_in_out_quad": "rate_functions.ease_in_out_quad",
    "ease_in_cubic": "rate_functions.ease_in_cubic",
    "ease_out_cubic": "rate_functions.ease_out_cubic",
    "ease_in_out_cubic": "rate_functions.ease_in_out_cubic",
    "ease_in_back": "rate_functions.ease_in_back",
    "ease_out_back": "rate_functions.ease_out_back",
    "ease_in_out_back": "rate_functions.ease_in_out_back",
    "ease_out_bounce": "rate_functions.ease_out_bounce",
    "ease_out_elastic": "rate_functions.ease_out_elastic",
}

#: Rate functions that end where they started (f(1) == 0).
RETURNING_RATE_FUNCTIONS = frozenset({"there_and_back", "there_and_back_with_pause", "wiggle"})

#: Kinds whose Manim objects need a LaTeX installation.
LATEX_KINDS = frozenset({ObjectKind.MATH_TEX, ObjectKind.TEX, ObjectKind.MATRIX})

#: Objects that are drawn on a function graph (and placed by its coordinate system).
GRAPH_TOOL_KINDS = frozenset(
    {
        ObjectKind.GRAPH_AREA,
        ObjectKind.RIEMANN,
        ObjectKind.TANGENT,
        ObjectKind.GRAPH_POINT,
        ObjectKind.GRAPH_MARKERS,
        ObjectKind.GRAPH_LABEL,
    }
)

#: Kinds that are not drawn and never added to the Manim scene.
INVISIBLE_KINDS = frozenset({ObjectKind.GROUP, ObjectKind.PARAMETER})
#: Looks of a highlight: frame, background, underline or cross over its target.
HIGHLIGHT_STYLES = ("frame", "background", "underline", "cross")

#: Kinds that are no mobjects and therefore cannot be members of a group.
UNGROUPABLE = frozenset({ObjectKind.PARAMETER, ObjectKind.CAMERA})
#: Kinds that are not added to the Manim scene (the camera is shown on the stage only).
UNADDED_KINDS = INVISIBLE_KINDS | {ObjectKind.CAMERA}
#: Animations a camera understands.
CAMERA_ANIMATIONS = frozenset({AnimationKind.MOVE, AnimationKind.SCALE, AnimationKind.ROTATE, AnimationKind.ORBIT})

#: Curve types of a function graph.
CURVE_FUNCTION = "function"
CURVE_DERIVATIVE = "derivative"
CURVE_PIECEWISE = "piecewise"
CURVE_PARAMETRIC = "parametric"
CURVE_POLAR = "polar"
CURVE_IMPLICIT = "implicit"
CURVES = (CURVE_FUNCTION, CURVE_DERIVATIVE, CURVE_PIECEWISE, CURVE_PARAMETRIC, CURVE_POLAR, CURVE_IMPLICIT)
#: Curves of the form ``y = f(x)``.
FUNCTION_CURVES = (CURVE_FUNCTION, CURVE_DERIVATIVE, CURVE_PIECEWISE)

#: Line-like kinds that get two endpoint handles on the stage.
LINE_KINDS = frozenset(
    {ObjectKind.LINE, ObjectKind.ARROW, ObjectKind.VECTOR, ObjectKind.DOUBLE_ARROW, ObjectKind.DASHED_LINE}
)

#: Manim frame size in scene units (16:9).
FRAME_WIDTH = 8.0 * 16.0 / 9.0
FRAME_HEIGHT = 8.0

#: Default colors of Manim's palette offered in the color picker.
MANIM_COLORS: dict[str, str] = {
    "WHITE": "#FFFFFF",
    "GRAY": "#888888",
    "BLACK": "#000000",
    "BLUE": "#58C4DD",
    "TEAL": "#5CD0B3",
    "GREEN": "#83C167",
    "YELLOW": "#F7D96F",
    "GOLD": "#F0AC5F",
    "ORANGE": "#FF862F",
    "RED": "#FC6255",
    "MAROON": "#C55F73",
    "PINK": "#D147BD",
    "PURPLE": "#9A72AC",
    "BLUE_D": "#29ABCA",
}
