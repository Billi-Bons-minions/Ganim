"""Check a scene for problems before code generation and rendering."""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from pathlib import Path

from manim_studio.model import graphs, groups
from manim_studio.model.assets import resolve_asset_path
from manim_studio.model.data import bar_values, data_points
from manim_studio.model.entities import STEP_TOGETHER, Animation, Scene, SceneObject, Step
from manim_studio.model.expression import check_expression, is_valid_name
from manim_studio.model.paths import local_outline
from manim_studio.model.schema import animation_allowed
from manim_studio.model.types import (
    CURVE_DERIVATIVE,
    CURVE_FUNCTION,
    CURVE_PARAMETRIC,
    CURVE_PIECEWISE,
    CURVE_POLAR,
    FUNCTION_CURVES,
    GRAPH_TOOL_KINDS,
    LATEX_KINDS,
    MODIFIER_ANIMATIONS,
    RATE_FUNCTIONS,
    REFERENCE_PARAMS,
    TRANSFORM_ANIMATIONS,
    AnimationKind,
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
    if obj.kind == ObjectKind.MATH_TEX and not str(params.get("latex", "")).strip():
        add(ERROR, "latex_empty")
    if obj.kind == ObjectKind.TEX and not str(params.get("tex", "")).strip():
        add(ERROR, "latex_empty")
    if obj.kind in LATEX_KINDS and not latex_available:
        add(ERROR, "latex_unavailable")
    if obj.kind == ObjectKind.POLYGON and len(params.get("points", [])) < 3:
        add(ERROR, "polygon_points")
    if obj.kind in (ObjectKind.STAR, ObjectKind.ANNULUS):
        if float(params.get("inner_radius", 0.5)) >= float(params.get("outer_radius", 1.0)):
            add(ERROR, "radii_invalid")
    if obj.kind in (ObjectKind.TABLE, ObjectKind.MATRIX) and not any(params.get("rows", [])):
        add(ERROR, "table_empty")
    if obj.kind == ObjectKind.GROUP:
        if not groups.members(scene, obj.id):
            add(ERROR, "group_empty")
        elif obj.id in groups.ancestors(scene, obj.id):
            add(ERROR, "group_cycle")
    if obj.kind in (ObjectKind.AXES, ObjectKind.NUMBER_PLANE):
        for axis in ("x", "y"):
            if float(params.get(f"{axis}_min", 0)) >= float(params.get(f"{axis}_max", 1)):
                add(ERROR, "axes_range_invalid", axis)
            if float(params.get(f"{axis}_step", 1)) <= 0:
                add(ERROR, "axes_step_invalid", axis)
    if obj.kind == ObjectKind.FUNCTION_GRAPH:
        _graph_issues(scene, obj, add)
    if obj.kind in GRAPH_TOOL_KINDS:
        _tool_issues(scene, obj, add)
    if obj.kind in (ObjectKind.SURFACE, ObjectKind.CURVE_3D):
        from manim_studio.model.three_d import axes_of

        if axes_of(scene, obj) is None:
            add(ERROR, "axes_3d_missing")
        if obj.kind == ObjectKind.SURFACE:
            _expression_issue_names(scene, str(params.get("expression", "")), "x", ("y",), add)
        else:
            for key in ("x_expression", "y_expression", "z_expression"):
                if _expression_issue(scene, str(params.get(key, "")), "t", add):
                    break
    if obj.kind == ObjectKind.DATA_PLOT:
        if graphs.data_axes(scene, obj) is None:
            add(ERROR, "data_needs_axes")
        if not data_points(obj):
            add(ERROR, "data_empty")
        elif params.get("regression", "none") != "none" and graphs.data_fit(obj) is None:
            add(WARNING, "regression_impossible")
    if obj.kind == ObjectKind.BAR_CHART and not bar_values(obj):
        add(ERROR, "data_empty")
    if obj.kind == ObjectKind.PARAMETER:
        symbol = graphs.parameter_symbol(obj)
        if not is_valid_name(symbol):
            add(ERROR, "parameter_symbol_invalid", symbol)
        elif symbol not in graphs.parameter_symbols(scene):
            add(ERROR, "parameter_symbol_duplicate", symbol)
        if float(params.get("minimum", 0)) >= float(params.get("maximum", 1)):
            add(WARNING, "parameter_range_invalid")
    if obj.kind == ObjectKind.IMAGE:
        path = str(params.get("path", ""))
        if not path:
            add(ERROR, "image_missing_path")
        elif not resolve_asset_path(path, base_dir).is_file():
            add(ERROR, "image_not_found", path)
    return issues


def _expression_issue_names(scene: Scene, text: str, variable: str, extra: tuple[str, ...], add) -> bool:
    error = check_expression(text, variable, (*extra, *graphs.parameter_symbols(scene)))
    if error is not None:
        add(ERROR, "expression_invalid", error.code + (f": {error.detail}" if error.detail else ""))
        return True
    return False


def _expression_issue(scene: Scene, text: str, variable: str, add) -> bool:
    error = check_expression(text, variable, graphs.parameter_symbols(scene))
    if error is not None:
        add(ERROR, "expression_invalid", error.code + (f": {error.detail}" if error.detail else ""))
        return True
    return False


def _graph_issues(scene: Scene, obj: SceneObject, add) -> None:
    params = obj.params
    curve = params.get("curve", CURVE_FUNCTION)
    if curve == CURVE_FUNCTION:
        _expression_issue(scene, str(params.get("expression", "")), "x", add)
    elif curve == CURVE_PIECEWISE:
        rows = [row for row in params.get("pieces", []) or [] if isinstance(row, (list, tuple)) and row]
        if not rows:
            add(ERROR, "pieces_empty")
        for row in rows:
            if _expression_issue(scene, str(row[0]), "x", add):
                break
    elif curve == CURVE_DERIVATIVE:
        source = scene.object_by_id(params.get("derive_from"))
        if source is None:
            add(ERROR, "derive_source_missing")
        elif graphs.function_pieces(scene, obj) is None:
            add(ERROR, "derive_source_invalid", source.name)
    elif curve == CURVE_PARAMETRIC:
        for key in ("x_expression", "y_expression"):
            if _expression_issue(scene, str(params.get(key, "")), "t", add):
                break
    elif curve == CURVE_POLAR:
        _expression_issue(scene, str(params.get("r_expression", "")), "t", add)
    if curve in FUNCTION_CURVES and float(params.get("x_min", 0)) >= float(params.get("x_max", 1)):
        add(ERROR, "graph_range_invalid")
    if curve in (CURVE_PARAMETRIC, CURVE_POLAR) and float(params.get("t_min", 0)) >= float(params.get("t_max", 1)):
        add(ERROR, "graph_range_invalid")
    axes_id = params.get("axes_id")
    if axes_id and scene.object_by_id(axes_id) is None:
        add(ERROR, "graph_axes_missing")


def _tool_issues(scene: Scene, obj: SceneObject, add) -> None:
    params = obj.params
    graph = scene.object_by_id(params.get("graph_id"))
    if graph is None:
        add(ERROR, "graph_missing")
        return
    if graphs.tool_graph(scene, obj) is None:
        add(ERROR, "graph_needs_axes", graph.name)
        return
    if not graphs.is_function_curve(graph) or graphs.function_pieces(scene, graph) is None:
        add(ERROR, "graph_not_function", graph.name)
        return
    needs_other = (obj.kind == ObjectKind.GRAPH_AREA and params.get("mode") == "between") or (
        obj.kind == ObjectKind.GRAPH_MARKERS and params.get("feature") == "intersections"
    )
    if needs_other:
        other = scene.object_by_id(params.get("other_graph_id"))
        if other is None or other.id == graph.id or not graphs.is_function_curve(other):
            add(ERROR, "other_graph_missing")
    if obj.kind in (ObjectKind.GRAPH_AREA, ObjectKind.RIEMANN) and float(params.get("x_min", 0)) >= float(params.get("x_max", 1)):
        add(ERROR, "graph_range_invalid")
    if obj.kind == ObjectKind.RIEMANN and float(params.get("dx", 0.1)) <= 0:
        add(ERROR, "riemann_dx_invalid")
    if obj.kind == ObjectKind.TANGENT and not graphs.tangent_points(scene, obj):
        add(ERROR, "tangent_undefined")
    if obj.kind == ObjectKind.GRAPH_POINT and graphs.graph_point(scene, obj) is None:
        add(ERROR, "point_undefined")
    if obj.kind == ObjectKind.GRAPH_MARKERS and not graphs.marker_points(scene, obj):
        add(WARNING, "markers_none")
    if obj.kind == ObjectKind.GRAPH_LABEL and params.get("use_latex") and not str(params.get("text", "")).strip():
        add(ERROR, "latex_empty")


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
    if target.kind == ObjectKind.CAMERA:
        from manim_studio.model.three_d import is_3d

        if anim.kind == AnimationKind.ORBIT and not is_3d(scene):
            add(ERROR, "orbit_needs_3d", object_id=target.id)
        elif anim.kind != AnimationKind.ORBIT and is_3d(scene):
            add(ERROR, "camera_3d_orbit_only", object_id=target.id)
    if anim.kind in (AnimationKind.MOVE_ALONG_PATH, AnimationKind.SWAP):
        key = REFERENCE_PARAMS[anim.kind]
        other = scene.object_by_id(anim.params.get(key))
        if other is None or other.id == target.id:
            add(ERROR, f"{key}_missing", object_id=target.id)
        elif anim.kind == AnimationKind.MOVE_ALONG_PATH and local_outline(scene, other) is None:
            add(ERROR, "path_unsupported", other.name, other.id)
    color = anim.params.get("color")
    if color is not None and not is_hex_color(color):
        add(ERROR, "color_invalid", str(color))
    return issues


def _code_issue(scene: Scene, index: int, step: Step) -> list[Issue]:
    try:
        compile(textwrap.dedent(step.code), f"step {index + 1}", "exec")
    except SyntaxError as error:
        return [Issue(ERROR, "code_syntax", scene.id, step_index=index, detail=f"{error.lineno}: {error.msg}")]
    return []


def _step_issues(scene: Scene, index: int, step: Step) -> list[Issue]:
    if step.kind == StepKind.CODE:
        return _code_issue(scene, index, step)
    if step.kind == StepKind.WAIT:
        if step.wait_time <= 0:
            return [Issue(ERROR, "wait_time_invalid", scene.id, step_index=index)]
        return []
    if not step.animations:
        return [Issue(WARNING, "step_empty", scene.id, step_index=index)]
    issues: list[Issue] = []
    for anim in step.animations:
        issues.extend(_animation_issues(scene, index, anim))
    if step.mode == STEP_TOGETHER:
        transformed = {anim.target_id for anim in step.animations if anim.kind in TRANSFORM_ANIMATIONS}
        moved = {anim.target_id for anim in step.animations if anim.kind in MODIFIER_ANIMATIONS}
        for target_id in sorted(transformed & moved):
            issues.append(Issue(ERROR, "transform_conflict", scene.id, target_id, index))
    return issues


def validate_scene(scene: Scene, latex_available: bool = True, base_dir: str | Path | None = None) -> list[Issue]:
    """Return all problems of a scene, errors first."""
    issues: list[Issue] = []
    if not is_hex_color(scene.background_color):
        issues.append(Issue(ERROR, "color_invalid", scene.id, detail=scene.background_color))
    cameras = [obj for obj in scene.objects if obj.kind == ObjectKind.CAMERA]
    for extra in cameras[1:]:
        issues.append(Issue(ERROR, "camera_duplicate", scene.id, extra.id))
    for obj in scene.objects:
        issues.extend(_object_issues(scene, obj, latex_available, base_dir))
    for index, step in enumerate(scene.steps):
        issues.extend(_step_issues(scene, index, step))
    return sorted(issues, key=lambda issue: issue.severity != ERROR)


def has_errors(issues: list[Issue]) -> bool:
    """Return ``True`` if any issue is an error."""
    return any(issue.severity == ERROR for issue in issues)
