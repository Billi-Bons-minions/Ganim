"""Guided tour: dims the window, highlights one widget and explains it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QRegion
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from manim_studio.i18n import tr
from manim_studio.ui.theme import current_palette, px

POLL_MS = 250
HOLE_PADDING = 6


@dataclass
class TourStep:
    """One step of the tour: a text, an optional highlighted widget and a goal."""

    key: str
    target: Callable[[], QWidget | None] = lambda: None
    done: Callable[[], bool] | None = None


def _ensure_visible(widget: QWidget) -> None:
    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QScrollArea):
            parent.ensureWidgetVisible(widget, px(20), px(20))
            return
        parent = parent.parentWidget()


class TutorialOverlay(QWidget):
    """Overlay on top of the main window that walks through :class:`TourStep` s."""

    finished = Signal()

    def __init__(self, window: QWidget, steps: list[TourStep]) -> None:
        super().__init__(window)
        self.window_widget = window
        self.steps = steps
        self.index = 0
        self._hole = QRect()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.bubble = QFrame(self)
        self.bubble.setProperty("role", "card")
        self.bubble.setFixedWidth(px(340))
        self.progress = QLabel()
        self.progress.setProperty("role", "faint")
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setTextFormat(Qt.TextFormat.RichText)
        self.skip = QPushButton(tr("tour.skip"))
        self.skip.clicked.connect(self.stop)
        self.next = QPushButton(tr("tour.next"))
        self.next.setProperty("variant", "primary")
        self.next.clicked.connect(self.advance)
        buttons = QHBoxLayout()
        buttons.addWidget(self.skip)
        buttons.addStretch(1)
        buttons.addWidget(self.next)
        column = QVBoxLayout(self.bubble)
        column.setContentsMargins(px(16), px(14), px(16), px(14))
        column.setSpacing(px(10))
        column.addWidget(self.progress)
        column.addWidget(self.text)
        column.addLayout(buttons)
        self._timer = QTimer(self, interval=POLL_MS)
        self._timer.timeout.connect(self._poll)
        window.installEventFilter(self)

    # --- control ---------------------------------------------------------------------

    def start(self) -> None:
        """Show the first step."""
        self.setGeometry(self.window_widget.rect())
        self.show()
        self.raise_()
        self._show_step()
        self._timer.start()

    def stop(self) -> None:
        """End the tour."""
        self._timer.stop()
        self.window_widget.removeEventFilter(self)
        self.hide()
        self.finished.emit()
        self.deleteLater()

    def advance(self) -> None:
        """Go to the next step (or finish)."""
        self.index += 1
        if self.index >= len(self.steps):
            self.stop()
            return
        self._show_step()

    def current(self) -> TourStep:
        """Return the active step."""
        return self.steps[self.index]

    # --- display -----------------------------------------------------------------------

    def _show_step(self) -> None:
        step = self.current()
        last = self.index == len(self.steps) - 1
        self.progress.setText(tr("tour.progress", step=self.index + 1, total=len(self.steps)))
        self.text.setText(tr(f"tour.{step.key}"))
        self.next.setText(tr("tour.finish") if last else tr("tour.next"))
        self.skip.setVisible(not last)
        target = step.target()
        if target is not None:
            _ensure_visible(target)
        self._update_geometry()

    def _poll(self) -> None:
        step = self.current()
        if step.done is not None and step.done():
            self.advance()
            return
        self._update_geometry()

    def _target_rect(self) -> QRect:
        target = self.current().target()
        if target is None or not target.isVisible():
            return QRect()
        top_left = target.mapTo(self.window_widget, QPoint(0, 0))
        return QRect(top_left, target.size()).adjusted(-HOLE_PADDING, -HOLE_PADDING, HOLE_PADDING, HOLE_PADDING)

    def _update_geometry(self) -> None:
        self.setGeometry(self.window_widget.rect())
        hole = self._target_rect()
        if hole != self._hole:
            self._hole = hole
            region = QRegion(self.rect())
            if not hole.isNull():
                region = region.subtracted(QRegion(hole))
            self.setMask(region)
        self.bubble.adjustSize()
        self.bubble.move(self._bubble_position(hole))
        self.raise_()
        self.update()

    def _bubble_position(self, hole: QRect) -> QPoint:
        size = self.bubble.size()
        area = self.rect().adjusted(px(12), px(12), -px(12), -px(12))
        if hole.isNull():
            return QPoint(area.center().x() - size.width() // 2, area.center().y() - size.height() // 2)
        candidates = [
            QPoint(hole.center().x() - size.width() // 2, hole.bottom() + px(14)),
            QPoint(hole.center().x() - size.width() // 2, hole.top() - size.height() - px(14)),
            QPoint(hole.right() + px(14), hole.center().y() - size.height() // 2),
            QPoint(hole.left() - size.width() - px(14), hole.center().y() - size.height() // 2),
        ]
        for point in candidates:
            if area.contains(QRect(point, size)):
                return point
        point = candidates[0]
        x = max(area.left(), min(point.x(), area.right() - size.width()))
        y = max(area.top(), min(point.y(), area.bottom() - size.height()))
        return QPoint(x, y)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRect(self.rect())
        if not self._hole.isNull():
            hole = QPainterPath()
            hole.addRoundedRect(self._hole, px(8), px(8))
            path = path.subtracted(hole)
        painter.fillPath(path, QColor(0, 0, 0, 150))
        if not self._hole.isNull():
            painter.setPen(QPen(QColor(current_palette().accent), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(self._hole, px(8), px(8))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt API
        if watched is self.window_widget and event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            QTimer.singleShot(0, self._update_geometry)
        return False
