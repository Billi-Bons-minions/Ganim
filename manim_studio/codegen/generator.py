"""Convert a project into a standalone Manim Community script."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from manim_studio import __version__
from manim_studio.codegen.animations import STUDIO_SHAPE, STUDIO_SHAPE_SOURCE, STUDIO_TRANSFORM, STUDIO_TRANSFORM_SOURCE, step_code
from manim_studio.codegen.errors import CodegenError
from manim_studio.codegen.formatting import indent_lines
from manim_studio.codegen.graph_code import (
    STUDIO_BESIDE,
    STUDIO_BESIDE_SOURCE,
    STUDIO_DASHED,
    STUDIO_DASHED_SOURCE,
    STUDIO_INTEGRAL,
    STUDIO_INTEGRAL_SOURCE,
    STUDIO_LINES,
    STUDIO_LINES_SOURCE,
    STUDIO_PLOT,
    STUDIO_PLOT_SOURCE,
    STUDIO_TERM,
    STUDIO_TERM_SOURCE,
)
from manim_studio.codegen.literals import LiteralError, fmt_float, py_color
from manim_studio.codegen.naming import class_names, variable_names
from manim_studio.codegen.objects import COLOR_TEX, COLOR_TEX_SOURCE, STUDIO_CAMERA, STUDIO_CAMERA_SOURCE, creation_order, object_code
from manim_studio.codegen.objects_extra import STUDIO_ANGLE, STUDIO_ANGLE_SOURCE, STUDIO_UNION, STUDIO_UNION_SOURCE
from manim_studio.codegen.three_d_code import camera_setup
from manim_studio.model.arrange import drawing_order
from manim_studio.model.entities import Project, Scene
from manim_studio.model.frame import ASPECTS, DEFAULT_ASPECT, frame_size
from manim_studio.model.state import visible_at_start
from manim_studio.model.three_d import is_3d
from manim_studio.model.types import UNADDED_KINDS, ObjectKind


@dataclass(frozen=True)
class CodegenOptions:
    """Options for :func:`generate_script`.

    ``base_dir`` resolves relative image paths, ``scene_ids`` limits the output
    to some scenes and ``stop_after_step`` cuts every scene after that step
    index (used to export a still image of an intermediate state).
    """

    base_dir: str | Path | None = None
    scene_ids: tuple[str, ...] | None = None
    stop_after_step: int | None = None
    #: Add a class that plays all scenes one after another (``JOINED_CLASS``).
    joined: bool = False
    #: Between joined scenes: ``"cut"`` or ``"fade"``.
    transition: str = "cut"


DEFAULT_OPTIONS = CodegenOptions()


Spans = dict[str, tuple[int, int]]


@dataclass
class SourceMap:
    """Which lines of the script belong to which object and step (0-based, inclusive)."""

    objects: dict[tuple[str, str], tuple[int, int]] = field(default_factory=dict)
    steps: dict[tuple[str, str], tuple[int, int]] = field(default_factory=dict)

    def object_at(self, line: int) -> tuple[str, str] | None:
        """``(scene_id, object_id)`` whose code contains ``line``."""
        return next((key for key, (first, last) in self.objects.items() if first <= line <= last), None)

    def step_at(self, line: int) -> tuple[str, str] | None:
        """``(scene_id, step_id)`` whose code contains ``line``."""
        return next((key for key, (first, last) in self.steps.items() if first <= line <= last), None)


def _object_lines(
    scene: Scene, names: dict[str, str], base_dir: str | Path | None, helpers: set[str], spans: Spans | None = None
) -> list[str]:
    lines: list[str] = []
    for obj in creation_order(scene):
        code = object_code(scene, obj, names, base_dir, helpers)
        if spans is not None and code:
            first = len(lines) + (1 if code[0] == "" else 0)
            spans[obj.id] = (first, len(lines) + len(code) - 1)
        lines += code
    return lines


def _updater_lines(scene: Scene, names: dict[str, str]) -> list[str]:
    """Coupled objects: ``add_updater`` that keeps them next to their target or on their formula."""
    from manim_studio.codegen.graph_code import renames
    from manim_studio.codegen.literals import fmt_float
    from manim_studio.model.attach import ATTACH_FOLLOW, ATTACH_FORMULA, attach_mode, follow_offset, follow_target, position_formulas

    lines: list[str] = []
    rename = renames(scene, names)
    for obj in scene.objects:
        mode = attach_mode(obj)
        if mode == ATTACH_FOLLOW:
            target = follow_target(scene, obj)
            if target is None or target.id not in names:
                raise CodegenError("attach_target_missing", obj.name)
            dx, dy = follow_offset(scene, obj, target)
            point = f"{names[target.id]}.get_center() + np.array([{fmt_float(dx)}, {fmt_float(dy)}, 0.0])"
        elif mode == ATTACH_FORMULA:
            formulas = position_formulas(scene, obj)
            if formulas is None:
                raise CodegenError("attach_formula_invalid", obj.name)
            x_code, y_code = (formula.to_numpy(rename, pad_variable=False) for formula in formulas)
            point = f"[{x_code}, {y_code}, 0.0]"
        else:
            continue
        if obj.kind == ObjectKind.CAMERA:
            lines.append(f"self.add({names[obj.id]})  # updaters only run on objects in the scene")
        lines.append(f"{names[obj.id]}.add_updater(lambda mob: mob.move_to({point}), call_updater=True)")
    return (["# Coupled objects move with their target or formula"] + lines) if lines else []


def _initial_add_line(scene: Scene, names: dict[str, str]) -> list[str]:
    # added from back to front, so the layers match the stage
    objects = [scene.object_by_id(object_id) for object_id in drawing_order(scene)]
    shown = [names[obj.id] for obj in objects if obj is not None and obj.kind not in UNADDED_KINDS and visible_at_start(scene, obj)]
    return [f"self.add({', '.join(shown)})"] if shown else []


def _timeline_lines(
    scene: Scene,
    names: dict[str, str],
    stop_after_step: int | None,
    helpers: set[str],
    base_dir: str | Path | None = None,
    spans: Spans | None = None,
) -> list[str]:
    steps = scene.steps if stop_after_step is None else scene.steps[: stop_after_step + 1]
    lines: list[str] = []
    played = False
    for number, step in enumerate(steps, start=1):
        block = step_code(step, number, scene, names, helpers, base_dir)
        played = played or len(block) > 1
        if lines:
            lines.append("")
        if spans is not None:
            spans[step.id] = (len(lines), len(lines) + len(block) - 1)
        lines += block
    if not played:
        if lines:
            lines.append("")
        lines += ["# Keep the scene visible for one second", "self.wait(1.0)"]
    return lines


def construct_body(
    scene: Scene, options: CodegenOptions = DEFAULT_OPTIONS, helpers: set[str] | None = None, spans: dict[str, Spans] | None = None
) -> list[str]:
    """Return the statements inside ``construct`` (without indentation).

    Names of helper definitions the body needs are added to ``helpers``;
    ``spans`` receives the line ranges of objects and steps.
    """
    helpers = helpers if helpers is not None else set()
    object_spans: Spans = {}
    step_spans: Spans = {}
    names = variable_names(scene)
    try:
        background = py_color(scene.background_color)
    except LiteralError:
        raise CodegenError("color_invalid", scene.background_color) from None
    lines = [f"self.camera.background_color = ManimColor({background})"]
    if is_3d(scene):
        lines += camera_setup(scene)
    object_lines = _object_lines(scene, names, options.base_dir, helpers, object_spans)
    if object_lines:
        _shift(object_spans, len(lines) + 1)
        lines += [""] + object_lines
    updaters = _updater_lines(scene, names)
    if updaters:
        lines += [""] + updaters
    add_line = _initial_add_line(scene, names)
    if add_line:
        lines += [""] + add_line
    timeline = _timeline_lines(scene, names, options.stop_after_step, helpers, options.base_dir, step_spans)
    _shift(step_spans, len(lines) + 1)
    lines += [""] + timeline
    if spans is not None:
        spans["objects"] = object_spans
        spans["steps"] = step_spans
    return lines


def _shift(spans: Spans, offset: int) -> None:
    for key, (first, last) in spans.items():
        spans[key] = (first + offset, last + offset)


def scene_class_code(
    scene: Scene,
    class_name: str,
    options: CodegenOptions = DEFAULT_OPTIONS,
    helpers: set[str] | None = None,
    spans: dict[str, Spans] | None = None,
) -> list[str]:
    """Return the full ``class ...(Scene)`` block of one scene (``spans`` count from its first line)."""
    if is_3d(scene):
        base = "ThreeDScene"
    else:
        base = "MovingCameraScene" if any(obj.kind == ObjectKind.CAMERA for obj in scene.objects) else "Scene"
    header = [f"class {class_name}({base}):", "    def construct(self):"]
    body = construct_body(scene, options, helpers, spans)
    if spans is not None:
        for group in spans.values():
            _shift(group, len(header))
    return header + indent_lines(body, 2)


def header_lines(first_class: str | None, aspect: str = DEFAULT_ASPECT) -> list[str]:
    """Return the comment and import block at the top of the script."""
    lines = [f"# Generated by Manim Studio {__version__}"]
    if first_class:
        lines.append(f"# Render with: manim -pql <this file> {first_class}")
    return lines + ["from manim import *", "import numpy as np"] + aspect_lines(aspect)


def aspect_lines(aspect: str) -> list[str]:
    """Configure the video format for formats other than 16:9."""
    if aspect not in ASPECTS or aspect == DEFAULT_ASPECT:
        return []
    width, height = ASPECTS[aspect]
    frame_width, _frame_height = frame_size(aspect)
    lines = ["", f"# Video format {aspect}", f"config.frame_width = {fmt_float(frame_width)}"]
    if width < height:
        lines += ["if config.pixel_width > config.pixel_height:", "    config.pixel_width, config.pixel_height = config.pixel_height, config.pixel_width"]
    elif width == height:
        lines.append("config.pixel_width = config.pixel_height = min(config.pixel_width, config.pixel_height)")
    else:
        lines.append(f"config.pixel_width = round(config.pixel_height * {width} / {height})")
    return lines


#: Name of the class that plays all scenes in a row.
JOINED_CLASS = "AllScenes"


def joined_class_code(project: Project, class_names_by_id: dict[str, str], scenes: list[Scene], transition: str) -> list[str]:
    """A scene that runs the ``construct`` of every scene one after another."""
    camera = any(obj.kind == ObjectKind.CAMERA for scene in scenes for obj in scene.objects)
    three_d = any(is_3d(scene) for scene in scenes)
    names = ", ".join(class_names_by_id[scene.id] for scene in scenes)
    base = "ThreeDScene" if three_d else "MovingCameraScene" if camera else "Scene"
    lines = [
        f"class {JOINED_CLASS}({base}):",
        '    """All scenes of the project, one after another."""',
        "",
        "    def construct(self):",
    ]
    if three_d:
        # the 3D camera gets a steerable frame, so 2D camera moves keep working
        lines.append(f"        {STUDIO_CAMERA}(self)")
    if camera or three_d:
        lines.append("        self.camera.frame.save_state()")
    lines.append(f"        for scene_class in ({names},):")
    if three_d:
        lines.append("            self.set_camera_orientation(phi=0, theta=-90 * DEGREES)")
    lines.append("            scene_class.construct(self)")
    if transition == "fade":
        lines += ["            if self.mobjects:", "                self.play(*[FadeOut(mobject) for mobject in self.mobjects], run_time=0.5)"]
    lines.append("            self.clear()")
    if camera or three_d:
        lines.append("            self.camera.frame.restore()")
    return lines


def generate_script(project: Project, options: CodegenOptions = DEFAULT_OPTIONS) -> str:
    """Generate the complete Python script for a project.

    The output is deterministic: the same model always yields the same text.
    Raises :class:`CodegenError` if the model cannot be expressed as valid code.
    """
    return generate_script_with_map(project, options)[0]


def generate_script_with_map(project: Project, options: CodegenOptions = DEFAULT_OPTIONS) -> tuple[str, SourceMap]:
    """Like :func:`generate_script`, plus the lines that belong to each object and step."""
    names = class_names(project)
    scenes = [s for s in project.scenes if options.scene_ids is None or s.id in options.scene_ids]
    if not scenes:
        raise CodegenError("no_scene")
    helpers: set[str] = set()
    blocks: list[str] = []
    local: list[tuple[Scene, int, dict[str, Spans]]] = []
    for scene in scenes:
        spans: dict[str, Spans] = {}
        blocks += ["", ""]
        local.append((scene, len(blocks), spans))
        blocks += scene_class_code(scene, names[scene.id], options, helpers, spans)
    if options.joined:
        if any(is_3d(scene) for scene in scenes):
            helpers.add(STUDIO_CAMERA)
        blocks += ["", ""] + joined_class_code(project, names, scenes, options.transition)
    lines = header_lines(JOINED_CLASS if options.joined else names[scenes[0].id], project.aspect)
    for name, source in ((COLOR_TEX, COLOR_TEX_SOURCE), (STUDIO_PLOT, STUDIO_PLOT_SOURCE), (STUDIO_INTEGRAL, STUDIO_INTEGRAL_SOURCE), (STUDIO_DASHED, STUDIO_DASHED_SOURCE), (STUDIO_LINES, STUDIO_LINES_SOURCE), (STUDIO_TERM, STUDIO_TERM_SOURCE), (STUDIO_BESIDE, STUDIO_BESIDE_SOURCE), (STUDIO_TRANSFORM, STUDIO_TRANSFORM_SOURCE), (STUDIO_SHAPE, STUDIO_SHAPE_SOURCE), (STUDIO_CAMERA, STUDIO_CAMERA_SOURCE), (STUDIO_ANGLE, STUDIO_ANGLE_SOURCE), (STUDIO_UNION, STUDIO_UNION_SOURCE)):
        if name in helpers:
            lines += ["", ""] + source.split("\n")
    source_map = SourceMap()
    for scene, start, spans in local:
        offset = len(lines) + start
        for object_id, (first, last) in spans.get("objects", {}).items():
            source_map.objects[(scene.id, object_id)] = (first + offset, last + offset)
        for step_id, (first, last) in spans.get("steps", {}).items():
            source_map.steps[(scene.id, step_id)] = (first + offset, last + offset)
    return "\n".join(lines + blocks) + "\n", source_map
