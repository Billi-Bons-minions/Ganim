"""Editing commands shared by menus, toolbars, panels and the stage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QWidget

from manim_studio.i18n import tr
from manim_studio.model import operations as ops
from manim_studio.model.animation_builder import allowed_for_objects, build_animations
from manim_studio.model.assets import relative_asset_path
from manim_studio.model.entities import Scene
from manim_studio.model.factory import (
    create_animation,
    create_object,
    create_play_step,
    create_scene,
    create_wait_step,
    unique_name,
)
from manim_studio.model.serialization import object_from_dict, object_to_dict
from manim_studio.model.stage_edits import (
    KIND_FOR_ACTION,
    MOVE,
    ROTATE,
    SCALE,
    check_edit,
    color_edit,
    is_recording,
    move_edit,
    rotate_edit,
    scale_edit,
    set_move_target,
    set_rotation_angle,
    set_scale_factor,
    would_create,
)
from manim_studio.model.state import START
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind
from manim_studio.ui.document import ProjectDocument
from manim_studio.ui.editor_state import INSPECT_ANIMATION, INSPECT_STEP, EditorState
from manim_studio.ui.settings import AppSettings

CLIPBOARD_PREFIX = "manim-studio-objects:"
PASTE_OFFSET = 0.5
IMAGE_FILTER_KEY = "dialog.image_filter"


class EditorController(QObject):
    """Turns user intentions into undoable model operations."""

    statusMessage = Signal(str)
    animationRecorded = Signal(str)

    def __init__(
        self,
        document: ProjectDocument,
        editor: EditorState,
        settings: AppSettings,
        window: Callable[[], QWidget | None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.document = document
        self.editor = editor
        self.settings = settings
        self.window = window

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
            self.window(), tr("dialog.choose_image"), self.settings.last_directory("image"), tr(IMAGE_FILTER_KEY)
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
        """Put the selected objects on the clipboard (as marked JSON text)."""
        scene = self.scene()
        objects = [scene.object_by_id(i) for i in self.editor.selected_objects]
        data = [object_to_dict(obj) for obj in objects if obj is not None]
        if not data:
            return
        QApplication.clipboard().setText(CLIPBOARD_PREFIX + json.dumps(data, ensure_ascii=False))
        self.statusMessage.emit(tr("status.copied", count=len(data)))

    def cut_objects(self) -> None:
        """Copy and then delete the selected objects."""
        self.copy_objects()
        self.delete_objects()

    def can_paste(self) -> bool:
        """Return ``True`` if the clipboard contains objects."""
        return QApplication.clipboard().text().startswith(CLIPBOARD_PREFIX)

    def paste_objects(self) -> None:
        """Insert objects from the clipboard."""
        if not self.can_paste():
            return
        raw = QApplication.clipboard().text()[len(CLIPBOARD_PREFIX):]
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

    def _announce_recording(self, ids: list[str], action: str) -> None:
        created = would_create(self.scene(), self.editor.cursor, ids, action)
        if not created:
            return
        names = ", ".join(self._object_name(object_id) for object_id in created)
        animation = tr(f"anim.{KIND_FOR_ACTION[action].value}")
        self.animationRecorded.emit(tr("record.created", animation=animation, name=names, step=self.editor.cursor + 1))

    def move_objects(self, ids: list[str], dx: float, dy: float) -> None:
        """Move objects at the start, or record a Move animation in the step."""
        if not self.edit_policy(MOVE, ids)[0]:
            return
        self._announce_recording(ids, MOVE)
        key = f"move:{self.editor.cursor}:{','.join(ids)}"
        self._edit(tr("undo.move"), move_edit(self.editor.cursor, ids, dx, dy), merge_key=key)

    def scale_object(self, object_id: str, factor: float) -> None:
        """Scale an object at the start, or record a Scale animation."""
        if self.edit_policy(SCALE, [object_id])[0]:
            self._announce_recording([object_id], SCALE)
            self._edit(tr("undo.scale"), scale_edit(self.editor.cursor, object_id, factor))

    def rotate_object(self, object_id: str, delta: float) -> None:
        """Rotate an object at the start, or record a Rotate animation."""
        if self.edit_policy(ROTATE, [object_id])[0]:
            self._announce_recording([object_id], ROTATE)
            self._edit(tr("undo.rotate"), rotate_edit(self.editor.cursor, object_id, delta))

    def recording(self) -> bool:
        """Return ``True`` if edits currently become animations."""
        return is_recording(self.scene(), self.editor.cursor)

    def set_step_value(self, object_id: str, action: str, *values: float | str, merge_key: str | None = None) -> None:
        """Set an absolute target value in the current step (from the inspector)."""
        if not self.edit_policy(action, [object_id])[0] or not self.recording():
            return
        self._announce_recording([object_id], action)
        cursor = self.editor.cursor
        if action == MOVE:
            mutation = set_move_target(cursor, object_id, float(values[0]), float(values[1]))
        elif action == SCALE:
            mutation = set_scale_factor(cursor, object_id, float(values[0]))
        elif action == ROTATE:
            mutation = set_rotation_angle(cursor, object_id, float(values[0]))
        else:
            mutation = color_edit(cursor, [object_id], str(values[0]), str(values[1]))
        self._edit(tr(f"undo.{action}"), mutation, merge_key=merge_key)

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

    def add_animation(self, kind: AnimationKind, same_step: bool, inspect: bool = True) -> None:
        """Animate the selected objects, in the current step or in a new step."""
        ids = list(self.editor.selected_objects)
        if not ids:
            self.statusMessage.emit(tr("status.select_object_first"))
            return
        if not self.animation_allowed(kind):
            self.statusMessage.emit(tr("status.animation_not_allowed"))
            return
        use_current = same_step and self.recording()
        base_cursor = self.editor.cursor - 1 if use_current else self.editor.cursor
        animations = build_animations(self.scene(), kind, ids, base_cursor)
        self._insert_animations(animations, use_current, kind, inspect)

    def add_transform(self, kind: AnimationKind, source_id: str, target_id: str, same_step: bool, inspect: bool = True) -> None:
        """Transform ``source_id`` into the existing object ``target_id``."""
        animation = create_animation(kind, source_id, target=target_id)
        self._insert_animations([animation], same_step and self.recording(), kind, inspect)

    def add_transform_to_new(self, kind: AnimationKind, source_id: str, new_kind: ObjectKind, same_step: bool) -> None:
        """Create a hidden object at the source's position and transform into it."""
        source = self.scene().object_by_id(source_id)
        if source is None:
            return
        name = unique_name([obj.name for obj in self.scene().objects], tr(f"kind.{new_kind.value}"))
        target = create_object(new_kind, name, source.x, source.y)
        self._edit(tr("undo.add_object", name=name), lambda s: ops.add_object(s, target))
        self.add_transform(kind, source_id, target.id, same_step, inspect=False)
        self.editor.select_objects([target.id])
        self.statusMessage.emit(tr("status.transform_target_created", name=name))

    def _insert_animations(self, animations: list, use_current: bool, kind: AnimationKind, inspect: bool) -> None:
        cursor = self.editor.cursor
        label = tr(f"anim.{kind.value}")
        if use_current:
            step_id = self.scene().steps[cursor].id

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
        if inspect:
            self.editor.inspect_animation(animations[0].id)
        self.animationRecorded.emit(tr("record.added", animation=label, step=index + 1))

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

    # --- timeline editing -------------------------------------------------------------

    def set_animation_timing(self, animation_id: str, delay: float | None = None, run_time: float | None = None) -> None:
        """Change the delay and/or duration of an animation (from the timeline)."""
        key = "delay" if run_time is None else "duration"
        self._edit(tr(f"undo.animation_{key}"), lambda s: ops.set_animation_timing(s, animation_id, delay, run_time), f"timing:{animation_id}:{key}")

    def set_wait_time(self, step_id: str, seconds: float) -> None:
        """Change the length of a wait step."""
        self._edit(tr("undo.wait_time"), lambda s: ops.set_wait_time(s, step_id, seconds), f"wait:{step_id}")

    def move_animation(self, animation_id: str, step_id: str) -> None:
        """Move an animation into another step."""
        self._edit(tr("undo.move_animation"), lambda s: ops.move_animation(s, animation_id, step_id))
        self.editor.inspect_animation(animation_id)

    def move_animation_to_new_step(self, animation_id: str, index: int) -> None:
        """Move an animation into a new step at ``index``."""
        self._edit(tr("undo.move_animation"), lambda s: ops.move_animation_to_new_step(s, animation_id, index))
        self.editor.inspect_animation(animation_id)

    def duplicate_animation(self, animation_id: str) -> None:
        """Copy an animation within its step."""
        new_id = self._edit(tr("undo.duplicate_animation"), lambda s: ops.duplicate_animation(s, animation_id))
        if new_id:
            self.editor.inspect_animation(new_id)

    def set_step_mode(self, step_id: str, mode: str, lag_ratio: float | None = None) -> None:
        """Run a step's animations together, staggered or one after another."""
        self._edit(tr("undo.step_mode"), lambda s: ops.set_step_mode(s, step_id, mode, lag_ratio), f"mode:{step_id}")

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
        name, ok = QInputDialog.getText(self.window(), tr("dialog.rename_scene"), tr("dialog.scene_name"), text=scene.name)
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
