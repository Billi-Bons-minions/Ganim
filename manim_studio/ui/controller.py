"""Editing commands shared by menus, toolbars, panels and the stage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QWidget

from manim_studio.codegen.objects import dependencies
from manim_studio.i18n import tr
from manim_studio.model import graphs, groups
from manim_studio.model import operations as ops
from manim_studio.model.animation_builder import allowed_for_objects, build_animations, reference_candidates
from manim_studio.model.arrange import arrange_deltas, move_layer
from manim_studio.model.assets import relative_asset_path
from manim_studio.model.entities import STEP_SEQUENCE, Scene
from manim_studio.model.factory import (
    clone_scene,
    create_animation,
    create_object,
    create_play_step,
    create_scene,
    create_wait_step,
    unique_name,
)
from manim_studio.model.geometry import bound_axes
from manim_studio.model.serialization import object_from_dict, object_to_dict
from manim_studio.model.stage_edits import (
    KIND_FOR_ACTION,
    MOVE,
    ROTATE,
    SCALE,
    VALUE,
    check_edit,
    color_edit,
    is_recording,
    move_each_edit,
    move_edit,
    rotate_edit,
    scale_edit,
    set_move_target,
    set_rotation_angle,
    set_scale_factor,
    value_edit,
    would_create,
)
from manim_studio.model.state import START, states_after
from manim_studio.model.types import GRAPH_TOOL_KINDS, LINE_KINDS, REFERENCE_PARAMS, UNADDED_KINDS, UNGROUPABLE, AnimationKind, ObjectKind, StepKind, simultaneous_conflicts
from manim_studio.ui.document import ProjectDocument
from manim_studio.ui.editor_state import INSPECT_ANIMATION, INSPECT_STEP, EditorState
from manim_studio.ui.settings import AppSettings
from manim_studio.ui.user_library import style_of

CLIPBOARD_PREFIX = "manim-studio-objects:"
PARAMETER_SYMBOLS = ("a", "b", "c", "k", "m", "n", "p", "q", "r", "s", "u", "v", "w")
DERIVATIVE_COLORS = ("#83C167", "#FC6255", "#9A72AC", "#5CD0B3")
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
        self.library = None

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

    def add_object(
        self, kind: ObjectKind, x: float | None = None, y: float | None = None, name: str | None = None, attributes: dict | None = None, **params
    ) -> str | None:
        """Create an object of ``kind`` (at the given position or a free spot)."""
        if kind == ObjectKind.IMAGE:
            path = self._choose_image()
            if path is None:
                return None
            params["path"] = path
        if x is None or y is None:
            x, y = self._free_position()
        scene = self.scene()
        existing_camera = next((o for o in scene.objects if o.kind == ObjectKind.CAMERA), None)
        if kind == ObjectKind.CAMERA and existing_camera is not None:
            self.editor.select_objects([existing_camera.id])
            self.statusMessage.emit(tr("status.camera_exists"))
            return existing_camera.id
        if kind == ObjectKind.CAMERA:
            x, y = 0.0, 0.0
        if kind == ObjectKind.ANGLE and not (params.get("first_line") and params.get("second_line")):
            selected = [i for i in self.editor.selected_objects if (o := scene.object_by_id(i)) is not None and o.kind in LINE_KINDS]
            others = [o.id for o in scene.objects if o.kind in LINE_KINDS and o.id not in selected]
            lines = (selected + others[::-1])[:2] if len(selected) < 2 else selected[:2]
            if len(lines) < 2:
                self.statusMessage.emit(tr("status.angle_needs_lines"))
                return None
            params["first_line"], params["second_line"] = lines
        if kind in (ObjectKind.HIGHLIGHT, ObjectKind.TRACE) and not params.get("target"):
            target = next((o for o in (scene.object_by_id(i) for i in self.editor.selected_objects) if o is not None and o.kind not in UNGROUPABLE and o.kind != kind), None)
            if target is None:
                self.statusMessage.emit(tr("status.highlight_needs_target" if kind == ObjectKind.HIGHLIGHT else "status.trace_needs_target"))
                return None
            params["target"] = target.id
            x, y = 0.0, 0.0
        if kind == ObjectKind.BULLET_LIST and "items" not in params:
            params["items"] = tr("default.list_items")
        if kind == ObjectKind.PARAMETER and "symbol" not in params:
            params["symbol"] = self._free_symbol()
        names = [obj.name for obj in scene.objects]
        if kind == ObjectKind.PARAMETER and not name and str(params["symbol"]) not in names:
            name = str(params["symbol"])
        else:
            name = unique_name(names, name or tr(f"kind.{kind.value}"))
        obj = create_object(kind, name, x, y, **params)
        for key, value in (attributes or {}).items():
            setattr(obj, key, value)
        self._attach(obj)
        hosts = self._missing_hosts(obj, names)

        def mutate(s: Scene) -> None:
            for host in hosts:
                ops.add_object(s, host)
            ops.add_object(s, obj)
            if obj.kind == ObjectKind.HIGHLIGHT:
                ops.place_highlight(s, obj.id)

        self._edit(tr("undo.add_object", name=name), mutate)
        if hosts:
            self.statusMessage.emit(tr("status.hosts_added", name=name, hosts=", ".join(host.name for host in hosts)))
        self.editor.select_objects([obj.id])
        return obj.id

    def _missing_hosts(self, obj, names: list[str]) -> list:
        """Create the axes / graph a new object needs but the scene does not have yet."""
        hosts = []

        def new(kind: ObjectKind, **params):
            host = create_object(kind, unique_name(names + [h.name for h in hosts], tr(f"kind.{kind.value}")), obj.x, obj.y, **params)
            hosts.append(host)
            return host

        if obj.kind in (ObjectKind.SURFACE, ObjectKind.CURVE_3D, ObjectKind.SOLID) and not obj.params.get("axes_id"):
            obj.params["axes_id"] = new(ObjectKind.AXES_3D).id
        elif obj.kind == ObjectKind.DATA_PLOT and not obj.params.get("axes_id"):
            obj.params["axes_id"] = new(ObjectKind.AXES, show_numbers=True).id
        elif obj.kind in GRAPH_TOOL_KINDS and not obj.params.get("graph_id"):
            axes = [o for o in self.scene().objects if o.kind in (ObjectKind.AXES, ObjectKind.NUMBER_PLANE)]
            axes_id = axes[-1].id if axes else new(ObjectKind.AXES).id
            obj.params["graph_id"] = new(ObjectKind.FUNCTION_GRAPH, axes_id=axes_id).id
        return hosts

    def _free_symbol(self) -> str:
        used = set(graphs.parameter_symbols(self.scene())) | {graphs.parameter_symbol(o) for o in graphs.parameter_objects(self.scene())}
        return next((symbol for symbol in PARAMETER_SYMBOLS if symbol not in used), f"p{len(used) + 1}")

    def _function_graphs(self) -> list:
        return [o for o in self.scene().objects if graphs.is_function_curve(o) and bound_axes(self.scene(), o) is not None]

    def _attach(self, obj) -> None:
        """Connect a new graph to axes and a new graph tool to a graph (the selected one if possible)."""
        scene = self.scene()
        if obj.kind in (ObjectKind.FUNCTION_GRAPH, ObjectKind.DATA_PLOT) and not obj.params.get("axes_id"):
            axes = [o for o in scene.objects if o.kind in (ObjectKind.AXES, ObjectKind.NUMBER_PLANE)]
            if axes:
                obj.params["axes_id"] = axes[-1].id
        if obj.kind in (ObjectKind.SURFACE, ObjectKind.CURVE_3D, ObjectKind.SOLID) and not obj.params.get("axes_id"):
            axes = [o for o in scene.objects if o.kind == ObjectKind.AXES_3D]
            if axes:
                obj.params["axes_id"] = axes[-1].id
        if obj.kind not in GRAPH_TOOL_KINDS or obj.params.get("graph_id"):
            return
        candidates = self._function_graphs()
        selected = [o for o in candidates if o.id in self.editor.selected_objects]
        graph = (selected or candidates or [None])[-1]
        if graph is None:
            return
        obj.params["graph_id"] = graph.id
        others = [o for o in candidates if o.id != graph.id]
        if others and not obj.params.get("other_graph_id"):
            obj.params["other_graph_id"] = others[-1].id

    def add_graph_tool(self, kind: ObjectKind, graph_id: str, **params) -> str | None:
        """Add an area, tangent, point, markers ... to a graph."""
        name = tr(f"feature.{params['feature']}") if kind == ObjectKind.GRAPH_MARKERS and "feature" in params else None
        graph = self.scene().object_by_id(graph_id)
        if graph is not None and kind in (ObjectKind.GRAPH_AREA, ObjectKind.RIEMANN):
            low, high = graphs.x_range(graph)
            params.setdefault("x_min", max(low, -1.0 if kind == ObjectKind.GRAPH_AREA else 0.0))
            params.setdefault("x_max", min(high, 2.0 if kind == ObjectKind.GRAPH_AREA else 3.0))
        return self.add_object(kind, 0.0, 0.0, name=name, graph_id=graph_id, **params)

    def add_derivative(self, graph_id: str, order: int = 1) -> str | None:
        """Add the graph of the derivative of a function graph."""
        graph = self.scene().object_by_id(graph_id)
        if graph is None:
            return None
        count = sum(1 for o in self.scene().objects if o.params.get("curve") == "derivative")
        color = DERIVATIVE_COLORS[count % len(DERIVATIVE_COLORS)]
        name = tr("graph.derivative_name" if order == 1 else "graph.second_derivative_name", name=graph.name)
        params = {
            "curve": "derivative",
            "derive_from": graph_id,
            "derive_order": str(order),
            "axes_id": graph.params.get("axes_id"),
            "x_min": graph.params.get("x_min", -5.0),
            "x_max": graph.params.get("x_max", 5.0),
        }
        return self.add_object(ObjectKind.FUNCTION_GRAPH, 0.0, 0.0, name=name, attributes={"stroke_color": color}, **params)

    def delete_objects(self, ids: list[str] | None = None) -> None:
        """Delete objects and everything that refers to them."""
        ids = list(ids if ids is not None else self.editor.selected_objects)
        if not ids:
            return
        dependents = ops.dependent_objects(self.scene(), ops.expand_for_delete(self.scene(), ids))
        names = ", ".join(sorted(self._object_name(object_id) for object_id in dependents))
        self._edit(tr("undo.delete_objects", count=len(ids) + len(dependents)), lambda s: ops.remove_objects(s, ids))
        if dependents:
            self.statusMessage.emit(tr("status.dependents_deleted", names=names))
        self.editor.select_objects([])

    def _with_members(self, ids: list[str]) -> list:
        """The objects plus all members of selected groups (a group copy needs its members)."""
        scene = self.scene()
        wanted: set[str] = set()
        for object_id in ids:
            wanted.add(object_id)
            pending = [object_id]
            while pending:
                obj = scene.object_by_id(pending.pop())
                if obj is not None and groups.is_group(obj):
                    members = [m for m in obj.params.get("members", []) if m not in wanted]
                    wanted.update(members)
                    pending += members
        return [obj for obj in scene.objects if obj.id in wanted]

    def duplicate_objects(self) -> None:
        """Copy the selected objects next to the originals."""
        objects = self._with_members(list(self.editor.selected_objects))
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
        objects = self._with_members(list(self.editor.selected_objects))
        if not objects:
            return
        # the hosts (axes, graph, marked object ...) travel along in case the target scene lacks them
        selected = {obj.id for obj in objects}
        hosts: list = []
        pending = [dep for obj in objects for dep in dependencies(scene, obj)]
        while pending:
            host = scene.object_by_id(pending.pop(0))
            if host is None or host.id in selected or host in hosts:
                continue
            hosts.append(host)
            pending += dependencies(scene, host)
        data = {"objects": [object_to_dict(obj) for obj in objects], "hosts": [object_to_dict(obj) for obj in hosts]}
        QApplication.clipboard().setText(CLIPBOARD_PREFIX + json.dumps(data, ensure_ascii=False))
        self.statusMessage.emit(tr("status.copied", count=len(objects)))

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
            data = json.loads(raw)
            if isinstance(data, list):  # clipboard of older versions
                data = {"objects": data, "hosts": []}
            objects = [object_from_dict(item) for item in data["objects"]]
            hosts = [object_from_dict(item) for item in data.get("hosts", [])]
        except (ValueError, KeyError, TypeError, AttributeError):
            return
        existing = {obj.id for obj in self.scene().objects}
        missing = [host for host in hosts if host.id not in existing]
        if missing:
            # pasted into a scene without the hosts: bring them along (before their dependents)
            objects = missing + objects
        new_ids = self._edit(
            tr("undo.paste_objects", count=len(objects)),
            lambda s: ops.paste_objects(s, objects, PASTE_OFFSET, -PASTE_OFFSET),
        )
        self.editor.select_objects(new_ids or [])

    def select_all(self) -> None:
        """Select every top-level object that is neither locked nor hidden in the editor."""
        scene = self.scene()
        ids = []
        for obj in scene.objects:
            top = groups.top_level(scene, obj.id)
            top_obj = scene.object_by_id(top)
            if top not in ids and top_obj is not None and not top_obj.locked and not top_obj.editor_hidden:
                ids.append(top)
        self.editor.select_objects(ids)

    def change_layer(self, delta: int) -> None:
        """Move the selected objects up or down in the layer order."""
        ids = list(self.editor.selected_objects)
        if ids:
            self._edit(tr("undo.layer"), lambda s: ops.change_z_index(s, ids, delta))

    # --- styles, building blocks and templates ---------------------------------------------

    def save_style(self, object_id: str) -> None:
        """Save the look of an object under a name the user chooses."""
        obj = self.scene().object_by_id(object_id)
        if obj is None or self.library is None:
            return
        name, ok = QInputDialog.getText(self.window(), tr("style.save_title"), tr("style.save_label"))
        if ok and name.strip():
            self.library.save_style(name.strip(), style_of(obj))
            self.statusMessage.emit(tr("style.saved", name=name.strip()))

    def apply_style(self, values: dict, ids: list[str] | None = None) -> None:
        """Give the selected objects a saved look."""
        ids = list(ids if ids is not None else self.editor.selected_objects)
        if ids:
            self._edit(tr("undo.apply_style"), lambda s: ops.apply_style(s, ids, values))

    def _with_descendants(self, ids: list[str]) -> list[str]:
        scene = self.scene()
        result: list[str] = []

        def visit(object_id: str) -> None:
            if object_id in result:
                return
            result.append(object_id)
            for member in groups.members(scene, object_id):
                visit(member)

        for object_id in ids:
            visit(object_id)
        return result

    def save_component(self, ids: list[str] | None = None) -> None:
        """Save the selected objects as a building block for later use."""
        ids = self._with_descendants(list(ids if ids is not None else self.editor.selected_objects))
        if not ids or self.library is None:
            return
        default = self.scene().object_by_id(ids[0]).name if len(ids) == 1 else ""
        name, ok = QInputDialog.getText(self.window(), tr("component.save_title"), tr("component.save_label"), text=default)
        if ok and name.strip():
            self.library.save_component(name.strip(), [self.scene().object_by_id(i) for i in ids])
            self.statusMessage.emit(tr("component.saved", name=name.strip()))

    def insert_component(self, component, x: float | None = None, y: float | None = None) -> list[str]:
        """Insert a building block (centered at ``x``/``y`` or at a free spot)."""
        objects = component.create_objects()
        if not objects:
            return []
        placed = [obj for obj in objects if obj.kind not in UNADDED_KINDS]
        if placed:
            cx = (min(o.x for o in placed) + max(o.x for o in placed)) / 2
            cy = (min(o.y for o in placed) + max(o.y for o in placed)) / 2
        else:
            cx = cy = 0.0
        if x is None or y is None:
            x, y = self._free_position()
        new_ids = self._edit(tr("undo.insert_component", name=component.name), lambda s: ops.paste_objects(s, objects, x - cx, y - cy))
        self.editor.select_objects(new_ids or [])
        return new_ids or []

    def add_scene_from_template(self, template_scene: Scene) -> None:
        """Add a new scene that starts as a copy of a template."""
        names = [scene.name for scene in self.document.project.scenes]
        scene = clone_scene(template_scene, unique_name(names, template_scene.name))
        self.document.edit_project(tr("undo.add_scene"), lambda p: ops.add_scene(p, scene))
        self.editor.set_scene(scene.id)

    def save_template(self) -> None:
        """Save the active scene as a template for new scenes."""
        if self.library is None:
            return
        name, ok = QInputDialog.getText(self.window(), tr("template.save_title"), tr("template.save_label"), text=self.scene().name)
        if ok and name.strip():
            self.library.save_template(name.strip(), self.scene())
            self.statusMessage.emit(tr("template.saved", name=name.strip()))

    # --- groups, arranging and layers ---------------------------------------------------

    def group_selection(self) -> None:
        """Put the selected objects into a new group."""
        scene = self.scene()
        ids = [i for i in self.editor.selected_objects if (obj := scene.object_by_id(i)) is not None and obj.kind not in UNGROUPABLE]
        if len(ids) < 2:
            self.statusMessage.emit(tr("status.group_needs_two"))
            return
        name = unique_name([obj.name for obj in self.scene().objects], tr("kind.group"))
        group_id = self._edit(tr("undo.group"), lambda s: ops.group_objects(s, ids, name))
        if group_id:
            self.editor.select_objects([group_id])

    def ungroup_selection(self) -> None:
        """Dissolve the selected groups and select their members."""
        scene = self.scene()
        group_ids = [i for i in self.editor.selected_objects if groups.is_group(scene.object_by_id(i))]
        if not group_ids:
            return

        def mutate(s: Scene) -> list[str]:
            members: list[str] = []
            for group_id in group_ids:
                members += ops.ungroup(s, group_id)
            return members

        members = self._edit(tr("undo.ungroup"), mutate)
        self.editor.select_objects(members or [])

    def can_group(self) -> bool:
        """Return ``True`` if the selection can be grouped."""
        return len(self.editor.selected_objects) >= 2

    def can_ungroup(self) -> bool:
        """Return ``True`` if a group is selected."""
        scene = self.scene()
        return any(groups.is_group(scene.object_by_id(i)) for i in self.editor.selected_objects)

    def arrange(self, mode: str, boxes: dict[str, tuple[float, float, float, float]], frame: tuple[float, float, float, float] | None = None) -> None:
        """Align or distribute objects given their drawn bounds (Manim units)."""
        deltas = arrange_deltas(boxes, mode, frame)
        moving = {object_id: delta for object_id, delta in deltas.items() if abs(delta[0]) > 1e-6 or abs(delta[1]) > 1e-6}
        if not moving:
            return
        allowed, message = self.edit_policy(MOVE, list(moving))
        if not allowed:
            self.statusMessage.emit(message)
            return
        self._announce_recording(list(moving), MOVE)
        self._edit(tr(f"undo.arrange.{mode}"), move_each_edit(self.editor.cursor, moving))

    def set_locked(self, ids: list[str], locked: bool) -> None:
        """Lock or unlock objects in the editor."""
        if ids:
            self._edit(tr("undo.lock" if locked else "undo.unlock"), lambda s: ops.set_editor_flags(s, ids, locked=locked))
            if locked:
                self.editor.select_objects([i for i in self.editor.selected_objects if i not in ids])

    def set_hidden(self, ids: list[str], hidden: bool) -> None:
        """Hide or show objects in the editor (the video is not affected)."""
        if ids:
            self._edit(tr("undo.hide" if hidden else "undo.show"), lambda s: ops.set_editor_flags(s, ids, hidden=hidden))
            if hidden:
                self.editor.select_objects([i for i in self.editor.selected_objects if i not in ids])

    def toggle_locked(self, ids: list[str] | None = None) -> None:
        """Lock the objects, or unlock them if all are locked."""
        ids = list(ids if ids is not None else self.editor.selected_objects)
        objects = [self.scene().object_by_id(i) for i in ids]
        self.set_locked(ids, not all(obj is not None and obj.locked for obj in objects))

    def toggle_hidden(self, ids: list[str] | None = None) -> None:
        """Hide the objects in the editor, or show them if all are hidden."""
        ids = list(ids if ids is not None else self.editor.selected_objects)
        objects = [self.scene().object_by_id(i) for i in ids]
        self.set_hidden(ids, not all(obj is not None and obj.editor_hidden for obj in objects))

    def rename_object(self, object_id: str, name: str) -> None:
        """Give an object a new name."""
        name = name.strip()
        obj = self.scene().object_by_id(object_id)
        if name and obj is not None and name != obj.name:
            self._edit(tr("undo.rename_object"), lambda s: ops.update_object(s, object_id, name=name))

    def move_layer(self, object_id: str, below_id: str | None, above_id: str | None) -> None:
        """Reorder an object in the layer list (drag and drop)."""
        self._edit(tr("undo.layer"), lambda s: move_layer(s, object_id, below_id, above_id))

    # --- vertices and endpoints (start of the timeline only) ----------------------------

    def _point_edit(self, text: str, mutate) -> None:
        try:
            self._edit(text, mutate)
        except ops.ModelError:
            self.statusMessage.emit(tr("status.point_edit_failed"))

    def move_vertex(self, object_id: str, index: int, x: float, y: float) -> None:
        """Move a polygon vertex (coordinates in the polygon's own system)."""
        self._point_edit(tr("undo.vertex"), lambda s: ops.set_polygon_point(s, object_id, index, x, y))

    def insert_vertex(self, object_id: str, index: int, x: float, y: float) -> None:
        """Add a polygon vertex before ``index``."""
        self._point_edit(tr("undo.vertex_add"), lambda s: ops.insert_polygon_point(s, object_id, index, x, y))

    def remove_vertex(self, object_id: str, index: int) -> None:
        """Delete a polygon vertex."""
        self._point_edit(tr("undo.vertex_remove"), lambda s: ops.remove_polygon_point(s, object_id, index))

    def set_line_endpoint(self, object_id: str, which: int, x: float, y: float) -> None:
        """Move the start (0) or end (1) of a line to a scene position."""
        self._point_edit(tr("undo.endpoint"), lambda s: ops.set_line_endpoint(s, object_id, which, x, y))

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

    def set_value(self, object_id: str, value: float, merge_key: str | None = None) -> None:
        """Change a parameter (or number) at the start, or record a "change value" animation."""
        if not self.edit_policy(VALUE, [object_id])[0]:
            return
        self._announce_recording([object_id], VALUE)
        self._edit(tr("undo.value"), value_edit(self.editor.cursor, object_id, value), merge_key=merge_key)

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
        """Insert an empty play step, a wait step or an expert code step after the current one."""
        if kind == StepKind.CODE:
            step = create_wait_step(1.0)
            step.kind = StepKind.CODE
            step.code = tr("code_step.template")
        else:
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
        self.add_reference_animation(kind, source_id, target_id, same_step, inspect)

    def add_reference_animation(self, kind: AnimationKind, source_id: str, other_id: str, same_step: bool, inspect: bool = True) -> None:
        """Add a transform, a move along a path or a swap with a second object."""
        if not allowed_for_objects(self.scene(), kind, [source_id]) or other_id not in {o.id for o in reference_candidates(self.scene(), kind, source_id)}:
            self.statusMessage.emit(tr("status.animation_not_allowed"))
            return
        animation = create_animation(kind, source_id, **{REFERENCE_PARAMS[kind]: other_id})
        self._insert_animations([animation], same_step and self.recording(), kind, inspect)

    def fade_out_all(self) -> None:
        """Add a step that fades out every object that is visible at this point."""
        scene = self.scene()
        states = states_after(scene, self.editor.cursor)
        ids = []
        for obj in scene.objects:
            if obj.kind in UNADDED_KINDS or groups.parent_group(scene, obj.id) is not None:
                continue
            state = states.get(obj.id)
            if state is not None and state.visible and allowed_for_objects(scene, AnimationKind.FADE_OUT, [obj.id]):
                ids.append(obj.id)
        if not ids:
            self.statusMessage.emit(tr("status.nothing_visible"))
            return
        animations = [create_animation(AnimationKind.FADE_OUT, object_id) for object_id in ids]
        self._insert_animations(animations, False, AnimationKind.FADE_OUT, False)

    def zoom_camera(self, center: tuple[float, float] | None, size: tuple[float, float] | None, frame: tuple[float, float]) -> None:
        """Add a step that moves and zooms the camera onto a region (``None`` = back to the start view).

        ``frame`` is the size of the video frame in Manim units.
        """
        scene = self.scene()
        from manim_studio.model.three_d import is_3d

        if is_3d(scene):
            self.statusMessage.emit(tr("status.camera_zoom_2d_only"))
            return
        camera = next((obj for obj in scene.objects if obj.kind == ObjectKind.CAMERA), None)
        if camera is None:
            if center is None:
                return
            camera_id = self.add_object(ObjectKind.CAMERA)
            camera = self.scene().object_by_id(camera_id)
            scene = self.scene()
        state = states_after(scene, self.editor.cursor).get(camera.id)
        base_width = float(camera.params.get("width", 0.0) or 0.0) or frame[0]
        current = base_width * (state.scale if state is not None else 1.0)
        if center is None or size is None:
            target_center, target_width = (camera.x, camera.y), base_width
        else:
            # leave a margin and keep the video's aspect ratio
            target_center = center
            target_width = max(size[0] * 1.3, size[1] * 1.3 * frame[0] / frame[1], 0.5)
        animations = [
            create_animation(AnimationKind.MOVE, camera.id, run_time=1.5, x=round(target_center[0], 4), y=round(target_center[1], 4)),
            create_animation(AnimationKind.SCALE, camera.id, run_time=1.5, factor=round(target_width / current, 5)),
        ]
        self._insert_animations(animations, False, AnimationKind.MOVE, False)

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
            step = self.scene().steps[cursor]
            if step.mode != STEP_SEQUENCE and simultaneous_conflicts([*step.animations, *animations]) - simultaneous_conflicts(step.animations):
                # e.g. transforming and moving one object, or creating it while it wiggles
                use_current = False
                self.statusMessage.emit(tr("status.own_step_for_conflict", step=cursor + 2))
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

    def set_step_fields(self, step_id: str, merge_key: str | None = None, **values) -> None:
        """Change section, subtitle, sound or code of a step."""
        self._edit(tr("undo.step_details"), lambda s: ops.set_step_fields(s, step_id, **values), merge_key)

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
