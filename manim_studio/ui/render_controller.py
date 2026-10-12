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
from manim_studio.codegen.generator import JOINED_CLASS
from manim_studio.i18n import tr
from manim_studio.model import operations as ops
from manim_studio.model.entities import RenderSettings, Scene
from manim_studio.model.playback import step_start_time
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


def emitted_calls(steps) -> int:
    """Return how many ``self.play``/``self.wait`` calls the steps produce."""
    return sum(1 for step in steps if step.kind in (StepKind.WAIT, StepKind.CODE) or step.animations)


def count_rendered_steps(scene: Scene, stop_after_step: int | None) -> int:
    """Return how many Manim animations (play/wait calls) a render will run."""
    steps = scene.steps if stop_after_step is None else scene.steps[: stop_after_step + 1]
    return max(1, emitted_calls(steps))


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
        self._queue: list[str] = []
        self._request: ExportRequest | None = None
        self._exported: list[Path] = []
        self.preview_offset = 0.0

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

    def _write_script(self, scene: Scene, stop_after_step: int | None, joined: bool = False, transition: str = "cut") -> tuple[Path, str] | None:
        scene_ids = None if joined else (scene.id,)
        options = CodegenOptions(
            base_dir=self.document.base_dir, scene_ids=scene_ids, stop_after_step=stop_after_step, joined=joined, transition=transition
        )
        try:
            script = generate_script(self.document.project, options)
        except CodegenError as error:
            QMessageBox.warning(self.window(), tr("render.failed_title"), codegen_error_text(error))
            return None
        path = self.work_dir() / SCRIPT_NAME
        path.write_text(script, encoding="utf-8")
        return path, JOINED_CLASS if joined else class_names(self.document.project)[scene.id]

    def _start(
        self,
        scene: Scene,
        settings: RenderSettings,
        mode: str,
        output_name: str,
        stop_after_step: int | None,
        from_step: int | None = None,
        joined: bool = False,
    ) -> bool:
        if self.is_busy():
            self.statusMessage.emit(tr("render.busy"))
            return False
        scenes = self.document.project.scenes if joined else [scene]
        if not all(self._validate(item) for item in scenes):
            return False
        written = self._write_script(scene, stop_after_step, joined, settings.transition)
        if written is None:
            return False
        script_path, class_name = written
        total = sum(count_rendered_steps(item, None) for item in scenes) if joined else count_rendered_steps(scene, stop_after_step)
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
            total_animations=total - (emitted_calls(scene.steps[:from_step]) if from_step else 0),
            from_animation=emitted_calls(scene.steps[:from_step]) if from_step else None,
            transparent=settings.transparent and mode == EXPORT,
            save_sections=settings.save_sections and mode == EXPORT,
        )
        self._mode = mode
        self.aboutToRender.emit()
        self.logCleared.emit()
        self.runner.start(job, self.settings.python_path)
        self.busyChanged.emit(True)
        self.statusMessage.emit(tr(f"render.started_{mode}", scene=scene.name))
        return True

    # --- public actions -----------------------------------------------------------------

    def preview(self, from_step: int | None = None) -> None:
        """Render the active scene quickly (optionally from a step) and show it in the player."""
        settings = RenderSettings(quality=self.settings.preview_quality, format="mp4")
        self._target = None
        scene = self.editor.scene()
        if from_step is not None and (from_step <= 0 or emitted_calls(scene.steps[:from_step]) == 0):
            from_step = None
        self.preview_offset = step_start_time(scene, from_step) if from_step else 0.0
        self._start(scene, settings, PREVIEW, "preview", None, from_step)

    def export(self, request: ExportRequest) -> None:
        """Render a scene (or all scenes) with the export settings and copy the result to the target."""
        scene = self.document.scene(request.scene_id)
        if scene is None:
            return
        self._exported = []
        if request.settings.scenes == "all_separate":
            if self.document.project.render != request.settings:
                self.document.edit_project(tr("undo.export_settings"), lambda p: setattr(p, "render", request.settings))
            self._queue = [item.id for item in self.document.project.scenes]
            self._request = request
            self._export_next()
            return
        if request.settings.scenes == "all_joined":
            if self.document.project.render != request.settings:
                self.document.edit_project(tr("undo.export_settings"), lambda p: setattr(p, "render", request.settings))
            self._queue = []
            self._target = request.target
            self._start(scene, request.settings, EXPORT, "export", None, joined=True)
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
        self._queue = []
        self._start(scene, request.settings, EXPORT, "export", stop)

    def _export_next(self) -> None:
        """Render the next scene of an "all scenes" export."""
        while self._queue:
            scene = self.document.scene(self._queue.pop(0))
            if scene is None:
                continue
            name = class_names(self.document.project)[scene.id]
            extension = RenderJob(Path(), "", Path(), "", format=self._request.settings.format, transparent=self._request.settings.transparent).extension()
            self._target = self._request.target / f"{name}.{extension}"
            if not self._start(scene, self._request.settings, EXPORT, "export", None):
                self._queue = []
            return
        self._show_export_done()

    def cancel(self) -> None:
        """Stop the running render (and the rest of an export queue)."""
        self._queue = []
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
        if not self._copy_export(result.output, result.job):
            self._queue = []
            return
        if self._queue:
            self._export_next()
        else:
            self._show_export_done()

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

    def _copy_export(self, output: Path, job: RenderJob) -> bool:
        """Copy the video (plus subtitles and section clips) to the chosen place."""
        target = self._target or output
        if target.suffix.lower() != output.suffix.lower():
            target = target.with_suffix(output.suffix)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(output, target)
            subtitles = output.with_suffix(".srt")
            if subtitles.exists():
                shutil.copyfile(subtitles, target.with_suffix(".srt"))
            if job.save_sections:
                sections = output.parent / "sections"
                if sections.is_dir():
                    folder = target.parent / f"{target.stem}_sections"
                    folder.mkdir(exist_ok=True)
                    for clip in sections.glob(f"{job.output_name}_*"):
                        shutil.copyfile(clip, folder / clip.name)
        except OSError as error:
            QMessageBox.critical(self.window(), tr("render.failed_title"), tr("render.copy_failed", error=str(error)))
            return False
        self._exported.append(target)
        return True

    def _show_export_done(self) -> None:
        if not self._exported:
            return
        target = self._exported[-1]
        text = tr("render.export_done", path=str(target)) if len(self._exported) == 1 else tr("render.export_done_many", count=len(self._exported), path=str(target.parent))
        self.statusMessage.emit(text)
        box = QMessageBox(self.window())
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(tr("render.export_done_title"))
        box.setText(text)
        open_folder = box.addButton(tr("render.open_folder"), QMessageBox.ButtonRole.ActionRole)
        open_file = box.addButton(tr("render.open_file"), QMessageBox.ButtonRole.ActionRole)
        box.setEscapeButton(box.addButton(QMessageBox.StandardButton.Ok))
        box.exec()
        if box.clickedButton() is open_folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.parent)))
        elif box.clickedButton() is open_file:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
