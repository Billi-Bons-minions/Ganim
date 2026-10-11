"""Embedded video player for the quick preview."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QImage, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStackedLayout,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from manim_studio.i18n import tr
from manim_studio.ui.icon_set import icon

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoFrame, QVideoSink

    MULTIMEDIA_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on the Qt installation
    MULTIMEDIA_AVAILABLE = False


def _time(milliseconds: int) -> str:
    seconds = max(0, milliseconds) / 1000
    return f"{int(seconds // 60)}:{seconds % 60:04.1f}"


class VideoView(QWidget):
    """Paints video frames itself; works without GPU acceleration."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image = QImage()
        self.setMinimumSize(160, 90)

    def show_frame(self, frame: "QVideoFrame") -> None:
        """Convert and display one decoded frame."""
        if frame.isValid():
            self._image = frame.toImage()
            self.update()

    def clear(self) -> None:
        """Remove the current frame."""
        self._image = QImage()
        self.update()

    def current_image(self) -> QImage:
        """Return the last displayed frame."""
        return self._image

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#000000"))
        if self._image.isNull():
            return
        size = self._image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        target = QRect(QPoint(0, 0), size)
        target.moveCenter(self.rect().center())
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(target, self._image)


class PlayerPanel(QWidget):
    """Plays the rendered preview video; falls back to the system player."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._file: Path | None = None
        self.placeholder = QLabel(tr("player.empty"))
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setWordWrap(True)
        self.stack = QStackedLayout()
        self.stack.addWidget(self.placeholder)
        self.player = None
        self.video = VideoView()
        if MULTIMEDIA_AVAILABLE:
            self.player = QMediaPlayer(self)
            self.audio = QAudioOutput(self)
            self.sink = QVideoSink(self)
            self.sink.videoFrameChanged.connect(self.video.show_frame)
            self.player.setAudioOutput(self.audio)
            self.player.setVideoSink(self.sink)
            self.player.positionChanged.connect(self._on_position)
            self.player.durationChanged.connect(self._on_duration)
            self.player.playbackStateChanged.connect(self._on_state)
            self.player.mediaStatusChanged.connect(self._on_media_status)
            self.stack.addWidget(self.video)
        self.play_button = QToolButton()
        self.play_button.setIcon(icon("play"))
        self.play_button.clicked.connect(self.toggle)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.sliderMoved.connect(self._seek)
        self.time_label = QLabel(_time(0))
        self.loop = QCheckBox(tr("player.loop"))
        self.loop.setChecked(True)
        self.external = QPushButton(icon("export"), tr("player.external"))
        self.external.clicked.connect(self.open_external)
        controls = QHBoxLayout()
        controls.addWidget(self.play_button)
        controls.addWidget(self.slider, 1)
        controls.addWidget(self.time_label)
        controls.addWidget(self.loop)
        controls.addWidget(self.external)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(self.stack, 1)
        layout.addLayout(controls)
        self._set_controls_enabled(False)

    def _set_controls_enabled(self, enabled: bool) -> None:
        for widget in (self.play_button, self.slider, self.loop):
            widget.setEnabled(enabled and self.player is not None)
        self.external.setEnabled(enabled)

    def load(self, path: Path) -> None:
        """Show and start playing a video file."""
        self._file = path
        self._set_controls_enabled(True)
        if self.player is None:
            self.placeholder.setText(tr("player.no_multimedia"))
            return
        self.stack.setCurrentIndex(1)
        self.player.stop()
        self.player.setSource(QUrl())
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.play()

    def stop(self) -> None:
        """Stop playback and release the file (e.g. before re-rendering)."""
        if self.player is not None:
            self.player.stop()
            self.player.setSource(QUrl())
        self.video.clear()

    def toggle(self) -> None:
        """Play or pause."""
        if self.player is None:
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def open_external(self) -> None:
        """Open the video with the system's default player."""
        if self._file is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._file)))

    def _seek(self, position: int) -> None:
        if self.player is not None:
            self.player.setPosition(position)

    def _on_position(self, position: int) -> None:
        if not self.slider.isSliderDown():
            self.slider.setValue(position)
        self.time_label.setText(f"{_time(position)} / {_time(self.player.duration())}")

    def _on_duration(self, duration: int) -> None:
        self.slider.setRange(0, duration)

    def _on_state(self, state) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.play_button.setIcon(icon("pause" if playing else "play"))

    def _on_media_status(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self.loop.isChecked():
            self.player.setPosition(0)
            self.player.play()
