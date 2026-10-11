"""Code generation for timeline steps and animations."""

from __future__ import annotations

from manim_studio.codegen.errors import CodegenError
from manim_studio.codegen.formatting import INDENT
from manim_studio.codegen.literals import (
    LiteralError,
    fmt_float,
    py_color,
    py_degrees,
    py_point,
)
from manim_studio.model.entities import Animation, Scene, Step
from manim_studio.model.schema import animation_allowed
from manim_studio.model.types import (
    MODIFIER_ANIMATIONS,
    RATE_FUNCTIONS,
    TRANSFORM_ANIMATIONS,
    AnimationKind,
    StepKind,
)

#: Manim class for every animation that is generated as a plain call.
ANIMATION_CLASSES: dict[AnimationKind, str] = {
    AnimationKind.CREATE: "Create",
    AnimationKind.WRITE: "Write",
    AnimationKind.DRAW_BORDER_THEN_FILL: "DrawBorderThenFill",
    AnimationKind.FADE_IN: "FadeIn",
    AnimationKind.FADE_OUT: "FadeOut",
    AnimationKind.GROW_FROM_CENTER: "GrowFromCenter",
    AnimationKind.TRANSFORM: "Transform",
    AnimationKind.REPLACEMENT_TRANSFORM: "ReplacementTransform",
    AnimationKind.ROTATE: "Rotate",
    AnimationKind.INDICATE: "Indicate",
    AnimationKind.CIRCUMSCRIBE: "Circumscribe",
    AnimationKind.UNCREATE: "Uncreate",
}

SHIFT_DIRECTIONS = {"up": "UP", "down": "DOWN", "left": "LEFT", "right": "RIGHT"}


def rate_func_code(name: str) -> str:
    """Return the Python expression of a rate function."""
    if name not in RATE_FUNCTIONS:
        raise CodegenError("rate_func_unknown", name)
    return RATE_FUNCTIONS[name]


def _timing(run_time: float, rate_func: str) -> list[str]:
    if run_time <= 0:
        raise CodegenError("run_time_invalid", fmt_float(run_time))
    return [f"run_time={fmt_float(run_time)}", f"rate_func={rate_func_code(rate_func)}"]


def _variable(names: dict[str, str], object_id: object) -> str:
    if object_id not in names:
        raise CodegenError("animation_target_missing", str(object_id))
    return names[str(object_id)]


def _extra_arguments(anim: Animation, scene: Scene, names: dict[str, str]) -> list[str]:
    params = anim.params
    if anim.kind in TRANSFORM_ANIMATIONS:
        target = params.get("target")
        if target == anim.target_id:
            raise CodegenError("transform_target_self", names.get(anim.target_id, ""))
        if target not in names:
            raise CodegenError("transform_target_missing", names.get(anim.target_id, ""))
        other = scene.object_by_id(str(target))
        if other is not None and not animation_allowed(anim.kind, other.kind, other.params):
            raise CodegenError("animation_incompatible", names[str(target)])
        return [names[str(target)]]
    if anim.kind in (AnimationKind.FADE_IN, AnimationKind.FADE_OUT):
        direction = SHIFT_DIRECTIONS.get(str(params.get("shift", "none")))
        return [f"shift={direction}"] if direction else []
    if anim.kind == AnimationKind.ROTATE:
        return [f"angle={py_degrees(float(params.get('angle', 0.0)))}"]
    if anim.kind == AnimationKind.INDICATE:
        return [
            f"color={py_color(str(params.get('color', '')))}",
            f"scale_factor={fmt_float(float(params.get('scale_factor', 1.2)))}",
        ]
    if anim.kind == AnimationKind.CIRCUMSCRIBE:
        return [f"color={py_color(str(params.get('color', '')))}"]
    return []


def simple_animation_code(anim: Animation, scene: Scene, names: dict[str, str]) -> str:
    """Return e.g. ``Create(circle, run_time=1.0, rate_func=smooth)``."""
    variable = _variable(names, anim.target_id)
    target = scene.object_by_id(anim.target_id)
    if target is not None and not animation_allowed(anim.kind, target.kind, target.params):
        raise CodegenError("animation_incompatible", variable)
    arguments = [variable] + _extra_arguments(anim, scene, names) + _timing(anim.run_time, anim.rate_func)
    return f"{ANIMATION_CLASSES[anim.kind]}({', '.join(arguments)})"


def _modifier_call(anim: Animation) -> str:
    params = anim.params
    if anim.kind == AnimationKind.MOVE:
        return f".move_to({py_point(float(params.get('x', 0.0)), float(params.get('y', 0.0)))})"
    if anim.kind == AnimationKind.SCALE:
        return f".scale({fmt_float(float(params.get('factor', 1.0)))})"
    if anim.kind == AnimationKind.ROTATE:
        return f".rotate({py_degrees(float(params.get('angle', 0.0)))})"
    color = py_color(str(params.get("color", "")))
    apply_to = params.get("apply_to", "both")
    if apply_to == "stroke":
        return f".set_stroke(color={color})"
    if apply_to == "fill":
        return f".set_fill(color={color})"
    return f".set_color({color})"


def modifier_group_code(group: list[Animation], scene: Scene, names: dict[str, str]) -> str:
    """Combine Move/Scale/Rotate/Color animations of one object into one expression."""
    if len(group) == 1 and group[0].kind == AnimationKind.ROTATE:
        return simple_animation_code(group[0], scene, names)
    first = group[0]
    variable = _variable(names, first.target_id)
    target = scene.object_by_id(first.target_id)
    for anim in group:
        if target is not None and not animation_allowed(anim.kind, target.kind, target.params):
            raise CodegenError("animation_incompatible", variable)
    options = _timing(max(anim.run_time for anim in group), first.rate_func)
    angle = sum(float(anim.params.get("angle", 0.0)) for anim in group if anim.kind == AnimationKind.ROTATE)
    if any(anim.kind == AnimationKind.ROTATE for anim in group) and round(angle, 6) != 0:
        options.append(f"path_arc={py_degrees(angle)}")
    chain = "".join(_modifier_call(anim) for anim in group)
    return f"{variable}.animate({', '.join(options)}){chain}"


def step_animation_codes(step: Step, scene: Scene, names: dict[str, str]) -> list[str]:
    """Return one expression per animation group of a play step."""
    groups: dict[str, list[Animation]] = {}
    order: list[tuple[str, object]] = []
    for anim in step.animations:
        if anim.kind in MODIFIER_ANIMATIONS:
            if anim.target_id not in groups:
                groups[anim.target_id] = []
                order.append(("group", anim.target_id))
            groups[anim.target_id].append(anim)
        else:
            order.append(("single", anim))
    codes: list[str] = []
    for kind, item in order:
        if kind == "group":
            codes.append(modifier_group_code(groups[str(item)], scene, names))
        else:
            assert isinstance(item, Animation)
            codes.append(simple_animation_code(item, scene, names))
    return codes


def step_code(step: Step, number: int, scene: Scene, names: dict[str, str]) -> list[str]:
    """Return the lines of one timeline step (comment + ``self.play``/``self.wait``)."""
    header = f"# Step {number}"
    if step.kind == StepKind.WAIT:
        if step.wait_time <= 0:
            raise CodegenError("wait_time_invalid", str(number))
        return [header, f"self.wait({fmt_float(step.wait_time)})"]
    try:
        codes = step_animation_codes(step, scene, names)
    except LiteralError as error:
        raise CodegenError("value_invalid", f"step {number}: {error}") from None
    if not codes:
        return [f"{header}: no animations"]
    if len(codes) == 1:
        return [header, f"self.play({codes[0]})"]
    return [header, "self.play("] + [f"{INDENT}{code}," for code in codes] + [")"]
