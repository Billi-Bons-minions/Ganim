"""Property editor for the selected object, animation, step or scene.

Forms are generated from :mod:`manim_studio.model.schema`. Each row is bound
to the model through a read function; after every model change the rows are
refreshed in place (unless the user is typing in them).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSpinBox,
    QWidget,
)

from manim_studio.codegen.naming import class_names
from manim_studio.i18n import has, tr
from manim_studio.model import operations as ops
from manim_studio.model.assets import relative_asset_path
from manim_studio.model.entities import Animation, SceneObject, Step
from manim_studio.model.expression import check_expression
from manim_studio.model.geometry import is_bound_graph
from manim_studio.model.schema import (
    ParamSpec,
    ParamType,
    animation_allowed,
    animation_params,
    kind_info,
)
from manim_studio.model.state import first_reference, visible_at_start
from manim_studio.model.types import RATE_FUNCTIONS, AnimationKind, StepKind, Visibility
from manim_studio.ui.document import ProjectDocument
from manim_studio.ui.editor_state import (
    INSPECT_ANIMATION,
    INSPECT_OBJECTS,
    INSPECT_STEP,
    EditorState,
)
from manim_studio.ui.settings import AppSettings
from manim_studio.ui.icon_set import icon
from manim_studio.ui.icons import kind_icon
from manim_studio.ui.theme import px
from manim_studio.ui.widgets import (
    ColorButton,
    DebouncedLineEdit,
    DebouncedTextEdit,
    FileField,
    SpinBox,
)

Reader = Callable[[], Any]
Shower = Callable[[Any], None]

_STYLE_SPECS = {
    "stroke_color": ParamSpec("stroke_color", ParamType.COLOR, "#FFFFFF"),
    "stroke_width": ParamSpec("stroke_width", ParamType.FLOAT, 4.0, minimum=0.0, maximum=50.0, step=0.5, decimals=1),
    "stroke_opacity": ParamSpec("stroke_opacity", ParamType.FLOAT, 1.0, minimum=0.0, maximum=1.0, step=0.05),
    "fill_color": ParamSpec("fill_color", ParamType.COLOR, "#FFFFFF"),
    "fill_opacity": ParamSpec("fill_opacity", ParamType.FLOAT, 0.0, minimum=0.0, maximum=1.0, step=0.05),
}
_POSITION_SPEC = ParamSpec("pos", ParamType.FLOAT, 0.0, minimum=-100.0, maximum=100.0, step=0.25, decimals=3)
_ROTATION_SPEC = ParamSpec("rotation", ParamType.FLOAT, 0.0, minimum=-360.0, maximum=360.0, step=15.0, decimals=1)
_RUN_TIME_SPEC = ParamSpec("run_time", ParamType.FLOAT, 1.0, minimum=0.05, maximum=120.0, step=0.25)


@dataclass
class Binding:
    """Connects one widget with a value in the model."""

    widget: QWidget
    read: Reader
    show: Shower

    def refresh(self) -> None:
        """Show the current model value unless the user is editing the widget."""
        focus = QApplication.focusWidget()
        if focus is not None and (focus is self.widget or self.widget.isAncestorOf(focus)):
            return
        try:
            value = self.read()
        except (AttributeError, KeyError, TypeError):
            return
        self.show(value)


def _set_spin(spin: SpinBox | QSpinBox, value: Any) -> None:
    if value is None:
        return
    if abs(float(spin.value()) - float(value)) > 1e-9:
        spin.blockSignals(True)
        spin.setValue(value)
        spin.blockSignals(False)


def _set_combo_data(combo: QComboBox, value: Any) -> None:
    index = combo.findData(value)
    if index != combo.currentIndex():
        combo.blockSignals(True)
        combo.setCurrentIndex(index)
        combo.blockSignals(False)


def _set_check(box: QCheckBox, value: Any) -> None:
    box.blockSignals(True)
    box.setChecked(bool(value))
    box.blockSignals(False)


def _set_line(edit: DebouncedLineEdit, value: Any) -> None:
    if edit.text() != str(value):
        edit.setText(str(value))


def _choice_label(key: str, value: str) -> str:
    specific = f"choice.{key}.{value}"
    return tr(specific) if has(specific) else value


class _Form:
    """Builds a form layout and collects its bindings."""

    def __init__(self) -> None:
        self.widget = QWidget()
        self.widget.setObjectName("Inspector")
        self.layout = QFormLayout(self.widget)
        self.layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.layout.setContentsMargins(px(14), px(12), px(14), px(14))
        self.layout.setHorizontalSpacing(px(10))
        self.layout.setVerticalSpacing(px(7))
        self.bindings: list[Binding] = []

    def header(self, text: str, header_icon: QIcon | None = None) -> None:
        row = QWidget()
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, px(4))
        line.setSpacing(px(8))
        if header_icon is not None:
            picture = QLabel()
            picture.setPixmap(header_icon.pixmap(QSize(px(22), px(22))))
            line.addWidget(picture)
        label = QLabel(text)
        label.setProperty("role", "title")
        font = label.font()
        font.setPointSizeF(font.pointSizeF() * 1.2)
        label.setFont(font)
        line.addWidget(label, 1)
        self.layout.addRow(row)

    def header_widget(self, widget: QWidget) -> None:
        self.layout.addRow(widget)

    def section(self, text: str) -> None:
        spacer = QWidget()
        spacer.setFixedHeight(px(6))
        self.layout.addRow(spacer)
        label = QLabel(text.upper())
        label.setProperty("role", "section")
        font = label.font()
        font.setPointSizeF(font.pointSizeF() * 0.85)
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 108)
        label.setFont(font)
        self.layout.addRow(label)

    def row(self, label: str, widget: QWidget, read: Reader, show: Shower) -> QWidget:
        self.layout.addRow(label, widget)
        binding = Binding(widget, read, show)
        self.bindings.append(binding)
        binding.refresh()
        return widget

    def note(self, read: Callable[[], str], warning: bool = False) -> QLabel:
        label = QLabel()
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setProperty("role", "warning" if warning else "muted")

        def show(text: str) -> None:
            label.setText(text)
            label.setVisible(bool(text))

        self.layout.addRow(label)
        binding = Binding(label, read, show)
        self.bindings.append(binding)
        binding.refresh()
        return label


class PropertiesPanel(QScrollArea):
    """Edits whatever :class:`EditorState` currently inspects."""

    def __init__(
        self,
        document: ProjectDocument,
        editor: EditorState,
        settings: AppSettings,
        latex_status: Callable[[str], str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.document = document
        self.editor = editor
        self.settings = settings
        self.latex_status = latex_status
        self.setWidgetResizable(True)
        self.setObjectName("Inspector")
        self.setMinimumWidth(px(280))
        self._key: tuple | None = None
        self._form: _Form | None = None
        document.changed.connect(self.refresh)
        editor.inspectorChanged.connect(self.refresh)
        editor.sceneChanged.connect(self.refresh)
        editor.cursorChanged.connect(self.refresh)
        editor.selectionChanged.connect(self.refresh)
        self.refresh()

    # --- dispatch -------------------------------------------------------------

    def _target_key(self) -> tuple:
        scene = self.editor.scene()
        kind, entity_id = self.editor.inspected
        if kind == INSPECT_ANIMATION:
            found = scene.find_animation(entity_id)
            if found:
                return ("animation", scene.id, entity_id, found[1].kind)
        if kind == INSPECT_STEP:
            step = scene.step_by_id(entity_id)
            if step:
                return ("step", scene.id, entity_id, step.kind)
        if kind == INSPECT_OBJECTS and self.editor.selected_objects:
            ids = tuple(self.editor.selected_objects)
            if len(ids) == 1:
                obj = scene.object_by_id(ids[0])
                if obj:
                    return ("object", scene.id, obj.id, obj.kind)
            return ("objects", scene.id, ids)
        return ("scene", scene.id)

    def refresh(self) -> None:
        """Update values in place or rebuild the form if the target changed."""
        key = self._target_key()
        if key == self._key and self._form is not None:
            for binding in self._form.bindings:
                binding.refresh()
            return
        self._key = key
        builders = {
            "animation": self._build_animation,
            "step": self._build_step,
            "object": self._build_object,
            "objects": self._build_multi,
            "scene": self._build_scene,
        }
        form = _Form()
        builders[key[0]](form, key)
        self._form = form
        old = self.takeWidget()
        if old is not None:
            old.deleteLater()
        self.setWidget(form.widget)

    # --- model access ---------------------------------------------------------

    def _edit(self, label: str, mutate, merge_key: str | None) -> None:
        self.document.edit_scene(tr("undo.edit_property", name=label), self.editor.scene_id, mutate, merge_key)

    def _object(self, object_id: str) -> SceneObject:
        obj = self.editor.scene().object_by_id(object_id)
        if obj is None:
            raise KeyError(object_id)
        return obj

    def _animation(self, animation_id: str) -> Animation:
        found = self.editor.scene().find_animation(animation_id)
        if found is None:
            raise KeyError(animation_id)
        return found[1]

    def _step(self, step_id: str) -> Step:
        step = self.editor.scene().step_by_id(step_id)
        if step is None:
            raise KeyError(step_id)
        return step

    # --- generic editors ---------------------------------------------------------

    def _float_editor(self, spec: ParamSpec, commit: Callable[[Any], None]) -> tuple[QWidget, Shower]:
        minimum = spec.minimum if spec.minimum is not None else -1e6
        maximum = spec.maximum if spec.maximum is not None else 1e6
        spin = SpinBox(minimum, maximum, spec.step, spec.decimals)
        spin.valueChanged.connect(lambda value: commit(round(value, spec.decimals)))
        return spin, lambda value: _set_spin(spin, value)

    def _object_ref_editor(
        self, spec: ParamSpec, commit: Callable[[Any], None], exclude: Callable[[], str | None], allowed: Callable[[SceneObject], bool]
    ) -> tuple[QWidget, Shower]:
        combo = QComboBox()

        def options() -> list[tuple[str, str | None]]:
            excluded = exclude()
            entries = [(tr("prop.none"), None)] if spec.optional else []
            for obj in self.editor.scene().objects:
                kind_ok = not spec.ref_kinds or obj.kind in spec.ref_kinds
                if obj.id != excluded and kind_ok and allowed(obj):
                    entries.append((obj.name, obj.id))
            if not spec.optional and not entries:
                entries.append((tr("prop.no_candidates"), None))
            return entries

        def show(value: Any) -> None:
            entries = options()
            current = [(combo.itemText(i), combo.itemData(i)) for i in range(combo.count())]
            if current != entries:
                combo.blockSignals(True)
                combo.clear()
                for text, data in entries:
                    combo.addItem(text, data)
                combo.blockSignals(False)
            if combo.findData(value) < 0 and not spec.optional:
                combo.blockSignals(True)
                combo.setCurrentIndex(-1)
                combo.blockSignals(False)
                return
            _set_combo_data(combo, value)

        combo.currentIndexChanged.connect(lambda _index: commit(combo.currentData()))
        return combo, show

    def _param_editor(
        self,
        spec: ParamSpec,
        commit: Callable[[Any], None],
        exclude: Callable[[], str | None] = lambda: None,
        allowed: Callable[[SceneObject], bool] = lambda obj: True,
    ) -> tuple[QWidget, Shower]:
        if spec.type == ParamType.FLOAT:
            return self._float_editor(spec, commit)
        if spec.type == ParamType.INT:
            spin = QSpinBox()
            spin.setRange(int(spec.minimum or -1000), int(spec.maximum or 1000))
            spin.setKeyboardTracking(False)
            spin.valueChanged.connect(commit)
            return spin, lambda value: _set_spin(spin, value)
        if spec.type == ParamType.BOOL:
            box = QCheckBox()
            box.toggled.connect(commit)
            return box, lambda value: _set_check(box, value)
        if spec.type == ParamType.COLOR:
            button = ColorButton()
            button.colorChosen.connect(commit)
            return button, lambda value: button.set_color(str(value))
        if spec.type == ParamType.CHOICE:
            combo = QComboBox()
            for choice in spec.choices:
                combo.addItem(_choice_label(spec.key, choice), choice)
            combo.currentIndexChanged.connect(lambda _index: commit(combo.currentData()))
            return combo, lambda value: _set_combo_data(combo, value)
        if spec.type in (ParamType.TEXT, ParamType.LATEX):
            edit = DebouncedTextEdit()
            edit.setFixedHeight(76)
            if spec.type == ParamType.LATEX:
                edit.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
            edit.committed.connect(commit)
            return edit, lambda value: edit.set_text_silently(str(value or ""))
        if spec.type == ParamType.FILE:
            field = FileField(tr("dialog.image_filter"), lambda: self.settings.last_directory("image"))
            field.committed.connect(commit)
            return field, lambda value: field.set_path(str(value or ""))
        if spec.type == ParamType.OBJECT_REF:
            return self._object_ref_editor(spec, commit, exclude, allowed)
        edit = DebouncedLineEdit()
        if spec.type == ParamType.EXPRESSION:
            edit.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
            edit.setPlaceholderText("2x^2 + sin(x)")
        edit.committed.connect(commit)
        return edit, lambda value: _set_line(edit, value or "")

    # --- object form -----------------------------------------------------------------

    def _object_field_row(self, form: _Form, object_id: str, field: str, spec: ParamSpec, label: str) -> QWidget:
        def commit(value: Any) -> None:
            self._edit(label, lambda s: ops.update_object(s, object_id, **{field: value}), f"obj:{object_id}:{field}")

        widget, show = self._param_editor(spec, commit)
        return form.row(label, widget, lambda: getattr(self._object(object_id), field), show)

    def _object_param_row(self, form: _Form, object_id: str, spec: ParamSpec) -> None:
        label = tr(f"param.{spec.key}")

        def commit(value: Any) -> None:
            if spec.type == ParamType.FILE:
                value = relative_asset_path(str(value), self.document.base_dir)
            self._edit(label, lambda s: ops.set_object_param(s, object_id, spec.key, value), f"obj:{object_id}:p:{spec.key}")

        widget, show = self._param_editor(spec, commit, exclude=lambda: object_id)
        form.row(label, widget, lambda: self._object(object_id).params.get(spec.key, spec.default), show)
        if spec.type == ParamType.EXPRESSION:
            form.note(lambda: self._expression_message(object_id), warning=True)
        if spec.type == ParamType.LATEX:
            form.note(lambda: self.latex_status(str(self._object(object_id).params.get("latex", ""))), warning=True)

    def _expression_message(self, object_id: str) -> str:
        error = check_expression(str(self._object(object_id).params.get("expression", "")))
        if error is None:
            return ""
        return tr(f"expr.{error.code}", detail=error.detail)

    def _visibility_note(self, object_id: str) -> str:
        scene = self.editor.scene()
        obj = self._object(object_id)
        if obj.visibility != Visibility.AUTO:
            return ""
        if visible_at_start(scene, obj):
            return tr("prop.visibility_auto_shown")
        reference = first_reference(scene, obj.id)
        animation = tr(f"anim.{reference[0].kind.value}") if reference else ""
        return tr("prop.visibility_auto_hidden", animation=animation)

    def _build_object(self, form: _Form, key: tuple) -> None:
        object_id, kind = key[2], key[3]
        info = kind_info(kind)
        form.header(tr(f"kind.{kind.value}"), kind_icon(kind))
        name_edit = DebouncedLineEdit()
        name_edit.committed.connect(
            lambda text: text.strip()
            and self._edit(tr("prop.name"), lambda s: ops.update_object(s, object_id, name=text.strip()), f"obj:{object_id}:name")
        )
        form.row(tr("prop.name"), name_edit, lambda: self._object(object_id).name, lambda v: _set_line(name_edit, v))
        form.section(tr("section.position"))
        bound = is_bound_graph(self.editor.scene(), self._object(object_id))
        for field, spec in (("x", _POSITION_SPEC), ("y", _POSITION_SPEC), ("rotation", _ROTATION_SPEC)):
            widget = self._object_field_row(form, object_id, field, spec, tr(f"prop.{field}"))
            widget.setEnabled(not bound)
        if bound:
            form.note(lambda: tr("prop.bound_graph_note"))
        form.note(lambda: tr("prop.step_view_note") if self.editor.cursor >= 0 else "")
        if info.params:
            form.section(tr("section.content"))
            for spec in info.params:
                self._object_param_row(form, object_id, spec)
        if info.style:
            form.section(tr("section.style"))
            for field in ("stroke_color", "stroke_width", "stroke_opacity", "fill_color", "fill_opacity"):
                if field in info.style:
                    self._object_field_row(form, object_id, field, _STYLE_SPECS[field], tr(f"prop.{field}"))
        form.section(tr("section.layer"))
        layer = ParamSpec("z_index", ParamType.INT, 0, minimum=-100, maximum=100)
        self._object_field_row(form, object_id, "z_index", layer, tr("prop.z_index"))
        visibility = ParamSpec("visibility", ParamType.CHOICE, "auto", choices=tuple(v.value for v in Visibility))

        def commit_visibility(value: Any) -> None:
            self._edit(
                tr("prop.visibility"),
                lambda s: ops.update_object(s, object_id, visibility=Visibility(value)),
                f"obj:{object_id}:visibility",
            )

        widget, show = self._param_editor(visibility, commit_visibility)
        form.row(tr("prop.visibility"), widget, lambda: self._object(object_id).visibility.value, show)
        form.note(lambda: self._visibility_note(object_id))

    # --- several objects -----------------------------------------------------------------

    def _build_multi(self, form: _Form, key: tuple) -> None:
        ids = list(key[2])
        form.header(tr("prop.multi_header", count=len(ids)), icon("group"))
        form.note(lambda: tr("prop.multi_note"))
        for field in ("stroke_color", "fill_color", "fill_opacity"):
            spec = _STYLE_SPECS[field]
            label = tr(f"prop.{field}")

            def commit(value: Any, field: str = field, label: str = label) -> None:
                def mutate(scene) -> None:
                    for object_id in ids:
                        obj = scene.object_by_id(object_id)
                        if obj is not None and field in kind_info(obj.kind).style:
                            setattr(obj, field, value)

                self._edit(label, mutate, f"multi:{','.join(ids)}:{field}")

            widget, show = self._param_editor(spec, commit)
            form.row(label, widget, lambda field=field: getattr(self._object(ids[0]), field), show)

    # --- animation form -------------------------------------------------------------------

    def _build_animation(self, form: _Form, key: tuple) -> None:
        animation_id, kind = key[2], key[3]
        scene = self.editor.scene()
        found = scene.find_animation(animation_id)
        step_number = scene.step_index(found[0].id) + 1 if found else 0
        form.header(tr("prop.animation_header", name=tr(f"anim.{kind.value}"), step=step_number), icon("sparkle"))
        form.note(lambda: tr(f"anim_help.{kind.value}"))
        target_spec = ParamSpec("target_id", ParamType.OBJECT_REF, None)

        def commit_target(value: Any) -> None:
            if value:
                self._edit(tr("prop.target"), lambda s: ops.update_animation(s, animation_id, target_id=value), None)

        def target_allowed(obj: SceneObject) -> bool:
            return animation_allowed(kind, obj.kind, obj.params)

        widget, show = self._param_editor(target_spec, commit_target, allowed=target_allowed)
        form.row(tr("prop.target"), widget, lambda: self._animation(animation_id).target_id, show)

        def commit_run_time(value: Any) -> None:
            self._edit(tr("prop.run_time"), lambda s: ops.update_animation(s, animation_id, run_time=value), f"anim:{animation_id}:run_time")

        widget, show = self._float_editor(_RUN_TIME_SPEC, commit_run_time)
        form.row(tr("prop.run_time"), widget, lambda: self._animation(animation_id).run_time, show)
        rate = QComboBox()
        for name in RATE_FUNCTIONS:
            rate.addItem(tr(f"rate.{name}"), name)
        rate.currentIndexChanged.connect(
            lambda _i: self._edit(
                tr("prop.rate_func"), lambda s: ops.update_animation(s, animation_id, rate_func=rate.currentData()), None
            )
        )
        form.row(tr("prop.rate_func"), rate, lambda: self._animation(animation_id).rate_func, lambda v: _set_combo_data(rate, v))
        for spec in animation_params(kind):
            self._animation_param_row(form, animation_id, kind, spec)
        if kind in (AnimationKind.MOVE, AnimationKind.SCALE, AnimationKind.ROTATE):
            form.note(lambda: tr("prop.drag_hint"))

    def _animation_param_row(self, form: _Form, animation_id: str, kind: AnimationKind, spec: ParamSpec) -> None:
        label = tr(f"aparam.{spec.key}")

        def commit(value: Any) -> None:
            self._edit(label, lambda s: ops.set_animation_param(s, animation_id, spec.key, value), f"anim:{animation_id}:{spec.key}")

        def allowed(obj: SceneObject) -> bool:
            return animation_allowed(kind, obj.kind, obj.params)

        widget, show = self._param_editor(spec, commit, exclude=lambda: self._animation(animation_id).target_id, allowed=allowed)
        form.row(label, widget, lambda: self._animation(animation_id).params.get(spec.key, spec.default), show)

    # --- step form ------------------------------------------------------------------------------

    def _step_summary(self, step_id: str) -> str:
        step = self._step(step_id)
        scene = self.editor.scene()
        lines = [tr("prop.step_duration", seconds=f"{step.duration():.2f}")]
        for anim in step.animations:
            target = scene.object_by_id(anim.target_id)
            lines.append(f"• {tr(f'anim.{anim.kind.value}')} – {target.name if target else '?'}")
        if not step.animations:
            lines.append(tr("prop.step_empty"))
        return "\n".join(lines)

    def _build_step(self, form: _Form, key: tuple) -> None:
        step_id, kind = key[2], key[3]
        number = self.editor.scene().step_index(step_id) + 1
        if kind == StepKind.WAIT:
            form.header(tr("prop.wait_header", step=number), icon("clock"))
            spec = ParamSpec("wait_time", ParamType.FLOAT, 1.0, minimum=0.05, maximum=600.0, step=0.25)

            def commit(value: Any) -> None:
                self._edit(tr("prop.wait_time"), lambda s: ops.set_wait_time(s, step_id, value), f"step:{step_id}:wait")

            widget, show = self._float_editor(spec, commit)
            form.row(tr("prop.wait_time"), widget, lambda: self._step(step_id).wait_time, show)
            return
        form.header(tr("prop.step_header", step=number), icon("layers"))
        form.note(lambda: self._step_summary(step_id))
        form.note(lambda: tr("prop.step_hint"))

    # --- scene form --------------------------------------------------------------------------------

    def _build_scene(self, form: _Form, key: tuple) -> None:
        scene_id = key[1]
        form.header(tr("prop.scene_header"), icon("scene"))
        name_edit = DebouncedLineEdit()
        name_edit.committed.connect(
            lambda text: text.strip()
            and self.document.edit_project(
                tr("undo.rename_scene"), lambda p: ops.rename_scene(p, scene_id, text.strip()), f"scene:{scene_id}:name"
            )
        )
        form.row(tr("prop.scene_name"), name_edit, lambda: self.editor.scene().name, lambda v: _set_line(name_edit, v))
        class_label = QLabel()
        class_label.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        form.row(
            tr("prop.class_name"),
            class_label,
            lambda: class_names(self.document.project).get(scene_id, ""),
            class_label.setText,
        )
        background = ColorButton()
        background.colorChosen.connect(
            lambda color: self._edit(tr("prop.background"), lambda s: ops.set_background(s, color), f"scene:{scene_id}:bg")
        )
        form.row(tr("prop.background"), background, lambda: self.editor.scene().background_color, lambda v: background.set_color(v))
        form.note(lambda: self._scene_summary())
        form.note(lambda: tr("prop.scene_hint"))

    def _scene_summary(self) -> str:
        scene = self.editor.scene()
        total = sum(step.duration() for step in scene.steps)
        return tr("prop.scene_summary", objects=len(scene.objects), steps=len(scene.steps), seconds=f"{total:.1f}")
