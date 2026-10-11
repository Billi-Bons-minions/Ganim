"""The stage: a zoomable view in Manim coordinates with direct manipulation."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import shiboken6
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QWidget

from manim_studio.model.entities import Scene
from manim_studio.model.stage_edits import MOVE, ROTATE, SCALE
from manim_studio.model.state import ObjectState
from manim_studio.model.types import FRAME_HEIGHT, FRAME_WIDTH
from manim_studio.ui.stage.drawing import PX, StageResources, build_drawing, pt
from manim_studio.ui.theme import color as theme_color
from manim_studio.ui.stage.items import (
    ROLE_ROTATE,
    HandleItem,
    ObjectItem,
    attach_handles,
)

KIND_MIME = "application/x-manim-studio-kind"
FRAME_MARGIN = 0.6
ROTATION_SNAP = 15.0
SCALE_SNAP = 0.05

#: ``policy(action, object_ids) -> (allowed, message)``
EditPolicy = Callable[[str, list[str]], tuple[bool, str]]


@dataclass
class _Drag:
    mode: str
    press: QPointF
    ids: list[str]
    origins: dict[str, QPointF] = field(default_factory=dict)
    center: QPointF = field(default_factory=QPointF)
    scale: float = 1.0
    rotation: float = 0.0
    value: float = 0.0
    delta: QPointF = field(default_factory=QPointF)


class StageView(QGraphicsView):
    """Shows the scene at the current timeline position and lets the user edit it."""

    selectionEdited = Signal(list)
    moveRequested = Signal(list, float, float)
    scaleRequested = Signal(str, float)
    rotateRequested = Signal(str, float)
    dropRequested = Signal(str, float, float)
    contextMenuRequested = Signal(QPoint, str)
    cursorMoved = Signal(float, float)
    statusMessage = Signal(str)
    zoomChanged = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(QRectF(-40 * PX, -25 * PX, 80 * PX, 50 * PX))
        self._scene.selectionChanged.connect(self._on_scene_selection)
        self.setScene(self._scene)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._items: dict[str, ObjectItem] = {}
        self._handles: list[HandleItem] = []
        self._selection: list[str] = []
        self._updating = False
        self._drag: _Drag | None = None
        self._pan_origin: QPoint | None = None
        self._policy: EditPolicy = lambda action, ids: (True, "")
        self._background = QColor("#000000")
        self._show_grid = True
        self._grid_step = 0.5
        self._snap = True
        self._auto_fit = True
        self._motion_paths: list[tuple[QPointF, QPointF]] = []

    # --- configuration --------------------------------------------------------

    def set_policy(self, policy: EditPolicy) -> None:
        """Install the function that decides which edits are allowed."""
        self._policy = policy

    def set_motion_paths(self, paths: list[tuple[tuple[float, float], tuple[float, float]]]) -> None:
        """Show dashed arrows for Move animations of the selected step."""
        self._motion_paths = [(pt(*start), pt(*end)) for start, end in paths]
        self.viewport().update()

    def set_grid(self, show: bool, step: float, snap: bool) -> None:
        """Configure grid display and snapping."""
        self._show_grid, self._grid_step, self._snap = show, max(0.05, step), snap
        self.viewport().update()

    def fit_frame(self) -> None:
        """Zoom so that the whole Manim frame is visible."""
        half_w, half_h = FRAME_WIDTH / 2 + FRAME_MARGIN, FRAME_HEIGHT / 2 + FRAME_MARGIN
        self.fitInView(QRectF(pt(-half_w, half_h), pt(half_w, -half_h)), Qt.AspectRatioMode.KeepAspectRatio)
        self._auto_fit = True
        self._refresh_handles()
        self.zoomChanged.emit(self.zoom_percent())

    def zoom(self, factor: float) -> None:
        """Zoom in (>1) or out (<1)."""
        current = self.transform().m11()
        factor = max(0.02 / current, min(factor, 20.0 / current))
        self.scale(factor, factor)
        self._auto_fit = False
        self._refresh_handles()
        self.zoomChanged.emit(self.zoom_percent())

    def view_scale(self) -> float:
        """Return the current zoom (screen pixels per scene pixel)."""
        return self.transform().m11()

    def zoom_percent(self) -> float:
        """Return the zoom relative to "one Manim unit = 100 screen pixels"."""
        return self.view_scale()

    # --- content --------------------------------------------------------------

    def set_content(
        self,
        scene: Scene,
        states: dict[str, ObjectState],
        resources: StageResources,
        selected: list[str],
        show_hidden: bool,
    ) -> None:
        """Synchronize the items with the model state."""
        self._updating = True
        self._clear_handles()
        self._background = QColor(scene.background_color)
        known = set()
        for index, obj in enumerate(scene.objects):
            state = states.get(obj.id)
            if state is None:
                continue
            known.add(obj.id)
            item = self._items.get(obj.id)
            if item is None:
                item = ObjectItem(obj.id)
                self._items[obj.id] = item
                self._scene.addItem(item)
            shape = scene.object_by_id(state.shape_id) or obj
            item.set_drawing(build_drawing(scene, shape, state, resources), ghost=not state.visible)
            item.setVisible(state.visible or show_hidden)
            item.setPos(pt(state.x, state.y))
            item.setRotation(-state.rotation)
            item.setScale(state.scale)
            item.setZValue(obj.z_index * 10_000 + index)
        for object_id in [object_id for object_id in self._items if object_id not in known]:
            self._scene.removeItem(self._items.pop(object_id))
        self._apply_selection(selected)
        self._updating = False
        self._refresh_handles()
        self.viewport().update()

    def _apply_selection(self, selected: list[str]) -> None:
        self._selection = [object_id for object_id in selected if object_id in self._items]
        for object_id, item in self._items.items():
            item.setSelected(object_id in self._selection and item.isVisible())

    def set_selection(self, selected: list[str]) -> None:
        """Select items without emitting :attr:`selectionEdited`."""
        self._updating = True
        self._apply_selection(selected)
        self._updating = False
        self._refresh_handles()

    def _clear_handles(self) -> None:
        for handle in self._handles:
            if shiboken6.isValid(handle) and handle.scene() is not None:
                self._scene.removeItem(handle)
        self._handles = []

    def _refresh_handles(self) -> None:
        self._clear_handles()
        if len(self._selection) != 1:
            return
        item = self._items.get(self._selection[0])
        if item is None or not item.isVisible():
            return
        self._handles = attach_handles(item, self.view_scale(), can_rotate=True)

    # --- selection ------------------------------------------------------------

    def _on_scene_selection(self) -> None:
        if self._updating:
            return
        current = {item.object_id for item in self._scene.selectedItems() if isinstance(item, ObjectItem)}
        ordered = [object_id for object_id in self._selection if object_id in current]
        ordered += sorted(object_id for object_id in current if object_id not in ordered)
        self._selection = ordered
        self._refresh_handles()
        self.selectionEdited.emit(list(ordered))

    def _emit_selection(self, ids: list[str]) -> None:
        self.set_selection(ids)
        self.selectionEdited.emit(list(self._selection))

    def _object_item_at(self, position: QPoint) -> ObjectItem | None:
        for item in self.items(position):
            if isinstance(item, ObjectItem) and item.isVisible():
                return item
        return None

    def _handle_at(self, position: QPoint) -> HandleItem | None:
        for item in self.items(position):
            if isinstance(item, HandleItem):
                return item
        return None

    # --- snapping ---------------------------------------------------------------

    def _snapping(self, modifiers: Qt.KeyboardModifier) -> bool:
        return self._snap != bool(modifiers & Qt.KeyboardModifier.AltModifier)

    def _snap_value(self, value: float, modifiers: Qt.KeyboardModifier) -> float:
        if not self._snapping(modifiers):
            return round(value, 4)
        return round(round(value / self._grid_step) * self._grid_step, 4)

    # --- mouse ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        position = event.position().toPoint()
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_origin = position
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self.setFocus()
        handle = self._handle_at(position)
        if handle is not None and self._selection:
            self._start_handle_drag(handle, self.mapToScene(position))
            return
        item = self._object_item_at(position)
        if item is None:
            super().mousePressEvent(event)
            return
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            ids = [i for i in self._selection if i != item.object_id]
            if item.object_id not in self._selection:
                ids.append(item.object_id)
            self._emit_selection(ids)
            return
        if item.object_id not in self._selection:
            self._emit_selection([item.object_id])
        self._start_move(self.mapToScene(position))

    def _allowed(self, action: str, ids: list[str]) -> bool:
        allowed, message = self._policy(action, ids)
        if not allowed:
            self.statusMessage.emit(message)
        return allowed

    def _start_move(self, press: QPointF) -> None:
        ids = list(self._selection)
        if not self._allowed(MOVE, ids):
            return
        origins = {object_id: QPointF(self._items[object_id].pos()) for object_id in ids}
        self._drag = _Drag(MOVE, press, ids, origins)

    def _start_handle_drag(self, handle: HandleItem, press: QPointF) -> None:
        object_id = self._selection[0]
        action = ROTATE if handle.role == ROLE_ROTATE else SCALE
        if not self._allowed(action, [object_id]):
            return
        item = self._items[object_id]
        self._drag = _Drag(action, press, [object_id], center=QPointF(item.pos()), scale=item.scale(), rotation=item.rotation())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        position = event.position().toPoint()
        scene_pos = self.mapToScene(position)
        self.cursorMoved.emit(scene_pos.x() / PX, -scene_pos.y() / PX)
        if self._pan_origin is not None:
            delta = position - self._pan_origin
            self._pan_origin = position
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            return
        if self._drag is None:
            super().mouseMoveEvent(event)
            return
        if self._drag.mode == MOVE:
            self._update_move(scene_pos, event.modifiers())
        elif self._drag.mode == SCALE:
            self._update_scale(scene_pos, event.modifiers())
        else:
            self._update_rotation(scene_pos, event.modifiers())

    def _update_move(self, scene_pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        drag = self._drag
        assert drag is not None
        primary = drag.origins[drag.ids[0]]
        raw = primary + (scene_pos - drag.press)
        snapped = QPointF(self._snap_value(raw.x() / PX, modifiers) * PX, -self._snap_value(-raw.y() / PX, modifiers) * PX)
        drag.delta = snapped - primary
        for object_id, origin in drag.origins.items():
            self._items[object_id].setPos(origin + drag.delta)

    def _update_scale(self, scene_pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        drag = self._drag
        assert drag is not None
        start = math.hypot(drag.press.x() - drag.center.x(), drag.press.y() - drag.center.y())
        now = math.hypot(scene_pos.x() - drag.center.x(), scene_pos.y() - drag.center.y())
        factor = max(0.05, now / max(start, 1.0))
        if self._snapping(modifiers):
            factor = max(SCALE_SNAP, round(factor / SCALE_SNAP) * SCALE_SNAP)
        drag.value = factor
        self._items[drag.ids[0]].setScale(drag.scale * factor)
        self.statusMessage.emit(f"× {factor:.2f}")

    def _angle(self, scene_pos: QPointF, center: QPointF) -> float:
        return math.degrees(math.atan2(-(scene_pos.y() - center.y()), scene_pos.x() - center.x()))

    def _update_rotation(self, scene_pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        drag = self._drag
        assert drag is not None
        delta = self._angle(scene_pos, drag.center) - self._angle(drag.press, drag.center)
        delta = (delta + 180.0) % 360.0 - 180.0
        if self._snapping(modifiers) or modifiers & Qt.KeyboardModifier.ShiftModifier:
            delta = round(delta / ROTATION_SNAP) * ROTATION_SNAP
        drag.value = delta
        self._items[drag.ids[0]].setRotation(drag.rotation - delta)
        self.statusMessage.emit(f"{delta:+.0f}°")

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.MiddleButton and self._pan_origin is not None:
            self._pan_origin = None
            self.unsetCursor()
            return
        drag, self._drag = self._drag, None
        if drag is None:
            super().mouseReleaseEvent(event)
            return
        if drag.mode == MOVE and (abs(drag.delta.x()) > 1e-6 or abs(drag.delta.y()) > 1e-6):
            self.moveRequested.emit(drag.ids, round(drag.delta.x() / PX, 4), round(-drag.delta.y() / PX, 4))
        elif drag.mode == SCALE and drag.value and abs(drag.value - 1.0) > 1e-4:
            self.scaleRequested.emit(drag.ids[0], drag.value)
        elif drag.mode == ROTATE and abs(drag.value) > 1e-4:
            self.rotateRequested.emit(drag.ids[0], drag.value)

    def contextMenuEvent(self, event) -> None:  # noqa: N802 - Qt API
        item = self._object_item_at(event.pos())
        if item is not None and item.object_id not in self._selection:
            self._emit_selection([item.object_id])
        self.contextMenuRequested.emit(event.globalPos(), item.object_id if item else "")

    # --- keyboard and wheel -------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API
        offsets = {
            Qt.Key.Key_Left: (-1.0, 0.0),
            Qt.Key.Key_Right: (1.0, 0.0),
            Qt.Key.Key_Up: (0.0, 1.0),
            Qt.Key.Key_Down: (0.0, -1.0),
        }
        if event.key() in offsets and self._selection:
            step = 1.0 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else (self._grid_step if self._snap else 0.1)
            dx, dy = offsets[event.key()]
            if self._allowed(MOVE, list(self._selection)):
                self.moveRequested.emit(list(self._selection), dx * step, dy * step)
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt API
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom(1.15 ** (event.angleDelta().y() / 120.0))
            return
        super().wheelEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if self._auto_fit:
            self.fit_frame()

    # --- drag and drop from the library -------------------------------------------------

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.mimeData().hasFormat(KIND_MIME):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.mimeData().hasFormat(KIND_MIME):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt API
        if not event.mimeData().hasFormat(KIND_MIME):
            super().dropEvent(event)
            return
        kind = bytes(event.mimeData().data(KIND_MIME).data()).decode("utf-8")
        scene_pos = self.mapToScene(event.position().toPoint())
        modifiers = event.modifiers()
        x = self._snap_value(scene_pos.x() / PX, modifiers)
        y = self._snap_value(-scene_pos.y() / PX, modifiers)
        event.acceptProposedAction()
        self.dropRequested.emit(kind, x, y)

    # --- painting ------------------------------------------------------------------------

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802 - Qt API
        painter.fillRect(rect, theme_color("stage_outside"))
        frame = QRectF(pt(-FRAME_WIDTH / 2, FRAME_HEIGHT / 2), pt(FRAME_WIDTH / 2, -FRAME_HEIGHT / 2))
        painter.fillRect(frame, self._background)
        if self._show_grid:
            self._draw_grid(painter, rect)
        border = QPen(theme_color("border_strong"), 1.0)
        border.setCosmetic(True)
        painter.setPen(border)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(frame)

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802 - Qt API
        if not self._motion_paths:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        record = theme_color("record")
        pen = QPen(record, 2.0, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        scale = max(self.view_scale(), 0.01)
        for start, end in self._motion_paths:
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(start, end)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(record)
            painter.drawEllipse(start, 4 / scale, 4 / scale)
            angle = math.atan2(end.y() - start.y(), end.x() - start.x())
            size = 12 / scale
            left = QPointF(end.x() - size * math.cos(angle - 0.45), end.y() - size * math.sin(angle - 0.45))
            right = QPointF(end.x() - size * math.cos(angle + 0.45), end.y() - size * math.sin(angle + 0.45))
            painter.drawPolygon([end, left, right])

    def _grid_color(self, alpha: int) -> QColor:
        light = self._background.lightnessF() > 0.6
        base = QColor(0, 0, 0) if light else QColor(255, 255, 255)
        base.setAlpha(alpha)
        return base

    def _draw_grid(self, painter: QPainter, rect: QRectF) -> None:
        left, right = math.floor(rect.left() / PX), math.ceil(rect.right() / PX)
        top, bottom = math.floor(rect.top() / PX), math.ceil(rect.bottom() / PX)
        if self._grid_step < 1.0 and self.view_scale() * self._grid_step * PX > 8:
            self._draw_lines(painter, rect, self._grid_step, self._grid_color(14))
        self._draw_lines(painter, rect, 1.0, self._grid_color(34))
        axis = QPen(self._grid_color(80), 1.0)
        axis.setCosmetic(True)
        painter.setPen(axis)
        if left <= 0 <= right:
            painter.drawLine(QPointF(0, top * PX), QPointF(0, bottom * PX))
        if top <= 0 <= bottom:
            painter.drawLine(QPointF(left * PX, 0), QPointF(right * PX, 0))

    def _draw_lines(self, painter: QPainter, rect: QRectF, step: float, color: QColor) -> None:
        pen = QPen(color, 1.0)
        pen.setCosmetic(True)
        painter.setPen(pen)
        spacing = step * PX
        x = math.floor(rect.left() / spacing) * spacing
        while x <= rect.right():
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            x += spacing
        y = math.floor(rect.top() / spacing) * spacing
        while y <= rect.bottom():
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            y += spacing
