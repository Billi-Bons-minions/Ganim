"""Two-color fills and strokes on the stage, laid out like Manim's Cairo camera.

Manim takes the bounding box of the object where it is (turned and scaled) and
draws a linear gradient from ``c − offset`` (first color) to ``c + offset``
(second color, ``model/gradients.py``). The stage computes that line in the
scene and maps it back into the object's own coordinates, where it paints.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPen

from manim_studio.model.dashes import is_dashed
from manim_studio.model.entities import SceneObject
from manim_studio.model.gradients import gradient_line, sheen_direction
from manim_studio.model.state import ObjectState
from manim_studio.ui.stage.drawing import PX, Primitive


def _gradient_brush(start: QPointF, end: QPointF, first: QColor, second: str) -> QBrush:
    gradient = QLinearGradient(start, end)
    other = QColor(second)
    other.setAlphaF(first.alphaF())
    gradient.setColorAt(0.0, first)
    gradient.setColorAt(1.0, other)
    return QBrush(gradient)  # outside the line the end colors continue (Cairo's EXTEND_PAD)


def gradient_points(primitives: list[Primitive], shape: SceneObject, state: ObjectState) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Start and end of the gradient in scene coordinates (Manim units), from the drawing where it is."""
    from manim_studio.ui.stage.drawing_extra import placement_transform

    to_scene = placement_transform(("", "", state.x, state.y, state.rotation, state.scale, tuple(state.matrix)))
    box = QRectF()
    for primitive in primitives:
        if primitive.path is not None:
            box = box.united(to_scene.map(primitive.path).boundingRect())
    if not box.isValid() and box.width() <= 0 and box.height() <= 0:
        return None
    center = (box.center().x() / PX, -box.center().y() / PX)
    from manim_studio.model.attach import REDRAWN_MODES, attach_mode

    # a shape between or through objects is built in place in every frame, never turned: its direction stays
    turn = 0.0 if attach_mode(shape) in REDRAWN_MODES else state.rotation
    return gradient_line(center, box.width() / 2 / PX, box.height() / 2 / PX, sheen_direction(shape), turn)


def apply_gradients(primitives: list[Primitive], shape: SceneObject, state: ObjectState) -> None:
    """Give fills and outlines their second color (``state.fill_color2``/``stroke_color2``)."""
    if not state.fill_color2 and not state.stroke_color2:
        return
    from manim_studio.ui.stage.drawing_extra import placement_transform

    back, invertible = placement_transform(("", "", state.x, state.y, state.rotation, state.scale, tuple(state.matrix))).inverted()
    if not invertible:
        return
    # every dash of a dashed shape is a VMobject of its own with its own gradient
    for group in [[primitive] for primitive in primitives] if is_dashed(shape) else [primitives]:
        _paint_group(group, shape, state, back)


def _paint_group(primitives: list[Primitive], shape: SceneObject, state: ObjectState, back) -> None:
    line = gradient_points(primitives, shape, state)
    if line is None:
        return
    (sx, sy), (ex, ey) = line
    start, end = back.map(QPointF(sx * PX, -sy * PX)), back.map(QPointF(ex * PX, -ey * PX))
    for primitive in primitives:
        if primitive.path is None:
            continue
        if state.fill_color2 and primitive.brush is not None:
            primitive.brush = _gradient_brush(start, end, primitive.brush.color(), state.fill_color2)
        if state.stroke_color2 and primitive.pen is not None:
            pen = QPen(primitive.pen)
            pen.setBrush(_gradient_brush(start, end, primitive.pen.color(), state.stroke_color2))
            primitive.pen = pen
