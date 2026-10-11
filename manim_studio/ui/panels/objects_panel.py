"""Layer tree of the active scene: groups, visibility, locking, renaming and order."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QDropEvent, QFont, QMouseEvent, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from manim_studio.i18n import tr
from manim_studio.model import groups
from manim_studio.model.arrange import drawing_order, layer_key
from manim_studio.model.entities import Scene
from manim_studio.model.state import states_after
from manim_studio.ui.controller import EditorController
from manim_studio.ui.document import ProjectDocument
from manim_studio.ui.editor_state import EditorState
from manim_studio.ui.icon_set import icon
from manim_studio.ui.icons import kind_icon
from manim_studio.ui.theme import current_palette, px

ID_ROLE = Qt.ItemDataRole.UserRole
COLUMN_NAME = 0
COLUMN_HIDDEN = 1
COLUMN_LOCKED = 2
TOGGLE_WIDTH = 26


class _ToggleDelegate(QStyledItemDelegate):
    """Paints the eye/lock columns: faint when off, highlighted when active."""

    def __init__(self, on_icon: str, off_icon: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.on_icon = icon(on_icon)
        self.off_icon = icon(off_icon)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        widget = option.widget
        style = widget.style() if widget is not None else None
        if style is not None:
            style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, widget)
        active = bool(index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked.value)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if not active and not hovered:
            return
        side = px(15)
        rect = QRect(option.rect.center().x() - side // 2, option.rect.center().y() - side // 2, side, side)
        painter.save()
        painter.setOpacity(1.0 if active else 0.45)
        (self.on_icon if active else self.off_icon).paint(painter, rect)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802 - Qt API
        return QSize(px(TOGGLE_WIDTH), px(24))


class ObjectsPanel(QTreeWidget):
    """Shows the objects front to back, mirrors the stage selection and edits layers."""

    contextMenuRequested = Signal(QPoint, str)

    def __init__(
        self, document: ProjectDocument, editor: EditorState, controller: EditorController, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.document = document
        self.editor = editor
        self.controller = controller
        self._updating = False
        self.setObjectName("LayerTree")
        self.setColumnCount(3)
        self.setHeaderHidden(True)
        self.setIndentation(px(14))
        self.setUniformRowHeights(True)
        self.setMouseTracking(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.EditKeyPressed | QAbstractItemView.EditTrigger.DoubleClicked)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header = self.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(COLUMN_NAME, header.ResizeMode.Stretch)
        for column in (COLUMN_HIDDEN, COLUMN_LOCKED):
            header.setSectionResizeMode(column, header.ResizeMode.Fixed)
            header.resizeSection(column, px(TOGGLE_WIDTH))
        self.setItemDelegateForColumn(COLUMN_HIDDEN, _ToggleDelegate("eye_off", "eye", self))
        self.setItemDelegateForColumn(COLUMN_LOCKED, _ToggleDelegate("lock", "unlock", self))
        self.customContextMenuRequested.connect(self._on_context_menu)
        self.itemSelectionChanged.connect(self._on_selection)
        self.itemChanged.connect(self._on_item_changed)
        document.changed.connect(self.refresh)
        editor.sceneChanged.connect(self.refresh)
        editor.cursorChanged.connect(self.refresh)
        editor.selectionChanged.connect(self._sync_selection)
        self.refresh()

    # --- building -----------------------------------------------------------------

    def _sorted(self, scene: Scene, ids: list[str], order: list[str]) -> list[str]:
        return sorted(ids, key=lambda object_id: layer_key(scene, object_id, order), reverse=True)

    def refresh(self) -> None:
        """Rebuild the tree from the model (keeps expanded groups)."""
        if self.state() == QAbstractItemView.State.EditingState:
            return
        expanded = {item.data(COLUMN_NAME, ID_ROLE) for item in self._all_items() if item.isExpanded()}
        self._updating = True
        scene = self.editor.scene()
        states = states_after(scene, self.editor.cursor)
        order = drawing_order(scene)
        self.clear()
        top = [obj.id for obj in scene.objects if groups.parent_group(scene, obj.id) is None]
        for object_id in self._sorted(scene, top, order):
            self.addTopLevelItem(self._make_item(scene, object_id, states, order, expanded))
        self._updating = False
        self._sync_selection()

    def _make_item(self, scene: Scene, object_id: str, states, order: list[str], expanded: set[str]) -> QTreeWidgetItem:
        obj = scene.object_by_id(object_id)
        assert obj is not None
        item = QTreeWidgetItem()
        item.setData(COLUMN_NAME, ID_ROLE, obj.id)
        item.setIcon(COLUMN_NAME, kind_icon(obj.kind, 20))
        item.setText(COLUMN_NAME, obj.name)
        flags = (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEditable
            | Qt.ItemFlag.ItemIsDragEnabled
            | Qt.ItemFlag.ItemIsDropEnabled
        )
        item.setFlags(flags)
        item.setCheckState(COLUMN_HIDDEN, Qt.CheckState.Checked if obj.editor_hidden else Qt.CheckState.Unchecked)
        item.setCheckState(COLUMN_LOCKED, Qt.CheckState.Checked if obj.locked else Qt.CheckState.Unchecked)
        item.setToolTip(COLUMN_HIDDEN, tr("objects.toggle_hidden"))
        item.setToolTip(COLUMN_LOCKED, tr("objects.toggle_locked"))
        kind = tr(f"kind.{obj.kind.value}")
        item.setToolTip(COLUMN_NAME, tr("objects.tooltip", kind=kind, layer=obj.z_index))
        state = states.get(obj.id)
        if groups.is_group(obj):
            for member in self._sorted(scene, groups.members(scene, obj.id), order):
                item.addChild(self._make_item(scene, member, states, order, expanded))
            item.setExpanded(obj.id in expanded)
        elif state is not None and not state.visible:
            font = QFont(item.font(COLUMN_NAME))
            font.setItalic(True)
            item.setFont(COLUMN_NAME, font)
            item.setForeground(COLUMN_NAME, QColor(current_palette().text_faint))
            item.setText(COLUMN_NAME, tr("objects.hidden_suffix", name=obj.name))
        if obj.editor_hidden or obj.locked:
            item.setForeground(COLUMN_NAME, QColor(current_palette().text_muted))
        return item

    def _all_items(self) -> list[QTreeWidgetItem]:
        result: list[QTreeWidgetItem] = []
        stack = [self.topLevelItem(i) for i in range(self.topLevelItemCount())]
        while stack:
            item = stack.pop()
            result.append(item)
            stack += [item.child(i) for i in range(item.childCount())]
        return result

    def item_for(self, object_id: str) -> QTreeWidgetItem | None:
        """Return the tree item of an object."""
        for item in self._all_items():
            if item.data(COLUMN_NAME, ID_ROLE) == object_id:
                return item
        return None

    # --- selection ------------------------------------------------------------------------

    def _sync_selection(self) -> None:
        self._updating = True
        selected = set(self.editor.selected_objects)
        for item in self._all_items():
            is_selected = item.data(COLUMN_NAME, ID_ROLE) in selected
            item.setSelected(is_selected)
            if is_selected:
                parent = item.parent()
                while parent is not None:
                    parent.setExpanded(True)
                    parent = parent.parent()
        self._updating = False

    def _on_selection(self) -> None:
        if self._updating:
            return
        current = [item.data(COLUMN_NAME, ID_ROLE) for item in self.selectedItems()]
        ordered = [i for i in self.editor.selected_objects if i in current]
        ordered += [i for i in current if i not in ordered]
        self.editor.select_objects(ordered)

    # --- toggles and renaming ----------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        index = self.indexAt(event.position().toPoint())
        if index.isValid() and index.column() in (COLUMN_HIDDEN, COLUMN_LOCKED) and event.button() == Qt.MouseButton.LeftButton:
            item = self.itemFromIndex(index)
            object_id = item.data(COLUMN_NAME, ID_ROLE)
            active = item.checkState(index.column()) == Qt.CheckState.Checked
            if index.column() == COLUMN_HIDDEN:
                self.controller.set_hidden([object_id], not active)
            else:
                self.controller.set_locked([object_id], not active)
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        index = self.indexAt(event.position().toPoint())
        if index.isValid() and index.column() != COLUMN_NAME:
            return
        super().mouseDoubleClickEvent(event)

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._updating or column != COLUMN_NAME:
            return
        object_id = item.data(COLUMN_NAME, ID_ROLE)
        obj = self.editor.scene().object_by_id(object_id)
        if obj is not None and item.text(COLUMN_NAME) != obj.name:
            self.controller.rename_object(object_id, item.text(COLUMN_NAME))
            self.refresh()

    def edit_name(self, object_id: str) -> None:
        """Start renaming an object inline."""
        item = self.item_for(object_id)
        if item is not None:
            self.scrollToItem(item)
            self.editItem(item, COLUMN_NAME)

    # --- drag and drop reorder ------------------------------------------------------------------

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 - Qt API
        dragged = self.currentItem()
        target = self.itemAt(event.position().toPoint())
        event.setDropAction(Qt.DropAction.IgnoreAction)
        event.accept()
        if dragged is None or target is None or target is dragged:
            return
        position = self.dropIndicatorPosition()
        if position == QAbstractItemView.DropIndicatorPosition.OnItem or target.parent() is not dragged.parent():
            if target.parent() is dragged.parent():
                return
            self.controller.statusMessage.emit(tr("objects.reorder_hint"))
            return
        siblings = self._siblings(dragged)
        siblings.remove(dragged)
        index = siblings.index(target) + (1 if position == QAbstractItemView.DropIndicatorPosition.BelowItem else 0)
        below = siblings[index] if index < len(siblings) else None
        above = siblings[index - 1] if index > 0 else None
        self.controller.move_layer(
            dragged.data(COLUMN_NAME, ID_ROLE),
            below.data(COLUMN_NAME, ID_ROLE) if below is not None else None,
            above.data(COLUMN_NAME, ID_ROLE) if above is not None else None,
        )

    def _siblings(self, item: QTreeWidgetItem) -> list[QTreeWidgetItem]:
        parent = item.parent()
        if parent is None:
            return [self.topLevelItem(i) for i in range(self.topLevelItemCount())]
        return [parent.child(i) for i in range(parent.childCount())]

    # --- context menu -----------------------------------------------------------------------------

    def _on_context_menu(self, position: QPoint) -> None:
        item = self.itemAt(position)
        object_id = item.data(COLUMN_NAME, ID_ROLE) if item else ""
        if object_id and object_id not in self.editor.selected_objects:
            self.editor.select_objects([object_id])
        self.contextMenuRequested.emit(self.viewport().mapToGlobal(position), object_id)
