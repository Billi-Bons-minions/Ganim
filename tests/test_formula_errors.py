"""Formulas LaTeX rejected on the stage stop a render before it starts (found by fuzzing)."""

from __future__ import annotations

import shutil

import pytest

from manim_studio.model.entities import Scene
from manim_studio.model.types import ObjectKind
from manim_studio.model.validation import validate_scene
from tests.helpers import make_object

SUM = r"\sum_{k=1}^n k"


def scene() -> Scene:
    text = make_object(ObjectKind.TEX, "LaTeX-Text", "t", tex=SUM)
    formula = make_object(ObjectKind.MATH_TEX, "Formel", "f", latex=SUM)
    return Scene(id="s", name="S", objects=[text, formula])


def test_known_latex_errors_become_issues() -> None:
    # math commands in a text-mode Tex fail, the same source as MathTex is fine
    def lookup(source: str, environment: str) -> str | None:
        return "Missing $ inserted." if (source, environment) == (SUM, "center") else None

    issues = [issue for issue in validate_scene(scene(), formula_errors=lookup) if issue.code == "latex_failed"]
    assert [(issue.object_id, issue.detail) for issue in issues] == [("t", "Missing $ inserted.")]
    assert not [issue for issue in validate_scene(scene()) if issue.code == "latex_failed"]  # nothing known, nothing blocked
    assert not [issue for issue in validate_scene(scene(), latex_available=False, formula_errors=lookup) if issue.code == "latex_failed"]


def test_preview_cache_keeps_errors_per_environment(qapp, tmp_path) -> None:
    from manim_studio.render.tex_preview import TexPreviewCache, latex_key

    cache = TexPreviewCache(tmp_path, enabled=False)
    cache._on_done(SUM, latex_key(SUM, "center"), "Missing $ inserted.", True)
    cache._on_done("x", latex_key("x"), "latex timed out", False)
    assert cache.error(SUM, "center") == "Missing $ inserted." and cache.formula_error(SUM, "center") == "Missing $ inserted."
    assert cache.error(SUM) is None  # as MathTex (align*) the same source is fine
    assert cache.error("x") == "latex timed out" and cache.formula_error("x") is None  # not the formula's fault


@pytest.mark.skipif(shutil.which("latex") is None or shutil.which("dvisvgm") is None, reason="LaTeX is not installed")
def test_latex_itself_rejects_math_in_text_mode(tmp_path) -> None:
    from manim_studio.render.tex_preview import LatexFailure, compile_latex_to_svg

    error = compile_latex_to_svg(SUM, tmp_path / "text.svg", environment="center")
    assert isinstance(error, LatexFailure) and "Missing $" in error
    assert compile_latex_to_svg(SUM, tmp_path / "math.svg") is None
