"""Timeline: a row of step cards plus the animations of the selected step."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from manim_studio.i18n import tr
from manim_studio.model.entities import Scene, Step
from manim_studio.model.state import START
from manim_studio.model.types import AnimationKind, StepKind
from manim_studio.ui.controller import EditorController
from manim_studio.ui.document import ProjectDocument
from manim_studio.ui.icon_set import icon
from manim_studio.ui.theme import color as theme_color
from manim_studio.ui.theme import px
from manim_studio.ui.editor_state import INSPECT_ANIMATION, EditorState

ID_ROLE = Qt.ItemDataRole.UserRole
TITLE_ROLE = Qt.ItemDataRole.UserRole + 1
LINES_ROLE = Qt.ItemDataRole.UserRole + 2
KIND_ROLE = Qt.ItemDataRole.UserRole + 3
DURATION_ROLE = Qt.ItemDataRole.UserRole + 4

CARD_SIZE = QSize(178, 100)
MAX_CARD_LINES = 3
def _kind_color(kind: str) -> QColor:
    names = {"start": "text_faint", "play": "accent", "wait": "warning"}
    return theme_color(names.get(kind, "accent"))

#: Order of animations in the menus.
ANIMATION_MENU = (
    (AnimationKind.CREATE, AnimationKind.WRITE, AnimationKind.DRAW_BORDER_THEN_FILL, AnimationKind.FADE_IN, AnimationKind.GROW_FROM_CENTER),
    (AnimationKind.TRANSFORM, AnimationKind.REPLACEMENT_TRANSFORM),
    (AnimationKind.MOVE, AnimationKind.SCALE, AnimationKind.ROTATE, AnimationKind.CHANGE_COLOR),
    (AnimationKind.INDICATE, AnimationKind.CIRCUMSCRIBE),
    (AnimationKind.FADE_OUT, AnimationKind.UNCREATE),
)


def build_animation_menu(menu: QMenu, controller: EditorController, same_step: bool) -> None:
    """Fill ``menu`` with all animations; unsuitable ones are disabled."""
    menu.clear()
    for group_index, group in enumerate(ANIMATION_MENU):
        if group_index:
            menu.addSeparator()
        for kind in group:
            action = menu.addAction(tr(f"anim.{kind.value}"))
            action.setToolTip(tr(f"anim_help.{kind.value}"))
            action.setEnabled(controller.animation_allowed(kind))
            action.triggered.connect(lambda _checked=False, k=kind: controller.add_animation(k, same_step))
    if not controller.editor.selected_objects:
        menu.addSeparator()
        hint = menu.addAction(tr("status.select_object_first"))
        hint.setEnabled(False)


class StepCardDelegate(QStyledItemDelegate):
    """Paints a step as a rounded card."""

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802 - Qt API
        return CARD_SIZE

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(option.rect).adjusted(4, 4, -4, -4)
        palette = option.palette
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        accent = _kind_color(index.data(KIND_ROLE))
        painter.setPen(QPen(theme_color("accent") if selected else theme_color("border_strong"), 2.0 if selected else 1.0))
        painter.setBrush(theme_color("raised"))
        painter.drawRoundedRect(rect, 7, 7)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawRoundedRect(QRectF(rect.left(), rect.top(), 5, rect.height()), 2, 2)
        text_rect = rect.adjusted(12, 6, -8, -6)
        title_font = QFont(option.font)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(palette.text().color())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, index.data(TITLE_ROLE) or "")
        painter.setFont(option.font)
        painter.setPen(palette.placeholderText().color())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, index.data(DURATION_ROLE) or "")
        line_height = painter.fontMetrics().height()
        painter.setPen(palette.text().color())
        for number, line in enumerate(index.data(LINES_ROLE) or []):
            line_rect = QRectF(text_rect.left(), text_rect.top() + line_height * (number + 1.3), text_rect.width(), line_height)
            elided = painter.fontMetrics().elidedText(line, Qt.TextElideMode.ElideRight, int(line_rect.width()))
            painter.drawText(line_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)
        painter.restore()


class StepList(QListWidget):
    """Horizontal list of step cards; emits the new order after drag and drop."""

    reordered = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(False)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setItemDelegate(StepCardDelegate(self))
        self.setFixedHeight(CARD_SIZE.height() + 24)

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().dropEvent(event)
        ids = [self.item(row).data(ID_ROLE) for row in range(self.count())]
        self.reordered.emit([step_id for step_id in ids if step_id])


def _format_seconds(seconds: float) -> str:
    return tr("timeline.seconds", seconds=f"{seconds:.1f}")


def _animation_line(scene: Scene, anim) -> str:
    target = scene.object_by_id(anim.target_id)
    return f"{tr(f'anim.{anim.kind.value}')} · {target.name if target else '?'}"


class TimelinePanel(QWidget):
    """The bottom panel with steps and animations."""

    def __init__(self, document: ProjectDocument, editor: EditorState, controller: EditorController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.document = document
        self.editor = editor
        self.controller = controller
        self._updating = False
        self.steps = StepList()
        self.steps.itemSelectionChanged.connect(self._on_step_selected)
        self.steps.reordered.connect(self._on_reordered)
        self.animations = QListWidget()
        self.animations.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.animations.itemClicked.connect(self._on_animation_clicked)
        self.animations.currentItemChanged.connect(lambda current, _old: self._on_animation_clicked(current))
        self.view_label = QLabel()
        self._build_layout()
        document.changed.connect(self.refresh)
        editor.sceneChanged.connect(self.refresh)
        editor.cursorChanged.connect(self.refresh)
        editor.inspectorChanged.connect(self._sync_animation_selection)
        self.refresh()

    # --- layout ----------------------------------------------------------------

    def _tool_button(self, text: str, tooltip: str, slot=None, menu: QMenu | None = None, icon_name: str = "") -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setToolTip(tooltip)
        if icon_name:
            button.setIcon(icon(icon_name))
            button.setIconSize(QSize(px(16), px(16)))
        style = Qt.ToolButtonStyle.ToolButtonTextBesideIcon if text and icon_name else (
            Qt.ToolButtonStyle.ToolButtonIconOnly if icon_name else Qt.ToolButtonStyle.ToolButtonTextOnly
        )
        button.setToolButtonStyle(style)
        if slot is not None:
            button.clicked.connect(slot)
        if menu is not None:
            button.setMenu(menu)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        return button

    def _animation_menu(self, same_step: bool) -> QMenu:
        menu = QMenu(self)
        menu.aboutToShow.connect(lambda: build_animation_menu(menu, self.controller, same_step))
        return menu

    def _build_layout(self) -> None:
        toolbar = QHBoxLayout()
        toolbar.addWidget(self._tool_button(tr("timeline.add_animation"), tr("timeline.add_animation_tip"), menu=self._animation_menu(False), icon_name="sparkle"))
        toolbar.addWidget(self._tool_button(tr("timeline.add_step"), tr("timeline.add_step_tip"), lambda: self.controller.add_step(StepKind.PLAY), icon_name="plus"))
        toolbar.addWidget(self._tool_button(tr("timeline.add_wait"), tr("timeline.add_wait_tip"), lambda: self.controller.add_step(StepKind.WAIT), icon_name="clock"))
        toolbar.addWidget(self._tool_button(tr("timeline.duplicate"), tr("timeline.duplicate_tip"), self.controller.duplicate_step, icon_name="duplicate"))
        toolbar.addWidget(self._tool_button(tr("timeline.delete"), tr("timeline.delete_tip"), self.controller.delete_step, icon_name="trash"))
        toolbar.addSpacing(16)
        toolbar.addWidget(self.view_label)
        toolbar.addStretch(1)
        animation_header = QHBoxLayout()
        self.animation_title = QLabel()
        animation_header.addWidget(self.animation_title, 1)
        animation_header.addWidget(self._tool_button("", tr("timeline.add_simultaneous_tip"), menu=self._animation_menu(True), icon_name="plus"))
        animation_header.addWidget(self._tool_button("", tr("timeline.remove_animation_tip"), self._remove_animation, icon_name="minus"))
        animation_box = QVBoxLayout()
        animation_box.setContentsMargins(0, 0, 0, 0)
        animation_box.addLayout(animation_header)
        animation_box.addWidget(self.animations)
        animation_widget = QWidget()
        animation_widget.setLayout(animation_box)
        animation_widget.setFixedWidth(300)
        animation_widget.setFixedHeight(self.steps.height())
        body = QHBoxLayout()
        body.addWidget(self.steps, 1)
        body.addWidget(animation_widget)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.addLayout(toolbar)
        layout.addLayout(body)

    # --- refresh -------------------------------------------------------------------

    def _card(self, step_id: str, title: str, kind: str, lines: list[str], duration: str, draggable: bool) -> QListWidgetItem:
        item = QListWidgetItem()
        item.setData(ID_ROLE, step_id)
        item.setData(TITLE_ROLE, title)
        item.setData(KIND_ROLE, kind)
        item.setData(LINES_ROLE, lines)
        item.setData(DURATION_ROLE, duration)
        item.setSizeHint(CARD_SIZE)
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if draggable:
            flags |= Qt.ItemFlag.ItemIsDragEnabled
        item.setFlags(flags)
        return item

    def _step_card(self, scene: Scene, number: int, step: Step) -> QListWidgetItem:
        if step.kind == StepKind.WAIT:
            return self._card(step.id, tr("timeline.wait_title", step=number), "wait", [tr("timeline.wait_line")], _format_seconds(step.wait_time), True)
        lines = [_animation_line(scene, anim) for anim in step.animations[:MAX_CARD_LINES]]
        if len(step.animations) > MAX_CARD_LINES:
            lines[-1] = tr("timeline.more", count=len(step.animations) - MAX_CARD_LINES + 1)
        if not lines:
            lines = [tr("timeline.empty_step")]
        return self._card(step.id, tr("timeline.step_title", step=number), "play", lines, _format_seconds(step.duration()), True)

    def refresh(self) -> None:
        """Rebuild cards and the animation list from the model."""
        self._updating = True
        scene = self.editor.scene()
        scroll = self.steps.horizontalScrollBar().value()
        self.steps.clear()
        total = sum(step.duration() for step in scene.steps)
        self.steps.addItem(self._card("", tr("timeline.start_title"), "start", [tr("timeline.start_line")], _format_seconds(total), False))
        for number, step in enumerate(scene.steps, start=1):
            self.steps.addItem(self._step_card(scene, number, step))
        self.steps.setCurrentRow(self.editor.cursor + 1)
        self.steps.horizontalScrollBar().setValue(scroll)
        self.steps.scrollToItem(self.steps.item(self.editor.cursor + 1))
        self._refresh_animations(scene)
        self._refresh_view_label()
        self._updating = False

    def _refresh_view_label(self) -> None:
        cursor = self.editor.cursor
        text = tr("timeline.view_start") if cursor == START else tr("timeline.view_step", step=cursor + 1)
        self.view_label.setText(text)

    def _refresh_animations(self, scene: Scene) -> None:
        self.animations.clear()
        cursor = self.editor.cursor
        step = scene.steps[cursor] if 0 <= cursor < len(scene.steps) else None
        if step is None:
            self.animation_title.setText(tr("timeline.animations_start"))
            return
        if step.kind == StepKind.WAIT:
            self.animation_title.setText(tr("timeline.animations_wait"))
            return
        self.animation_title.setText(tr("timeline.animations_of", step=cursor + 1))
        for anim in step.animations:
            item = QListWidgetItem(f"{_animation_line(scene, anim)}  ({anim.run_time:g} s)")
            item.setData(ID_ROLE, anim.id)
            self.animations.addItem(item)
        self._sync_animation_selection()

    def _sync_animation_selection(self) -> None:
        kind, entity_id = self.editor.inspected
        self.animations.blockSignals(True)
        self.animations.clearSelection()
        for row in range(self.animations.count()):
            item = self.animations.item(row)
            if kind == INSPECT_ANIMATION and item.data(ID_ROLE) == entity_id:
                item.setSelected(True)
                self.animations.setCurrentItem(item)
        self.animations.blockSignals(False)

    # --- interaction ------------------------------------------------------------------

    def _on_step_selected(self) -> None:
        if self._updating:
            return
        row = self.steps.currentRow()
        if row >= 0:
            self.editor.inspect_step(row - 1)

    def _on_reordered(self, ids: list[str]) -> None:
        if not self._updating:
            self.controller.reorder_steps(ids)
        self.refresh()

    def _on_animation_clicked(self, item: QListWidgetItem | None) -> None:
        if item is not None and not self._updating:
            self.editor.inspect_animation(item.data(ID_ROLE))

    def _remove_animation(self) -> None:
        item = self.animations.currentItem()
        if item is not None:
            self.controller.delete_animation(item.data(ID_ROLE))
