"""Transient editor state: active scene, timeline position and selection."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from manim_studio.model.entities import Scene
from manim_studio.model.state import START
from manim_studio.ui.document import ProjectDocument

INSPECT_SCENE = "scene"
INSPECT_OBJECTS = "objects"
INSPECT_STEP = "step"
INSPECT_ANIMATION = "animation"


class EditorState(QObject):
    """What the user is currently looking at and working on.

    ``cursor`` is the index of the timeline step whose end state the stage
    shows (``START`` = before the first step). ``inspected`` decides what the
    property panel edits.
    """

    sceneChanged = Signal()
    cursorChanged = Signal()
    selectionChanged = Signal()
    inspectorChanged = Signal()

    def __init__(self, document: ProjectDocument, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.document = document
        self.scene_id = document.project.scenes[0].id
        self.cursor = START
        self.selected_objects: list[str] = []
        self.inspected: tuple[str, str | None] = (INSPECT_SCENE, None)
        document.changed.connect(self.sanitize)

    # --- accessors -----------------------------------------------------------

    def scene(self) -> Scene:
        """Return the active scene (falls back to the first one)."""
        scene = self.document.scene(self.scene_id)
        if scene is None:
            scene = self.document.project.scenes[0]
            self.scene_id = scene.id
        return scene

    # --- setters -------------------------------------------------------------

    def reset(self) -> None:
        """Start fresh after a project was created or opened."""
        self.scene_id = self.document.project.scenes[0].id
        self.cursor = START
        self.selected_objects = []
        self.inspected = (INSPECT_SCENE, None)
        self.sceneChanged.emit()
        self.cursorChanged.emit()
        self.selectionChanged.emit()
        self.inspectorChanged.emit()

    def set_scene(self, scene_id: str) -> None:
        """Activate another scene."""
        if scene_id == self.scene_id or self.document.scene(scene_id) is None:
            return
        self.scene_id = scene_id
        self.cursor = START
        self.selected_objects = []
        self.inspected = (INSPECT_SCENE, None)
        self.sceneChanged.emit()
        self.cursorChanged.emit()
        self.selectionChanged.emit()
        self.inspectorChanged.emit()

    def set_cursor(self, index: int) -> None:
        """Show the state after timeline step ``index``."""
        index = max(START, min(index, len(self.scene().steps) - 1))
        if index != self.cursor:
            self.cursor = index
            self.cursorChanged.emit()

    def select_objects(self, object_ids: list[str], inspect: bool = True) -> None:
        """Select objects on the stage (order is kept for transforms)."""
        ids = [object_id for object_id in dict.fromkeys(object_ids) if self.scene().object_by_id(object_id)]
        changed = ids != self.selected_objects
        self.selected_objects = ids
        if changed:
            self.selectionChanged.emit()
        if inspect:
            self.inspect(INSPECT_OBJECTS if ids else INSPECT_SCENE, None)

    def inspect(self, kind: str, entity_id: str | None) -> None:
        """Choose what the property panel shows."""
        if (kind, entity_id) != self.inspected:
            self.inspected = (kind, entity_id)
            self.inspectorChanged.emit()

    def inspect_step(self, index: int) -> None:
        """Select a timeline step (or the start) and show it in the inspector."""
        self.set_cursor(index)
        steps = self.scene().steps
        if 0 <= index < len(steps):
            self.inspect(INSPECT_STEP, steps[index].id)
        else:
            self.inspect(INSPECT_OBJECTS if self.selected_objects else INSPECT_SCENE, None)

    def inspect_animation(self, animation_id: str) -> None:
        """Select an animation and move the cursor to its step."""
        found = self.scene().find_animation(animation_id)
        if found is None:
            return
        self.set_cursor(self.scene().step_index(found[0].id))
        self.inspect(INSPECT_ANIMATION, animation_id)

    # --- consistency ---------------------------------------------------------

    def sanitize(self) -> None:
        """Drop references to entities that no longer exist (after undo, delete ...)."""
        scene = self.scene()
        cursor = max(START, min(self.cursor, len(scene.steps) - 1))
        if cursor != self.cursor:
            self.cursor = cursor
            self.cursorChanged.emit()
        valid = [object_id for object_id in self.selected_objects if scene.object_by_id(object_id)]
        if valid != self.selected_objects:
            self.selected_objects = valid
            self.selectionChanged.emit()
        kind, entity_id = self.inspected
        missing = (
            (kind == INSPECT_STEP and scene.step_by_id(entity_id) is None)
            or (kind == INSPECT_ANIMATION and scene.find_animation(entity_id) is None)
            or (kind == INSPECT_OBJECTS and not self.selected_objects)
        )
        if missing:
            self.inspect(INSPECT_OBJECTS if self.selected_objects else INSPECT_SCENE, None)
