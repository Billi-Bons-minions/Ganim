"""The open project with undo/redo support.

Every change goes through :meth:`ProjectDocument.edit_scene` or
:meth:`ProjectDocument.edit_project`, which record a snapshot command on the
:class:`QUndoStack`. Views refer to model entities by id only, because undo
replaces the model objects.
"""

from __future__ import annotations

import copy
import time
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoCommand, QUndoStack

from manim_studio.model.entities import Project, Scene
from manim_studio.model.factory import create_project
from manim_studio.model.operations import require_scene
from manim_studio.model.serialization import load_project, save_project

MERGE_ID = 4711
MERGE_WINDOW_SECONDS = 2.0


class SnapshotCommand(QUndoCommand):
    """Undo command that swaps whole project snapshots."""

    def __init__(self, document: "ProjectDocument", text: str, before: Project, after: Project, merge_key: str | None) -> None:
        super().__init__(text)
        self.document = document
        self.before = before
        self.after = after
        self.merge_key = merge_key
        self.timestamp = time.monotonic()
        self._first_redo = True

    def id(self) -> int:  # noqa: A003 - Qt API
        return MERGE_ID if self.merge_key else -1

    def mergeWith(self, other: QUndoCommand) -> bool:  # noqa: N802 - Qt API
        if not isinstance(other, SnapshotCommand) or other.merge_key != self.merge_key:
            return False
        if other.timestamp - self.timestamp > MERGE_WINDOW_SECONDS:
            return False
        self.after = other.after
        self.timestamp = other.timestamp
        return True

    def redo(self) -> None:
        if self._first_redo:
            self._first_redo = False
            return
        self.document.replace_project(copy.deepcopy(self.after))

    def undo(self) -> None:
        self.document.replace_project(copy.deepcopy(self.before))


class ProjectDocument(QObject):
    """Holds the project, its file path and the undo stack."""

    changed = Signal()
    pathChanged = Signal()
    dirtyChanged = Signal(bool)

    def __init__(self, default_scene_name: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.project: Project = create_project(default_scene_name)
        self.path: Path | None = None
        self.undo_stack = QUndoStack(self)
        self.undo_stack.cleanChanged.connect(lambda clean: self.dirtyChanged.emit(not clean))

    # --- state ---------------------------------------------------------------

    @property
    def is_dirty(self) -> bool:
        """Return ``True`` if there are unsaved changes."""
        return not self.undo_stack.isClean()

    @property
    def base_dir(self) -> Path | None:
        """Folder of the project file (for relative image paths)."""
        return self.path.parent if self.path else None

    def scene(self, scene_id: str) -> Scene | None:
        """Return a scene of the current project."""
        return self.project.scene_by_id(scene_id)

    def replace_project(self, project: Project) -> None:
        """Swap the model (used by undo/redo) and notify views."""
        self.project = project
        self.changed.emit()

    # --- editing -------------------------------------------------------------

    def edit_project(self, text: str, mutate: Callable[[Project], Any], merge_key: str | None = None) -> Any:
        """Run ``mutate`` on the project and record it as one undo step."""
        before = copy.deepcopy(self.project)
        try:
            result = mutate(self.project)
        except Exception:
            self.project = before
            raise
        if self.project == before:
            return result
        command = SnapshotCommand(self, text, before, copy.deepcopy(self.project), merge_key)
        self.undo_stack.push(command)
        self.changed.emit()
        return result

    def edit_scene(self, text: str, scene_id: str, mutate: Callable[[Scene], Any], merge_key: str | None = None) -> Any:
        """Run ``mutate`` on one scene and record it as one undo step."""
        return self.edit_project(text, lambda project: mutate(require_scene(project, scene_id)), merge_key)

    # --- files ---------------------------------------------------------------

    def new(self, default_scene_name: str) -> None:
        """Start an empty project."""
        self.project = create_project(default_scene_name)
        self._set_path(None)
        self.undo_stack.clear()
        self.changed.emit()

    def load(self, project: Project) -> None:
        """Show an in-memory project (e.g. an example) as a new, unsaved document."""
        self.project = project
        self._set_path(None)
        self.undo_stack.clear()
        self.changed.emit()

    def open(self, path: str | Path) -> None:
        """Load a project file (raises ``ProjectFormatError``)."""
        project = load_project(path)
        self.project = project
        self._set_path(Path(path).resolve())
        self.undo_stack.clear()
        self.changed.emit()

    def save(self, path: str | Path | None = None) -> None:
        """Save to ``path`` or to the current file."""
        target = Path(path).resolve() if path else self.path
        if target is None:
            raise ValueError("no file name")
        save_project(self.project, target)
        self._set_path(target)
        self.undo_stack.setClean()
        self.dirtyChanged.emit(False)

    def _set_path(self, path: Path | None) -> None:
        self.path = path
        self.pathChanged.emit()
