"""Text with a color gradient (Manim's ``Text(gradient=(a, b))``): one color per letter."""

from __future__ import annotations

import importlib.util
import re

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model.entities import Scene, Step
from manim_studio.model.gradients import letter_colors
from manim_studio.model.state import states_after
from manim_studio.model.types import ObjectKind, StepKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_object, make_project

HAS_MANIM = importlib.util.find_spec("manim") is not None


def text_scene() -> Scene:
    title = make_object(ObjectKind.TEXT, "Titel", "t", 0.0, 2.5, text="Manim Studio", font_size=60.0, gradient="letters", gradient_color="#FC6255")
    title.fill_color = "#58C4DD"
    lines = make_object(ObjectKind.TEXT, "Zeilen", "z", -3.0, -0.5, text="zwei\nZeilen", gradient="letters", gradient_color="#FFFF00")
    centered = make_object(ObjectKind.TEXT, "Mitte", "m", 3.0, -0.5, text="ab\ncde f", alignment="center", gradient="letters", gradient_color="#000000")
    return Scene(id="s", name="Verlauf", objects=[title, lines, centered])


def test_colors_rules_and_code() -> None:
    assert letter_colors("#000000", "#FFFFFF", 3) == ["#000000", "#808080", "#FFFFFF"]
    scene = text_scene()
    assert not has_errors(validate_scene(scene))
    assert states_after(scene, -1)["t"].fill_color2 == "#FC6255"
    code = generate_script(make_project(scene))
    assert 'gradient=("#58C4DD", "#FC6255")' in code
    assert "titel.set_fill([" not in code  # letters, not a linear gradient
    scene.object_by_id("t").params["colored_words"] = [["Studio", "#FFFFFF"]]
    assert any(issue.code == "text_gradient_words" for issue in validate_scene(scene))


def test_import() -> None:
    from manim_studio.importer import import_script

    imported = import_script(generate_script(make_project(text_scene()))).project.scenes[0]
    title = next(obj for obj in imported.objects if obj.params.get("text") == "Manim Studio")
    assert (title.fill_color, title.params["gradient"], title.params["gradient_color"]) == ("#58C4DD", "letters", "#FC6255")


def test_stage_colors_every_letter(qapp) -> None:
    from manim_studio.ui.stage.drawing import StageResources, build_drawing

    scene = text_scene()
    for key in ("t", "z", "m"):
        state = states_after(scene, -1)[key]
        text = str(scene.object_by_id(key).params["text"])
        drawing = build_drawing(scene, scene.object_by_id(key), state, StageResources())
        expected = {color for character, color in zip(text, letter_colors(state.fill_color, state.fill_color2, len(text))) if not character.isspace()}
        assert {primitive.brush.color().name().upper() for primitive in drawing.primitives} == expected, key


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_letter_colors_like_manim(tmp_path, qapp) -> None:
    from tests.test_manim_integration import run_manim

    scene = text_scene()
    report = "\n".join(
        f"print('COLORS {key}', *[glyph.get_fill_color().to_hex().upper() for glyph in {name}.family_members_with_points()])" for key, name in (("t", "titel"), ("z", "zeilen"), ("m", "mitte"))
    )
    scene.steps.append(Step(id="report", kind=StepKind.CODE, code=report, wait_time=0.0))
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Verlauf", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    for key in ("t", "z", "m"):
        theirs = re.search(rf"COLORS {key} ([^\n]+)", result.stdout).group(1).split()
        text = str(scene.object_by_id(key).params["text"])
        state = states_after(scene, -1)[key]
        ours = [color for character, color in zip(text, letter_colors(state.fill_color, state.fill_color2, len(text))) if not character.isspace()]
        assert len(ours) == len(theirs), key
        for mine, manim in zip(ours, theirs):
            assert all(abs(int(mine[i : i + 2], 16) - int(manim[i : i + 2], 16)) <= 1 for i in (1, 3, 5)), (key, mine, manim)
