"""Pure geometry helpers shared by the state computation and the stage.

All coordinates are Manim units with y pointing up. The helpers mirror how
Manim lays out coordinate systems so that the stage matches the rendering.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.types import ObjectKind

AXES_TIP_LENGTH = 0.35
AXES_TICK_SIZE = 0.1
GRAPH_SAMPLES = 400
GRAPH_VALUE_LIMIT = 1.0e4

Point = tuple[float, float]
Segment = list[Point]


def origin_shift(low: float, high: float) -> float:
    """Return where the other axis crosses an axis range (Manim's ``_origin_shift``)."""
    if low > 0:
        return low
    if high < 0:
        return high
    return 0.0


def _arange(start: float, stop: float, step: float) -> list[float]:
    """``numpy.arange``: ``ceil((stop - start) / step)`` values from ``start``."""
    count = math.ceil((stop - start) / step)
    return [start + index * step for index in range(max(0, min(count, 2000)))]


def tick_values(low: float, high: float, step: float, tip: bool, exclude_origin: bool = False) -> list[float]:
    """Where Manim's ``NumberLine.get_tick_range`` puts ticks (and numbers).

    With a tip the last value is left out (the tip sits there). A range that contains 0
    is counted from 0 in both directions; a range that does not starts at ``low``.
    """
    if step <= 0 or high <= low:
        return []
    end = high if tip else high + 1e-6
    if low < end < 0 or end > low > 0:
        return _arange(low, end, step)
    start = step if exclude_origin else 0.0
    negative = [-value for value in _arange(start, abs(low) + 1e-6, step)]
    positive = _arange(start, end, step)
    return sorted(set(negative) | set(positive))


def plane_line_values(low: float, high: float, step: float) -> list[float]:
    """Where Manim's ``NumberPlane`` draws its grid lines across one axis (axis values).

    From the axis outwards in both directions; the far ends are left out (``arange``), so a
    plane from -2 to 2 has lines at -1, 0 and 1 only.
    """
    if step <= 0 or high <= low:
        return []
    origin = origin_shift(low, high)
    # the ranges are measured from the axis, like Manim does for ranges with and without 0
    span_low, span_high = low - origin, high - origin
    offsets = [0.0] + _arange(step, min(span_high - span_low, span_high), step) + [-value for value in _arange(step, -max(span_low - span_high, span_low), step)]
    return sorted(origin + offset for offset in offsets)


def rotate_point(x: float, y: float, degrees: float) -> Point:
    """Rotate a point counter-clockwise around the origin."""
    radians = math.radians(degrees)
    cos_a, sin_a = math.cos(radians), math.sin(radians)
    return x * cos_a - y * sin_a, x * sin_a + y * cos_a


@dataclass(frozen=True)
class AxesLayout:
    """Layout of an ``Axes``/``NumberPlane`` relative to its bounding-box center."""

    x_min: float
    x_max: float
    y_min: float
    y_max: float
    x_length: float
    y_length: float
    offset: Point

    def to_local(self, xv: float, yv: float) -> Point:
        """Map axes coordinates onto local coordinates (bounding-box center = 0)."""
        x_span = self.x_max - self.x_min or 1.0
        y_span = self.y_max - self.y_min or 1.0
        lx = (xv - (self.x_min + self.x_max) / 2) / x_span * self.x_length
        ly = (yv - (self.y_min + self.y_max) / 2) / y_span * self.y_length
        return lx - self.offset[0], ly - self.offset[1]

    def origin_local(self) -> Point:
        """Return the local point where both axes intersect."""
        return self.to_local(origin_shift(self.x_min, self.x_max), origin_shift(self.y_min, self.y_max))


#: Ink width and height of the characters of axis numbers, ``Text(c, font_size=48)`` measured with Manim,
#: for the serif fonts Pango usually picks as its default (Manim's ``Text`` without ``font=``).
_GLYPH_TABLES = {
    "Noto Serif": {
        "0": (0.3125, 0.48984), "1": (0.27422, 0.47812), "2": (0.28984, 0.48281), "3": (0.29531, 0.48984), "4": (0.35156, 0.47578),
        "5": (0.2875, 0.48281), "6": (0.29766, 0.48984), "7": (0.30156, 0.47578), "8": (0.31172, 0.48984), "9": (0.29766, 0.48984),
        "-": (0.17344, 0.05), ".": (0.08359, 0.09063), ",": (0.10859, 0.18828),
    },
    "DejaVu Serif": {
        "0": (0.33594, 0.50391), "1": (0.24844, 0.49453), "2": (0.31328, 0.49453), "3": (0.32344, 0.50391), "4": (0.37031, 0.49453),
        "5": (0.31641, 0.49531), "6": (0.3375, 0.50391), "7": (0.31953, 0.48594), "8": (0.33438, 0.50391), "9": (0.33672, 0.50391),
        "-": (0.16719, 0.05078), ".": (0.08672, 0.08672), ",": (0.12344, 0.16484),
    },
    "Liberation Serif": {
        "0": (0.28281, 0.44922), "1": (0.23438, 0.43984), "2": (0.26719, 0.44141), "3": (0.275, 0.44766), "4": (0.30938, 0.43828),
        "5": (0.26797, 0.44297), "6": (0.28438, 0.44766), "7": (0.27031, 0.43672), "8": (0.28281, 0.44922), "9": (0.28516, 0.44766),
        "-": (0.17266, 0.05), ".": (0.07891, 0.07891), ",": (0.1, 0.17109),
    },
}  # fmt: skip
_SERIF: list[str | None] = []


def serif_family() -> str | None:
    """The font fontconfig (and with it Pango) picks for "serif", e.g. "Noto Serif" (``None`` without fontconfig)."""
    if not _SERIF:
        import shutil
        import subprocess

        family = None
        command = shutil.which("fc-match")
        if command is not None:
            try:
                result = subprocess.run([command, "-f", "%{family[0]}", "serif"], capture_output=True, text=True, timeout=5)
                family = result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None
            except (OSError, subprocess.SubprocessError):
                family = None
        _SERIF.append(family)
    return _SERIF[0]


def _glyphs() -> dict[str, tuple[float, float]]:
    return _GLYPH_TABLES.get(serif_family() or "", _GLYPH_TABLES["Noto Serif"])


#: Font size of axis numbers in the script, and their distance from the axis (Manim's ``MED_SMALL_BUFF``).
AXIS_NUMBER_SIZE = 24.0
AXIS_NUMBER_BUFF = 0.25


def decimals_from_step(step: float) -> int:
    """Manim's ``_decimal_places_from_step`` for the step as the script writes it (``1`` or ``0.25``)."""
    rounded = round(float(step), 6)
    if rounded == int(rounded):
        return 0
    return len(repr(rounded).split(".")[-1])


def axis_number_text(value: float, step: float) -> str:
    """How ``DecimalNumber`` writes an axis number: as many decimals as the step, digits grouped with commas."""
    text = f"{value:,.{decimals_from_step(step)}f}"
    return text[1:] if text.startswith("-") and float(text.replace(",", "")) == 0 else text


def number_size(text: str, font_size: float = AXIS_NUMBER_SIZE) -> tuple[float, float, float]:
    """Width, height and width of the first character of a ``DecimalNumber`` made of ``Text`` characters."""
    scale = font_size / 48.0
    table = _glyphs()
    glyphs = [table.get(char, (0.3, 0.48)) for char in text] or [(0.0, 0.0)]
    width = sum(glyph[0] for glyph in glyphs) * scale + 0.001 * font_size * (len(glyphs) - 1)
    height = max(glyph[1] for glyph in glyphs) * scale
    return width, height, glyphs[0][0] * scale


#: Numbers of a number plane sit to the lower right of their point (``label_direction=DR``, ``SMALL_BUFF``).
PLANE_NUMBER_BUFF = 0.1


def plane_numbers(obj: SceneObject) -> list[tuple[str, float, float, bool]]:
    """``(text, x, y, is_decimal_number)`` of the numbers of a number plane in axes values.

    Like ``NumberPlane.add_coordinates`` or, for a complex plane, like ``ComplexPlane.add_coordinates``
    (the y-axis as ``i``, ``2i`` …, written with ``Text`` instead of LaTeX); 0 is left out.
    """
    mode = obj.params.get("numbers", "none")
    if obj.kind != ObjectKind.NUMBER_PLANE or mode not in ("real", "complex"):
        return []
    params = obj.params
    x_min, x_max, x_step = float(params.get("x_min", -7.0)), float(params.get("x_max", 7.0)), float(params.get("x_step", 1.0))
    y_min, y_max, y_step = float(params.get("y_min", -4.0)), float(params.get("y_max", 4.0)), float(params.get("y_step", 1.0))
    ox, oy = origin_shift(x_min, x_max), origin_shift(y_min, y_max)
    # the axes of a number plane leave out the origin (exclude_origin_tick)
    numbers = [(axis_number_text(x, x_step), x, oy, True) for x in tick_values(x_min, x_max, x_step, False) if abs(x) > 1e-9]
    for y in tick_values(y_min, y_max, y_step, False):
        if abs(y) < 1e-9:
            continue
        numbers.append((imaginary_text(y, y_step) if mode == "complex" else axis_number_text(y, y_step), ox, y, mode != "complex"))
    return numbers


def imaginary_text(value: float, step: float) -> str:
    """``i``, ``-i``, ``2i``, ``0.5i`` …: an imaginary axis number (the script's ``studio_complex_labels``)."""
    number = axis_number_text(abs(value), step)
    sign = "-" if value < 0 else ""
    return sign + ("i" if number == "1" else number + "i")


def axis_number_boxes(layout: AxesLayout, x_step: float, y_step: float, tips: bool) -> list[tuple[float, float, float, float]]:
    """``(left, bottom, right, top)`` of every axis number in local coordinates, placed like Manim.

    x numbers hang below the axis (``next_to(point, DOWN, buff)``, negative ones moved left by half
    their minus sign so the digits are centered); y numbers sit left of the axis.
    """
    boxes = []
    ox, oy = origin_shift(layout.x_min, layout.x_max), origin_shift(layout.y_min, layout.y_max)
    for value in tick_values(layout.x_min, layout.x_max, x_step, tips):
        if abs(value) < 1e-9:
            continue
        width, height, first = number_size(axis_number_text(value, x_step))
        x, y = layout.to_local(value, oy)
        center = x - (first / 2 if value < 0 else 0.0)
        top = y - AXIS_NUMBER_BUFF
        boxes.append((center - width / 2, top - height, center + width / 2, top))
    for value in tick_values(layout.y_min, layout.y_max, y_step, tips):
        if abs(value) < 1e-9:
            continue
        width, height, _first = number_size(axis_number_text(value, y_step))
        x, y = layout.to_local(ox, value)
        right = x - AXIS_NUMBER_BUFF
        boxes.append((right - width, y - height / 2, right, y + height / 2))
    return boxes


def axes_layout(obj: SceneObject) -> AxesLayout:
    """Compute the layout of a coordinate system object.

    Manim centers the plot area and then ``move_to`` uses the bounding box,
    which is enlarged by the arrow tips (or ticks) on the axis lines and by the numbers.
    """
    params = obj.params
    x_min, x_max = float(params.get("x_min", -5.0)), float(params.get("x_max", 5.0))
    y_min, y_max = float(params.get("y_min", -3.0)), float(params.get("y_max", 3.0))
    x_length, y_length = float(params.get("x_length", 10.0)), float(params.get("y_length", 6.0))
    plain = AxesLayout(x_min, x_max, y_min, y_max, x_length, y_length, (0.0, 0.0))
    if obj.kind == ObjectKind.NUMBER_PLANE:
        return plain
    half = AXES_TIP_LENGTH / 2 if params.get("tips", True) else AXES_TICK_SIZE
    axis_x, axis_y = plain.origin_local()
    left = min(-x_length / 2, axis_x - half)
    right = max(x_length / 2, axis_x + half)
    bottom = min(-y_length / 2, axis_y - half)
    top = max(y_length / 2, axis_y + half)
    if params.get("show_numbers"):
        x_step, y_step = float(params.get("x_step", 1.0)), float(params.get("y_step", 1.0))
        for box_left, box_bottom, box_right, box_top in axis_number_boxes(plain, x_step, y_step, bool(params.get("tips", True))):
            left, bottom, right, top = min(left, box_left), min(bottom, box_bottom), max(right, box_right), max(top, box_top)
    offset = ((left + right) / 2, (bottom + top) / 2)
    return AxesLayout(x_min, x_max, y_min, y_max, x_length, y_length, offset)


@dataclass(frozen=True)
class PolarGrid:
    """Circles and rays of a polar grid around the origin of a number plane (axes units)."""

    radius_max: float
    radius_step: float
    divisions: int
    unit: float


def polar_grid(obj: SceneObject) -> PolarGrid | None:
    """The polar grid of a number plane, reaching into all corners of its rectangle."""
    if obj.kind != ObjectKind.NUMBER_PLANE or obj.params.get("grid") != "polar":
        return None
    layout = axes_layout(obj)
    step = abs(param_float(obj.params, "x_step", 1.0)) or 1.0
    corner = max(math.hypot(x, y) for x in (layout.x_min, layout.x_max) for y in (layout.y_min, layout.y_max))
    radius = math.ceil(corner / step - 1e-9) * step
    unit = layout.x_length / ((layout.x_max - layout.x_min) or 1.0)
    divisions = max(2, int(obj.params.get("azimuth_divisions", 12)))
    return PolarGrid(radius, step, divisions, unit)


def polar_units_match(obj: SceneObject) -> bool:
    """A polar grid needs the same scale on both axes (otherwise its circles would not fit the coordinates)."""
    layout = axes_layout(obj)
    unit_x = layout.x_length / ((layout.x_max - layout.x_min) or 1.0)
    unit_y = layout.y_length / ((layout.y_max - layout.y_min) or 1.0)
    return abs(unit_x - unit_y) < 1e-6 * max(unit_x, unit_y, 1.0)


def local_to_scene(obj: SceneObject, local: Point) -> Point:
    """Place a local point using the object's position and rotation."""
    rx, ry = rotate_point(local[0], local[1], obj.rotation)
    return obj.x + rx, obj.y + ry


def axes_to_scene(axes: SceneObject, xv: float, yv: float) -> Point:
    """Map axes coordinates of a coordinate system onto scene coordinates."""
    return local_to_scene(axes, axes_layout(axes).to_local(xv, yv))


def bound_axes(scene: Scene, graph: SceneObject) -> SceneObject | None:
    """Return the coordinate system a function graph is attached to."""
    axes = scene.object_by_id(graph.params.get("axes_id"))
    if axes is None or axes.kind not in (ObjectKind.AXES, ObjectKind.NUMBER_PLANE):
        return None
    return axes


def bbox_center(segments: list[Segment]) -> Point | None:
    """Return the center of the bounding box of point segments."""
    points = [point for segment in segments for point in segment]
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def param_float(params: dict[str, Any], key: str, default: float) -> float:
    """Read a numeric parameter defensively."""
    try:
        return float(params.get(key, default))
    except (TypeError, ValueError):
        return default
