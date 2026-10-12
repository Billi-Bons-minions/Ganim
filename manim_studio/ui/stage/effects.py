"""Helpers to draw partially finished animations (trim, morph, outline)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath, QPolygonF

from manim_studio.ui.stage.drawing import Drawing

MORPH_SAMPLES = 160


@dataclass
class Effects:
    """Per-item partial-animation settings taken from :class:`ObjectState`."""

    opacity: float = 1.0
    draw: float = 1.0
    fill: float = 1.0
    morph: Drawing | None = None
    morph_t: float = 0.0
    outline: float = 0.0
    outline_color: str = "#F7D96F"
    morph_weights: tuple[complex, complex] | None = None

    def is_plain(self) -> bool:
        """Return ``True`` if nothing special has to be drawn."""
        return self.opacity >= 1.0 and self.draw >= 1.0 and self.fill >= 1.0 and self.morph is None and self.outline <= 0.0


def _length(polygon: QPolygonF) -> float:
    return sum(math.dist((polygon[i].x(), polygon[i].y()), (polygon[i + 1].x(), polygon[i + 1].y())) for i in range(polygon.size() - 1))


def trim_path(path: QPainterPath, fraction: float) -> QPainterPath:
    """Return the first ``fraction`` of a path's outline (all subpaths in order)."""
    polygons = path.toSubpathPolygons()
    total = sum(_length(polygon) for polygon in polygons)
    remaining = total * max(0.0, min(1.0, fraction))
    result = QPainterPath()
    for polygon in polygons:
        if remaining <= 0 or polygon.size() < 2:
            break
        result.moveTo(polygon[0])
        for index in range(1, polygon.size()):
            start, end = polygon[index - 1], polygon[index]
            segment = math.dist((start.x(), start.y()), (end.x(), end.y()))
            if segment >= remaining:
                ratio = remaining / segment if segment else 0.0
                result.lineTo(QPointF(start.x() + (end.x() - start.x()) * ratio, start.y() + (end.y() - start.y()) * ratio))
                remaining = 0
                break
            result.lineTo(end)
            remaining -= segment
    return result


def _main_outline(drawing: Drawing) -> QPolygonF:
    best = QPolygonF()
    best_length = -1.0
    for primitive in drawing.primitives:
        if primitive.path is None:
            if primitive.rect is not None and primitive.image is not None:
                rect = QRectF(primitive.rect)
                polygon = QPolygonF([rect.topLeft(), rect.topRight(), rect.bottomRight(), rect.bottomLeft(), rect.topLeft()])
                if _length(polygon) > best_length:
                    best, best_length = polygon, _length(polygon)
            continue
        for polygon in primitive.path.toSubpathPolygons():
            length = _length(polygon)
            if length > best_length:
                best, best_length = polygon, length
    return best


def _resample(polygon: QPolygonF, count: int) -> list[QPointF]:
    if polygon.size() < 2:
        return [QPointF(0, 0)] * count
    total = _length(polygon) or 1.0
    points: list[QPointF] = []
    index, travelled = 1, 0.0
    for sample in range(count):
        target = total * sample / (count - 1)
        while index < polygon.size() - 1:
            segment = math.dist((polygon[index - 1].x(), polygon[index - 1].y()), (polygon[index].x(), polygon[index].y()))
            if travelled + segment >= target:
                break
            travelled += segment
            index += 1
        start, end = polygon[index - 1], polygon[index]
        segment = math.dist((start.x(), start.y()), (end.x(), end.y())) or 1.0
        ratio = max(0.0, min(1.0, (target - travelled) / segment))
        points.append(QPointF(start.x() + (end.x() - start.x()) * ratio, start.y() + (end.y() - start.y()) * ratio))
    return points


def morph_path(source: Drawing, target: Drawing, t: float, weights: tuple[complex, complex] | None = None) -> QPainterPath:
    """Interpolate between the main outlines of two drawings.

    ``weights`` (a Transform on an arc) mix the outlines as complex numbers, so the
    points travel on arcs; they are meant for y pointing up, the stage's y points down.
    """
    first = _resample(_main_outline(source), MORPH_SAMPLES)
    second = _resample(_main_outline(target), MORPH_SAMPLES)
    path = QPainterPath()
    for index, (a, b) in enumerate(zip(first, second)):
        if weights is None:
            point = QPointF(a.x() + (b.x() - a.x()) * t, a.y() + (b.y() - a.y()) * t)
        else:
            mixed = weights[0].conjugate() * complex(a.x(), a.y()) + weights[1].conjugate() * complex(b.x(), b.y())
            point = QPointF(mixed.real, mixed.imag)
        if index == 0:
            path.moveTo(point)
        else:
            path.lineTo(point)
    path.closeSubpath()
    return path
