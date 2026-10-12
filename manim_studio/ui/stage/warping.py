"""Bend the drawing of an object with the nonlinear maps it went through (``model/warps.py``).

The outlines are taken into the scene (where the object is), flattened into polylines,
moved point by point and taken back into the object's own coordinates, so the item
keeps its usual position, turn and scale.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainterPath, QTransform

from manim_studio.model.state import ObjectState
from manim_studio.model.warps import warp_polyline
from manim_studio.ui.stage.drawing import PX, Primitive

FINE = 10.0


def warp_path(path: QPainterPath, state: ObjectState) -> QPainterPath:
    """The path after the object's maps (local coordinates in, local coordinates out)."""
    from manim_studio.ui.stage.drawing_extra import placement_transform

    to_scene = placement_transform(("", "", state.x, state.y, state.rotation, state.scale, tuple(state.matrix)))
    back, invertible = to_scene.inverted()
    if not invertible:
        return path
    result = QPainterPath()
    result.setFillRule(path.fillRule())
    # flattened at ten times the resolution: a map can magnify, so curves need more corners than on screen
    for polygon in path.toSubpathPolygons(to_scene * QTransform.fromScale(FINE, FINE)):
        points = [(point.x() / PX / FINE, -point.y() / PX / FINE) for point in polygon]
        if len(points) < 2:
            continue
        closed = points[0] == points[-1]
        moved = warp_polyline(state.warps, points[:-1] if closed else points, closed)
        local = [back.map(QPointF(x * PX, -y * PX)) for x, y in moved]
        result.moveTo(local[0])
        for point in local[1:]:
            result.lineTo(point)
        if closed:
            result.closeSubpath()
    return result


def warp_primitives(primitives: list[Primitive], state: ObjectState) -> list[Primitive]:
    """Bend every outline; pictures (images) cannot be bent and stay as they are."""
    for primitive in primitives:
        if primitive.path is not None and primitive.image is None:
            primitive.path = warp_path(primitive.path, state)
        if primitive.image is None:
            primitive.rect = None  # a box that only widened the bounds no longer fits the bent shape
    return [primitive for primitive in primitives if primitive.path is not None or primitive.image is not None]
