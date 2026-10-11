"""Load and save projects as JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from manim_studio.model.entities import (
    STEP_MODES,
    STEP_TOGETHER,
    Animation,
    Project,
    RenderSettings,
    Scene,
    SceneObject,
    Step,
)
from manim_studio.model.frame import ASPECTS, DEFAULT_ASPECT
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind, Visibility

FILE_FORMAT = "manim-studio-project"
FILE_VERSION = 1
FILE_SUFFIX = ".msproj"


class ProjectFormatError(ValueError):
    """Raised when a project file cannot be read."""


# --- to dict -----------------------------------------------------------------


def object_to_dict(obj: SceneObject) -> dict[str, Any]:
    """Convert an object into JSON-compatible data."""
    return {
        "id": obj.id,
        "kind": obj.kind.value,
        "name": obj.name,
        "x": obj.x,
        "y": obj.y,
        "rotation": obj.rotation,
        "stroke_color": obj.stroke_color,
        "fill_color": obj.fill_color,
        "stroke_width": obj.stroke_width,
        "stroke_opacity": obj.stroke_opacity,
        "fill_opacity": obj.fill_opacity,
        "z_index": obj.z_index,
        "visibility": obj.visibility.value,
        "params": dict(obj.params),
        "locked": obj.locked,
        "editor_hidden": obj.editor_hidden,
    }


def animation_to_dict(anim: Animation) -> dict[str, Any]:
    """Convert an animation into JSON-compatible data."""
    return {
        "id": anim.id,
        "kind": anim.kind.value,
        "target_id": anim.target_id,
        "run_time": anim.run_time,
        "rate_func": anim.rate_func,
        "params": dict(anim.params),
        "delay": anim.delay,
    }


def step_to_dict(step: Step) -> dict[str, Any]:
    """Convert a step into JSON-compatible data."""
    return {
        "id": step.id,
        "kind": step.kind.value,
        "wait_time": step.wait_time,
        "mode": step.mode,
        "lag_ratio": step.lag_ratio,
        "animations": [animation_to_dict(anim) for anim in step.animations],
        "section": step.section,
        "subcaption": step.subcaption,
        "sound": step.sound,
        "sound_gain": step.sound_gain,
        "sound_offset": step.sound_offset,
        "code": step.code,
    }


def scene_to_dict(scene: Scene) -> dict[str, Any]:
    """Convert a scene into JSON-compatible data."""
    return {
        "id": scene.id,
        "name": scene.name,
        "background_color": scene.background_color,
        "objects": [object_to_dict(obj) for obj in scene.objects],
        "steps": [step_to_dict(step) for step in scene.steps],
    }


def render_to_dict(settings: RenderSettings) -> dict[str, Any]:
    """Convert render settings into JSON-compatible data."""
    return {
        "quality": settings.quality,
        "width": settings.width,
        "height": settings.height,
        "fps": settings.fps,
        "format": settings.format,
        "output_dir": settings.output_dir,
        "png_after_step": settings.png_after_step,
        "transparent": settings.transparent,
        "scenes": settings.scenes,
        "transition": settings.transition,
        "save_sections": settings.save_sections,
    }


def project_to_dict(project: Project) -> dict[str, Any]:
    """Convert a whole project into JSON-compatible data."""
    return {
        "format": FILE_FORMAT,
        "version": FILE_VERSION,
        "scenes": [scene_to_dict(scene) for scene in project.scenes],
        "render": render_to_dict(project.render),
        "aspect": project.aspect,
    }


# --- from dict ---------------------------------------------------------------


def _enum(enum_type: type, value: Any, default: Any = None) -> Any:
    try:
        return enum_type(value)
    except ValueError:
        if default is not None:
            return default
        raise ProjectFormatError(f"unknown {enum_type.__name__}: {value!r}") from None


def object_from_dict(data: dict[str, Any]) -> SceneObject:
    """Create an object from JSON data."""
    return SceneObject(
        id=str(data["id"]),
        kind=_enum(ObjectKind, data["kind"]),
        name=str(data.get("name", "")),
        x=float(data.get("x", 0.0)),
        y=float(data.get("y", 0.0)),
        rotation=float(data.get("rotation", 0.0)),
        stroke_color=str(data.get("stroke_color", "#58C4DD")),
        fill_color=str(data.get("fill_color", "#58C4DD")),
        stroke_width=float(data.get("stroke_width", 4.0)),
        stroke_opacity=float(data.get("stroke_opacity", 1.0)),
        fill_opacity=float(data.get("fill_opacity", 0.0)),
        z_index=int(data.get("z_index", 0)),
        visibility=_enum(Visibility, data.get("visibility", "auto"), Visibility.AUTO),
        params=dict(data.get("params", {})),
        locked=bool(data.get("locked", False)),
        editor_hidden=bool(data.get("editor_hidden", False)),
    )


def animation_from_dict(data: dict[str, Any]) -> Animation:
    """Create an animation from JSON data."""
    return Animation(
        id=str(data["id"]),
        kind=_enum(AnimationKind, data["kind"]),
        target_id=str(data.get("target_id", "")),
        run_time=float(data.get("run_time", 1.0)),
        rate_func=str(data.get("rate_func", "smooth")),
        params=dict(data.get("params", {})),
        delay=float(data.get("delay", 0.0)),
    )


def step_from_dict(data: dict[str, Any]) -> Step:
    """Create a step from JSON data."""
    return Step(
        id=str(data["id"]),
        kind=_enum(StepKind, data.get("kind", "play")),
        wait_time=float(data.get("wait_time", 1.0)),
        animations=[animation_from_dict(item) for item in data.get("animations", [])],
        mode=str(data.get("mode", STEP_TOGETHER)) if data.get("mode") in STEP_MODES else STEP_TOGETHER,
        lag_ratio=float(data.get("lag_ratio", 0.25)),
        section=str(data.get("section", "")),
        subcaption=str(data.get("subcaption", "")),
        sound=str(data.get("sound", "")),
        sound_gain=float(data.get("sound_gain", 0.0)),
        sound_offset=float(data.get("sound_offset", 0.0)),
        code=str(data.get("code", "")),
    )


def scene_from_dict(data: dict[str, Any]) -> Scene:
    """Create a scene from JSON data."""
    return Scene(
        id=str(data["id"]),
        name=str(data.get("name", "Scene")),
        background_color=str(data.get("background_color", "#000000")),
        objects=[object_from_dict(item) for item in data.get("objects", [])],
        steps=[step_from_dict(item) for item in data.get("steps", [])],
    )


def render_from_dict(data: dict[str, Any]) -> RenderSettings:
    """Create render settings from JSON data."""
    defaults = RenderSettings()
    return RenderSettings(
        quality=str(data.get("quality", defaults.quality)),
        width=int(data.get("width", defaults.width)),
        height=int(data.get("height", defaults.height)),
        fps=int(data.get("fps", defaults.fps)),
        format=str(data.get("format", defaults.format)),
        output_dir=str(data.get("output_dir", defaults.output_dir)),
        png_after_step=int(data.get("png_after_step", defaults.png_after_step)),
        transparent=bool(data.get("transparent", defaults.transparent)),
        scenes=str(data.get("scenes", defaults.scenes)),
        transition=str(data.get("transition", defaults.transition)),
        save_sections=bool(data.get("save_sections", defaults.save_sections)),
    )


def project_from_dict(data: dict[str, Any]) -> Project:
    """Create a project from JSON data or raise :class:`ProjectFormatError`."""
    if not isinstance(data, dict) or data.get("format") != FILE_FORMAT:
        raise ProjectFormatError("not a Manim Studio project")
    if int(data.get("version", 0)) > FILE_VERSION:
        raise ProjectFormatError("project was created by a newer version")
    try:
        scenes = [scene_from_dict(item) for item in data.get("scenes", [])]
        render = render_from_dict(data.get("render", {}))
    except (KeyError, TypeError, ValueError) as error:
        raise ProjectFormatError(str(error)) from error
    if not scenes:
        raise ProjectFormatError("project contains no scene")
    aspect = str(data.get("aspect", DEFAULT_ASPECT))
    return Project(scenes=scenes, render=render, aspect=aspect if aspect in ASPECTS else DEFAULT_ASPECT)


# --- files -------------------------------------------------------------------


def dumps_project(project: Project) -> str:
    """Serialize a project to a JSON string."""
    return json.dumps(project_to_dict(project), indent=2, ensure_ascii=False)


def loads_project(text: str) -> Project:
    """Parse a project from a JSON string."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ProjectFormatError(str(error)) from error
    return project_from_dict(data)


def save_project(project: Project, path: str | Path) -> None:
    """Write a project file atomically."""
    target = Path(path)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(dumps_project(project), encoding="utf-8")
    temporary.replace(target)


def load_project(path: str | Path) -> Project:
    """Read a project file."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise ProjectFormatError(str(error)) from error
    return loads_project(text)
