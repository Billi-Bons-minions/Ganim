"""Object library: searchable, grouped tiles that can be clicked or dragged."""

from __future__ import annotations

from PySide6.QtCore import QMimeData, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QScrollArea, QToolButton, QVBoxLayout, QWidget

from manim_studio.i18n import tr
from manim_studio.model.types import ObjectKind
from manim_studio.ui.flow_layout import flow_container
from manim_studio.ui.icon_set import icon
from manim_studio.ui.icons import kind_icon, kind_pixmap
from manim_studio.ui.stage.view import KIND_MIME
from manim_studio.ui.theme import px

#: Library categories in display order.
CATEGORIES: tuple[tuple[str, tuple[ObjectKind, ...]], ...] = (
    ("shapes", (ObjectKind.CIRCLE, ObjectKind.SQUARE, ObjectKind.RECTANGLE, ObjectKind.TRIANGLE, ObjectKind.ELLIPSE, ObjectKind.DOT)),
    ("lines", (ObjectKind.LINE, ObjectKind.ARROW)),
    ("text", (ObjectKind.TEXT, ObjectKind.MATH_TEX)),
    ("math", (ObjectKind.AXES, ObjectKind.NUMBER_PLANE, ObjectKind.FUNCTION_GRAPH)),
    ("media", (ObjectKind.IMAGE,)),
)

LIBRARY_ORDER: tuple[ObjectKind, ...] = tuple(kind for _, kinds in CATEGORIES for kind in kinds)


class LibraryTile(QToolButton):
    """A clickable and draggable object tile."""

    requested = Signal(str)

    def __init__(self, kind: ObjectKind, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self._press: QPoint | None = None
        self._dragged = False
        self.setProperty("variant", "tile")
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setIcon(kind_icon(kind))
        self.setIconSize(QSize(px(30), px(30)))
        self.setText(tr(f"kind.{kind.value}"))
        self.setFixedSize(px(76), px(66))
        self.setToolTip(tr("library.tooltip", name=self.text()))
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self) -> None:
        if not self._dragged:
            self.requested.emit(self.kind.value)
        self._dragged = False

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.position().toPoint()
            self._dragged = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if self._press is None or not (event.buttons() & Qt.MouseButton.LeftButton) or not self.isEnabled():
            super().mouseMoveEvent(event)
            return
        if (event.position().toPoint() - self._press).manhattanLength() < QApplication.startDragDistance():
            return
        self._press = None
        self._dragged = True
        self.setDown(False)
        mime = QMimeData()
        mime.setData(KIND_MIME, self.kind.value.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(kind_pixmap(self.kind, px(40)))
        drag.setHotSpot(QPoint(px(20), px(20)))
        drag.exec(Qt.DropAction.CopyAction)


class LibraryPanel(QWidget):
    """Searchable object library grouped by category."""

    objectRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("library.search"))
        self.search.setClearButtonEnabled(True)
        self.search.addAction(icon("search"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self._filter)
        self.tiles: dict[ObjectKind, LibraryTile] = {}
        self._sections: list[tuple[QLabel, QWidget, list[LibraryTile]]] = []
        content = QWidget()
        content.setObjectName("Panel")
        column = QVBoxLayout(content)
        column.setContentsMargins(px(10), px(4), px(10), px(10))
        column.setSpacing(px(6))
        for key, kinds in CATEGORIES:
            label = QLabel(tr(f"library.category.{key}"))
            label.setProperty("role", "section")
            grid, flow = flow_container(px(6))
            tiles = []
            for kind in kinds:
                tile = LibraryTile(kind)
                tile.requested.connect(self.objectRequested)
                flow.addWidget(tile)
                self.tiles[kind] = tile
                tiles.append(tile)
            column.addWidget(label)
            column.addWidget(grid)
            self._sections.append((label, grid, tiles))
        column.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, px(6), 0, 0)
        layout.setSpacing(px(4))
        search_row = QVBoxLayout()
        search_row.setContentsMargins(px(10), 0, px(10), 0)
        search_row.addWidget(self.search)
        layout.addLayout(search_row)
        layout.addWidget(scroll, 1)

    def set_latex_available(self, available: bool) -> None:
        """Enable or disable the formula tile depending on LaTeX."""
        tile = self.tiles.get(ObjectKind.MATH_TEX)
        if tile is None:
            return
        tile.setEnabled(available)
        tile.setToolTip(tr("library.tooltip", name=tile.text()) if available else tr("library.latex_missing"))

    def _filter(self, text: str) -> None:
        needle = text.strip().lower()
        for label, grid, tiles in self._sections:
            visible = 0
            for tile in tiles:
                match = not needle or needle in tile.text().lower() or needle in tile.kind.value
                tile.setVisible(match)
                visible += int(match)
            label.setVisible(visible > 0)
            grid.setVisible(visible > 0)
            grid.updateGeometry()
