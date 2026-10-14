"""Tables on the stage laid out like Manim's ``Table`` (cells, lines, size)."""

from __future__ import annotations

import importlib.util
import re

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model.entities import Scene, Step
from manim_studio.model.state import states_after
from manim_studio.model.types import ObjectKind, StepKind
from tests.helpers import make_object, make_project

HAS_MANIM = importlib.util.find_spec("manim") is not None


def table_scene() -> Scene:
    first = make_object(ObjectKind.TABLE, "Tabelle", "t", -3.0, 0.5)
    second = make_object(
        ObjectKind.TABLE, "Werte", "u", 2.5, -1.0, rows=[["x", "-2", "-1", "0", "1", "2"], ["f(x)", "4", "1", "0", "1", "4"]], font_size=28.0, outer_lines=False, h_buff=0.6, v_buff=0.3
    )
    return Scene(id="s", name="Tabellen", objects=[first, second])


def stage_cells(scene: Scene, key: str) -> dict[tuple[int, int], tuple[float, float, float, float]]:
    """Every cell (and the whole table at 0, 0) as left, right, bottom, top in the scene."""
    from manim_studio.ui.stage.drawing import PX, StageResources, build_drawing
    from manim_studio.ui.stage.drawing_extra import table_layout

    obj = scene.object_by_id(key)
    state = states_after(scene, -1)[key]
    offset = build_drawing(scene, obj, state, StageResources()).offset
    layout = table_layout(obj)
    cells = {}
    for row in range(len(layout.rows) + 1):
        for column in range(len(layout.columns) + 1):
            box = layout.cell(row, column)
            left, right = state.x + (box.left() - offset.x()) / PX, state.x + (box.right() - offset.x()) / PX
            top, bottom = state.y - (box.top() - offset.y()) / PX, state.y - (box.bottom() - offset.y()) / PX
            cells[(row, column)] = (left, right, bottom, top)
    return cells


def test_layout_follows_the_entries(qapp) -> None:
    from manim_studio.ui.stage.drawing_extra import table_layout

    layout = table_layout(table_scene().object_by_id("t"))
    # rows are as high as their highest entry: "f(x)" with parentheses is higher than the digits
    first_row = layout.rows[0][1] - layout.rows[0][0]
    second_row = layout.rows[1][1] - layout.rows[1][0]
    assert first_row > second_row * 1.2
    whole = layout.cell()
    assert whole.contains(layout.cell(2, 2)) and layout.cell(2, 0).width() == pytest.approx(whole.width())


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_cells_like_manim(tmp_path, qapp) -> None:
    from tests.test_manim_integration import run_manim

    scene = table_scene()
    report = []
    for name in ("tabelle", "werte"):
        report += [
            f"print('BOX {name}', *[round(float(v), 4) for v in ({name}.get_left()[0], {name}.get_right()[0], {name}.get_bottom()[1], {name}.get_top()[1])])",
            f"for r in range(1, len({name}.get_rows()) + 1):",
            f"    for c in range(1, len({name}.get_columns()) + 1):",
            f"        cell = {name}.get_cell((r, c))",
            f"        print('CELL {name}', r, c, *[round(float(v), 4) for v in (cell.get_left()[0], cell.get_right()[0], cell.get_bottom()[1], cell.get_top()[1])])",
        ]
    scene.steps.append(Step(id="report", kind=StepKind.CODE, code="\n".join(report), wait_time=0.0))
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Tabellen", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    for key, name in (("t", "tabelle"), ("u", "werte")):
        ours = stage_cells(scene, key)
        box = [float(v) for v in re.search(rf"BOX {name} (\S+) (\S+) (\S+) (\S+)", result.stdout).groups()]
        assert ours[(0, 0)] == pytest.approx(box, abs=0.02), name
        for r, c, *values in re.findall(rf"CELL {name} (\d+) (\d+) (\S+) (\S+) (\S+) (\S+)", result.stdout):
            assert ours[(int(r), int(c))] == pytest.approx([float(v) for v in values], abs=0.02), (name, r, c)
