"""Time-based timeline: ruler, step headers and animation bars."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QSizePolicy, QWidget

from manim_studio.i18n import tr
from manim_studio.model.entities import STEP_LAGGED, STEP_SEQUENCE, Animation, Scene, Step
from manim_studio.model.state import START
from manim_studio.model.types import (
    EMPHASIS_ANIMATIONS,
    ENTRANCE_ANIMATIONS,
    EXIT_ANIMATIONS,
    MODIFIER_ANIMATIONS,
    TRANSFORM_ANIMATIONS,
    AnimationKind,
    StepKind,
)
from manim_studio.ui.theme import color as theme_color
from manim_studio.ui.theme import current_palette, px

DEFAULT_PPS = 140.0
MIN_PPS, MAX_PPS = 30.0, 900.0
TIME_SNAP = 0.05
EDGE_GRAB = 7
DRAG_THRESHOLD = 5

#: What a drag in progress changes.
DRAG_PLAYHEAD = "playhead"
DRAG_DELAY = "delay"
DRAG_DURATION = "duration"
DRAG_WAIT = "wait"
DRAG_STEP = "step"
DRAG_MOVE_ANIMATION = "move_animation"


def group_color(kind: AnimationKind) -> QColor:
    """Bar color by animation purpose."""
    palette = current_palette()
    if kind in ENTRANCE_ANIMATIONS:
        return QColor(palette.success)
    if kind in EXIT_ANIMATIONS:
        return QColor(palette.danger)
    if kind in TRANSFORM_ANIMATIONS:
        return QColor("#9A72AC")
    if kind in EMPHASIS_ANIMATIONS:
        return QColor(palette.warning)
    if kind in MODIFIER_ANIMATIONS:
        return QColor(palette.accent)
    return QColor(palette.text_muted)


@dataclass
class StepBlock:
    """Geometry of one step in the canvas."""

    index: int
    step: Step
    header: QRectF
    body: QRectF
    bars: list[tuple[Animation, QRectF]] = field(default_factory=list)


@dataclass
class _Drag:
    mode: str
    press: QPointF
    step_index: int = -1
    animation_id: str = ""
    original: float = 0.0
    value: float = 0.0
    active: bool = False
    drop_index: int = -1
    drop_step: int = -1


class TimelineCanvas(QWidget):
    """Draws the timeline and turns mouse gestures into editing requests."""

    stepClicked = Signal(int)
    animationClicked = Signal(str)
    playheadRequested = Signal(float)
    timingRequested = Signal(str, float, float)
    waitRequested = Signal(str, float)
    stepsReordered = Signal(list)
    animationMoved = Signal(str, str)
    animationToNewStep = Signal(str, int)
    stepMenuRequested = Signal(QPoint, int)
    animationMenuRequested = Signal(QPoint, str)
    zoomChanged = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.scene: Scene | None = None
        self.cursor = START
        self.selected_animation = ""
        self.playhead: float | None = None
        self.names: dict[str, str] = {}
        self.pps = DEFAULT_PPS
        self._blocks: list[StepBlock] = []
        self._drag: _Drag | None = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # --- metrics ---------------------------------------------------------------------

    @property
    def ruler_height(self) -> int:
        return px(22)

    @property
    def header_height(self) -> int:
        return px(26)

    @property
    def lane_height(self) -> int:
        return px(24)

    @property
    def lane_gap(self) -> int:
        return px(4)

    @property
    def start_width(self) -> int:
        return px(86)

    def time_to_x(self, time: float) -> float:
        """Map seconds to a horizontal pixel position."""
        return self.start_width + px(8) + time * self.pps

    def x_to_time(self, x: float) -> float:
        """Map a horizontal pixel position to seconds (≥ 0)."""
        return max(0.0, (x - self.start_width - px(8)) / self.pps)

    def _body_top(self) -> float:
        return self.ruler_height + self.header_height + px(4)

    # --- content ---------------------------------------------------------------------

    def set_content(self, scene: Scene, names: dict[str, str], cursor: int, selected_animation: str, playhead: float | None) -> None:
        """Show ``scene``'s timeline."""
        self.scene = scene
        self.names = names
        self.cursor = cursor
        self.selected_animation = selected_animation
        self.playhead = playhead
        self._layout()
        self.updateGeometry()
        self.update()

    def set_playhead(self, playhead: float | None) -> None:
        """Move the playhead without relayouting."""
        self.playhead = playhead
        self.update()

    def set_zoom(self, pps: float) -> None:
        """Set pixels per second."""
        self.pps = max(MIN_PPS, min(MAX_PPS, pps))
        self._layout()
        self.updateGeometry()
        self.update()
        self.zoomChanged.emit(self.pps)

    def _effective_steps(self) -> list[Step]:
        """Steps with the value currently being dragged applied (on copies only)."""
        assert self.scene is not None
        drag = self._drag
        if drag is None or not drag.active or drag.mode not in (DRAG_DELAY, DRAG_DURATION, DRAG_WAIT):
            return list(self.scene.steps)
        steps = list(self.scene.steps)
        changed = copy.deepcopy(steps[drag.step_index])
        if drag.mode == DRAG_WAIT:
            changed.wait_time = drag.value
        else:
            for anim in changed.animations:
                if anim.id == drag.animation_id:
                    if drag.mode == DRAG_DELAY:
                        anim.delay = drag.value
                    else:
                        anim.run_time = drag.value
        steps[drag.step_index] = changed
        return steps

    def _layout(self) -> None:
        self._blocks = []
        if self.scene is None:
            return
        top = self._body_top()
        start = 0.0
        for index, step in enumerate(self._effective_steps()):
            end = start + step.duration()
            left, right = self.time_to_x(start), self.time_to_x(end)
            width = max(right - left, px(6))
            header = QRectF(left, self.ruler_height, width, self.header_height)
            lanes = max(1, len(step.animations))
            body = QRectF(left, top, width, lanes * (self.lane_height + self.lane_gap))
            block = StepBlock(index, step, header, body)
            for lane, (anim, (a0, a1)) in enumerate(zip(step.animations, step.windows())):
                bar = QRectF(left + a0 * self.pps, top + lane * (self.lane_height + self.lane_gap), max((a1 - a0) * self.pps, px(4)), self.lane_height)
                block.bars.append((anim, bar))
            self._blocks.append(block)
            start = end

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        width = self.start_width + px(40)
        height = self._body_top() + self.lane_height + px(20)
        if self._blocks:
            width = int(max(block.header.right() for block in self._blocks)) + px(160)
            height = int(max(block.body.bottom() for block in self._blocks)) + px(16)
        return QSize(width, max(height, px(120)))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return self.sizeHint()

    # --- painting ----------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), theme_color("panel"))
        self._paint_ruler(painter)
        self._paint_start(painter)
        for block in self._blocks:
            self._paint_block(painter, block)
        if not self._blocks:
            self._paint_empty(painter)
        self._paint_drop_indicator(painter)
        self._paint_playhead(painter)

    def _paint_ruler(self, painter: QPainter) -> None:
        painter.fillRect(QRectF(0, 0, self.width(), self.ruler_height), theme_color("window"))
        step = 1.0 if self.pps >= 60 else 2.0
        minor = 0.25 if self.pps >= 200 else 0.5
        font = QFont(self.font())
        font.setPointSizeF(font.pointSizeF() * 0.85)
        painter.setFont(font)
        time = 0.0
        end = self.x_to_time(self.width())
        while time <= end + step:
            x = self.time_to_x(time)
            major = abs(time / step - round(time / step)) < 1e-6
            painter.setPen(QPen(theme_color("text_faint" if not major else "text_muted"), 1))
            painter.drawLine(QPointF(x, self.ruler_height - (px(8) if major else px(4))), QPointF(x, self.ruler_height))
            if major:
                painter.drawText(QPointF(x + px(3), self.ruler_height - px(9)), f"{time:g}s")
            time += minor

    def _paint_start(self, painter: QPainter) -> None:
        rect = QRectF(px(4), self.ruler_height + px(2), self.start_width - px(6), self.header_height - px(4))
        selected = self.cursor == START
        painter.setPen(QPen(theme_color("accent") if selected else theme_color("border_strong"), 2 if selected else 1))
        painter.setBrush(theme_color("accent_soft") if selected else theme_color("raised"))
        painter.drawRoundedRect(rect, px(6), px(6))
        painter.setPen(theme_color("text"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, tr("timeline.start_title"))

    def _paint_block(self, painter: QPainter, block: StepBlock) -> None:
        selected = block.index == self.cursor
        wait = block.step.kind == StepKind.WAIT
        header = block.header.adjusted(1, px(2), -1, -px(2))
        accent = theme_color("warning") if wait else theme_color("accent")
        painter.setPen(QPen(accent if selected else theme_color("border_strong"), 2 if selected else 1))
        painter.setBrush(theme_color("accent_soft") if selected else theme_color("raised"))
        painter.drawRoundedRect(header, px(6), px(6))
        painter.setPen(theme_color("text"))
        title = tr("timeline.wait_title", step=block.index + 1) if wait else tr("timeline.step_title", step=block.index + 1)
        mode_mark = {STEP_LAGGED: " ⋰", STEP_SEQUENCE: " →"}.get(block.step.mode, "") if not wait else ""
        text_rect = header.adjusted(px(6), 0, -px(4), 0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         painter.fontMetrics().elidedText(title + mode_mark, Qt.TextElideMode.ElideRight, int(text_rect.width())))
        if wait:
            body = QRectF(block.body.left() + 1, block.body.top(), block.body.width() - 2, self.lane_height)
            painter.setPen(Qt.PenStyle.NoPen)
            hatch = QColor(current_palette().warning)
            hatch.setAlphaF(0.18)
            painter.setBrush(hatch)
            painter.drawRoundedRect(body, px(5), px(5))
            return
        if not block.bars:
            painter.setPen(theme_color("text_faint"))
            painter.drawText(QRectF(block.body.left() + px(6), block.body.top(), max(block.body.width(), px(160)), self.lane_height),
                             Qt.AlignmentFlag.AlignVCenter, tr("timeline.empty_step"))
        for anim, rect in block.bars:
            self._paint_bar(painter, anim, rect)

    def _paint_bar(self, painter: QPainter, anim: Animation, rect: QRectF) -> None:
        base = group_color(anim.kind)
        selected = anim.id == self.selected_animation
        fill = QColor(base)
        fill.setAlphaF(0.85 if selected else 0.55)
        painter.setPen(QPen(theme_color("text") if selected else base, 2 if selected else 1))
        painter.setBrush(fill)
        painter.drawRoundedRect(rect.adjusted(0, 0, -1, 0), px(5), px(5))
        name = self.names.get(anim.target_id, "?")
        label = f"{tr(f'anim_short.{anim.kind.value}')} · {name}"
        painter.setPen(QColor("#FFFFFF") if current_palette().name == "dark" else QColor("#101114"))
        text_rect = rect.adjusted(px(6), 0, -px(4), 0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         painter.fontMetrics().elidedText(label, Qt.TextElideMode.ElideRight, int(max(0, text_rect.width()))))

    def _paint_empty(self, painter: QPainter) -> None:
        painter.setPen(theme_color("text_muted"))
        rect = QRectF(self.start_width + px(20), self.ruler_height, self.width() - self.start_width - px(40), self.height() - self.ruler_height)
        painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, tr("timeline.empty_hint"))

    def _paint_playhead(self, painter: QPainter) -> None:
        if self.playhead is None:
            return
        x = self.time_to_x(self.playhead)
        pen = QPen(theme_color("record"), 2)
        painter.setPen(pen)
        painter.drawLine(QPointF(x, 0), QPointF(x, self.height()))
        painter.setBrush(theme_color("record"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon([QPointF(x - px(5), 0), QPointF(x + px(5), 0), QPointF(x, px(7))])

    def _paint_drop_indicator(self, painter: QPainter) -> None:
        drag = self._drag
        if drag is None or not drag.active:
            return
        painter.setPen(QPen(theme_color("accent"), 3))
        if drag.mode == DRAG_STEP and drag.drop_index >= 0:
            x = self._insert_x(drag.drop_index)
            painter.drawLine(QPointF(x, self.ruler_height), QPointF(x, self.height()))
        elif drag.mode == DRAG_MOVE_ANIMATION and drag.drop_step >= 0:
            block = self._blocks[drag.drop_step]
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(block.header.united(block.body).adjusted(-2, -2, 2, 2), px(6), px(6))
        elif drag.mode == DRAG_MOVE_ANIMATION and drag.drop_index >= 0:
            x = self._insert_x(drag.drop_index)
            painter.drawLine(QPointF(x, self.ruler_height), QPointF(x, self.height()))

    def _insert_x(self, index: int) -> float:
        if not self._blocks:
            return self.time_to_x(0)
        if index >= len(self._blocks):
            return self._blocks[-1].header.right()
        return self._blocks[index].header.left()

    # --- hit testing ------------------------------------------------------------------------

    def _block_at_x(self, x: float) -> StepBlock | None:
        for block in self._blocks:
            if block.header.left() <= x <= block.header.right():
                return block
        return None

    def _bar_at(self, point: QPointF) -> tuple[StepBlock, Animation, QRectF] | None:
        for block in self._blocks:
            for anim, rect in block.bars:
                if rect.contains(point):
                    return block, anim, rect
        return None

    def _insert_index(self, x: float) -> int:
        for block in self._blocks:
            if x < block.header.center().x():
                return block.index
        return len(self._blocks)

    # --- mouse ------------------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        point = event.position()
        self.setFocus()
        if event.button() == Qt.MouseButton.RightButton:
            self._context_menu(point, event.globalPosition().toPoint())
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if point.y() < self.ruler_height:
            self._drag = _Drag(DRAG_PLAYHEAD, point, active=True)
            self.playheadRequested.emit(self.x_to_time(point.x()))
            return
        if point.x() < self.start_width and point.y() < self.ruler_height + self.header_height:
            self.stepClicked.emit(START)
            return
        hit = self._bar_at(point)
        if hit is not None:
            block, anim, rect = hit
            self.animationClicked.emit(anim.id)
            if point.x() >= rect.right() - EDGE_GRAB:
                self._drag = _Drag(DRAG_DURATION, point, block.index, anim.id, anim.run_time, anim.run_time)
            else:
                self._drag = _Drag(DRAG_DELAY, point, block.index, anim.id, anim.delay, anim.delay)
            return
        block = self._block_at_x(point.x())
        if block is None:
            return
        self.stepClicked.emit(block.index)
        if block.step.kind == StepKind.WAIT and point.x() >= block.header.right() - EDGE_GRAB:
            self._drag = _Drag(DRAG_WAIT, point, block.index, original=block.step.wait_time, value=block.step.wait_time)
        elif point.y() < self.ruler_height + self.header_height:
            self._drag = _Drag(DRAG_STEP, point, block.index)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        point = event.position()
        drag = self._drag
        if drag is None:
            self._update_cursor(point)
            return
        delta = point - drag.press
        if not drag.active and abs(delta.x()) + abs(delta.y()) >= DRAG_THRESHOLD:
            drag.active = True
        if not drag.active:
            return
        if drag.mode == DRAG_PLAYHEAD:
            self.playheadRequested.emit(self.x_to_time(point.x()))
        elif drag.mode in (DRAG_DELAY, DRAG_MOVE_ANIMATION):
            self._drag_animation(drag, point, delta)
        elif drag.mode in (DRAG_DURATION, DRAG_WAIT):
            drag.value = max(0.05, round((drag.original + delta.x() / self.pps) / TIME_SNAP) * TIME_SNAP)
            self._preview_value(drag)
        elif drag.mode == DRAG_STEP:
            drag.drop_index = self._insert_index(point.x())
        self.update()

    def _drag_animation(self, drag: _Drag, point: QPointF, delta: QPointF) -> None:
        source = self._blocks[drag.step_index]
        if abs(delta.y()) > self.lane_height or drag.mode == DRAG_MOVE_ANIMATION:
            drag.mode = DRAG_MOVE_ANIMATION
            block = self._block_at_x(point.x())
            if block is not None and block.step.kind == StepKind.PLAY and block.index != source.index:
                drag.drop_step, drag.drop_index = block.index, -1
            elif block is None:
                drag.drop_step, drag.drop_index = -1, self._insert_index(point.x())
            else:
                drag.drop_step, drag.drop_index = -1, -1
            return
        if source.step.mode == STEP_LAGGED:
            return
        drag.value = max(0.0, round((drag.original + delta.x() / self.pps) / TIME_SNAP) * TIME_SNAP)
        self._preview_value(drag)

    def _preview_value(self, drag: _Drag) -> None:
        self._layout()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        drag, self._drag = self._drag, None
        self._layout()
        if drag is None or not drag.active:
            self.update()
            return
        if drag.mode == DRAG_DELAY and drag.value != drag.original:
            self.timingRequested.emit(drag.animation_id, drag.value, -1.0)
        elif drag.mode == DRAG_DURATION and drag.value != drag.original:
            self.timingRequested.emit(drag.animation_id, -1.0, drag.value)
        elif drag.mode == DRAG_WAIT and drag.value != drag.original:
            self.waitRequested.emit(self._blocks[drag.step_index].step.id, drag.value)
        elif drag.mode == DRAG_STEP and drag.drop_index >= 0:
            self._emit_reorder(drag)
        elif drag.mode == DRAG_MOVE_ANIMATION:
            if drag.drop_step >= 0:
                self.animationMoved.emit(drag.animation_id, self._blocks[drag.drop_step].step.id)
            elif drag.drop_index >= 0:
                self.animationToNewStep.emit(drag.animation_id, drag.drop_index)
        self.update()

    def _emit_reorder(self, drag: _Drag) -> None:
        ids = [block.step.id for block in self._blocks]
        moving = ids.pop(drag.step_index)
        target = drag.drop_index - (1 if drag.drop_index > drag.step_index else 0)
        ids.insert(target, moving)
        self.stepsReordered.emit(ids)

    def _update_cursor(self, point: QPointF) -> None:
        hit = self._bar_at(point)
        if hit is not None and point.x() >= hit[2].right() - EDGE_GRAB:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            return
        block = self._block_at_x(point.x())
        if block is not None and block.step.kind == StepKind.WAIT and point.x() >= block.header.right() - EDGE_GRAB:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif hit is not None:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.unsetCursor()

    def _context_menu(self, point: QPointF, global_position: QPoint) -> None:
        hit = self._bar_at(point)
        if hit is not None:
            self.animationClicked.emit(hit[1].id)
            self.animationMenuRequested.emit(global_position, hit[1].id)
            return
        block = self._block_at_x(point.x())
        if block is not None:
            self.stepClicked.emit(block.index)
            self.stepMenuRequested.emit(global_position, block.index)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt API
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 ** (event.angleDelta().y() / 120.0)
            self.set_zoom(self.pps * factor)
            event.accept()
            return
        event.ignore()
