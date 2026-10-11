"""Long-lived application state that survives rebuilding the main window."""

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QStandardPaths, QThreadPool, Signal
from PySide6.QtWidgets import QWidget

from manim_studio.i18n import tr
from manim_studio.logging_setup import log
from manim_studio.render.environment import EnvironmentReport, check_environment
from manim_studio.render.tex_preview import TexPreviewCache
from manim_studio.ui.autosave import AutoSaver
from manim_studio.ui.controller import EditorController
from manim_studio.ui.document import ProjectDocument
from manim_studio.ui.editor_state import EditorState
from manim_studio.ui.render_controller import RenderController
from manim_studio.ui.settings import AppSettings


def cache_dir() -> Path:
    """Return the application's cache folder."""
    return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation))


CACHE_FOLDERS = ("render", "still", "tex")


def cache_size() -> int:
    """Bytes used by rendered previews, still images and formula images."""
    total = 0
    for name in CACHE_FOLDERS:
        for path in (cache_dir() / name).rglob("*"):
            try:
                if path.is_file():
                    total += path.stat().st_size
            except OSError:
                continue
    return total


def clear_cache() -> None:
    """Delete the render cache (it is rebuilt when needed)."""
    for name in CACHE_FOLDERS:
        shutil.rmtree(cache_dir() / name, ignore_errors=True)


def data_dir() -> Path:
    """Return the application's data folder (logs, autosave, components)."""
    return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))


class _EnvironmentSignals(QObject):
    done = Signal(object)


class _EnvironmentJob(QRunnable):
    def __init__(self, python: str, signals: _EnvironmentSignals) -> None:
        super().__init__()
        self.python = python
        self.signals = signals

    def run(self) -> None:
        report = check_environment(self.python)
        try:
            self.signals.done.emit(report)
        except RuntimeError:
            pass


class AppContext(QObject):
    """Project, editor state, commands and rendering – independent of the window."""

    environmentChanged = Signal()

    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self.settings = settings
        self._window: QWidget | None = None
        self.document = ProjectDocument(tr("scene.first_name"), self)
        self.editor = EditorState(self.document, self)
        self.controller = EditorController(self.document, self.editor, settings, self.window, self)
        latex_found = shutil.which("latex") is not None
        self.tex_cache = TexPreviewCache(cache_dir() / "tex", enabled=settings.latex_preview and latex_found, parent=self)
        self.environment: EnvironmentReport | None = None
        self.render = RenderController(self.document, self.editor, settings, self.latex_available, self.window, self)
        self.autosaver = AutoSaver(self.document, data_dir() / "autosave", self)
        self._env_signals = _EnvironmentSignals()
        self._env_signals.done.connect(self._on_environment)
        self._checking = False

    # --- window -------------------------------------------------------------------

    def window(self) -> QWidget | None:
        """Return the current main window (parent for dialogs)."""
        return self._window

    def set_window(self, window: QWidget | None) -> None:
        """Register the main window that dialogs should use as parent."""
        self._window = window

    # --- environment ----------------------------------------------------------------

    def latex_available(self) -> bool:
        """Return whether LaTeX can be used (for MathTex)."""
        if self.environment is not None:
            return self.environment.latex.found
        return shutil.which("latex") is not None and shutil.which("dvisvgm") is not None

    def latex_status(self, latex: str) -> str:
        """Explain why a formula cannot be previewed, if it cannot."""
        if not self.latex_available():
            return tr("prop.latex_missing")
        error = self.tex_cache.error(latex)
        return tr("prop.latex_error", error=error) if error else ""

    def is_checking_environment(self) -> bool:
        """Return ``True`` while the background check runs."""
        return self._checking

    def check_environment(self) -> None:
        """Check Manim, FFmpeg and LaTeX in a background thread."""
        if self._checking:
            return
        self._checking = True
        QThreadPool.globalInstance().start(_EnvironmentJob(self.settings.python_path, self._env_signals))

    def _on_environment(self, report: EnvironmentReport) -> None:
        self._checking = False
        self.environment = report
        self.tex_cache.enabled = self.settings.latex_preview and report.latex.found
        log.info("Environment: %s", ", ".join(f"{t.name}={'ok' if t.found else 'missing'} {t.version}" for t in report.tools))
        self.environmentChanged.emit()
