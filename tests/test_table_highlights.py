"""Highlights on a cell, row or column of a table (``studio_table_cells``, like Manim's ``Table.get_cell``)."""

from __future__ import annotations

import importlib.util
import re

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model.entities import Scene, Step
from manim_studio.model.state import states_after
from manim_studio.model.tables import table_selection
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_animation, make_object, make_project, play

HAS_MANIM = importlib.util.find_spec("manim") is not None


def highlight_scene() -> Scene:
    table = make_object(ObjectKind.TABLE, "Tabelle", "t", -1.0, 0.3, rows=[["x", "-1", "0", "1", "2"], ["f(x)", "1", "0", "1", "4"], ["f'(x)", "-2", "0", "2", "4"]])
    cell = make_object(ObjectKind.HIGHLIGHT, "Zelle", "c", target="t", table_row=2, table_column=3, buff=0.0)
    row = make_object(ObjectKind.HIGHLIGHT, "Zeile", "r", target="t", table_row=3, style="background", buff=0.0)
    row.fill_color = "#FC6255"
    column = make_object(ObjectKind.HIGHLIGHT, "Spalte", "s", target="t", table_column=1, buff=0.1)
    under = make_object(ObjectKind.HIGHLIGHT, "Unterstrich", "u", target="t", table_row=1, table_column=5, style="underline", buff=0.05)
    scene = Scene(id="s", name="Hervorhebung", objects=[table, cell, row, column, under])
    scene.steps = [play(*(make_animation(AnimationKind.CREATE, key, f"c-{key}") for key in ("c", "s", "u")), make_animation(AnimationKind.FADE_IN, "r", "f-r"))]
    return scene


def test_rules_and_code() -> None:
    scene = highlight_scene()
    assert not has_errors(validate_scene(scene))
    assert table_selection(scene, scene.object_by_id("c")) == (2, 3) and table_selection(scene, scene.object_by_id("r")) == (3, 0)
    # a highlight of a whole table or of another object keeps its usual box
    whole = make_object(ObjectKind.HIGHLIGHT, "Ganz", "g", target="t")
    other = make_object(ObjectKind.HIGHLIGHT, "Anders", "a", target="c", table_row=1)
    assert table_selection(scene, whole) is None and table_selection(scene, other) is None
    outside = make_object(ObjectKind.HIGHLIGHT, "Daneben", "d", target="t", table_row=9)
    scene.objects.append(outside)
    assert any(issue.code == "table_cell_missing" for issue in validate_scene(scene))
    code = generate_script(make_project(highlight_scene()))
    assert "studio_table_cells(tabelle, 2, 3)" in code and "studio_table_cells(tabelle, 3, 0)" in code and "def studio_table_cells" in code


def _stage_box(scene: Scene, key: str) -> tuple[float, float, float, float]:
    from manim_studio.ui.stage.drawing import PX, StageResources, build_drawing
    from manim_studio.ui.stage.drawing_extra import placement_transform

    state = states_after(scene, 0)[key]
    drawing = build_drawing(scene, scene.object_by_id(key), state, StageResources())
    to_scene = placement_transform(("", "", state.x, state.y, state.rotation, state.scale, tuple(state.matrix)))
    box = to_scene.map(drawing.primitives[0].path).boundingRect()
    return box.left() / PX, box.right() / PX, -box.bottom() / PX, -box.top() / PX


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_boxes_like_manim(tmp_path, qapp) -> None:
    from tests.test_manim_integration import run_manim

    scene = highlight_scene()
    names = {"c": "zelle", "r": "zeile", "s": "spalte", "u": "unterstrich"}
    report = "\n".join(
        f"print('BOX {key}', *[round(float(v), 4) for v in ({name}.get_left()[0], {name}.get_right()[0], {name}.get_bottom()[1], {name}.get_top()[1])])"
        for key, name in names.items()
    )
    scene.steps.append(Step(id="report", kind=StepKind.CODE, code=report, wait_time=0.0))
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Hervorhebung", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    for key in names:
        theirs = [float(v) for v in re.search(rf"BOX {key} (\S+) (\S+) (\S+) (\S+)", result.stdout).groups()]
        assert _stage_box(scene, key) == pytest.approx(theirs, abs=0.03), key


def test_background_lies_behind_its_target_on_the_stage(qapp) -> None:
    """Like the script's ``set_z_index(target − 1)``: the row background must not cover the entries."""
    from manim_studio.ui.stage.drawing import StageResources
    from manim_studio.ui.stage.view import StageView

    scene = highlight_scene()
    view = StageView()
    view.set_content(scene, states_after(scene, 0), StageResources(), [], False)
    assert view._items["r"].zValue() < view._items["t"].zValue() < view._items["c"].zValue()
