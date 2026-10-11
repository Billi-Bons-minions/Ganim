"""Small looping previews that show what an animation does (used on hover)."""

from __future__ import annotations

import math

import shiboken6
from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from manim_studio.i18n import tr
from manim_studio.model.types import AnimationKind
from manim_studio.ui.theme import current_palette, px

LOOP_MS = 2200
ACTIVE_MS = 1500
FRAME_MS = 33
BLUE = QColor("#58C4DD")
YELLOW = QColor("#F7D96F")
RED = QColor("#FC6255")


def smooth(t: float) -> float:
    """Manim's ``smooth`` rate function (approximation)."""
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _mix(first: QColor, second: QColor, t: float) -> QColor:
    return QColor(
        round(first.red() + (second.red() - first.red()) * t),
        round(first.green() + (second.green() - first.green()) * t),
        round(first.blue() + (second.blue() - first.blue()) * t),
        round(first.alpha() + (second.alpha() - first.alpha()) * t),
    )


class AnimationPreview(QWidget):
    """Animates a sample shape with the effect of one animation kind."""

    def __init__(self, kind: AnimationKind, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self._elapsed = 0
        self._timer = QTimer(self, interval=FRAME_MS)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(px(200), px(112))

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._elapsed = 0
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._timer.stop()
        super().hideEvent(event)

    def _tick(self) -> None:
        self._elapsed = (self._elapsed + FRAME_MS) % LOOP_MS
        self.update()

    def progress(self) -> float:
        """Return the eased animation progress of the current frame."""
        return smooth(self._elapsed / ACTIVE_MS)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#0B0C0F"))
        painter.translate(self.width() / 2, self.height() / 2)
        unit = self.height() / 4
        draw = getattr(self, f"_draw_{self.kind.value}", self._draw_fade_in)
        draw(painter, self.progress(), unit)

    # --- helpers -----------------------------------------------------------------------

    @staticmethod
    def _pen(color: QColor, width: float = 3.0) -> QPen:
        pen = QPen(color, width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return pen

    def _circle(self, painter: QPainter, unit: float, color: QColor = BLUE, fill: float = 0.35, offset: float = 0.0) -> None:
        painter.setPen(self._pen(color))
        brush = QColor(color)
        brush.setAlphaF(fill * color.alphaF())
        painter.setBrush(brush)
        painter.drawEllipse(QPointF(offset, 0), unit, unit)

    def _square_path(self, unit: float, roundness: float) -> QPainterPath:
        path = QPainterPath()
        radius = unit * roundness
        path.addRoundedRect(QRectF(-unit, -unit, 2 * unit, 2 * unit), radius, radius)
        return path

    # --- effects ------------------------------------------------------------------------

    def _draw_create(self, painter: QPainter, t: float, unit: float) -> None:
        painter.setPen(self._pen(BLUE))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(-unit, -unit, 2 * unit, 2 * unit), 90 * 16, round(-360 * 16 * t))

    def _draw_uncreate(self, painter: QPainter, t: float, unit: float) -> None:
        painter.setPen(self._pen(BLUE))
        painter.drawArc(QRectF(-unit, -unit, 2 * unit, 2 * unit), 90 * 16, round(-360 * 16 * (1 - t)))

    def _draw_write(self, painter: QPainter, t: float, unit: float) -> None:
        font = QFont()
        font.setPixelSize(round(unit * 1.5))
        font.setBold(True)
        path = QPainterPath()
        path.addText(QPointF(0, 0), font, "Manim")
        bounds = path.boundingRect()
        path.translate(-bounds.center())
        painter.setClipRect(QRectF(-bounds.width() / 2 - 2, -unit * 2, (bounds.width() + 4) * t, unit * 4))
        painter.setPen(self._pen(QColor("#FFFFFF"), 1.2))
        fill = QColor("#FFFFFF")
        fill.setAlphaF(max(0.0, (t - 0.4) / 0.6))
        painter.setBrush(fill)
        painter.drawPath(path)

    def _draw_set_value(self, painter: QPainter, t: float, unit: float) -> None:
        font = QFont()
        font.setPixelSize(round(unit * 1.2))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(QRectF(-unit * 2, -unit * 1.6, unit * 4, unit * 1.6), Qt.AlignmentFlag.AlignCenter, f"{smooth(t) * 10:.1f}")
        painter.setPen(self._pen(QColor("#888888"), 2.0))
        painter.drawLine(QPointF(-unit * 1.5, unit * 0.6), QPointF(unit * 1.5, unit * 0.6))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(BLUE)
        painter.drawEllipse(QPointF(-unit * 1.5 + 3 * unit * smooth(t), unit * 0.6), unit * 0.18, unit * 0.18)

    def _draw_draw_border_then_fill(self, painter: QPainter, t: float, unit: float) -> None:
        border = min(1.0, t * 2)
        painter.setPen(self._pen(BLUE))
        fill = QColor(BLUE)
        fill.setAlphaF(max(0.0, t * 2 - 1) * 0.8)
        painter.setBrush(fill)
        path = self._square_path(unit, 0.05)
        if border < 1.0:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            length = path.length() * border
            trimmed = QPainterPath(path.pointAtPercent(0))
            steps = 60
            for index in range(1, steps + 1):
                percent = path.percentAtLength(length * index / steps)
                trimmed.lineTo(path.pointAtPercent(percent))
            painter.drawPath(trimmed)
        else:
            painter.drawPath(path)

    def _draw_fade_in(self, painter: QPainter, t: float, unit: float) -> None:
        painter.setOpacity(t)
        self._circle(painter, unit)

    def _draw_fade_out(self, painter: QPainter, t: float, unit: float) -> None:
        painter.setOpacity(1 - t)
        self._circle(painter, unit)

    def _draw_grow_from_center(self, painter: QPainter, t: float, unit: float) -> None:
        painter.scale(max(t, 0.001), max(t, 0.001))
        self._circle(painter, unit)

    def _draw_transform(self, painter: QPainter, t: float, unit: float) -> None:
        color = _mix(BLUE, RED, t)
        painter.setPen(self._pen(color))
        fill = QColor(color)
        fill.setAlphaF(0.35)
        painter.setBrush(fill)
        painter.drawPath(self._square_path(unit, 1.0 - t))

    def _draw_replacement_transform(self, painter: QPainter, t: float, unit: float) -> None:
        self._draw_transform(painter, t, unit)

    def _draw_move(self, painter: QPainter, t: float, unit: float) -> None:
        self._circle(painter, unit * 0.7, offset=-self.width() / 4 + t * self.width() / 2)

    def _draw_scale(self, painter: QPainter, t: float, unit: float) -> None:
        self._circle(painter, unit * (0.7 + 0.6 * t))

    def _draw_rotate(self, painter: QPainter, t: float, unit: float) -> None:
        painter.rotate(-90 * t)
        painter.setPen(self._pen(RED))
        fill = QColor(RED)
        fill.setAlphaF(0.35)
        painter.setBrush(fill)
        painter.drawPath(self._square_path(unit * 0.9, 0.05))

    def _draw_change_color(self, painter: QPainter, t: float, unit: float) -> None:
        self._circle(painter, unit, _mix(BLUE, YELLOW, t))

    def _draw_indicate(self, painter: QPainter, t: float, unit: float) -> None:
        bump = math.sin(math.pi * t)
        painter.scale(1 + 0.25 * bump, 1 + 0.25 * bump)
        self._circle(painter, unit, _mix(BLUE, YELLOW, bump))

    def _draw_circumscribe(self, painter: QPainter, t: float, unit: float) -> None:
        self._circle(painter, unit * 0.8)
        frame = QPainterPath()
        frame.addRect(QRectF(-unit * 1.2, -unit * 1.2, unit * 2.4, unit * 2.4))
        start, end = max(0.0, t * 1.6 - 0.6), min(1.0, t * 1.6)
        if end <= start:
            return
        trimmed = QPainterPath(frame.pointAtPercent(start))
        for index in range(1, 41):
            trimmed.lineTo(frame.pointAtPercent(start + (end - start) * index / 40))
        painter.setPen(self._pen(YELLOW))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(trimmed)


class AnimationPopup(QFrame):
    """Tooltip-like window with a preview, title and short explanation."""

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        palette = current_palette()
        self.setStyleSheet(
            f"AnimationPopup {{ background: {palette.raised}; border: 1px solid {palette.border_strong};"
            f" border-radius: {px(10)}px; }}"
        )
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(px(8), px(8), px(8), px(10))
        self._layout.setSpacing(px(6))
        self._preview: AnimationPreview | None = None
        self._title = QLabel()
        self._title.setProperty("role", "title")
        self._text = QLabel()
        self._text.setWordWrap(True)
        self._text.setFixedWidth(px(200))
        self._text.setProperty("role", "muted")
        self._layout.addWidget(self._title)
        self._layout.addWidget(self._text)

    def show_for(self, kind: AnimationKind, anchor: QPoint) -> None:
        """Show the preview of ``kind`` next to ``anchor`` (global coordinates)."""
        if self._preview is not None:
            self._preview.deleteLater()
        self._preview = AnimationPreview(kind)
        self._layout.insertWidget(0, self._preview)
        self._title.setText(tr(f"anim.{kind.value}"))
        self._text.setText(tr(f"anim_help.{kind.value}"))
        self.adjustSize()
        self.move(anchor - QPoint(self.width() + px(12), 0))
        self.show()


class PreviewHover(QObject):
    """Event filter that shows an :class:`AnimationPopup` while hovering a widget."""

    _popup: AnimationPopup | None = None

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self._kinds: dict[QObject, AnimationKind] = {}
        self._pending: tuple[QWidget, AnimationKind] | None = None
        self._timer = QTimer(self, singleShot=True, interval=350)
        self._timer.timeout.connect(self._show)

    @classmethod
    def reset(cls) -> None:
        """Drop the shared popup (after a theme change)."""
        if cls._popup is not None and shiboken6.isValid(cls._popup):
            cls._popup.deleteLater()
        cls._popup = None

    @classmethod
    def popup(cls) -> AnimationPopup:
        """Return the shared popup window."""
        if cls._popup is None or not shiboken6.isValid(cls._popup):
            cls._popup = AnimationPopup()
        return cls._popup

    @classmethod
    def hide_popup(cls) -> None:
        """Hide the popup if it exists (never creates one)."""
        if cls._popup is not None and shiboken6.isValid(cls._popup):
            cls._popup.hide()

    def attach(self, widget: QWidget, kind: AnimationKind) -> None:
        """Show the preview of ``kind`` when hovering ``widget``."""
        self._kinds[widget] = kind
        widget.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt API
        if event.type() == QEvent.Type.Enter and watched in self._kinds:
            self._pending = (watched, self._kinds[watched])
            self._timer.start()
        elif event.type() in (QEvent.Type.Leave, QEvent.Type.MouseButtonPress, QEvent.Type.Hide):
            self._timer.stop()
            self._pending = None
            PreviewHover.hide_popup()
        return False

    def _show(self) -> None:
        if self._pending is None:
            return
        widget, kind = self._pending
        if not widget.isVisible():
            return
        anchor = widget.mapToGlobal(QPoint(0, 0))
        PreviewHover.popup().show_for(kind, anchor)


def preview_size() -> QSize:
    """Return the size of an animation preview."""
    return QSize(px(200), px(112))
