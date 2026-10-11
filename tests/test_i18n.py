"""Both languages must contain every text the application uses."""

from __future__ import annotations

import re
import string
from pathlib import Path

import pytest

from manim_studio.i18n import LANGUAGES, catalog, set_language, tr
from manim_studio.model.expression import ExpressionError
from manim_studio.model.schema import ANIMATION_PARAMS, KIND_INFO, ParamType
from manim_studio.model.stage_edits import MOVE, ROTATE, SCALE
from manim_studio.model.types import MANIM_COLORS, RATE_FUNCTIONS, AnimationKind, ObjectKind, Visibility
from manim_studio.render.command import QUALITY_PRESETS

SOURCE = Path(__file__).resolve().parent.parent / "manim_studio"
STATIC_KEY = re.compile(r"""\btr\(\s*["']([a-z_]+(?:\.[a-z_0-9]+)+)["']""")


def placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def used_static_keys() -> set[str]:
    keys = set()
    for path in SOURCE.rglob("*.py"):
        keys.update(STATIC_KEY.findall(path.read_text(encoding="utf-8")))
    return keys


def dynamic_keys() -> set[str]:
    keys: set[str] = set()
    keys |= {f"kind.{kind.value}" for kind in ObjectKind}
    keys |= {f"anim.{kind.value}" for kind in AnimationKind}
    keys |= {f"anim_help.{kind.value}" for kind in AnimationKind}
    keys |= {f"rate.{name}" for name in RATE_FUNCTIONS}
    keys |= {f"param.{spec.key}" for info in KIND_INFO.values() for spec in info.params}
    keys |= {f"aparam.{spec.key}" for specs in ANIMATION_PARAMS.values() for spec in specs}
    keys |= {f"choice.{spec.key}.{choice}" for specs in ANIMATION_PARAMS.values() for spec in specs if spec.type == ParamType.CHOICE for choice in spec.choices}
    keys |= {f"choice.visibility.{v.value}" for v in Visibility}
    keys |= {f"prop.{field}" for field in ("x", "y", "rotation", "stroke_color", "stroke_width", "stroke_opacity", "fill_color", "fill_opacity")}
    keys |= {f"lock.{reason}" for reason in ("nothing_selected", "bound_graph", "wait_step")}
    keys |= {f"lock.needs_{action}" for action in (MOVE, SCALE, ROTATE)}
    keys |= {f"export.format.{name}" for name in ("mp4", "gif", "png")}
    keys |= {f"export.quality.{key}" for key in QUALITY_PRESETS}
    keys |= {f"render.started_{mode}" for mode in ("preview", "export")}
    tools = ("manim", "ffmpeg", "latex")
    keys |= {f"env.tool.{tool}" for tool in tools} | {f"env.missing.{tool}" for tool in tools}
    keys |= {f"env.hint.{tool}.{platform}" for tool in tools for platform in ("windows", "macos", "linux")}
    keys |= {f"color.{name}" for name in MANIM_COLORS}
    keys |= {f"library.category.{key}" for key in ("shapes", "lines", "text", "math", "media")}
    keys |= {f"settings.theme.{name}" for name in ("dark", "light")}
    keys |= {f"dock.{dock}" for dock in ("library", "objects", "properties", "preview", "code", "log", "timeline")}
    keys |= {f"expr.{code}" for code in ("empty", "too_long", "too_complex", "invalid_character", "syntax", "not_allowed",
                                          "missing_parenthesis", "unknown_name", "unknown_function", "wrong_argument_count")}
    keys |= {f"render_error.{code}" for code in ("manim_missing", "python_not_found", "scene_not_found", "latex_error",
                                                  "file_not_found", "out_of_memory", "syntax_error", "python_error",
                                                  "output_missing", "unknown")}
    return keys


def codes_raised_in(folder: str, pattern: str) -> set[str]:
    codes = set()
    for path in (SOURCE / folder).rglob("*.py"):
        codes.update(re.findall(pattern, path.read_text(encoding="utf-8")))
    return codes


@pytest.mark.parametrize("language", list(LANGUAGES))
def test_all_used_keys_exist(language: str) -> None:
    texts = catalog(language)
    missing = sorted((used_static_keys() | dynamic_keys()) - set(texts))
    assert not missing, missing


def test_validation_and_codegen_codes_are_translated() -> None:
    issue_codes = codes_raised_in("model", r'Issue\((?:ERROR|WARNING),\s*"([a-z_]+)"') | codes_raised_in("model", r'add\((?:ERROR|WARNING),\s*"([a-z_]+)"')
    codegen_codes = codes_raised_in("codegen", r'CodegenError\(\s*"([a-z_]+)"')
    expression_codes = codes_raised_in("model", r'ExpressionError\(\s*"([a-z_]+)"')
    for language in LANGUAGES:
        texts = catalog(language)
        assert {f"issue.{code}" for code in issue_codes} <= set(texts)
        assert {f"codegen.{code}" for code in codegen_codes} <= set(texts)
        assert {f"expr.{code}" for code in expression_codes} <= set(texts)
    assert issubclass(ExpressionError, ValueError)


def test_languages_have_the_same_keys_and_placeholders() -> None:
    german, english = catalog("de"), catalog("en")
    assert set(german) == set(english)
    for key in german:
        assert placeholders(german[key]) == placeholders(english[key]), key


def test_tr_formats_and_falls_back() -> None:
    set_language("en")
    assert tr("status.copied", count=2) == "2 object(s) copied"
    set_language("de")
    assert tr("status.copied", count=2) == "2 Objekt(e) kopiert"
    assert tr("does.not.exist") == "does.not.exist"
