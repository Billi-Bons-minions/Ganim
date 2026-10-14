"""Color gradients of shapes, like Manim's ``set_fill([a, b])`` and ``set_stroke([a, b])``.

Manim draws a two-color VMobject with a linear gradient between
``c − offset`` (first color) and ``c + offset`` (second color), where ``c`` is
the center of the object's bounding box and ``offset = (dx · w/2, dy · h/2)``
for the *sheen direction* ``(dx, dy)`` (default ``UL``). The sheen direction
turns with the object (``VMobject.rotate``), the bounding box is that of the
turned object.
"""

from __future__ import annotations

import math

from manim_studio.model.entities import SceneObject
from manim_studio.model.types import ObjectKind

#: Where the second color lies, as Manim's direction vectors (not normalized, like ``UL``).
SHEEN_DIRECTIONS: dict[str, tuple[float, float]] = {
    "ul": (-1.0, 1.0),
    "up": (0.0, 1.0),
    "ur": (1.0, 1.0),
    "right": (1.0, 0.0),
    "dr": (1.0, -1.0),
    "down": (0.0, -1.0),
    "dl": (-1.0, -1.0),
    "left": (-1.0, 0.0),
}
#: Manim's constants for the directions.
SHEEN_CODE = {"ul": "UL", "up": "UP", "ur": "UR", "right": "RIGHT", "dr": "DR", "down": "DOWN", "dl": "DL", "left": "LEFT"}
DEFAULT_DIRECTION = "ul"

#: Shapes with an area: the gradient can color the fill, the outline or both.
FILLED_KINDS = frozenset(
    {
        ObjectKind.CIRCLE,
        ObjectKind.SQUARE,
        ObjectKind.RECTANGLE,
        ObjectKind.ELLIPSE,
        ObjectKind.TRIANGLE,
        ObjectKind.POLYGON,
        ObjectKind.REGULAR_POLYGON,
        ObjectKind.STAR,
        ObjectKind.SECTOR,
        ObjectKind.ANNULUS,
    }
)
#: Lines: only the stroke.
STROKE_KINDS = frozenset({ObjectKind.LINE, ObjectKind.ARC})
GRADIENT_KINDS = FILLED_KINDS | STROKE_KINDS


def gradient_parts(obj: SceneObject) -> tuple[bool, bool]:
    """``(fill, stroke)``: which parts of the object have a gradient (a text's letters are its fill)."""
    if obj.kind == ObjectKind.TEXT:
        return obj.params.get("gradient", "none") == "letters", False
    if obj.kind not in GRADIENT_KINDS:
        return False, False
    mode = str(obj.params.get("gradient", "none"))
    fill = mode in ("fill", "both") and obj.kind in FILLED_KINDS
    return fill, mode in ("stroke", "both")


def gradient_color(obj: SceneObject) -> str:
    """The second color of the gradient."""
    return str(obj.params.get("gradient_color", "#83C167"))


def letter_colors(first: str, second: str, count: int) -> list[str]:
    """Manim's ``color_gradient`` for ``Text(gradient=…)``: one color per character, the first and last exact.

    Every character counts, spaces and line breaks too (Pango colors the characters of the string).
    """
    def channels(value: str) -> tuple[float, float, float]:
        value = value.lstrip("#")
        try:
            return int(value[0:2], 16) / 255, int(value[2:4], 16) / 255, int(value[4:6], 16) / 255
        except (ValueError, IndexError):
            return 1.0, 1.0, 1.0

    a, b = channels(first), channels(second)
    colors = []
    for index in range(count):
        t = index / (count - 1) if count > 1 else 0.0
        colors.append("#" + "".join(f"{round((x + (y - x) * t) * 255):02X}" for x, y in zip(a, b)))
    return colors


def sheen_direction(obj: SceneObject) -> tuple[float, float]:
    """The direction of the second color before the object is turned."""
    return SHEEN_DIRECTIONS.get(str(obj.params.get("gradient_direction", DEFAULT_DIRECTION)), SHEEN_DIRECTIONS[DEFAULT_DIRECTION])


def gradient_line(
    center: tuple[float, float], half_width: float, half_height: float, direction: tuple[float, float], rotation: float
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Start (first color) and end (second color) of Manim's gradient, in scene coordinates.

    ``half_width``/``half_height`` belong to the bounding box of the turned object,
    ``rotation`` (degrees) turns the sheen direction like ``VMobject.rotate``.
    """
    angle = math.radians(rotation)
    dx = direction[0] * math.cos(angle) - direction[1] * math.sin(angle)
    dy = direction[0] * math.sin(angle) + direction[1] * math.cos(angle)
    ox, oy = dx * half_width, dy * half_height
    return (center[0] - ox, center[1] - oy), (center[0] + ox, center[1] + oy)
