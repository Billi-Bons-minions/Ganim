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
from manim_studio.ui.stage.effects import Effects, morph_path, trim_path
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
        self.effects = Effects()
        self.content_hidden = False
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

    def set_drawing(self, drawing: Drawing, ghost: bool, effects: Effects | None = None) -> None:
        """Replace the drawing, ghost flag and partial-animation effects."""
        self.prepareGeometryChange()
        self.drawing = drawing
        self.ghost = ghost
        self.effects = effects or Effects()
        self.update()

    def boundingRect(self) -> QRectF:  # noqa: N802 - Qt API
        margin = 6.0 / max(self.scale(), 0.01)
        rect = self.drawing.bounds.adjusted(-margin, -margin, margin, margin).united(self._primitive_bounds())
        if self.effects.morph is not None:
            rect = rect.united(self.effects.morph.bounds.adjusted(-margin, -margin, margin, margin))
        if self.effects.outline > 0:
            rect = rect.adjusted(-30, -30, 30, 30)
        return rect

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
        effects = self.effects
        painter.setOpacity((0.28 if self.ghost else 1.0) * max(0.0, min(1.0, effects.opacity)))
        if self.content_hidden:
            if self.isSelected():
                self._paint_outline(painter, theme_color("accent"), Qt.PenStyle.DashLine)
            return
        if effects.morph is not None and 0.0 < effects.morph_t < 1.0:
            self._paint_morph(painter)
        else:
            for primitive in self.drawing.primitives:
                if effects.draw < 1.0:
                    self._paint_partial(painter, primitive, effects.draw, effects.fill)
                else:
                    self._paint_primitive(painter, primitive, effects.fill)
        painter.setOpacity(1.0)
        if effects.outline > 0:
            self._paint_circumscribe(painter)
        if self.ghost:
            self._paint_outline(painter, QColor(170, 170, 170), Qt.PenStyle.DotLine)
        if self.isSelected():
            self._paint_outline(painter, theme_color("accent"), Qt.PenStyle.DashLine)

    @staticmethod
    def _faded_brush(brush: QBrush | None, fill: float) -> QBrush | None:
        if brush is None or fill >= 1.0:
            return brush
        color = QColor(brush.color())
        color.setAlphaF(color.alphaF() * max(0.0, fill))
        return QBrush(color)

    def _paint_primitive(self, painter: QPainter, primitive, fill: float = 1.0) -> None:
        if primitive.image is not None and primitive.rect is not None:
            alpha = primitive.brush.color().alphaF() if primitive.brush is not None else 1.0
            painter.save()
            painter.setOpacity(painter.opacity() * alpha)
            painter.drawImage(primitive.rect, primitive.image)
            painter.restore()
            return
        if primitive.path is None:
            return
        brush = self._faded_brush(primitive.brush, fill)
        painter.setPen(primitive.pen if primitive.pen is not None else Qt.PenStyle.NoPen)
        painter.setBrush(brush if brush is not None else Qt.BrushStyle.NoBrush)
        painter.drawPath(primitive.path)

    def _paint_partial(self, painter: QPainter, primitive, draw: float, fill: float) -> None:
        if primitive.image is not None and primitive.rect is not None:
            painter.save()
            rect = QRectF(primitive.rect)
            painter.setClipRect(QRectF(rect.left(), rect.top(), rect.width() * draw, rect.height()))
            self._paint_primitive(painter, primitive)
            painter.restore()
            return
        if primitive.path is None or draw <= 0:
            return
        if primitive.brush is not None and fill > 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._faded_brush(primitive.brush, fill))
            painter.drawPath(primitive.path)
        pen = QPen(primitive.pen) if primitive.pen is not None else QPen(primitive.brush.color() if primitive.brush else QColor("#FFFFFF"), 1.5)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(trim_path(primitive.path, draw))

    def _paint_morph(self, painter: QPainter) -> None:
        effects = self.effects
        assert effects.morph is not None
        path = morph_path(self.drawing, effects.morph, effects.morph_t)
        styled = next((p for p in self.drawing.primitives if p.path is not None), None)
        pen = QPen(styled.pen) if styled is not None and styled.pen is not None else Qt.PenStyle.NoPen
        brush = styled.brush if styled is not None and styled.brush is not None else Qt.BrushStyle.NoBrush
        painter.setPen(pen)
        painter.setBrush(brush)
        painter.drawPath(path)

    def _paint_circumscribe(self, painter: QPainter) -> None:
        frame = QPainterPath()
        frame.addRect(self.drawing.bounds.adjusted(-14, -14, 14, 14))
        progress = self.effects.outline
        pen = QPen(QColor(self.effects.outline_color), 4.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setOpacity(1.0 if progress < 0.75 else (1.0 - progress) / 0.25)
        painter.drawPath(trim_path(frame, min(1.0, progress / 0.6)))
        painter.setOpacity(1.0)

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
