"""List of all objects of the active scene (also hidden ones)."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem, QWidget

from manim_studio.i18n import tr
from manim_studio.model.state import states_after
from manim_studio.ui.document import ProjectDocument
from manim_studio.ui.editor_state import EditorState
from manim_studio.ui.icons import kind_icon

ID_ROLE = Qt.ItemDataRole.UserRole


class ObjectsPanel(QListWidget):
    """Shows the objects in layer order and mirrors the stage selection."""

    contextMenuRequested = Signal(QPoint, str)

    def __init__(self, document: ProjectDocument, editor: EditorState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.document = document
        self.editor = editor
        self._updating = False
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self.itemSelectionChanged.connect(self._on_selection)
        document.changed.connect(self.refresh)
        editor.sceneChanged.connect(self.refresh)
        editor.cursorChanged.connect(self.refresh)
        editor.selectionChanged.connect(self._sync_selection)
        self.refresh()

    def refresh(self) -> None:
        """Rebuild the list from the model."""
        self._updating = True
        scene = self.editor.scene()
        states = states_after(scene, self.editor.cursor)
        self.clear()
        for obj in scene.objects:
            item = QListWidgetItem(kind_icon(obj.kind, 20), obj.name)
            item.setData(ID_ROLE, obj.id)
            visible = states[obj.id].visible
            item.setToolTip(tr("objects.tooltip", kind=tr(f"kind.{obj.kind.value}"), layer=obj.z_index))
            if not visible:
                font = QFont(item.font())
                font.setItalic(True)
                item.setFont(font)
                item.setForeground(QColor(150, 150, 150))
                item.setText(tr("objects.hidden_suffix", name=obj.name))
            self.addItem(item)
        self._updating = False
        self._sync_selection()

    def _sync_selection(self) -> None:
        self._updating = True
        selected = set(self.editor.selected_objects)
        for row in range(self.count()):
            item = self.item(row)
            item.setSelected(item.data(ID_ROLE) in selected)
        self._updating = False

    def _on_selection(self) -> None:
        if self._updating:
            return
        current = [item.data(ID_ROLE) for item in self.selectedItems()]
        ordered = [i for i in self.editor.selected_objects if i in current]
        ordered += [i for i in current if i not in ordered]
        self.editor.select_objects(ordered)

    def _on_context_menu(self, position: QPoint) -> None:
        item = self.itemAt(position)
        object_id = item.data(ID_ROLE) if item else ""
        if object_id and object_id not in self.editor.selected_objects:
            self.editor.select_objects([object_id])
        self.contextMenuRequested.emit(self.viewport().mapToGlobal(position), object_id)
