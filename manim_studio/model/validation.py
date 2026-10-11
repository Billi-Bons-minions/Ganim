"""Check a scene for problems before code generation and rendering."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from manim_studio.model.assets import resolve_asset_path
from manim_studio.model.entities import Animation, Scene, SceneObject, Step
from manim_studio.model.expression import check_expression
from manim_studio.model.schema import animation_allowed
from manim_studio.model.types import (
    MODIFIER_ANIMATIONS,
    RATE_FUNCTIONS,
    TRANSFORM_ANIMATIONS,
    ObjectKind,
    StepKind,
)

ERROR = "error"
WARNING = "warning"

_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


@dataclass(frozen=True)
class Issue:
    """One validation finding; ``code`` is translated by the UI."""

    severity: str
    code: str
    scene_id: str
    object_id: str | None = None
    step_index: int | None = None
    animation_id: str | None = None
    detail: str = ""


def is_hex_color(value: object) -> bool:
    """Return ``True`` for colors in ``#RRGGBB`` notation."""
    return isinstance(value, str) and bool(_HEX_COLOR.match(value))


def _object_issues(scene: Scene, obj: SceneObject, latex_available: bool, base_dir: str | Path | None) -> list[Issue]:
    issues: list[Issue] = []

    def add(severity: str, code: str, detail: str = "") -> None:
        issues.append(Issue(severity, code, scene.id, object_id=obj.id, detail=detail))

    for color in (obj.stroke_color, obj.fill_color):
        if not is_hex_color(color):
            add(ERROR, "color_invalid", str(color))
    params = obj.params
    if obj.kind == ObjectKind.TEXT and not str(params.get("text", "")).strip():
        add(ERROR, "text_empty")
    if obj.kind == ObjectKind.MATH_TEX:
        if not str(params.get("latex", "")).strip():
            add(ERROR, "latex_empty")
        if not latex_available:
            add(ERROR, "latex_unavailable")
    if obj.kind in (ObjectKind.AXES, ObjectKind.NUMBER_PLANE):
        for axis in ("x", "y"):
            if float(params.get(f"{axis}_min", 0)) >= float(params.get(f"{axis}_max", 1)):
                add(ERROR, "axes_range_invalid", axis)
            if float(params.get(f"{axis}_step", 1)) <= 0:
                add(ERROR, "axes_step_invalid", axis)
    if obj.kind == ObjectKind.FUNCTION_GRAPH:
        error = check_expression(str(params.get("expression", "")))
        if error is not None:
            add(ERROR, "expression_invalid", error.code + (f": {error.detail}" if error.detail else ""))
        if float(params.get("x_min", 0)) >= float(params.get("x_max", 1)):
            add(ERROR, "graph_range_invalid")
        axes_id = params.get("axes_id")
        if axes_id and scene.object_by_id(axes_id) is None:
            add(ERROR, "graph_axes_missing")
    if obj.kind == ObjectKind.IMAGE:
        path = str(params.get("path", ""))
        if not path:
            add(ERROR, "image_missing_path")
        elif not resolve_asset_path(path, base_dir).is_file():
            add(ERROR, "image_not_found", path)
    return issues


def _animation_issues(scene: Scene, step_index: int, anim: Animation) -> list[Issue]:
    issues: list[Issue] = []

    def add(severity: str, code: str, detail: str = "", object_id: str | None = None) -> None:
        issues.append(Issue(severity, code, scene.id, object_id, step_index, anim.id, detail))

    target = scene.object_by_id(anim.target_id)
    if target is None:
        add(ERROR, "animation_target_missing")
        return issues
    if not animation_allowed(anim.kind, target.kind, target.params):
        add(ERROR, "animation_incompatible", anim.kind.value, target.id)
    if anim.run_time <= 0:
        add(ERROR, "run_time_invalid")
    if anim.rate_func not in RATE_FUNCTIONS:
        add(ERROR, "rate_func_unknown", anim.rate_func)
    if anim.kind in TRANSFORM_ANIMATIONS:
        other = scene.object_by_id(anim.params.get("target"))
        if other is None:
            add(ERROR, "transform_target_missing", object_id=target.id)
        elif other.id == target.id:
            add(ERROR, "transform_target_self", object_id=target.id)
        elif not animation_allowed(anim.kind, other.kind, other.params):
            add(ERROR, "animation_incompatible", anim.kind.value, other.id)
    color = anim.params.get("color")
    if color is not None and not is_hex_color(color):
        add(ERROR, "color_invalid", str(color))
    return issues


def _step_issues(scene: Scene, index: int, step: Step) -> list[Issue]:
    if step.kind == StepKind.WAIT:
        if step.wait_time <= 0:
            return [Issue(ERROR, "wait_time_invalid", scene.id, step_index=index)]
        return []
    if not step.animations:
        return [Issue(WARNING, "step_empty", scene.id, step_index=index)]
    issues: list[Issue] = []
    for anim in step.animations:
        issues.extend(_animation_issues(scene, index, anim))
    modifier_targets = [anim.target_id for anim in step.animations if anim.kind in MODIFIER_ANIMATIONS]
    for target_id in sorted(set(modifier_targets)):
        if modifier_targets.count(target_id) > 1:
            issues.append(Issue(WARNING, "animations_merged", scene.id, target_id, index))
    return issues


def validate_scene(scene: Scene, latex_available: bool = True, base_dir: str | Path | None = None) -> list[Issue]:
    """Return all problems of a scene, errors first."""
    issues: list[Issue] = []
    if not is_hex_color(scene.background_color):
        issues.append(Issue(ERROR, "color_invalid", scene.id, detail=scene.background_color))
    for obj in scene.objects:
        issues.extend(_object_issues(scene, obj, latex_available, base_dir))
    for index, step in enumerate(scene.steps):
        issues.extend(_step_issues(scene, index, step))
    return sorted(issues, key=lambda issue: issue.severity != ERROR)


def has_errors(issues: list[Issue]) -> bool:
    """Return ``True`` if any issue is an error."""
    return any(issue.severity == ERROR for issue in issues)
