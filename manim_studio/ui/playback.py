"""Plays the timeline on the stage (approximate, real time)."""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, QTimer, Signal

from manim_studio.model.playback import step_start_time, total_duration
from manim_studio.model.state import START
from manim_studio.ui.editor_state import EditorState

FRAME_MS = 33


class PlaybackController(QObject):
    """Advances :attr:`EditorState.playhead` in real time."""

    playingChanged = Signal(bool)

    def __init__(self, editor: EditorState, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.editor = editor
        self.loop = False
        self._timer = QTimer(self, interval=FRAME_MS)
        self._timer.timeout.connect(self._tick)
        self._last = 0.0

    def is_playing(self) -> bool:
        """Return ``True`` while playing."""
        return self._timer.isActive()

    def toggle(self) -> None:
        """Play or pause."""
        if self.is_playing():
            self.pause()
        else:
            self.play()

    def play(self) -> None:
        """Start playing from the playhead (or the start of the selected step)."""
        scene = self.editor.scene()
        total = total_duration(scene)
        if total <= 0:
            return
        start = self.editor.playhead
        if start is None:
            start = step_start_time(scene, self.editor.cursor) if self.editor.cursor != START else 0.0
        if start >= total - 1e-6:
            start = 0.0
        self.editor.set_playhead(start)
        self._last = time.monotonic()
        self._timer.start()
        self.playingChanged.emit(True)

    def pause(self) -> None:
        """Stop at the current time."""
        if self._timer.isActive():
            self._timer.stop()
            self.playingChanged.emit(False)

    def stop(self) -> None:
        """Stop and return to the editing view of the start."""
        self.pause()
        self.editor.inspect_step(START)

    def _tick(self) -> None:
        now = time.monotonic()
        elapsed, self._last = now - self._last, now
        scene = self.editor.scene()
        total = total_duration(scene)
        current = (self.editor.playhead or 0.0) + elapsed
        if current >= total:
            if self.loop:
                current = 0.0
            else:
                self.editor.set_playhead(total)
                self.pause()
                return
        self.editor.set_playhead(current)
