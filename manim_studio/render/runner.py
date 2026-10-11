"""Run Manim in a background process without blocking the GUI."""

from __future__ import annotations

import codecs
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from manim_studio.render.command import (
    RenderJob,
    build_arguments,
    find_output,
    render_environment,
)
from manim_studio.render.output_parser import (
    ErrorSummary,
    is_progress_line,
    overall_fraction,
    parse_progress,
    split_output,
    strip_ansi,
    summarize_error,
)


@dataclass
class RenderResult:
    """Outcome of a render run."""

    job: RenderJob
    success: bool
    output: Path | None = None
    cancelled: bool = False
    error: ErrorSummary | None = None
    log_lines: list[str] = field(default_factory=list)

    @property
    def log(self) -> str:
        """Return the complete log as text."""
        return "\n".join(self.log_lines)


class ManimRunner(QObject):
    """Start Manim with :class:`QProcess` and report progress, log and result."""

    progressChanged = Signal(float)
    logLine = Signal(str)
    finished = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._job: RenderJob | None = None
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._buffer = ""
        self._log: list[str] = []
        self._cancelled = False
        self._last_progress_line = ""

    def is_running(self) -> bool:
        """Return ``True`` while a render process is active."""
        return self._process is not None

    def start(self, job: RenderJob, python: str) -> None:
        """Start rendering ``job`` with the given Python interpreter."""
        if self.is_running():
            raise RuntimeError("a render is already running")
        self._job = job
        self._buffer = ""
        self._log = []
        self._cancelled = False
        self._last_progress_line = ""
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.setWorkingDirectory(str(job.script_path.parent))
        environment = QProcessEnvironment()
        for key, value in render_environment().items():
            environment.insert(key, value)
        process.setProcessEnvironment(environment)
        process.readyReadStandardOutput.connect(self._read_output)
        process.finished.connect(self._on_finished)
        process.errorOccurred.connect(self._on_error)
        process.started.connect(process.closeWriteChannel)
        self._process = process
        arguments = build_arguments(job)
        self._append_log("$ " + " ".join([python] + arguments))
        process.start(python, arguments)

    def cancel(self) -> None:
        """Stop the running render."""
        if self._process is None:
            return
        self._cancelled = True
        self._process.kill()

    def _append_log(self, line: str) -> None:
        self._log.append(line)
        self.logLine.emit(line)

    def _handle_line(self, raw_line: str) -> None:
        line = strip_ansi(raw_line).rstrip()
        progress = parse_progress(line)
        if progress is not None and self._job is not None:
            self.progressChanged.emit(overall_fraction(progress, self._job.total_animations))
        if is_progress_line(line):
            self._last_progress_line = line.strip()
            return
        if line.strip():
            self._append_log(line)

    def _read_output(self) -> None:
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardOutput().data())
        self._buffer += self._decoder.decode(data)
        lines, self._buffer = split_output(self._buffer)
        for line in lines:
            self._handle_line(line)

    def _flush(self) -> None:
        self._read_output()
        self._buffer += self._decoder.decode(b"", final=True)
        if self._buffer:
            self._handle_line(self._buffer)
            self._buffer = ""
        if self._last_progress_line:
            self._append_log(self._last_progress_line)
            self._last_progress_line = ""

    def _finish(self, result: RenderResult) -> None:
        process = self._process
        self._process = None
        if process is not None:
            process.deleteLater()
        self.finished.emit(result)

    def _on_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        if self._process is None or self._job is None:
            return
        self._flush()
        job = self._job
        if self._cancelled:
            self._finish(RenderResult(job, False, cancelled=True, log_lines=list(self._log)))
            return
        if exit_code != 0:
            error = summarize_error("\n".join(self._log))
            self._finish(RenderResult(job, False, error=error, log_lines=list(self._log)))
            return
        output = find_output(job.media_dir, job.output_name, job.format)
        if output is None:
            error = ErrorSummary("output_missing")
            self._finish(RenderResult(job, False, error=error, log_lines=list(self._log)))
            return
        self.progressChanged.emit(1.0)
        self._finish(RenderResult(job, True, output=output, log_lines=list(self._log)))

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if self._process is None or self._job is None:
            return
        if error == QProcess.ProcessError.FailedToStart:
            self._append_log(self._process.errorString())
            summary = ErrorSummary("python_not_found", self._process.errorString())
            self._finish(RenderResult(self._job, False, error=summary, log_lines=list(self._log)))
