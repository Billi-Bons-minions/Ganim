"""Property editor for the selected object, animation, step or scene.

Forms are generated from :mod:`manim_studio.model.schema`. Each row is bound
to the model through a read function; after every model change the rows are
refreshed in place (unless the user is typing in them).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from manim_studio.codegen.naming import class_names, variable_names
from manim_studio.i18n import has, tr
from manim_studio.model import graphs, groups
from manim_studio.model import operations as ops
from manim_studio.model.animation_builder import allowed_for_objects, reference_candidates
from manim_studio.model.arrange import ALIGN_MODES, DISTRIBUTE_MODES
from manim_studio.model.assets import relative_asset_path
from manim_studio.model.attach import ATTACH_FOLLOW, ATTACH_FORMULA, ATTACH_SPECS, ATTACHABLE_KINDS, attach_mode, can_follow, is_attached, set_attach_mode
from manim_studio.model.booleans import OPERAND_KEYS, can_use
from manim_studio.model.entities import STEP_LAGGED, STEP_MODES, STEP_TOGETHER, Animation, SceneObject, Step
from manim_studio.model.expression import check_expression
from manim_studio.model.frame import ASPECTS
from manim_studio.model.graphs import is_bound
from manim_studio.model.schema import (
    STYLE_FIELDS,
    ParamSpec,
    ParamType,
    animation_allowed,
    animation_params,
    default_params,
    kind_info,
)
from manim_studio.model.stage_edits import COLOR, MOVE, ROTATE, SCALE, is_recording, step_animation
from manim_studio.model.state import first_reference, states_after, visible_at_start
from manim_studio.model.types import (
    GRAPH_TOOL_KINDS,
    LABELED_TOOL_KINDS,
    LINE_KINDS,
    RATE_FUNCTIONS,
    REFERENCE_PARAMS,
    TRANSFORM_ANIMATIONS,
    AnimationKind,
    ObjectKind,
    StepKind,
    Visibility,
)
from manim_studio.ui.animation_catalog import ANIMATION_GROUPS, ONLY_WHEN_ALLOWED
from manim_studio.ui.animation_preview import PreviewHover
from manim_studio.ui.controller import EditorController
from manim_studio.ui.data_editors import BarsEditor, DataEditor, FontPicker, PiecesEditor, PointsEditor, TableEditor, WordColorsEditor
from manim_studio.ui.document import ProjectDocument
from manim_studio.ui.editor_state import (
    INSPECT_ANIMATION,
    INSPECT_OBJECTS,
    INSPECT_STEP,
    EditorState,
)
from manim_studio.ui.flow_layout import flow_container
from manim_studio.ui.icon_set import icon
from manim_studio.ui.icons import kind_icon, rate_icon
from manim_studio.ui.parameter_slider import ParameterSlider
from manim_studio.ui.settings import AppSettings
from manim_studio.ui.style_menu import fill_style_menu
from manim_studio.ui.theme import px
from manim_studio.ui.widgets import (
    ColorButton,
    DebouncedLineEdit,
    DebouncedTextEdit,
    FileField,
    SpinBox,
)

Reader = Callable[[], Any]
#: Widget property: the editor protects its own in-progress edits, so it may always be refreshed.
ALWAYS_REFRESH = "alwaysRefresh"
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
#: Shapes offered as new targets for "transform into".
TRANSFORM_TARGET_KINDS = (
    ObjectKind.SQUARE, ObjectKind.CIRCLE, ObjectKind.RECTANGLE, ObjectKind.TRIANGLE, ObjectKind.ELLIPSE, ObjectKind.TEXT, ObjectKind.MATH_TEX
)
#: Object references that must point to graphs of the form y = f(x).
FUNCTION_GRAPH_REFS = ("graph_id", "other_graph_id", "derive_from")
#: Formulas of parameters (and graph values such as f(a)) instead of terms in x.
FORMULA_KEYS = ("formula", "attach_x", "attach_y")
#: Quick actions on a function graph: (key, kind or special action, extra params).
GRAPH_ACTIONS: tuple[tuple[str, str, dict], ...] = (
    ("derivative", "derivative", {}),
    ("antiderivative", "antiderivative", {}),
    ("second_derivative", "second_derivative", {}),
    ("zeros", ObjectKind.GRAPH_MARKERS.value, {"feature": "zeros"}),
    ("extrema", ObjectKind.GRAPH_MARKERS.value, {"feature": "extrema"}),
    ("inflection", ObjectKind.GRAPH_MARKERS.value, {"feature": "inflection"}),
    ("intersections", ObjectKind.GRAPH_MARKERS.value, {"feature": "intersections"}),
    ("tangent", ObjectKind.TANGENT.value, {}),
    ("secant", ObjectKind.SECANT.value, {}),
    ("point", ObjectKind.GRAPH_POINT.value, {}),
    ("area", ObjectKind.GRAPH_AREA.value, {}),
    ("riemann", ObjectKind.RIEMANN.value, {}),
    ("label", ObjectKind.GRAPH_LABEL.value, {}),
    ("value_table", "value_table", {}),
)
#: Icons of the align/distribute buttons in the multi-selection inspector.
ARRANGE_ICONS = tuple(
    zip(
        ALIGN_MODES + DISTRIBUTE_MODES,
        ("align_left", "align_center_h", "align_right", "align_top", "align_center_v", "align_bottom", "distribute_h", "distribute_v"),
    )
)
_DELAY_SPEC = ParamSpec("delay", ParamType.FLOAT, 0.0, minimum=0.0, maximum=600.0, step=0.1)
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
        guarded = not self.widget.property(ALWAYS_REFRESH)
        if guarded and focus is not None and (focus is self.widget or self.widget.isAncestorOf(focus)):
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
        if not edit.hasFocus():
            edit.setCursorPosition(0)  # long names show their beginning, not their end


def _compact_combo() -> QComboBox:
    """A combo box that does not widen the inspector to its longest entry."""
    combo = QComboBox()
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(8)
    return combo


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
        self.layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
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
        # long titles (e.g. "Highlight vertices/edges · Step 12") wrap instead of widening the panel
        label.setWordWrap(True)
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

    arrangeRequested = Signal(str)

    def __init__(
        self,
        document: ProjectDocument,
        editor: EditorState,
        settings: AppSettings,
        latex_status: Callable[[str], str],
        controller: EditorController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.document = document
        self.editor = editor
        self.settings = settings
        self.latex_status = latex_status
        self.controller = controller
        self.hover = PreviewHover(self)
        self.animation_buttons: dict[AnimationKind, QToolButton] = {}
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
        # the selection may still name deleted objects until the editor sanitizes it
        ids = tuple(object_id for object_id in self.editor.selected_objects if scene.object_by_id(object_id))
        if kind == INSPECT_OBJECTS and ids:
            if len(ids) == 1:
                obj = scene.object_by_id(ids[0])
                if obj:
                    recording = self.editor.cursor if is_recording(scene, self.editor.cursor) else -1
                    return ("object", scene.id, obj.id, obj.kind, recording)
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
        self.animation_buttons = {}
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
        combo = _compact_combo()

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
            combo = _compact_combo()
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
        if spec.type == ParamType.FONT:
            picker = FontPicker()
            picker.committed.connect(commit)
            return picker, picker.set_value
        if spec.type in (ParamType.POINTS, ParamType.TABLE, ParamType.WORD_COLORS, ParamType.PIECES, ParamType.DATA, ParamType.BARS):
            editors = {
                ParamType.POINTS: PointsEditor,
                ParamType.TABLE: TableEditor,
                ParamType.WORD_COLORS: WordColorsEditor,
                ParamType.PIECES: PiecesEditor,
                ParamType.DATA: DataEditor,
                ParamType.BARS: BarsEditor,
            }
            grid = editors[spec.type]()
            grid.setProperty(ALWAYS_REFRESH, True)
            grid.committed.connect(commit)
            return grid, grid.set_value
        edit = DebouncedLineEdit()
        if spec.type == ParamType.EXPRESSION:
            edit.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
            if spec.key in ("formula", "attach_x", "attach_y"):
                edit.setPlaceholderText("a^2 / 2")  # only numbers and parameters
            else:
                edit.setPlaceholderText("2x^2 + sin(x)" if spec.variable == "x" else f"2cos({spec.variable})")
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
        defaults = default_params(kind_info(self._object(object_id).kind).params)

        def commit(value: Any) -> None:
            if spec.type == ParamType.FILE:
                value = relative_asset_path(str(value), self.document.base_dir)
            if spec.key == "attach":
                self._edit(label, lambda s: set_attach_mode(s, object_id, str(value)), f"obj:{object_id}:p:{spec.key}")
                return
            self._edit(label, lambda s: ops.set_object_param(s, object_id, spec.key, value), f"obj:{object_id}:p:{spec.key}")

        def visible() -> bool:
            return spec.is_visible(self._object(object_id).params, defaults)

        allowed = graphs.is_function_curve if spec.key in FUNCTION_GRAPH_REFS else (lambda obj: True)
        if spec.key == "attach_target":
            allowed = lambda obj: can_follow(self.editor.scene(), object_id, obj)  # noqa: E731
        if spec.key in OPERAND_KEYS:
            allowed = lambda obj: can_use(self.editor.scene(), object_id, obj)  # noqa: E731
        widget, show = self._param_editor(spec, commit, exclude=lambda: object_id, allowed=allowed)
        form.row(label, widget, lambda: self._object(object_id).params.get(spec.key, spec.default), show)
        if spec.type == ParamType.EXPRESSION:
            form.note(lambda: self._expression_message(object_id, spec) if visible() else "", warning=True)
        if spec.type == ParamType.PIECES:
            form.note(lambda: self._pieces_message(object_id) if visible() else "", warning=True)
        if spec.type == ParamType.LATEX:
            form.note(lambda: self.latex_status(str(self._object(object_id).params.get("latex", ""))), warning=True)
        if spec.visible_when is not None:
            marker = QWidget(form.widget)
            marker.hide()
            form.bindings.append(Binding(marker, visible, lambda value: form.layout.setRowVisible(widget, bool(value))))
            form.bindings[-1].refresh()

    def _attach_note(self, object_id: str) -> str:
        mode = attach_mode(self._object(object_id))
        if mode == ATTACH_FOLLOW:
            return tr("prop.attach_follow_note")
        if mode == ATTACH_FORMULA:
            symbols = ", ".join(graphs.parameter_symbols(self.editor.scene()))
            functions = ", ".join(f"{name}(…)" for name in sorted(graphs.formula_functions(self.editor.scene())))
            return tr("prop.attach_formula_note", symbols=symbols or "–", functions=functions or "–")
        return tr("prop.attach_none_note")

    def _expression_message(self, object_id: str, spec: ParamSpec) -> str:
        scene = self.editor.scene()
        text = str(self._object(object_id).params.get(spec.key, ""))
        if spec.key in FORMULA_KEYS:
            # formulas of parameters may also use values of graphs, e.g. f(a)
            if spec.key == "formula" and not text.strip():
                return ""
            error = graphs.formula_error(scene, text)
        else:
            error = check_expression(text, spec.variable, (*spec.extra_names, *graphs.parameter_symbols(scene)))
        if error is None:
            return ""
        return tr(f"expr.{error.code}", detail=error.detail)

    def _pieces_message(self, object_id: str) -> str:
        scene = self.editor.scene()
        for index, row in enumerate(self._object(object_id).params.get("pieces", []) or [], start=1):
            error = check_expression(str(row[0]) if row else "", "x", graphs.parameter_symbols(scene))
            if error is not None:
                return tr("prop.piece_error", number=index, message=tr(f"expr.{error.code}", detail=error.detail))
        return ""

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
        if kind == ObjectKind.GROUP:
            self._build_group(form, key)
            return
        if kind == ObjectKind.PARAMETER:
            self._build_parameter(form, key)
            return
        info = kind_info(kind)
        form.header(tr(f"kind.{kind.value}"), kind_icon(kind))
        name_edit = DebouncedLineEdit()
        name_edit.committed.connect(
            lambda text: text.strip()
            and self._edit(tr("prop.name"), lambda s: ops.update_object(s, object_id, name=text.strip()), f"obj:{object_id}:name")
        )
        form.row(tr("prop.name"), name_edit, lambda: self._object(object_id).name, lambda v: _set_line(name_edit, v))
        self._animate_section(form, [object_id])
        recording = key[4]
        if recording >= 0:
            self._step_section(form, object_id, recording)
        bound = is_bound(self.editor.scene(), self._object(object_id))
        if not bound and kind not in GRAPH_TOOL_KINDS and kind != ObjectKind.BOOLEAN_SHAPE:
            form.section(tr("section.start_position") if recording >= 0 else tr("section.position"))
            for field, spec in (("x", _POSITION_SPEC), ("y", _POSITION_SPEC), ("rotation", _ROTATION_SPEC)):
                self._object_field_row(form, object_id, field, spec, tr(f"prop.{field}"))
        if kind in LINE_KINDS and recording < 0:
            self._endpoint_rows(form, object_id)
        if kind in ATTACHABLE_KINDS:
            form.section(tr("section.attach"))
            for spec in ATTACH_SPECS:
                self._object_param_row(form, object_id, spec)
            form.note(lambda: self._attach_note(object_id))
        if kind == ObjectKind.FUNCTION_GRAPH:
            self._graph_tools_section(form, object_id)
        if info.params:
            form.section(tr("section.content"))
            if bound:
                form.note(lambda: tr("prop.bound_graph_note"))
            for spec in info.params:
                self._object_param_row(form, object_id, spec)
            form.note(lambda: self._analysis_note(object_id))
        if kind in LABELED_TOOL_KINDS:
            button = QToolButton()
            button.setText(tr("tool_label.add"))
            button.setToolTip(tr("tool_label.add_tip"))
            button.setProperty("variant", "button")
            button.clicked.connect(lambda _checked=False: self.controller.add_tool_label(object_id))
            form.layout.addRow(button)
        if info.style:
            form.section(tr("section.style"))
            form.header_widget(self._style_button([object_id]))
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

    # --- graphs and parameters ------------------------------------------------------------

    def _graph_tools_section(self, form: _Form, object_id: str) -> None:
        form.section(tr("section.graph_tools"))
        obj = self._object(object_id)
        scene = self.editor.scene()
        usable = graphs.is_function_curve(obj) and is_bound(scene, obj)
        others = [o for o in scene.objects if o.id != object_id and graphs.is_function_curve(o) and is_bound(scene, o)]
        container, flow = flow_container(px(4))
        for key, action, params in GRAPH_ACTIONS:
            button = QToolButton()
            button.setText(tr(f"graph_action.{key}"))
            button.setToolTip(tr(f"graph_action.{key}_tip"))
            button.setProperty("variant", "button")
            button.setEnabled(usable and (key != "intersections" or bool(others)))
            if action in ("derivative", "second_derivative"):
                order = 1 if action == "derivative" else 2
                button.clicked.connect(lambda _checked=False, order=order: self.controller.add_derivative(object_id, order))
            elif action == "antiderivative":
                button.clicked.connect(lambda _checked=False: self.controller.add_antiderivative(object_id))
            elif action == "value_table":
                button.clicked.connect(lambda _checked=False: self.controller.add_value_table(object_id))
            else:
                kind = ObjectKind(action)
                button.clicked.connect(lambda _checked=False, kind=kind, params=params: self.controller.add_graph_tool(kind, object_id, **params))
            flow.addWidget(button)
        form.layout.addRow(container)
        if not usable:
            form.note(lambda: tr("prop.graph_tools_need_axes"))

    def _analysis_note(self, object_id: str) -> str:
        """Live results: derivative term, slope, coordinates, found points, area."""
        scene = self.editor.scene()
        obj = self._object(object_id)
        kind = obj.kind
        if kind == ObjectKind.FUNCTION_GRAPH and obj.params.get("curve") == "derivative":
            pieces = graphs.function_pieces(scene, obj)
            if not pieces:
                return tr("prop.derivative_missing")
            return "\n".join(tr("prop.derivative_term", term=piece.expression.source) for piece in pieces)
        if kind == ObjectKind.TANGENT:
            slope = graphs.tangent_slope(scene, obj)
            return tr("prop.tangent_slope", slope=graphs.format_coordinate(slope)) if slope is not None else tr("prop.tool_undefined")
        if kind == ObjectKind.SECANT:
            found = graphs.secant(scene, obj)
            if found is None:
                return tr("prop.tool_undefined")
            key = "prop.secant_tangent" if found.x1 == found.x0 else "prop.secant_slope"
            return tr(key, slope=graphs.format_coordinate(found.slope))
        if kind == ObjectKind.GRAPH_POINT:
            point = graphs.graph_point(scene, obj)
            return tr("prop.point_value", point=graphs.point_label(*point)) if point is not None else tr("prop.tool_undefined")
        if kind == ObjectKind.GRAPH_MARKERS:
            points = graphs.marker_points(scene, obj)
            if not points:
                return tr("prop.markers_none")
            text = ", ".join(graphs.point_label(point.x, point.y) for point in points[:12])
            return tr("prop.markers_found", count=len(points), points=text)
        if kind == ObjectKind.GRAPH_AREA:
            value = graphs.area_value(scene, obj)
            return tr("prop.area_value", value=graphs.format_coordinate(value)) if value is not None else tr("prop.tool_undefined")
        if kind == ObjectKind.RIEMANN:
            value = graphs.riemann_value(scene, obj)
            return tr("prop.riemann_value", value=graphs.format_coordinate(value)) if value is not None else ""
        if kind == ObjectKind.DATA_PLOT and obj.params.get("regression", "none") != "none":
            fit = graphs.data_fit(obj)
            if fit is None:
                return tr("prop.regression_impossible")
            return tr("prop.regression", equation=fit.text(), r2=f"{fit.r_squared:.4f}")
        return ""

    def _build_parameter(self, form: _Form, key: tuple) -> None:
        object_id = key[2]
        form.header(tr("kind.parameter"), kind_icon(ObjectKind.PARAMETER))
        name_edit = DebouncedLineEdit()
        name_edit.committed.connect(lambda text: self.controller.rename_object(object_id, text))
        form.row(tr("prop.name"), name_edit, lambda: self._object(object_id).name, lambda v: _set_line(name_edit, v))
        form.note(lambda: tr("prop.parameter_hint", symbol=graphs.parameter_symbol(self._object(object_id))))
        form.section(tr("section.parameter_value"))
        slider = ParameterSlider(self.editor, self.controller, object_id)
        slider.setProperty(ALWAYS_REFRESH, True)
        form.layout.addRow(slider)
        form.bindings.append(Binding(slider, lambda: None, lambda _value: slider.refresh()))
        form.section(tr("section.content"))
        for spec in kind_info(ObjectKind.PARAMETER).params:
            self._object_param_row(form, object_id, spec)
        form.note(lambda: self._parameter_issue(object_id), warning=True)
        form.note(lambda: self._parameter_users(object_id))

    def _parameter_issue(self, object_id: str) -> str:
        scene = self.editor.scene()
        symbol = graphs.parameter_symbol(self._object(object_id))
        if symbol not in graphs.parameter_symbols(scene):
            return tr("prop.parameter_symbol_invalid", symbol=symbol)
        return ""

    def _parameter_users(self, object_id: str) -> str:
        scene = self.editor.scene()
        users = [obj.name for obj in scene.objects if object_id in graphs.parameter_users(scene, obj)]
        return tr("prop.parameter_users", names=", ".join(users)) if users else tr("prop.parameter_unused")

    # --- animate section ---------------------------------------------------------------

    def _animation_button(self, kind: AnimationKind, object_ids: list[str], simultaneous: QCheckBox) -> QToolButton:
        button = QToolButton()
        button.setIcon(icon(f"a_{kind.value}"))
        button.setIconSize(QSize(px(16), px(16)))
        button.setText(tr(f"anim_short.{kind.value}"))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setProperty("variant", "button")
        allowed = allowed_for_objects(self.editor.scene(), kind, object_ids)
        if kind in REFERENCE_PARAMS:
            allowed = allowed and len(object_ids) == 1
        button.setEnabled(allowed)
        self.hover.attach(button, kind)
        object_id = object_ids[0]
        if kind in REFERENCE_PARAMS:
            menu = QMenu(button)
            menu.aboutToShow.connect(lambda: self._fill_reference_menu(menu, kind, object_id, simultaneous.isChecked()))
            button.setMenu(menu)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        else:
            button.clicked.connect(lambda: self.controller.add_animation(kind, simultaneous.isChecked(), inspect=False))
        return button

    def _fill_reference_menu(self, menu: QMenu, kind: AnimationKind, object_id: str, same_step: bool) -> None:
        menu.clear()
        scene = self.editor.scene()
        key = REFERENCE_PARAMS[kind]
        header = menu.addAction(tr(f"animate.choose_{key}"))
        header.setEnabled(False)
        for obj in reference_candidates(scene, kind, object_id):
            action = menu.addAction(kind_icon(obj.kind), obj.name)
            action.triggered.connect(
                lambda _checked=False, other=obj.id: self.controller.add_reference_animation(kind, object_id, other, same_step, inspect=False)
            )
        if kind not in TRANSFORM_ANIMATIONS:
            if menu.actions() == [header]:
                hint = menu.addAction(tr("animate.no_candidates"))
                hint.setEnabled(False)
            return
        menu.addSeparator()
        new_menu = menu.addMenu(icon("plus"), tr("animate.new_target"))
        for new_kind in TRANSFORM_TARGET_KINDS:
            action = new_menu.addAction(kind_icon(new_kind), tr(f"kind.{new_kind.value}"))
            action.triggered.connect(
                lambda _checked=False, k=new_kind: self.controller.add_transform_to_new(kind, object_id, k, same_step)
            )

    def _animate_section(self, form: _Form, object_ids: list[str]) -> None:
        form.section(tr("section.animate"))
        simultaneous = QCheckBox()
        cursor = self.editor.cursor
        recording = is_recording(self.editor.scene(), cursor)
        simultaneous.setText(tr("animate.simultaneous", step=cursor + 1))
        simultaneous.setVisible(recording)
        simultaneous.setToolTip(tr("animate.simultaneous_tip"))
        box = QWidget()
        column = QVBoxLayout(box)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(px(4))
        for group, kinds in ANIMATION_GROUPS:
            caption = QLabel(tr(f"animgroup.{group}"))
            caption.setProperty("role", "faint")
            column.addWidget(caption)
            container, flow = flow_container(px(4))
            for kind in kinds:
                if kind in ONLY_WHEN_ALLOWED and not allowed_for_objects(self.editor.scene(), kind, object_ids):
                    continue
                button = self._animation_button(kind, object_ids, simultaneous)
                self.animation_buttons[kind] = button
                flow.addWidget(button)
            column.addWidget(container)
        column.addWidget(simultaneous)
        hint = QLabel(tr("animate.hint_recording", step=cursor + 1) if recording else tr("animate.hint_new_step"))
        hint.setWordWrap(True)
        hint.setProperty("role", "muted")
        column.addWidget(hint)
        form.layout.addRow(box)

    # --- values recorded in the current step ----------------------------------------------

    def _step_section(self, form: _Form, object_id: str, cursor: int) -> None:
        form.section(tr("section.in_step", step=cursor + 1))
        note = QLabel(tr("prop.in_step_note", step=cursor + 1))
        note.setWordWrap(True)
        note.setProperty("role", "hint")
        form.layout.addRow(note)
        scene_state = lambda: states_after(self.editor.scene(), self.editor.cursor)[object_id]  # noqa: E731
        bound = is_bound(self.editor.scene(), self._object(object_id))
        for axis in ("x", "y"):
            def commit(value: Any, axis: str = axis) -> None:
                state = scene_state()
                x, y = (value, state.y) if axis == "x" else (state.x, value)
                self.controller.set_step_value(object_id, MOVE, x, y, merge_key=f"step:{object_id}:move")

            widget, show = self._float_editor(_POSITION_SPEC, commit)
            # a coupled object is placed by its updater, a bound graph by its axes
            widget.setEnabled(not bound and not is_attached(self._object(object_id)))
            form.row(tr(f"prop.target_{axis}"), widget, lambda axis=axis: getattr(scene_state(), axis), show)

        def angle() -> float:
            anim = step_animation(self.editor.scene(), self.editor.cursor, object_id, ROTATE)
            return float(anim.params.get("angle", 0.0)) if anim else 0.0

        def factor() -> float:
            anim = step_animation(self.editor.scene(), self.editor.cursor, object_id, SCALE)
            return float(anim.params.get("factor", 1.0)) if anim else 1.0

        rotate_spec = ParamSpec("angle", ParamType.FLOAT, 0.0, minimum=-3600.0, maximum=3600.0, step=15.0, decimals=1)
        widget, show = self._float_editor(rotate_spec, lambda v: self.controller.set_step_value(object_id, ROTATE, v, merge_key=f"step:{object_id}:rot"))
        widget.setEnabled(not bound)
        form.row(tr("prop.rotate_by"), widget, angle, show)
        scale_spec = ParamSpec("factor", ParamType.FLOAT, 1.0, minimum=0.01, maximum=100.0, step=0.1)
        widget, show = self._float_editor(scale_spec, lambda v: self.controller.set_step_value(object_id, SCALE, v, merge_key=f"step:{object_id}:scale"))
        widget.setEnabled(not bound)
        form.row(tr("prop.scale_by"), widget, factor, show)
        style = kind_info(self._object(object_id).kind).style
        for field in ("stroke_color", "fill_color"):
            if field not in style:
                continue
            button = ColorButton()
            button.colorChosen.connect(lambda color, field=field: self.controller.set_step_value(object_id, COLOR, field, color))
            form.row(tr(f"prop.{field}"), button, lambda field=field: getattr(scene_state(), field), lambda v, b=button: b.set_color(str(v)))

    # --- several objects -----------------------------------------------------------------

    def _build_multi(self, form: _Form, key: tuple) -> None:
        ids = list(key[2])
        form.header(tr("prop.multi_header", count=len(ids)), icon("group"))
        form.header_widget(self._arrange_bar(len(ids)))
        self._animate_section(form, ids)
        self._selection_position_rows(form, ids, tr("section.position"))
        objects = [self._object(object_id) for object_id in ids]
        style_fields = [f for f in STYLE_FIELDS if any(f in kind_info(obj.kind).style for obj in objects)]
        if style_fields:
            form.section(tr("section.style"))
            form.header_widget(self._style_button(ids))
            for field in style_fields:
                self._multi_field_row(form, ids, field, _STYLE_SPECS[field], tr(f"prop.{field}"))
        shared = self._shared_params(objects)
        if shared:
            form.section(tr("section.shared_content"))
            for spec in shared:
                self._multi_param_row(form, ids, spec)
        form.section(tr("section.layer"))
        layer = ParamSpec("z_index", ParamType.INT, 0, minimum=-100, maximum=100)
        self._multi_field_row(form, ids, "z_index", layer, tr("prop.z_index"))
        form.note(lambda: tr("prop.multi_note"))

    def _style_button(self, ids: list[str]) -> QToolButton:
        button = QToolButton()
        button.setText(tr("menu.styles"))
        button.setIcon(icon("a_change_color"))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setProperty("variant", "button")
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(button)
        menu.aboutToShow.connect(lambda: fill_style_menu(menu, self.controller, self.controller.library, ids[0] if len(ids) == 1 else ""))
        button.setMenu(menu)
        return button

    def _arrange_bar(self, count: int) -> QWidget:
        bar, row = flow_container(px(1))
        entries = [("group", "group", None)] + [(mode, icon_name, mode) for mode, icon_name in ARRANGE_ICONS]
        for name, icon_name, mode in entries:
            button = QToolButton()
            button.setIcon(icon(icon_name))
            button.setIconSize(QSize(px(18), px(18)))
            button.setToolTip(tr(f"action.{name}") if mode is None else tr(f"action.arrange.{mode}"))
            if mode is None:
                button.clicked.connect(self.controller.group_selection)
            else:
                button.setEnabled(count >= (3 if mode in DISTRIBUTE_MODES else 1))
                button.clicked.connect(lambda _checked=False, m=mode: self.arrangeRequested.emit(m))
            row.addWidget(button)
        return bar

    def _selection_bounds(self, ids: list[str]) -> tuple[float, float, float, float]:
        scene = self.editor.scene()
        leaves = [leaf for object_id in ids for leaf in groups.leaves(scene, object_id)]
        return groups.bounds_of(scene, leaves, states_after(scene, self.editor.cursor))

    def _selection_position_rows(self, form: _Form, ids: list[str], title: str) -> None:
        """Center of several objects (or a group); editing moves all of them."""
        form.section(title)
        for axis in ("x", "y"):
            def read(axis: str = axis) -> float:
                left, bottom, right, top = self._selection_bounds(ids)
                return round((left + right) / 2 if axis == "x" else (bottom + top) / 2, 3)

            def commit(value: Any, axis: str = axis, read=read) -> None:
                delta = float(value) - read()
                if abs(delta) > 1e-9:
                    dx, dy = (delta, 0.0) if axis == "x" else (0.0, delta)
                    self.controller.move_objects(ids, dx, dy)

            widget, show = self._float_editor(_POSITION_SPEC, commit)
            form.row(tr(f"prop.center_{axis}"), widget, read, show)

    def _multi_field_row(self, form: _Form, ids: list[str], field: str, spec: ParamSpec, label: str) -> None:
        def applies(obj: SceneObject) -> bool:
            return field == "z_index" or field in kind_info(obj.kind).style

        def commit(value: Any) -> None:
            def mutate(scene) -> None:
                for object_id in ids:
                    obj = scene.object_by_id(object_id)
                    if obj is not None and applies(obj):
                        setattr(obj, field, value)

            self._edit(label, mutate, f"multi:{','.join(ids)}:{field}")

        def read() -> Any:
            first = next(obj for obj in (self._object(i) for i in ids) if applies(obj))
            return getattr(first, field)

        widget, show = self._param_editor(spec, commit)
        form.row(label, widget, read, show)

    @staticmethod
    def _shared_params(objects: list[SceneObject]) -> list[ParamSpec]:
        """Parameters that all objects have (same key and type) and that make sense in bulk."""
        bulk_types = {ParamType.FLOAT, ParamType.INT, ParamType.BOOL, ParamType.CHOICE, ParamType.COLOR, ParamType.FONT}
        first, *rest = objects
        shared = []
        for spec in kind_info(first.kind).params:
            if spec.type not in bulk_types:
                continue
            if all((other := kind_info(obj.kind).param(spec.key)) is not None and other.type == spec.type for obj in rest):
                shared.append(spec)
        return shared

    def _multi_param_row(self, form: _Form, ids: list[str], spec: ParamSpec) -> None:
        label = tr(f"param.{spec.key}")

        def commit(value: Any) -> None:
            def mutate(scene) -> None:
                for object_id in ids:
                    ops.set_object_param(scene, object_id, spec.key, value)

            self._edit(label, mutate, f"multi:{','.join(ids)}:p:{spec.key}")

        widget, show = self._param_editor(spec, commit)
        form.row(label, widget, lambda: self._object(ids[0]).params.get(spec.key, spec.default), show)

    # --- groups ------------------------------------------------------------------------------

    def _build_group(self, form: _Form, key: tuple) -> None:
        group_id = key[2]
        form.header(tr("kind.group"), kind_icon(ObjectKind.GROUP))
        name_edit = DebouncedLineEdit()
        name_edit.committed.connect(lambda text: self.controller.rename_object(group_id, text))
        form.row(tr("prop.name"), name_edit, lambda: self._object(group_id).name, lambda v: _set_line(name_edit, v))
        self._animate_section(form, [group_id])
        recording = key[4]
        if recording >= 0:
            self._step_section(form, group_id, recording)
        self._selection_position_rows(form, [group_id], tr("section.start_position") if recording >= 0 else tr("section.position"))
        form.section(tr("section.members"))
        form.note(lambda: self._member_summary(group_id))
        ungroup = QToolButton()
        ungroup.setIcon(icon("ungroup"))
        ungroup.setText(tr("action.ungroup"))
        ungroup.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        ungroup.setProperty("variant", "button")
        ungroup.clicked.connect(self.controller.ungroup_selection)
        form.layout.addRow(ungroup)
        leaves = groups.leaves(self.editor.scene(), group_id)
        objects = [self._object(leaf) for leaf in leaves]
        style_fields = [f for f in ("stroke_color", "fill_color", "fill_opacity") if any(f in kind_info(o.kind).style for o in objects)]
        if style_fields:
            form.section(tr("section.group_style"))
            for field in style_fields:
                self._multi_field_row(form, leaves, field, _STYLE_SPECS[field], tr(f"prop.{field}"))
        form.note(lambda: tr("prop.group_hint"))

    def _member_summary(self, group_id: str) -> str:
        scene = self.editor.scene()
        lines = []
        for member in groups.members(scene, group_id):
            obj = scene.object_by_id(member)
            if obj is not None:
                lines.append(f"• {obj.name} ({tr(f'kind.{obj.kind.value}')})")
        return "\n".join(lines)

    # --- line endpoints ----------------------------------------------------------------------

    def _endpoint_rows(self, form: _Form, object_id: str) -> None:
        for which, prefix in ((0, "start"), (1, "end")):
            for axis in ("x", "y"):
                def read(which: int = which, axis: str = axis) -> float:
                    point = ops.line_endpoints(self._object(object_id))[which]
                    return round(point[0] if axis == "x" else point[1], 3)

                def commit(value: Any, which: int = which, axis: str = axis) -> None:
                    x, y = ops.line_endpoints(self._object(object_id))[which]
                    x, y = (float(value), y) if axis == "x" else (x, float(value))
                    self.controller.set_line_endpoint(object_id, which, x, y)

                widget, show = self._float_editor(_POSITION_SPEC, commit)
                form.row(tr(f"prop.{prefix}_{axis}"), widget, read, show)

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
        step_mode = found[0].mode if found else STEP_TOGETHER

        def commit_delay(value: Any) -> None:
            self._edit(tr("prop.delay"), lambda s: ops.set_animation_timing(s, animation_id, delay=value), f"anim:{animation_id}:delay")

        widget, show = self._float_editor(_DELAY_SPEC, commit_delay)
        widget.setEnabled(step_mode != STEP_LAGGED)
        widget.setToolTip(tr("prop.delay_tip") if step_mode != STEP_LAGGED else tr("prop.delay_lagged"))
        form.row(tr("prop.delay"), widget, lambda: self._animation(animation_id).delay, show)
        rate = _compact_combo()
        rate.setIconSize(QSize(px(34), px(18)))
        for name in RATE_FUNCTIONS:
            rate.addItem(rate_icon(name), tr(f"rate.{name}"), name)
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
        if kind == StepKind.CODE:
            self._build_code_step(form, step_id, number)
            self._step_details(form, step_id)
            return
        if kind == StepKind.WAIT:
            form.header(tr("prop.wait_header", step=number), icon("clock"))
            spec = ParamSpec("wait_time", ParamType.FLOAT, 1.0, minimum=0.05, maximum=600.0, step=0.25)

            def commit(value: Any) -> None:
                self._edit(tr("prop.wait_time"), lambda s: ops.set_wait_time(s, step_id, value), f"step:{step_id}:wait")

            widget, show = self._float_editor(spec, commit)
            form.row(tr("prop.wait_time"), widget, lambda: self._step(step_id).wait_time, show)
            self._step_details(form, step_id)
            return
        form.header(tr("prop.step_header", step=number), icon("layers"))
        mode_spec = ParamSpec("mode", ParamType.CHOICE, STEP_TOGETHER, choices=STEP_MODES)

        def commit_mode(value: Any) -> None:
            self._edit(tr("undo.step_mode"), lambda s: ops.set_step_mode(s, step_id, str(value)), None)

        widget, show = self._param_editor(mode_spec, commit_mode)
        form.row(tr("timeline.mode"), widget, lambda: self._step(step_id).mode, show)
        lag_spec = ParamSpec("lag_ratio", ParamType.FLOAT, 0.25, minimum=0.0, maximum=1.0, step=0.05)

        def commit_lag(value: Any) -> None:
            step = self._step(step_id)
            self._edit(tr("undo.step_mode"), lambda s: ops.set_step_mode(s, step_id, step.mode, value), f"step:{step_id}:lag")

        lag_widget, lag_show = self._float_editor(lag_spec, commit_lag)

        def show_lag(value: Any) -> None:
            lag_show(value)
            form.layout.setRowVisible(lag_widget, self._step(step_id).mode == STEP_LAGGED)

        form.row(tr("prop.lag_ratio"), lag_widget, lambda: self._step(step_id).lag_ratio, show_lag)
        form.note(lambda: tr(f"step_mode_help.{self._step(step_id).mode}"))
        form.note(lambda: self._step_summary(step_id))
        form.note(lambda: tr("prop.step_hint"))
        self._step_details(form, step_id)

    def _build_code_step(self, form: _Form, step_id: str, number: int) -> None:
        form.header(tr("prop.code_header", step=number), icon("code"))
        form.note(lambda: tr("prop.code_hint"))
        editor = DebouncedTextEdit()
        editor.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        editor.setMinimumHeight(px(200))
        editor.setLineWrapMode(DebouncedTextEdit.LineWrapMode.NoWrap)
        editor.committed.connect(lambda text: self.controller.set_step_fields(step_id, f"step:{step_id}:code", code=text))
        form.layout.addRow(editor)
        form.bindings.append(Binding(editor, lambda: self._step(step_id).code, lambda v: editor.set_text_silently(str(v))))
        form.bindings[-1].refresh()
        form.note(lambda: self._code_message(step_id), warning=True)
        spec = ParamSpec("wait_time", ParamType.FLOAT, 1.0, minimum=0.05, maximum=600.0, step=0.25)
        widget, show = self._float_editor(spec, lambda value: self.controller.set_step_fields(step_id, f"step:{step_id}:wait", wait_time=value))
        form.row(tr("prop.code_duration"), widget, lambda: self._step(step_id).wait_time, show)
        form.note(lambda: tr("prop.code_names", names=", ".join(variable_names(self.editor.scene()).values()) or "–"))

    def _code_message(self, step_id: str) -> str:
        import textwrap

        try:
            compile(textwrap.dedent(self._step(step_id).code), "code", "exec")
        except SyntaxError as error:
            return tr("prop.code_error", line=error.lineno or 0, message=error.msg)
        return ""

    def _step_details(self, form: _Form, step_id: str) -> None:
        """Section start, subtitle and sound of a step."""
        form.section(tr("section.step_details"))
        for key, placeholder in (("section", "prop.section_placeholder"), ("subcaption", "prop.subcaption_placeholder")):
            edit = DebouncedLineEdit()
            edit.setPlaceholderText(tr(placeholder))
            edit.committed.connect(lambda text, key=key: self.controller.set_step_fields(step_id, f"step:{step_id}:{key}", **{key: text}))
            form.row(tr(f"prop.step_{key}"), edit, lambda key=key: getattr(self._step(step_id), key), lambda v, e=edit: _set_line(e, v))
        sound = FileField(tr("dialog.sound_filter"), lambda: self.settings.last_directory("sound"))
        sound.committed.connect(
            lambda path: self.controller.set_step_fields(
                step_id, None, sound=relative_asset_path(path, self.document.base_dir) if path.strip() else ""
            )
        )
        form.row(tr("prop.step_sound"), sound, lambda: self._step(step_id).sound, lambda v: sound.set_path(str(v)))
        for key, spec in (
            ("sound_gain", ParamSpec("sound_gain", ParamType.FLOAT, 0.0, minimum=-60.0, maximum=30.0, step=1.0, decimals=1)),
            ("sound_offset", ParamSpec("sound_offset", ParamType.FLOAT, 0.0, minimum=0.0, maximum=600.0, step=0.1)),
        ):
            widget, show = self._float_editor(spec, lambda value, key=key: self.controller.set_step_fields(step_id, f"step:{step_id}:{key}", **{key: value}))
            form.row(tr(f"prop.step_{key}"), widget, lambda key=key: getattr(self._step(step_id), key), show)
        form.note(lambda: tr("prop.step_details_hint"))

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
        aspect = _compact_combo()
        for key in ASPECTS:
            aspect.addItem(tr(f"aspect.{key}"), key)
        aspect.currentIndexChanged.connect(
            lambda _index: self.document.edit_project(tr("undo.aspect"), lambda p: setattr(p, "aspect", aspect.currentData()), None)
        )
        form.row(tr("prop.aspect"), aspect, lambda: self.document.project.aspect, lambda v: _set_combo_data(aspect, v))
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
