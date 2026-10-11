"""Editing commands shared by menus, toolbars, panels and the stage."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QMimeData, QObject, Signal
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QWidget

from manim_studio.i18n import tr
from manim_studio.model import operations as ops
from manim_studio.model.animation_builder import allowed_for_objects, build_animations
from manim_studio.model.assets import relative_asset_path
from manim_studio.model.entities import Scene
from manim_studio.model.factory import (
    create_object,
    create_play_step,
    create_scene,
    create_wait_step,
    unique_name,
)
from manim_studio.model.serialization import object_from_dict, object_to_dict
from manim_studio.model.stage_edits import (
    check_edit,
    move_edit,
    rotate_edit,
    scale_edit,
)
from manim_studio.model.state import START
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind
from manim_studio.ui.document import ProjectDocument
from manim_studio.ui.editor_state import INSPECT_ANIMATION, INSPECT_STEP, EditorState
from manim_studio.ui.settings import AppSettings

OBJECTS_MIME = "application/x-manim-studio-objects"
PASTE_OFFSET = 0.5
IMAGE_FILTER_KEY = "dialog.image_filter"


class EditorController(QObject):
    """Turns user intentions into undoable model operations."""

    statusMessage = Signal(str)

    def __init__(self, document: ProjectDocument, editor: EditorState, settings: AppSettings, parent: QWidget) -> None:
        super().__init__(parent)
        self.document = document
        self.editor = editor
        self.settings = settings
        self.window = parent

    # --- helpers -------------------------------------------------------------

    def scene(self) -> Scene:
        """Return the active scene."""
        return self.editor.scene()

    def _edit(self, text: str, mutate, merge_key: str | None = None):
        return self.document.edit_scene(text, self.editor.scene_id, mutate, merge_key)

    def _object_name(self, object_id: str) -> str:
        obj = self.scene().object_by_id(object_id)
        return obj.name if obj else "?"

    # --- objects ---------------------------------------------------------------

    def _free_position(self) -> tuple[float, float]:
        taken = {(round(obj.x, 3), round(obj.y, 3)) for obj in self.scene().objects}
        offset = 0.0
        while (offset, -offset) in taken and offset < 5:
            offset += 0.5
        return offset, -offset

    def _choose_image(self) -> str | None:
        path, _ = QFileDialog.getOpenFileName(
            self.window, tr("dialog.choose_image"), self.settings.last_directory("image"), tr(IMAGE_FILTER_KEY)
        )
        if not path:
            return None
        self.settings.set_last_directory("image", str(Path(path).parent))
        return relative_asset_path(path, self.document.base_dir)

    def add_object(self, kind: ObjectKind, x: float | None = None, y: float | None = None) -> str | None:
        """Create an object of ``kind`` (at the given position or a free spot)."""
        params = {}
        if kind == ObjectKind.IMAGE:
            path = self._choose_image()
            if path is None:
                return None
            params["path"] = path
        if x is None or y is None:
            x, y = self._free_position()
        scene = self.scene()
        name = unique_name([obj.name for obj in scene.objects], tr(f"kind.{kind.value}"))
        obj = create_object(kind, name, x, y, **params)
        if kind == ObjectKind.FUNCTION_GRAPH:
            axes = [o for o in scene.objects if o.kind in (ObjectKind.AXES, ObjectKind.NUMBER_PLANE)]
            if axes:
                obj.params["axes_id"] = axes[-1].id
        self._edit(tr("undo.add_object", name=name), lambda s: ops.add_object(s, obj))
        self.editor.select_objects([obj.id])
        return obj.id

    def delete_objects(self, ids: list[str] | None = None) -> None:
        """Delete objects and everything that refers to them."""
        ids = list(ids if ids is not None else self.editor.selected_objects)
        if not ids:
            return
        self._edit(tr("undo.delete_objects", count=len(ids)), lambda s: ops.remove_objects(s, ids))
        self.editor.select_objects([])

    def duplicate_objects(self) -> None:
        """Copy the selected objects next to the originals."""
        scene = self.scene()
        originals = [scene.object_by_id(i) for i in self.editor.selected_objects]
        objects = [obj for obj in originals if obj is not None]
        if not objects:
            return
        new_ids = self._edit(
            tr("undo.duplicate_objects", count=len(objects)),
            lambda s: ops.paste_objects(s, objects, PASTE_OFFSET, -PASTE_OFFSET),
        )
        self.editor.select_objects(new_ids or [])

    def copy_objects(self) -> None:
        """Put the selected objects on the clipboard."""
        scene = self.scene()
        objects = [scene.object_by_id(i) for i in self.editor.selected_objects]
        data = [object_to_dict(obj) for obj in objects if obj is not None]
        if not data:
            return
        mime = QMimeData()
        payload = json.dumps(data, ensure_ascii=False)
        mime.setData(OBJECTS_MIME, payload.encode("utf-8"))
        mime.setText(", ".join(item["name"] for item in data))
        QApplication.clipboard().setMimeData(mime)
        self.statusMessage.emit(tr("status.copied", count=len(data)))

    def release_clipboard(self) -> None:
        """Replace our clipboard data with plain text before the application exits.

        PySide6 crashes on shutdown if a ``QMimeData`` created in Python is
        still owned by the clipboard, so it is swapped for Qt-owned text.
        """
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        if mime is not None and mime.hasFormat(OBJECTS_MIME):
            clipboard.setText(mime.text())

    def cut_objects(self) -> None:
        """Copy and then delete the selected objects."""
        self.copy_objects()
        self.delete_objects()

    def can_paste(self) -> bool:
        """Return ``True`` if the clipboard contains objects."""
        mime = QApplication.clipboard().mimeData()
        return mime is not None and mime.hasFormat(OBJECTS_MIME)

    def paste_objects(self) -> None:
        """Insert objects from the clipboard."""
        if not self.can_paste():
            return
        raw = bytes(QApplication.clipboard().mimeData().data(OBJECTS_MIME).data()).decode("utf-8")
        try:
            objects = [object_from_dict(item) for item in json.loads(raw)]
        except (ValueError, KeyError, TypeError):
            return
        new_ids = self._edit(
            tr("undo.paste_objects", count=len(objects)),
            lambda s: ops.paste_objects(s, objects, PASTE_OFFSET, -PASTE_OFFSET),
        )
        self.editor.select_objects(new_ids or [])

    def select_all(self) -> None:
        """Select every object of the scene."""
        self.editor.select_objects([obj.id for obj in self.scene().objects])

    def change_layer(self, delta: int) -> None:
        """Move the selected objects up or down in the layer order."""
        ids = list(self.editor.selected_objects)
        if ids:
            self._edit(tr("undo.layer"), lambda s: ops.change_z_index(s, ids, delta))

    # --- stage manipulation ---------------------------------------------------------

    def edit_policy(self, action: str, ids: list[str]) -> tuple[bool, str]:
        """Decide whether a stage edit is allowed and explain why not."""
        check = check_edit(self.scene(), self.editor.cursor, ids, action)
        if check.allowed:
            return True, ""
        name = self._object_name(check.object_id) if check.object_id else ""
        return False, tr(f"lock.{check.reason}", name=name, step=self.editor.cursor + 1)

    def move_objects(self, ids: list[str], dx: float, dy: float) -> None:
        """Move objects (or their Move targets) by a delta."""
        if not self.edit_policy("move", ids)[0]:
            return
        key = f"move:{self.editor.cursor}:{','.join(ids)}"
        self._edit(tr("undo.move"), move_edit(self.editor.cursor, ids, dx, dy), merge_key=key)

    def scale_object(self, object_id: str, factor: float) -> None:
        """Scale an object (or its Scale factor)."""
        if self.edit_policy("scale", [object_id])[0]:
            self._edit(tr("undo.scale"), scale_edit(self.editor.cursor, object_id, factor))

    def rotate_object(self, object_id: str, delta: float) -> None:
        """Rotate an object (or change its Rotate angle)."""
        if self.edit_policy("rotate", [object_id])[0]:
            self._edit(tr("undo.rotate"), rotate_edit(self.editor.cursor, object_id, delta))

    # --- steps ---------------------------------------------------------------------

    def _insert_index(self) -> int:
        return self.editor.cursor + 1

    def add_step(self, kind: StepKind = StepKind.PLAY) -> None:
        """Insert an empty play step or a wait step after the current one."""
        step = create_play_step() if kind == StepKind.PLAY else create_wait_step(1.0)
        index = self._insert_index()
        self._edit(tr("undo.add_step"), lambda s: ops.add_step(s, step, index))
        self.editor.inspect_step(index)

    def current_step_id(self) -> str | None:
        """Return the id of the step at the cursor."""
        steps = self.scene().steps
        return steps[self.editor.cursor].id if 0 <= self.editor.cursor < len(steps) else None

    def duplicate_step(self) -> None:
        """Duplicate the current step."""
        step_id = self.current_step_id()
        if step_id is None:
            return
        self._edit(tr("undo.duplicate_step"), lambda s: ops.duplicate_step(s, step_id))
        self.editor.inspect_step(self.editor.cursor + 1)

    def delete_step(self) -> None:
        """Delete the current step."""
        step_id = self.current_step_id()
        if step_id is None:
            return
        index = self.editor.cursor
        self._edit(tr("undo.delete_step"), lambda s: ops.remove_steps(s, [step_id]))
        self.editor.inspect_step(min(index, len(self.scene().steps) - 1))

    def reorder_steps(self, ordered_ids: list[str]) -> None:
        """Apply a new step order from drag and drop."""
        if ordered_ids == [step.id for step in self.scene().steps]:
            return
        selected = self.current_step_id()
        self._edit(tr("undo.reorder_steps"), lambda s: ops.reorder_steps(s, ordered_ids))
        if selected is not None:
            self.editor.inspect_step(self.scene().step_index(selected))

    def go_to_step(self, delta: int) -> None:
        """Move the timeline cursor forward or backward."""
        self.editor.inspect_step(max(START, min(self.editor.cursor + delta, len(self.scene().steps) - 1)))

    # --- animations -------------------------------------------------------------------

    def animation_allowed(self, kind: AnimationKind) -> bool:
        """Return ``True`` if ``kind`` fits the selected objects."""
        return allowed_for_objects(self.scene(), kind, list(self.editor.selected_objects))

    def add_animation(self, kind: AnimationKind, same_step: bool) -> None:
        """Animate the selected objects, in the current step or in a new step."""
        ids = list(self.editor.selected_objects)
        if not ids:
            self.statusMessage.emit(tr("status.select_object_first"))
            return
        if not self.animation_allowed(kind):
            self.statusMessage.emit(tr("status.animation_not_allowed"))
            return
        scene = self.scene()
        cursor = self.editor.cursor
        current = scene.steps[cursor] if 0 <= cursor < len(scene.steps) else None
        use_current = same_step and current is not None and current.kind == StepKind.PLAY
        base_cursor = cursor - 1 if use_current else cursor
        animations = build_animations(scene, kind, ids, base_cursor)
        label = tr(f"anim.{kind.value}")
        if use_current:
            step_id = current.id

            def mutate(s: Scene) -> None:
                for anim in animations:
                    ops.add_animation(s, step_id, anim)

            self._edit(tr("undo.add_animation", name=label), mutate)
            index = cursor
        else:
            step = create_play_step(animations)
            index = cursor + 1
            self._edit(tr("undo.add_animation", name=label), lambda s: ops.add_step(s, step, index))
        self.editor.set_cursor(index)
        self.editor.inspect_animation(animations[0].id)

    def delete_animation(self, animation_id: str) -> None:
        """Remove one animation from its step."""
        self._edit(tr("undo.delete_animation"), lambda s: ops.remove_animations(s, [animation_id]))

    def delete_in_timeline(self) -> None:
        """Delete the inspected animation, otherwise the current step."""
        kind, entity_id = self.editor.inspected
        if kind == INSPECT_ANIMATION and entity_id:
            self.delete_animation(entity_id)
        elif kind == INSPECT_STEP or self.current_step_id():
            self.delete_step()

    # --- scenes ---------------------------------------------------------------------

    def add_scene(self) -> None:
        """Append a new empty scene and switch to it."""
        names = [scene.name for scene in self.document.project.scenes]
        scene = create_scene(unique_name(names, tr("scene.default_name")))
        self.document.edit_project(tr("undo.add_scene"), lambda p: ops.add_scene(p, scene))
        self.editor.set_scene(scene.id)

    def duplicate_scene(self) -> None:
        """Copy the active scene."""
        names = [scene.name for scene in self.document.project.scenes]
        name = unique_name(names, self.scene().name)
        scene_id = self.editor.scene_id
        new_id = self.document.edit_project(tr("undo.duplicate_scene"), lambda p: ops.duplicate_scene(p, scene_id, name))
        self.editor.set_scene(new_id)

    def rename_scene(self, scene_id: str | None = None) -> None:
        """Ask for a new scene name."""
        scene_id = scene_id or self.editor.scene_id
        scene = self.document.scene(scene_id)
        if scene is None:
            return
        name, ok = QInputDialog.getText(self.window, tr("dialog.rename_scene"), tr("dialog.scene_name"), text=scene.name)
        if ok and name.strip():
            self.document.edit_project(tr("undo.rename_scene"), lambda p: ops.rename_scene(p, scene_id, name.strip()))

    def delete_scene(self, scene_id: str | None = None) -> None:
        """Delete a scene (the last one is kept)."""
        scene_id = scene_id or self.editor.scene_id
        if len(self.document.project.scenes) <= 1:
            self.statusMessage.emit(tr("status.last_scene"))
            return
        index = [s.id for s in self.document.project.scenes].index(scene_id)
        self.document.edit_project(tr("undo.delete_scene"), lambda p: ops.remove_scene(p, scene_id))
        scenes = self.document.project.scenes
        self.editor.set_scene(scenes[min(index, len(scenes) - 1)].id)

    def move_scene(self, scene_id: str, new_index: int) -> None:
        """Reorder scenes (tab drag)."""
        self.document.edit_project(tr("undo.move_scene"), lambda p: ops.move_scene(p, scene_id, new_index))
