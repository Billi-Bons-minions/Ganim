"""Exact stage view: Manim renders the selected step as an image in the background."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from manim_studio.codegen import CodegenError, CodegenOptions, class_names, generate_script
from manim_studio.model.state import START
from manim_studio.model.validation import has_errors, validate_scene
from manim_studio.render.command import RenderJob
from manim_studio.render.runner import ManimRunner, RenderResult
from manim_studio.ui.document import ProjectDocument
from manim_studio.ui.editor_state import EditorState
from manim_studio.ui.settings import AppSettings

DEBOUNCE_MS = 700


class StillPreview(QObject):
    """Keeps a Manim-rendered PNG of the current step up to date."""

    imageReady = Signal(object)
    busyChanged = Signal(bool)

    def __init__(self, document: ProjectDocument, editor: EditorState, settings: AppSettings, folder: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.document = document
        self.editor = editor
        self.settings = settings
        self.folder = folder
        self.enabled = False
        self.latex_available = lambda: True
        self.formula_errors = None
        self._runner = ManimRunner(self)
        self._runner.finished.connect(self._on_finished)
        self._timer = QTimer(self, singleShot=True, interval=DEBOUNCE_MS)
        self._timer.timeout.connect(self._render)
        self._cache: dict[str, Path] = {}
        self._pending_key = ""
        self._wanted_key = ""

    def set_enabled(self, enabled: bool) -> None:
        """Turn the exact view on or off."""
        self.enabled = enabled
        if enabled:
            self.request()
        else:
            self._timer.stop()
            self._runner.cancel()
            self.imageReady.emit(None)

    def request(self) -> None:
        """Schedule a render of the current step (debounced)."""
        if self.enabled:
            self._timer.start()

    def _script(self) -> tuple[str, str] | None:
        scene = self.editor.scene()
        if has_errors(validate_scene(scene, self.latex_available(), self.document.base_dir, self.formula_errors)):
            return None
        cursor = self.editor.cursor
        stop = cursor if cursor != START else -1
        options = CodegenOptions(base_dir=self.document.base_dir, scene_ids=(scene.id,), stop_after_step=stop)
        try:
            script = generate_script(self.document.project, options)
        except CodegenError:
            return None
        return script, class_names(self.document.project)[scene.id]

    def _render(self) -> None:
        prepared = self._script()
        if prepared is None:
            self.imageReady.emit(None)
            return
        script, class_name = prepared
        key = hashlib.sha1(script.encode("utf-8")).hexdigest()[:16]
        self._wanted_key = key
        if key in self._cache and self._cache[key].exists():
            self.imageReady.emit(self._cache[key])
            return
        if self._runner.is_running():
            self._runner.cancel()
            self._timer.start()
            return
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / f"still_{key}.py"
        path.write_text(script, encoding="utf-8")
        job = RenderJob(path, class_name, self.folder / "media", f"still_{key}", format="png", quality="l")
        self._pending_key = key
        self.busyChanged.emit(True)
        self._runner.start(job, self.settings.python_path)

    def _on_finished(self, result: RenderResult) -> None:
        self.busyChanged.emit(False)
        if result.success and result.output is not None:
            self._cache[self._pending_key] = result.output
            if self._pending_key == self._wanted_key and self.enabled:
                self.imageReady.emit(result.output)
        elif self.enabled and not result.cancelled:
            self.imageReady.emit(None)
