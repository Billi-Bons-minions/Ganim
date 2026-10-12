"""Angle marks between two lines (like Manim's ``Angle`` and ``RightAngle``)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.geometry import param_float
from manim_studio.model.types import LINE_KINDS, ObjectKind

#: Parameters of an angle that name its two lines.
ANGLE_LINE_KEYS = ("first_line", "second_line")


@dataclass(frozen=True)
class AngleGeometry:
    """Where the two lines meet and which arc the mark covers (degrees, counter-clockwise)."""

    x: float
    y: float
    start: float
    sweep: float
    first: tuple[float, float]
    second: tuple[float, float]

    @property
    def value(self) -> float:
        """The size of the marked angle in degrees."""
        return abs(self.sweep)


def angle_lines(scene: Scene, angle: SceneObject) -> tuple[SceneObject, SceneObject] | None:
    """The two lines of an angle mark (``None`` if one is missing or not a line)."""
    lines = [scene.object_by_id(angle.params.get(key)) for key in ANGLE_LINE_KEYS]
    if any(line is None or line.kind not in LINE_KINDS for line in lines) or lines[0].id == lines[1].id:
        return None
    return lines[0], lines[1]


def _direction(rotation: float) -> tuple[float, float]:
    radians = math.radians(rotation)
    return math.cos(radians), math.sin(radians)


def _line_points(line: SceneObject, state) -> tuple[tuple[float, float], tuple[float, float]]:
    """Center and unit direction of a line in its current state."""
    return (state.x, state.y), _direction(state.rotation)


def angle_geometry(scene: Scene, angle: SceneObject, states: dict) -> AngleGeometry | None:
    """Mirror of Manim's ``Angle``: intersection of both lines and the arc between them."""
    lines = angle_lines(scene, angle)
    if lines is None or lines[0].id not in states or lines[1].id not in states:
        return None
    (p1, d1), (p2, d2) = (_line_points(line, states[line.id]) for line in lines)
    cross = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(cross) < 1e-9:
        return None  # parallel lines meet nowhere
    t = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / cross
    x, y = p1[0] + t * d1[0], p1[1] + t * d1[1]
    q1 = -1.0 if angle.params.get("flip_first") else 1.0
    q2 = -1.0 if angle.params.get("flip_second") else 1.0
    first = (q1 * d1[0], q1 * d1[1])
    second = (q2 * d2[0], q2 * d2[1])
    angle_1 = math.degrees(math.atan2(first[1], first[0])) % 360.0
    angle_2 = math.degrees(math.atan2(second[1], second[0])) % 360.0
    if not angle.params.get("reflex"):
        sweep = angle_2 - angle_1 if angle_2 > angle_1 else 360.0 - (angle_1 - angle_2)
    else:
        sweep = -angle_1 + angle_2 if angle_2 < angle_1 else -360.0 + (angle_2 - angle_1)
    return AngleGeometry(x, y, angle_1, sweep, first, second)


def angle_label(angle: SceneObject, geometry: AngleGeometry | None) -> str:
    """The text written next to the mark ("" for none)."""
    kind = angle.params.get("label", "none")
    if kind == "symbol":
        return str(angle.params.get("symbol", "α"))
    if kind == "degrees" and geometry is not None:
        decimals = max(0, int(angle.params.get("decimals", 0)))
        return f"{geometry.value:.{decimals}f}°"
    return ""


def label_position(angle: SceneObject, geometry: AngleGeometry) -> tuple[float, float]:
    """Center of the label: on the bisector, a bit outside the arc."""
    middle = math.radians(geometry.start + geometry.sweep / 2)
    distance = param_float(angle.params, "radius", 0.6) + 0.3
    return geometry.x + distance * math.cos(middle), geometry.y + distance * math.sin(middle)


def is_angle(obj: SceneObject | None) -> bool:
    return obj is not None and obj.kind == ObjectKind.ANGLE
