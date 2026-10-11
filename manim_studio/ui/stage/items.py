"""Graphics items for objects and their manipulation handles."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QStyleOptionGraphicsItem,
    QWidget,
)

from manim_studio.ui.stage.drawing import Drawing
from manim_studio.ui.theme import color as theme_color

HANDLE_SIZE = 9.0
ROTATE_HANDLE_DISTANCE = 28.0

ROLE_SCALE = "scale"
ROLE_ROTATE = "rotate"


class ObjectItem(QGraphicsObject):
    """Displays one scene object; position and rotation follow the Manim state."""

    def __init__(self, object_id: str) -> None:
        super().__init__()
        self.object_id = object_id
        self.drawing = Drawing()
        self.ghost = False
        self.locked = False
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

    def set_drawing(self, drawing: Drawing, ghost: bool) -> None:
        """Replace the drawing (and whether it is shown as invisible ghost)."""
        self.prepareGeometryChange()
        self.drawing = drawing
        self.ghost = ghost
        self.update()

    def boundingRect(self) -> QRectF:  # noqa: N802 - Qt API
        margin = 6.0 / max(self.scale(), 0.01)
        return self.drawing.bounds.adjusted(-margin, -margin, margin, margin).united(self._primitive_bounds())

    def _primitive_bounds(self) -> QRectF:
        rect = QRectF()
        for primitive in self.drawing.primitives:
            if primitive.path is not None:
                width = primitive.pen.widthF() if primitive.pen is not None else 0.0
                rect = rect.united(primitive.path.boundingRect().adjusted(-width, -width, width, width))
        return rect

    def shape(self) -> QPainterPath:
        if self.drawing.hit_path is not None:
            return self.drawing.hit_path
        path = QPainterPath()
        path.addRect(self.drawing.bounds)
        return path

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        if self.ghost:
            painter.setOpacity(0.28)
        for primitive in self.drawing.primitives:
            self._paint_primitive(painter, primitive)
        painter.setOpacity(1.0)
        if self.ghost:
            self._paint_outline(painter, QColor(170, 170, 170), Qt.PenStyle.DotLine)
        if self.isSelected():
            self._paint_outline(painter, theme_color("accent"), Qt.PenStyle.DashLine)

    def _paint_primitive(self, painter: QPainter, primitive) -> None:
        if primitive.image is not None and primitive.rect is not None:
            alpha = primitive.brush.color().alphaF() if primitive.brush is not None else 1.0
            painter.save()
            painter.setOpacity(painter.opacity() * alpha)
            painter.drawImage(primitive.rect, primitive.image)
            painter.restore()
            return
        if primitive.path is None:
            return
        painter.setPen(primitive.pen if primitive.pen is not None else Qt.PenStyle.NoPen)
        painter.setBrush(primitive.brush if primitive.brush is not None else Qt.BrushStyle.NoBrush)
        painter.drawPath(primitive.path)

    def _paint_outline(self, painter: QPainter, color: QColor, style: Qt.PenStyle) -> None:
        pen = QPen(color, 1.2, style)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.drawing.bounds)


class HandleItem(QGraphicsItem):
    """A small square (scale) or circle (rotate) attached to an object item."""

    def __init__(self, parent: ObjectItem, role: str, corner: QPointF | None = None) -> None:
        super().__init__(parent)
        self.role = role
        self.corner = corner
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setZValue(10_000)
        cursor = Qt.CursorShape.CrossCursor if role == ROLE_ROTATE else Qt.CursorShape.SizeFDiagCursor
        self.setCursor(cursor)

    def boundingRect(self) -> QRectF:  # noqa: N802 - Qt API
        half = HANDLE_SIZE / 2 + 1
        return QRectF(-half, -half, 2 * half, 2 * half)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(theme_color("accent"), 1.5))
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        half = HANDLE_SIZE / 2
        if self.role == ROLE_ROTATE:
            painter.drawEllipse(QPointF(0, 0), half, half)
        else:
            painter.drawRect(QRectF(-half, -half, HANDLE_SIZE, HANDLE_SIZE))


def attach_handles(item: ObjectItem, view_scale: float, can_rotate: bool) -> list[HandleItem]:
    """Create scale handles at the corners and an optional rotation handle."""
    bounds = item.drawing.bounds
    handles = [
        HandleItem(item, ROLE_SCALE, corner)
        for corner in (bounds.topLeft(), bounds.topRight(), bounds.bottomLeft(), bounds.bottomRight())
    ]
    for handle in handles:
        handle.setPos(handle.corner)
    if can_rotate:
        rotate = HandleItem(item, ROLE_ROTATE)
        distance = ROTATE_HANDLE_DISTANCE / max(view_scale * item.scale(), 0.01)
        rotate.setPos(QPointF(bounds.center().x(), bounds.top() - distance))
        handles.append(rotate)
    return handles
