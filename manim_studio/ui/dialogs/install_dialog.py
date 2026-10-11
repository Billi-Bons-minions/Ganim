"""Install Manim with pip into the configured Python interpreter (live log)."""

from __future__ import annotations

from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPlainTextEdit, QProgressBar, QVBoxLayout, QWidget

from manim_studio.i18n import tr
from manim_studio.render.command import render_environment

PACKAGES = ("manim",)


def install_arguments(packages: tuple[str, ...] = PACKAGES) -> list[str]:
    """Arguments for ``python -m pip install --upgrade ...``."""
    return ["-m", "pip", "install", "--upgrade", *packages]


class InstallDialog(QDialog):
    """Runs pip and shows its output; ``succeeded`` tells whether it worked."""

    def __init__(self, python: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.python = python
        self.succeeded = False
        self.setWindowTitle(tr("install.title"))
        self.resize(640, 420)
        self.info = QLabel(tr("install.running", python=python))
        self.info.setWordWrap(True)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(QDialogButtonBox.StandardButton.Close).setEnabled(False)
        layout = QVBoxLayout(self)
        layout.addWidget(self.info)
        layout.addWidget(self.progress)
        layout.addWidget(self.log, 1)
        layout.addWidget(self.buttons)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        environment = self.process.processEnvironment()
        for key, value in render_environment().items():
            environment.insert(key, value)
        self.process.setProcessEnvironment(environment)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._error)

    def start(self) -> None:
        """Begin the installation (the dialog stays open until it ends)."""
        self.log.appendPlainText(f"$ {self.python} {' '.join(install_arguments())}")
        self.process.start(self.python, install_arguments())

    def _read(self) -> None:
        text = bytes(self.process.readAllStandardOutput().data()).decode("utf-8", errors="replace")
        self.log.appendPlainText(text.rstrip())

    def _finished(self, code: int, _status) -> None:
        self.succeeded = code == 0
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.info.setText(tr("install.done") if self.succeeded else tr("install.failed", code=code))
        self.buttons.button(QDialogButtonBox.StandardButton.Close).setEnabled(True)

    def _error(self, _error) -> None:
        self.info.setText(tr("install.failed", code=-1))
        self.log.appendPlainText(self.process.errorString())
        self.progress.setRange(0, 1)
        self.buttons.button(QDialogButtonBox.StandardButton.Close).setEnabled(True)

    def reject(self) -> None:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return
        super().reject()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.key() == Qt.Key.Key_Escape and self.process.state() != QProcess.ProcessState.NotRunning:
            return
        super().keyPressEvent(event)
