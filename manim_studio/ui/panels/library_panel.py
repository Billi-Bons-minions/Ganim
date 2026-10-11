"""Object library: click or drag an object kind onto the stage."""

from __future__ import annotations

from PySide6.QtCore import QMimeData, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListView,
    QListWidget,
    QListWidgetItem,
    QWidget,
)

from manim_studio.i18n import tr
from manim_studio.model.types import ObjectKind
from manim_studio.ui.icons import kind_icon
from manim_studio.ui.stage.view import KIND_MIME

LIBRARY_ORDER = (
    ObjectKind.CIRCLE,
    ObjectKind.SQUARE,
    ObjectKind.RECTANGLE,
    ObjectKind.TRIANGLE,
    ObjectKind.ELLIPSE,
    ObjectKind.LINE,
    ObjectKind.ARROW,
    ObjectKind.DOT,
    ObjectKind.TEXT,
    ObjectKind.MATH_TEX,
    ObjectKind.AXES,
    ObjectKind.NUMBER_PLANE,
    ObjectKind.FUNCTION_GRAPH,
    ObjectKind.IMAGE,
)

KIND_ROLE = Qt.ItemDataRole.UserRole


class LibraryPanel(QListWidget):
    """Grid of object kinds; emits :attr:`objectRequested` on click."""

    objectRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setIconSize(QSize(36, 36))
        self.setGridSize(QSize(96, 68))
        self.setSpacing(2)
        self.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.setMinimumWidth(214)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setWordWrap(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        for kind in LIBRARY_ORDER:
            item = QListWidgetItem(kind_icon(kind), tr(f"kind.{kind.value}"))
            item.setData(KIND_ROLE, kind.value)
            item.setToolTip(tr("library.tooltip", name=tr(f"kind.{kind.value}")))
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            self.addItem(item)
        self.itemClicked.connect(self._on_clicked)

    def set_latex_available(self, available: bool) -> None:
        """Enable or disable the MathTex entry depending on LaTeX."""
        for row in range(self.count()):
            item = self.item(row)
            if item.data(KIND_ROLE) != ObjectKind.MATH_TEX.value:
                continue
            flags = item.flags()
            enabled = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsSelectable
            item.setFlags(flags | enabled if available else flags & ~enabled)
            item.setToolTip(tr("library.tooltip", name=item.text()) if available else tr("library.latex_missing"))

    def _on_clicked(self, item: QListWidgetItem) -> None:
        if item.flags() & Qt.ItemFlag.ItemIsEnabled:
            self.objectRequested.emit(item.data(KIND_ROLE))
        self.clearSelection()

    def mimeTypes(self) -> list[str]:  # noqa: N802 - Qt API
        return [KIND_MIME]

    def mimeData(self, items: list[QListWidgetItem]) -> QMimeData:  # noqa: N802 - Qt API
        mime = QMimeData()
        if items:
            mime.setData(KIND_MIME, str(items[0].data(KIND_ROLE)).encode("utf-8"))
        return mime
