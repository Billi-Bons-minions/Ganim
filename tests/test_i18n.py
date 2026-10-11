"""Both languages must contain every text the application uses."""

from __future__ import annotations

import re
import string
from pathlib import Path

import pytest

from manim_studio.examples import EXAMPLES
from manim_studio.i18n import LANGUAGES, catalog, set_language, tr
from manim_studio.model.arrange import ALIGN_MODES, DISTRIBUTE_MODES
from manim_studio.model.expression import ExpressionError
from manim_studio.model.frame import ASPECTS
from manim_studio.model.schema import ANIMATION_PARAMS, KIND_INFO, MARKER_FEATURES, ParamType
from manim_studio.model.stage_edits import COLOR, MOVE, ROTATE, SCALE, VALUE
from manim_studio.model.types import MANIM_COLORS, RATE_FUNCTIONS, AnimationKind, ObjectKind, Visibility
from manim_studio.render.command import QUALITY_PRESETS
from manim_studio.templates import BUILTIN_TEMPLATES
from manim_studio.ui.dialogs.export_dialog import EXPORT_SCENES
from manim_studio.ui.panels.properties_panel import GRAPH_ACTIONS
from manim_studio.ui.user_library import BUILTIN_STYLES

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
    keys |= {f"anim_short.{kind.value}" for kind in AnimationKind}
    keys |= {f"animgroup.{group}" for group in ("appear", "change", "transform", "emphasize", "disappear")}
    keys |= {f"undo.{action}" for action in (MOVE, SCALE, ROTATE, COLOR)}
    keys |= {f"export.format.{name}" for name in ("mp4", "gif", "png")}
    keys |= {f"export.quality.{key}" for key in QUALITY_PRESETS}
    keys |= {f"render.started_{mode}" for mode in ("preview", "export")}
    tools = ("manim", "ffmpeg", "latex")
    keys |= {f"env.tool.{tool}" for tool in tools} | {f"env.missing.{tool}" for tool in tools}
    keys |= {f"env.hint.{tool}.{platform}" for tool in tools for platform in ("windows", "macos", "linux")}
    keys |= {f"color.{name}" for name in MANIM_COLORS}
    keys |= {f"example.{example.key}.{part}" for example in EXAMPLES for part in ("name", "text", "scene")}
    keys |= {f"tour.{step}" for step in ("intro", "add_circle", "animate", "timeline", "new_step", "drag", "preview", "done")}
    keys |= {f"library.category.{key}" for key in ("shapes", "lines", "text", "math", "analysis", "three_d", "media")}
    keys |= {f"settings.theme.{name}" for name in ("dark", "light")}
    keys |= {f"{prefix}.arrange.{mode}" for prefix in ("action", "undo") for mode in ALIGN_MODES + DISTRIBUTE_MODES}
    keys |= {f"graph_action.{key}{suffix}" for key, _action, _params in GRAPH_ACTIONS for suffix in ("", "_tip")}
    keys |= {f"feature.{feature}" for feature in MARKER_FEATURES}
    keys |= {f"aspect.{aspect}" for aspect in ASPECTS}
    keys |= {f"export.scenes.{key}" for key in EXPORT_SCENES} | {f"export.transition.{key}" for key in ("cut", "fade")}
    keys |= {f"prop.step_{key}" for key in ("section", "subcaption", "sound_gain", "sound_offset")}
    keys |= {"banner.code", "lock.code_step", "action.add_code_step", "action.fade_out_all", "action.camera_view"}
    keys |= {"action.save_package", "action.open_package", "action.import_script"}
    keys |= {f"style.builtin.{style.name}" for style in BUILTIN_STYLES}
    keys |= {f"template.{template.key}.name" for template in BUILTIN_TEMPLATES}
    keys |= {f"undo.{action}" for action in (VALUE,)}
    keys |= {f"lock.{reason}" for reason in ("transform_conflict",)}
    keys |= {f"prop.{point}_{axis}" for point in ("start", "end", "center") for axis in ("x", "y")}
    keys |= {f"choice.{spec.key}.{choice}" for info in KIND_INFO.values() for spec in info.params
             if spec.type == ParamType.CHOICE and spec.key != "language" for choice in spec.choices}
    keys |= {f"dock.{dock}" for dock in ("library", "objects", "properties", "preview", "code", "log", "timeline", "history")}
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
