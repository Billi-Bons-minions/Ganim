"""Overview of all keyboard shortcuts and mouse gestures."""

from __future__ import annotations

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QHeaderView, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from manim_studio.i18n import tr
from manim_studio.ui.theme import px

#: Gestures that are not bound to an action: (description key, shortcut key).
GESTURES = (
    ("shortcuts.nudge", "shortcuts.nudge_keys"),
    ("shortcuts.snap_off", "shortcuts.snap_off_keys"),
    ("shortcuts.multi_select", "shortcuts.multi_select_keys"),
    ("shortcuts.zoom", "shortcuts.zoom_keys"),
    ("shortcuts.pan", "shortcuts.pan_keys"),
    ("shortcuts.rotate_snap", "shortcuts.rotate_snap_keys"),
)


class ShortcutsDialog(QDialog):
    """Table of shortcuts collected from the window's actions."""

    def __init__(self, actions: list[QAction], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("shortcuts.title"))
        self.resize(px(560), px(620))
        rows: list[tuple[str, str]] = []
        for action in actions:
            sequence = action.shortcut()
            if sequence.isEmpty():
                continue
            text = action.text().replace("&", "")
            rows.append((text, sequence.toString(QKeySequence.SequenceFormat.NativeText)))
        rows.sort(key=lambda row: row[0].lower())
        rows += [(tr(description), tr(keys)) for description, keys in GESTURES]
        table = QTableWidget(len(rows), 2)
        table.setHorizontalHeaderLabels([tr("shortcuts.action"), tr("shortcuts.keys")])
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        for row, (text, keys) in enumerate(rows):
            table.setItem(row, 0, QTableWidgetItem(text))
            table.setItem(row, 1, QTableWidgetItem(keys))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(table)
        layout.addWidget(buttons)
