"""Starts previews and exports and handles their results."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QStandardPaths, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox, QWidget

from manim_studio.codegen import (
    CodegenError,
    CodegenOptions,
    class_names,
    generate_script,
)
from manim_studio.i18n import tr
from manim_studio.model import operations as ops
from manim_studio.model.entities import RenderSettings, Scene
from manim_studio.model.types import StepKind
from manim_studio.model.validation import has_errors, validate_scene
from manim_studio.render.command import RenderJob
from manim_studio.render.runner import ManimRunner, RenderResult
from manim_studio.ui.dialogs.export_dialog import ExportRequest
from manim_studio.ui.dialogs.messages import (
    codegen_error_text,
    issue_text,
    render_error_text,
    show_issues,
)
from manim_studio.ui.document import ProjectDocument
from manim_studio.ui.editor_state import EditorState
from manim_studio.ui.settings import AppSettings

SCRIPT_NAME = "manim_studio_scene.py"
PREVIEW = "preview"
EXPORT = "export"


def count_rendered_steps(scene: Scene, stop_after_step: int | None) -> int:
    """Return how many Manim animations (play/wait calls) a render will run."""
    steps = scene.steps if stop_after_step is None else scene.steps[: stop_after_step + 1]
    count = sum(1 for step in steps if step.kind == StepKind.WAIT or step.animations)
    return max(1, count)


class RenderController(QObject):
    """Owns the :class:`ManimRunner` and connects it with the UI."""

    busyChanged = Signal(bool)
    progressChanged = Signal(float)
    statusMessage = Signal(str)
    logLine = Signal(str)
    logCleared = Signal()
    previewReady = Signal(object)
    showLogRequested = Signal()
    aboutToRender = Signal()

    def __init__(
        self,
        document: ProjectDocument,
        editor: EditorState,
        settings: AppSettings,
        latex_available: Callable[[], bool],
        window: Callable[[], QWidget | None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.document = document
        self.editor = editor
        self.settings = settings
        self.latex_available = latex_available
        self.window = window
        self.runner = ManimRunner(self)
        self.runner.progressChanged.connect(self.progressChanged)
        self.runner.logLine.connect(self.logLine)
        self.runner.finished.connect(self._on_finished)
        self._mode = ""
        self._target: Path | None = None

    def is_busy(self) -> bool:
        """Return ``True`` while Manim is running."""
        return self.runner.is_running()

    # --- preparation ----------------------------------------------------------------

    def work_dir(self) -> Path:
        """Return the cache folder for scripts and media of this project."""
        base = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation))
        key = hashlib.sha1(str(self.document.path or "unsaved").encode("utf-8")).hexdigest()[:12]
        folder = base / "render" / key
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _validate(self, scene: Scene) -> bool:
        issues = validate_scene(scene, self.latex_available(), self.document.base_dir)
        for issue in issues:
            self.logLine.emit(f"[{issue.severity}] {issue_text(scene, issue)}")
        if has_errors(issues):
            show_issues(self.window(), scene, issues)
            return False
        return True

    def _write_script(self, scene: Scene, stop_after_step: int | None) -> tuple[Path, str] | None:
        options = CodegenOptions(base_dir=self.document.base_dir, scene_ids=(scene.id,), stop_after_step=stop_after_step)
        try:
            script = generate_script(self.document.project, options)
        except CodegenError as error:
            QMessageBox.warning(self.window(), tr("render.failed_title"), codegen_error_text(error))
            return None
        path = self.work_dir() / SCRIPT_NAME
        path.write_text(script, encoding="utf-8")
        return path, class_names(self.document.project)[scene.id]

    def _start(self, scene: Scene, settings: RenderSettings, mode: str, output_name: str, stop_after_step: int | None) -> bool:
        if self.is_busy():
            self.statusMessage.emit(tr("render.busy"))
            return False
        if not self._validate(scene):
            return False
        written = self._write_script(scene, stop_after_step)
        if written is None:
            return False
        script_path, class_name = written
        job = RenderJob(
            script_path=script_path,
            scene_class=class_name,
            media_dir=script_path.parent / "media",
            output_name=f"{output_name}_{class_name}",
            format=settings.format,
            quality=settings.quality,
            width=settings.width,
            height=settings.height,
            fps=settings.fps,
            total_animations=count_rendered_steps(scene, stop_after_step),
        )
        self._mode = mode
        self.aboutToRender.emit()
        self.logCleared.emit()
        self.runner.start(job, self.settings.python_path)
        self.busyChanged.emit(True)
        self.statusMessage.emit(tr(f"render.started_{mode}", scene=scene.name))
        return True

    # --- public actions -----------------------------------------------------------------

    def preview(self) -> None:
        """Render the active scene quickly and show it in the player."""
        settings = RenderSettings(quality="l", format="mp4")
        self._target = None
        self._start(self.editor.scene(), settings, PREVIEW, "preview", None)

    def export(self, request: ExportRequest) -> None:
        """Render a scene with the export settings and copy it to the target."""
        scene = self.document.scene(request.scene_id)
        if scene is None:
            return
        if scene.background_color.upper() != request.background.upper():
            self.document.edit_scene(
                tr("prop.background"), scene.id, lambda s: ops.set_background(s, request.background), None
            )
        if self.document.project.render != request.settings:
            self.document.edit_project(tr("undo.export_settings"), lambda p: setattr(p, "render", request.settings))
        scene = self.document.scene(request.scene_id)
        stop = request.settings.png_after_step if request.settings.format == "png" and request.settings.png_after_step >= 0 else None
        self._target = request.target
        self._start(scene, request.settings, EXPORT, "export", stop)

    def cancel(self) -> None:
        """Stop the running render."""
        self.runner.cancel()

    # --- results -----------------------------------------------------------------------

    def _on_finished(self, result: RenderResult) -> None:
        self.busyChanged.emit(False)
        if result.cancelled:
            self.statusMessage.emit(tr("render.cancelled"))
            return
        if not result.success or result.output is None:
            self._report_failure(result)
            return
        if self._mode == PREVIEW:
            self.statusMessage.emit(tr("render.preview_done"))
            self.previewReady.emit(result.output)
            return
        self._finish_export(result.output)

    def _report_failure(self, result: RenderResult) -> None:
        message = render_error_text(result.error) if result.error else tr("render_error.unknown", detail="")
        self.statusMessage.emit(tr("render.failed_status"))
        box = QMessageBox(self.window())
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(tr("render.failed_title"))
        box.setText(message)
        show_log = box.addButton(tr("render.show_log"), QMessageBox.ButtonRole.ActionRole)
        box.setEscapeButton(box.addButton(QMessageBox.StandardButton.Ok))
        box.exec()
        if box.clickedButton() is show_log:
            self.showLogRequested.emit()

    def _finish_export(self, output: Path) -> None:
        target = self._target or output
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(output, target)
        except OSError as error:
            QMessageBox.critical(self.window(), tr("render.failed_title"), tr("render.copy_failed", error=str(error)))
            return
        self.statusMessage.emit(tr("render.export_done", path=str(target)))
        box = QMessageBox(self.window())
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(tr("render.export_done_title"))
        box.setText(tr("render.export_done", path=str(target)))
        open_folder = box.addButton(tr("render.open_folder"), QMessageBox.ButtonRole.ActionRole)
        open_file = box.addButton(tr("render.open_file"), QMessageBox.ButtonRole.ActionRole)
        box.setEscapeButton(box.addButton(QMessageBox.StandardButton.Ok))
        box.exec()
        if box.clickedButton() is open_folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.parent)))
        elif box.clickedButton() is open_file:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
