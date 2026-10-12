"""The stage: a zoomable view in Manim coordinates with direct manipulation."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import shiboken6
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QKeyEvent, QMouseEvent, QPainter, QPen, QPixmap, QTransform, QWheelEvent
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView, QWidget

from manim_studio.model import groups
from manim_studio.model.entities import Scene
from manim_studio.model.stage_edits import MOVE, ROTATE, SCALE
from manim_studio.model.state import ObjectState
from manim_studio.model.three_d import View, depth_order, is_3d
from manim_studio.model.types import FRAME_HEIGHT, FRAME_WIDTH, INVISIBLE_KINDS, LINE_KINDS, ObjectKind
from manim_studio.ui.stage.drawing import PX, StageResources, build_drawing, pt
from manim_studio.ui.stage.effects import Effects
from manim_studio.ui.stage.items import (
    ROLE_ENDPOINT,
    ROLE_ROTATE,
    ROLE_VERTEX,
    GroupItem,
    HandleItem,
    ObjectItem,
    attach_handles,
    attach_point_handles,
)
from manim_studio.ui.theme import color as theme_color

KIND_MIME = "application/x-manim-studio-kind"
COMPONENT_MIME = "application/x-manim-studio-component"
FRAME_MARGIN = 0.6
ROTATION_SNAP = 15.0
SCALE_SNAP = 0.05
GUIDE_DISTANCE = 7.0
DRAG_VERTEX = "vertex"
DRAG_ENDPOINT = "endpoint"

#: ``policy(action, object_ids) -> (allowed, message)``
EditPolicy = Callable[[str, list[str]], tuple[bool, str]]


def local_matrix(matrix: tuple[float, float, float, float], rotation: float) -> QTransform:
    """The item transform for a linear map that the state keeps inside the object's rotation.

    The state draws ``R · M · shape`` (``M`` in scene axes, y up), but Qt applies an item's
    base transform after its rotation, so the map is turned into ``R · M · R⁻¹`` and its
    y axis is flipped for the stage (y down).
    """
    if matrix == (1.0, 0.0, 0.0, 1.0):
        return QTransform()
    radians = math.radians(rotation)
    cos, sin = math.cos(radians), math.sin(radians)
    m11, m12, m21, m22 = matrix
    # R · M
    a, b, c, d = cos * m11 - sin * m21, cos * m12 - sin * m22, sin * m11 + cos * m21, sin * m12 + cos * m22
    # (R · M) · R⁻¹
    p, q, r, s = a * cos - b * sin, a * sin + b * cos, c * cos - d * sin, c * sin + d * cos
    return QTransform(p, -r, -q, s, 0.0, 0.0)


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
    handle: HandleItem | None = None
    point: QPointF = field(default_factory=QPointF)


class StageView(QGraphicsView):
    """Shows the scene at the current timeline position and lets the user edit it."""

    selectionEdited = Signal(list)
    moveRequested = Signal(list, float, float)
    scaleRequested = Signal(str, float)
    rotateRequested = Signal(str, float)
    dropRequested = Signal(str, float, float)
    componentDropRequested = Signal(str, float, float)
    contextMenuRequested = Signal(QPoint, str)
    cursorMoved = Signal(float, float)
    statusMessage = Signal(str)
    zoomChanged = Signal(float)
    viewChanged = Signal()
    vertexMoved = Signal(str, int, float, float)
    vertexInserted = Signal(str, int, float, float)
    vertexMenuRequested = Signal(QPoint, str, int)
    endpointMoved = Signal(str, int, float, float)

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
        self.horizontalScrollBar().valueChanged.connect(lambda _value: self.viewChanged.emit())
        self.verticalScrollBar().valueChanged.connect(lambda _value: self.viewChanged.emit())
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
        self._guides: list[tuple[QPointF, QPointF]] = []
        self._exact_item: QGraphicsPixmapItem | None = None
        self._scene_model: Scene | None = None
        self._entered_group: str | None = None
        self._point_editing = False
        self._frame_size = (FRAME_WIDTH, FRAME_HEIGHT)

    # --- configuration --------------------------------------------------------

    def set_policy(self, policy: EditPolicy) -> None:
        """Install the function that decides which edits are allowed."""
        self._policy = policy

    def set_point_editing(self, enabled: bool) -> None:
        """Allow editing polygon vertices and line endpoints (only at the start)."""
        self._point_editing = enabled

    def set_exact_image(self, path: object) -> None:
        """Show a Manim-rendered PNG of the frame instead of the approximate drawing."""
        if path is None:
            if self._exact_item is not None:
                self._scene.removeItem(self._exact_item)
                self._exact_item = None
            for item in self._items.values():
                item.content_hidden = False
                item.update()
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return
        if self._exact_item is None:
            self._exact_item = QGraphicsPixmapItem()
            self._exact_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self._exact_item.setZValue(-1_000_000)
            self._exact_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
            self._scene.addItem(self._exact_item)
        frame = self.frame_rect()
        self._exact_item.setPixmap(pixmap)
        self._exact_item.setPos(frame.topLeft())
        self._exact_item.setScale(frame.width() / max(1, pixmap.width()))
        for item in self._items.values():
            item.content_hidden = True
            item.update()

    def has_exact_image(self) -> bool:
        """Return ``True`` while the exact image is shown."""
        return self._exact_item is not None

    def set_motion_paths(self, paths: list[tuple[tuple[float, float], tuple[float, float]]]) -> None:
        """Show dashed arrows for Move animations of the selected step."""
        self._motion_paths = [(pt(*start), pt(*end)) for start, end in paths]
        self.viewport().update()

    def set_grid(self, show: bool, step: float, snap: bool) -> None:
        """Configure grid display and snapping."""
        self._show_grid, self._grid_step, self._snap = show, max(0.05, step), snap
        self.viewport().update()

    def frame_rect(self) -> QRectF:
        """Return the Manim frame in scene pixels."""
        width, height = self._frame_size
        return QRectF(pt(-width / 2, height / 2), pt(width / 2, -height / 2))

    def set_frame_size(self, width: float, height: float) -> None:
        """Change the video format (frame size in Manim units)."""
        if (width, height) == self._frame_size:
            return
        self._frame_size = (width, height)
        if self._auto_fit:
            self.fit_frame()
        self.viewport().update()

    def fit_frame(self) -> None:
        """Zoom so that the whole Manim frame is visible."""
        self.fitInView(self.frame_rect().adjusted(-FRAME_MARGIN * PX, -FRAME_MARGIN * PX, FRAME_MARGIN * PX, FRAME_MARGIN * PX), Qt.AspectRatioMode.KeepAspectRatio)
        self._auto_fit = True
        self._after_zoom()

    def zoom_to(self, rect: QRectF) -> None:
        """Zoom onto a scene rectangle (e.g. the selection)."""
        if rect.isEmpty():
            return
        margin = max(rect.width(), rect.height()) * 0.25 + PX * 0.5
        self.fitInView(rect.adjusted(-margin, -margin, margin, margin), Qt.AspectRatioMode.KeepAspectRatio)
        self._auto_fit = False
        self._after_zoom()

    def follow_rect(self, rect: QRectF) -> None:
        """Show exactly ``rect`` (the camera's view) without changing the auto-fit mode."""
        if rect.isEmpty():
            return
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        self._auto_fit = False
        self._refresh_handles()
        self.zoomChanged.emit(self.zoom_percent())
        self.viewChanged.emit()

    def zoom(self, factor: float) -> None:
        """Zoom in (>1) or out (<1)."""
        current = self.transform().m11()
        factor = max(0.02 / current, min(factor, 20.0 / current))
        self.scale(factor, factor)
        self._auto_fit = False
        self._after_zoom()

    def _after_zoom(self) -> None:
        self._refresh_handles()
        self.zoomChanged.emit(self.zoom_percent())
        self.viewChanged.emit()

    def view_scale(self) -> float:
        """Return the current zoom (screen pixels per scene pixel)."""
        return self.transform().m11()

    def zoom_percent(self) -> float:
        """Return the zoom relative to "one Manim unit = 100 screen pixels"."""
        return self.view_scale()

    # --- content --------------------------------------------------------------

    def _render_lens_views(self) -> None:
        """Draw what a zoom lens frames into its display (outside of painting: Qt cannot nest scene renders)."""
        for item in self._items.values():
            for primitive in item.drawing.primitives:
                if primitive.view_source is None or primitive.rect is None:
                    continue
                size = primitive.rect.size() * 2.0
                image = QImage(max(1, round(size.width())), max(1, round(size.height())), QImage.Format.Format_ARGB32_Premultiplied)
                image.fill(Qt.GlobalColor.transparent)
                painter = QPainter(image)
                painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
                ObjectItem.rendering_view = True  # the lens leaves itself out
                try:
                    self._scene.render(painter, QRectF(image.rect()), primitive.view_source, Qt.AspectRatioMode.IgnoreAspectRatio)
                finally:
                    ObjectItem.rendering_view = False
                    painter.end()
                primitive.image = image
                primitive.brush = QBrush(QColor(255, 255, 255))
                item.update()

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
        self._scene_model = scene
        self._background = QColor(scene.background_color)
        if self._entered_group is not None and not groups.is_group(scene.object_by_id(self._entered_group)):
            self._entered_group = None
        known = set()
        # in 3D scenes Manim draws shaded objects sorted by depth and everything else above them
        depth_ranks = depth_order(scene, resources.view3d or View(), resources.values, states) if is_3d(scene) else {}
        for index, obj in enumerate(scene.objects):
            state = states.get(obj.id)
            if state is None or obj.kind in INVISIBLE_KINDS:
                continue
            known.add(obj.id)
            item = self._items.get(obj.id)
            if item is None or isinstance(item, GroupItem):
                if item is not None:
                    self._scene.removeItem(item)
                item = ObjectItem(obj.id)
                self._items[obj.id] = item
                self._scene.addItem(item)
            shape = scene.object_by_id(state.shape_id) or obj
            effects = Effects(state.opacity, state.draw, state.fill, None, state.morph_t, state.outline, state.outline_color)
            morph_shape = scene.object_by_id(state.morph_to) if state.morph_to else None
            if morph_shape is not None:
                effects.morph = build_drawing(scene, morph_shape, state, resources)
            item.set_drawing(build_drawing(scene, shape, state, resources), ghost=not state.visible, effects=effects)
            item.setVisible((state.visible or show_hidden) and not obj.editor_hidden)
            item.locked = obj.locked
            item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, not obj.locked)
            item.setPos(pt(state.x, state.y))
            item.setRotation(-state.rotation)
            # the lens draws its zoom itself (its display keeps its size)
            item.setScale(1.0 if obj.kind == ObjectKind.ZOOM_LENS else state.scale)
            item.setTransform(local_matrix(state.matrix, state.rotation))
            if obj.kind == ObjectKind.CAMERA:
                item.setZValue(9_000_000)
            elif obj.kind == ObjectKind.ZOOM_LENS:
                item.setZValue(8_900_000)  # a foreground mobject in Manim
            elif obj.id in depth_ranks:
                item.setZValue(-900_000 + depth_ranks[obj.id])  # above the exact frame (-1 000 000)
            else:
                item.setZValue(obj.z_index * 10_000 + index)
            item.content_hidden = self._exact_item is not None
        self._sync_groups(scene, known)
        self._render_lens_views()
        for object_id in [object_id for object_id in self._items if object_id not in known]:
            self._scene.removeItem(self._items.pop(object_id))
        self._apply_selection(selected)
        self._updating = False
        self._refresh_handles()
        self.viewport().update()

    def _sync_groups(self, scene: Scene, known: set[str]) -> None:
        for obj in scene.objects:
            if not groups.is_group(obj):
                continue
            members = [self._items[leaf] for leaf in groups.leaves(scene, obj.id) if leaf in self._items and self._items[leaf].isVisible()]
            item = self._items.get(obj.id)
            if not isinstance(item, GroupItem):
                if item is not None:
                    self._scene.removeItem(item)
                item = GroupItem(obj.id)
                self._items[obj.id] = item
                self._scene.addItem(item)
            known.add(obj.id)
            rect = QRectF()
            for member in members:
                rect = rect.united(member.mapRectToScene(member.drawing.bounds))
            item.set_rect(rect if not rect.isNull() else QRectF(0, 0, 1, 1))
            item.setVisible(bool(members))
            item.setZValue(5_000_000)

    def item_rect(self, object_id: str) -> QRectF:
        """Return the drawn bounds of an object (or group) in scene pixels."""
        item = self._items.get(object_id)
        if item is None:
            return QRectF()
        return item.mapRectToScene(item.drawing.bounds)

    def selection_rect(self) -> QRectF:
        """Return the union of the selected objects' bounds."""
        rect = QRectF()
        for object_id in self._selection:
            rect = rect.united(self.item_rect(object_id))
        return rect

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
        if item is None or not item.isVisible() or item.locked:
            return
        obj = self._scene_model.object_by_id(item.object_id) if self._scene_model else None
        if obj is not None and self._point_editing and obj.kind in LINE_KINDS:
            half = item.drawing.bounds.width() / 2
            self._handles = attach_point_handles(item, [QPointF(-half, 0), QPointF(half, 0)], ROLE_ENDPOINT)
            return
        self._handles = attach_handles(item, self.view_scale(), can_rotate=True)
        if obj is not None and self._point_editing and obj.kind == ObjectKind.POLYGON:
            offset = item.drawing.offset
            local = [pt(float(x), float(y)) - offset for x, y in obj.params.get("points", [])]
            self._handles += attach_point_handles(item, local, ROLE_VERTEX)

    # --- selection ------------------------------------------------------------

    def _selectable_id(self, object_id: str) -> str:
        """Map a clicked object to what gets selected (its group unless entered)."""
        if self._scene_model is None:
            return object_id
        chain = [object_id] + groups.ancestors(self._scene_model, object_id)
        if self._entered_group in chain:
            index = chain.index(self._entered_group)
            return chain[index - 1] if index > 0 else object_id
        return chain[-1]

    def _on_scene_selection(self) -> None:
        if self._updating:
            return
        current: list[str] = []
        for item in self._scene.selectedItems():
            if isinstance(item, ObjectItem) and not isinstance(item, GroupItem):
                target = self._selectable_id(item.object_id)
                if target not in current:
                    current.append(target)
        ordered = [object_id for object_id in self._selection if object_id in current]
        ordered += [object_id for object_id in current if object_id not in ordered]
        self._updating = True
        self._apply_selection(ordered)
        self._updating = False
        self._refresh_handles()
        self.selectionEdited.emit(list(ordered))

    def _emit_selection(self, ids: list[str]) -> None:
        self.set_selection(ids)
        self.selectionEdited.emit(list(self._selection))

    def _object_item_at(self, position: QPoint) -> ObjectItem | None:
        for item in self.items(position):
            if isinstance(item, ObjectItem) and not isinstance(item, GroupItem) and item.isVisible() and not item.locked:
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

    def _snap_point(self, scene_pos: QPointF, modifiers: Qt.KeyboardModifier) -> QPointF:
        return QPointF(self._snap_value(scene_pos.x() / PX, modifiers) * PX, -self._snap_value(-scene_pos.y() / PX, modifiers) * PX)

    def _guide_candidates(self, moving: set[str]) -> tuple[list[float], list[float]]:
        xs, ys = [0.0], [0.0]
        for object_id, item in self._items.items():
            if object_id in moving or not item.isVisible() or isinstance(item, GroupItem):
                continue
            rect = item.mapRectToScene(item.drawing.bounds)
            xs += [rect.left(), rect.center().x(), rect.right()]
            ys += [rect.top(), rect.center().y(), rect.bottom()]
        frame = self.frame_rect()
        xs += [frame.left(), frame.right()]
        ys += [frame.top(), frame.bottom()]
        return xs, ys

    def _object_snap(self, rect: QRectF, moving: set[str]) -> tuple[QPointF, list[tuple[QPointF, QPointF]]]:
        """Return a correction that aligns ``rect`` with other objects, plus guide lines."""
        threshold = GUIDE_DISTANCE / max(self.view_scale(), 0.01)
        xs, ys = self._guide_candidates(moving)
        best_x = min(((c - v, c) for v in (rect.left(), rect.center().x(), rect.right()) for c in xs), key=lambda d: abs(d[0]), default=(math.inf, 0))
        best_y = min(((c - v, c) for v in (rect.top(), rect.center().y(), rect.bottom()) for c in ys), key=lambda d: abs(d[0]), default=(math.inf, 0))
        dx = best_x[0] if abs(best_x[0]) <= threshold else 0.0
        dy = best_y[0] if abs(best_y[0]) <= threshold else 0.0
        guides = []
        visible = self.mapToScene(self.viewport().rect()).boundingRect()
        if dx or abs(best_x[0]) <= threshold:
            guides.append((QPointF(best_x[1], visible.top()), QPointF(best_x[1], visible.bottom())))
        if dy or abs(best_y[0]) <= threshold:
            guides.append((QPointF(visible.left(), best_y[1]), QPointF(visible.right(), best_y[1])))
        return QPointF(dx, dy), guides

    # --- mouse ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        position = event.position().toPoint()
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_origin = position
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if event.button() == Qt.MouseButton.RightButton:
            handle = self._handle_at(position)
            if handle is not None and handle.role == ROLE_VERTEX and self._selection:
                self.vertexMenuRequested.emit(event.globalPosition().toPoint(), self._selection[0], handle.index)
                return
            super().mousePressEvent(event)
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
            self._entered_group = None
            super().mousePressEvent(event)
            return
        target = self._selectable_id(item.object_id)
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            ids = [i for i in self._selection if i != target]
            if target not in self._selection:
                ids.append(target)
            self._emit_selection(ids)
            return
        if target not in self._selection:
            self._emit_selection([target])
        self._start_move(self.mapToScene(position))

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        position = event.position().toPoint()
        item = self._object_item_at(position)
        if item is None or self._scene_model is None:
            super().mouseDoubleClickEvent(event)
            return
        top = groups.top_level(self._scene_model, item.object_id)
        if top != item.object_id and self._entered_group != top:
            self._entered_group = top
            self._emit_selection([self._selectable_id(item.object_id)])
            self.statusMessage.emit("")
            return
        obj = self._scene_model.object_by_id(item.object_id)
        if obj is not None and obj.kind == ObjectKind.POLYGON and self._point_editing:
            self._insert_vertex(obj.id, self.mapToScene(position))

    def _insert_vertex(self, object_id: str, scene_pos: QPointF) -> None:
        item = self._items[object_id]
        obj = self._scene_model.object_by_id(object_id) if self._scene_model else None
        if obj is None:
            return
        offset = item.drawing.offset
        corners = [item.mapToScene(pt(float(x), float(y)) - offset) for x, y in obj.params.get("points", [])]
        best_index, best_distance = 0, math.inf
        for index, start in enumerate(corners):
            end = corners[(index + 1) % len(corners)]
            distance = _segment_distance(scene_pos, start, end)
            if distance < best_distance:
                best_index, best_distance = index + 1, distance
        self.vertexInserted.emit(object_id, best_index, scene_pos.x() / PX, -scene_pos.y() / PX)

    def _allowed(self, action: str, ids: list[str]) -> bool:
        allowed, message = self._policy(action, ids)
        if not allowed:
            self.statusMessage.emit(message)
        return allowed

    def _moving_item_ids(self, ids: list[str]) -> list[str]:
        result = list(ids)
        if self._scene_model is not None:
            for object_id in ids:
                for leaf in groups.leaves(self._scene_model, object_id):
                    if leaf not in result:
                        result.append(leaf)
        return [object_id for object_id in result if object_id in self._items]

    def _start_move(self, press: QPointF) -> None:
        ids = list(self._selection)
        if not self._allowed(MOVE, ids):
            return
        origins = {object_id: QPointF(self._items[object_id].pos()) for object_id in self._moving_item_ids(ids)}
        self._drag = _Drag(MOVE, press, ids, origins)

    def _start_handle_drag(self, handle: HandleItem, press: QPointF) -> None:
        object_id = self._selection[0]
        item = self._items[object_id]
        if handle.role in (ROLE_VERTEX, ROLE_ENDPOINT):
            if self._allowed(MOVE, [object_id]):
                mode = DRAG_VERTEX if handle.role == ROLE_VERTEX else DRAG_ENDPOINT
                self._drag = _Drag(mode, press, [object_id], handle=handle, point=item.mapToScene(handle.pos()))
            return
        action = ROTATE if handle.role == ROLE_ROTATE else SCALE
        if not self._allowed(action, [object_id]):
            return
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
        mode = self._drag.mode
        if mode == MOVE:
            self._update_move(scene_pos, event.modifiers())
        elif mode == SCALE:
            self._update_scale(scene_pos, event.modifiers())
        elif mode == ROTATE:
            self._update_rotation(scene_pos, event.modifiers())
        else:
            self._update_point(scene_pos, event.modifiers())

    def _update_move(self, scene_pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        drag = self._drag
        assert drag is not None
        primary = drag.origins.get(drag.ids[0], next(iter(drag.origins.values()), QPointF()))
        raw_delta = scene_pos - drag.press
        snapped = self._snap_point(primary + raw_delta, modifiers)
        delta = snapped - primary if self._snapping(modifiers) else raw_delta
        self._guides = []
        if self._snapping(modifiers):
            rect = QRectF()
            for object_id in drag.ids:
                rect = rect.united(self.item_rect(object_id).translated(raw_delta - (self._items[object_id].pos() - drag.origins.get(object_id, self._items[object_id].pos()))))
            correction, guides = self._object_snap(rect, set(drag.origins))
            if correction.x() or correction.y():
                delta = QPointF(raw_delta.x() + correction.x() if correction.x() else delta.x(), raw_delta.y() + correction.y() if correction.y() else delta.y())
                self._guides = guides
        drag.delta = delta
        for object_id, origin in drag.origins.items():
            self._items[object_id].setPos(origin + drag.delta)
        self.viewport().update()

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

    def _update_point(self, scene_pos: QPointF, modifiers: Qt.KeyboardModifier) -> None:
        drag = self._drag
        assert drag is not None and drag.handle is not None
        drag.point = self._snap_point(scene_pos, modifiers)
        item = self._items[drag.ids[0]]
        drag.handle.setPos(item.mapFromScene(drag.point))
        self.statusMessage.emit(f"({drag.point.x() / PX:.2f}, {-drag.point.y() / PX:.2f})")

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.MiddleButton and self._pan_origin is not None:
            self._pan_origin = None
            self.unsetCursor()
            return
        drag, self._drag = self._drag, None
        self._guides = []
        self.viewport().update()
        if drag is None:
            super().mouseReleaseEvent(event)
            return
        if drag.mode == MOVE and (abs(drag.delta.x()) > 1e-6 or abs(drag.delta.y()) > 1e-6):
            self.moveRequested.emit(drag.ids, round(drag.delta.x() / PX, 4), round(-drag.delta.y() / PX, 4))
        elif drag.mode == SCALE and drag.value and abs(drag.value - 1.0) > 1e-4:
            self.scaleRequested.emit(drag.ids[0], drag.value)
        elif drag.mode == ROTATE and abs(drag.value) > 1e-4:
            self.rotateRequested.emit(drag.ids[0], drag.value)
        elif drag.mode in (DRAG_VERTEX, DRAG_ENDPOINT) and drag.handle is not None:
            signal = self.vertexMoved if drag.mode == DRAG_VERTEX else self.endpointMoved
            signal.emit(drag.ids[0], drag.handle.index, round(drag.point.x() / PX, 4), round(-drag.point.y() / PX, 4))

    def contextMenuEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._handle_at(event.pos()) is not None:
            return
        item = self._object_item_at(event.pos())
        target = self._selectable_id(item.object_id) if item is not None else ""
        if target and target not in self._selection:
            self._emit_selection([target])
        self.contextMenuRequested.emit(event.globalPos(), target)

    # --- keyboard and wheel -------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API
        offsets = {
            Qt.Key.Key_Left: (-1.0, 0.0),
            Qt.Key.Key_Right: (1.0, 0.0),
            Qt.Key.Key_Up: (0.0, 1.0),
            Qt.Key.Key_Down: (0.0, -1.0),
        }
        if event.key() == Qt.Key.Key_Escape and self._entered_group is not None:
            group = self._entered_group
            self._entered_group = None
            self._emit_selection([group])
            return
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
        self.viewChanged.emit()

    # --- drag and drop from the library -------------------------------------------------

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.mimeData().hasFormat(KIND_MIME) or event.mimeData().hasFormat(COMPONENT_MIME):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.mimeData().hasFormat(KIND_MIME) or event.mimeData().hasFormat(COMPONENT_MIME):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt API
        mime = event.mimeData()
        if not (mime.hasFormat(KIND_MIME) or mime.hasFormat(COMPONENT_MIME)):
            super().dropEvent(event)
            return
        scene_pos = self.mapToScene(event.position().toPoint())
        modifiers = event.modifiers()
        x = self._snap_value(scene_pos.x() / PX, modifiers)
        y = self._snap_value(-scene_pos.y() / PX, modifiers)
        event.acceptProposedAction()
        if mime.hasFormat(COMPONENT_MIME):
            self.componentDropRequested.emit(bytes(mime.data(COMPONENT_MIME).data()).decode("utf-8"), x, y)
            return
        self.dropRequested.emit(bytes(mime.data(KIND_MIME).data()).decode("utf-8"), x, y)

    # --- painting ------------------------------------------------------------------------

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802 - Qt API
        painter.fillRect(rect, theme_color("stage_outside"))
        frame = self.frame_rect()
        painter.fillRect(frame, self._background)
        if self._show_grid:
            self._draw_grid(painter, rect)
        border = QPen(theme_color("border_strong"), 1.0)
        border.setCosmetic(True)
        painter.setPen(border)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(frame)

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802 - Qt API
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._guides:
            guide = QPen(theme_color("accent"), 1.0, Qt.PenStyle.DashLine)
            guide.setCosmetic(True)
            painter.setPen(guide)
            for start, end in self._guides:
                painter.drawLine(start, end)
        if not self._motion_paths:
            return
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


def _segment_distance(point: QPointF, start: QPointF, end: QPointF) -> float:
    dx, dy = end.x() - start.x(), end.y() - start.y()
    length = dx * dx + dy * dy
    if length == 0:
        return math.hypot(point.x() - start.x(), point.y() - start.y())
    t = max(0.0, min(1.0, ((point.x() - start.x()) * dx + (point.y() - start.y()) * dy) / length))
    return math.hypot(point.x() - start.x() - t * dx, point.y() - start.y() - t * dy)
