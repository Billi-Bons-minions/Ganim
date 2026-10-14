"""Cells, rows and columns of a table as the target of a highlight (Manim's ``Table.get_cell``)."""

from __future__ import annotations

from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.types import ObjectKind

#: Parameters of a highlight that pick part of a table (1-based, 0 = all).
TABLE_SELECTION_KEYS = ("table_row", "table_column")


def table_size(table: SceneObject) -> tuple[int, int]:
    """Number of rows and columns (short rows are filled up, like the generated table)."""
    rows = [row for row in table.params.get("rows", []) if isinstance(row, list)]
    return len(rows), max((len(row) for row in rows), default=0)


def highlighted_table(scene: Scene, highlight: SceneObject) -> SceneObject | None:
    """The table a highlight points at (``None`` for other targets)."""
    target = scene.object_by_id(highlight.params.get("target"))
    return target if target is not None and target.kind == ObjectKind.TABLE else None


def table_selection(scene: Scene, highlight: SceneObject) -> tuple[int, int] | None:
    """``(row, column)`` of a highlight on part of a table; ``None`` for a whole table or another target."""
    if highlighted_table(scene, highlight) is None:
        return None
    try:
        row, column = (int(highlight.params.get(key, 0) or 0) for key in TABLE_SELECTION_KEYS)
    except (TypeError, ValueError):
        return None
    if row <= 0 and column <= 0:
        return None
    return max(row, 0), max(column, 0)


def selection_outside(scene: Scene, highlight: SceneObject) -> bool:
    """``True`` if the chosen row or column does not exist in the table."""
    table = highlighted_table(scene, highlight)
    selection = table_selection(scene, highlight)
    if table is None or selection is None:
        return False
    rows, columns = table_size(table)
    return selection[0] > rows or selection[1] > columns
