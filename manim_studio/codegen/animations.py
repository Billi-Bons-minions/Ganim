"""Code generation for timeline steps and animations."""

from __future__ import annotations

from dataclasses import dataclass

from manim_studio.codegen.errors import CodegenError
from manim_studio.codegen.formatting import INDENT, MAX_LINE
from manim_studio.codegen.literals import LiteralError, fmt_float, py_color, py_degrees, py_point
from manim_studio.model.entities import STEP_LAGGED, STEP_SEQUENCE, Animation, Scene, Step
from manim_studio.model.schema import animation_allowed
from manim_studio.model.types import MODIFIER_ANIMATIONS, RATE_FUNCTIONS, TRANSFORM_ANIMATIONS, AnimationKind, StepKind

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

#: Name of the helper class emitted into scripts that need individual timing.
STUDIO_TRANSFORM = "StudioTransform"


@dataclass(frozen=True)
class Timing:
    """``run_time`` and rate function code of one generated animation."""

    run_time: float
    rate_func: str

    def args(self) -> list[str]:
        return [f"run_time={fmt_float(self.run_time)}", f"rate_func={self.rate_func}"]


def rate_func_code(name: str) -> str:
    """Return the Python expression of a rate function."""
    if name not in RATE_FUNCTIONS:
        raise CodegenError("rate_func_unknown", name)
    return RATE_FUNCTIONS[name]


def _check_run_time(run_time: float) -> None:
    if run_time <= 0:
        raise CodegenError("run_time_invalid", fmt_float(run_time))


def plain_timing(anim: Animation) -> Timing:
    """Timing without delay: the animation's own run time and rate function."""
    _check_run_time(anim.run_time)
    return Timing(anim.run_time, rate_func_code(anim.rate_func))


def delayed_timing(anim: Animation, total: float) -> Timing:
    """Stretch an animation over ``total`` seconds and squish it after its delay."""
    _check_run_time(anim.run_time)
    rate = rate_func_code(anim.rate_func)
    if anim.delay <= 0 or total <= 0:
        return Timing(anim.run_time, rate)
    start = anim.delay / total
    end = (anim.delay + anim.run_time) / total
    return Timing(total, f"squish_rate_func({rate}, {fmt_float(start)}, {fmt_float(end)})")


def _variable(names: dict[str, str], object_id: object) -> str:
    if object_id not in names:
        raise CodegenError("animation_target_missing", str(object_id))
    return names[str(object_id)]


def _check_allowed(anim: Animation, scene: Scene, names: dict[str, str]) -> None:
    target = scene.object_by_id(anim.target_id)
    if target is not None and not animation_allowed(anim.kind, target.kind, target.params):
        raise CodegenError("animation_incompatible", names.get(anim.target_id, ""))


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


def simple_animation_code(anim: Animation, scene: Scene, names: dict[str, str], timing: Timing | None = None) -> str:
    """Return e.g. ``Create(circle, run_time=1.0, rate_func=smooth)``."""
    variable = _variable(names, anim.target_id)
    _check_allowed(anim, scene, names)
    timing = timing or plain_timing(anim)
    arguments = [variable] + _extra_arguments(anim, scene, names) + timing.args()
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


def _studio_part(anim: Animation, begin: float) -> str:
    params = anim.params
    rate = rate_func_code(anim.rate_func)
    timing = f"{fmt_float(begin)}, {fmt_float(anim.run_time)}, {rate}"
    if anim.kind == AnimationKind.MOVE:
        return f'("move", {timing}, {py_point(float(params.get("x", 0.0)), float(params.get("y", 0.0)))})'
    if anim.kind == AnimationKind.SCALE:
        return f'("scale", {timing}, {fmt_float(float(params.get("factor", 1.0)))})'
    if anim.kind == AnimationKind.ROTATE:
        return f'("rotate", {timing}, {py_degrees(float(params.get("angle", 0.0)))})'
    mode = {"stroke": "stroke", "fill": "fill"}.get(str(params.get("apply_to", "both")), "color")
    return f'("{mode}", {timing}, {py_color(str(params.get("color", "")))})'


def studio_transform_code(group: list[Animation], names: dict[str, str], offsets: list[float], helpers: set[str]) -> str:
    """Return a ``StudioTransform`` that runs modifiers with individual timing."""
    helpers.add(STUDIO_TRANSFORM)
    variable = _variable(names, group[0].target_id)
    for anim in group:
        _check_run_time(anim.run_time)
    parts = [_studio_part(anim, offset) for anim, offset in zip(group, offsets)]
    total = max(offset + anim.run_time for anim, offset in zip(group, offsets))
    return f"{STUDIO_TRANSFORM}({variable}, [{', '.join(parts)}], run_time={fmt_float(total)})"


def _same_timing(group: list[Animation]) -> bool:
    first = group[0]
    return all((a.delay, a.run_time, a.rate_func) == (first.delay, first.run_time, first.rate_func) for a in group)


def modifier_group_code(group: list[Animation], scene: Scene, names: dict[str, str], total: float, helpers: set[str]) -> str:
    """Combine Move/Scale/Rotate/Color animations of one object (together mode)."""
    for anim in group:
        _check_allowed(anim, scene, names)
    if not _same_timing(group):
        return studio_transform_code(group, names, [anim.delay for anim in group], helpers)
    first = group[0]
    timing = delayed_timing(first, total)
    if len(group) == 1 and first.kind == AnimationKind.ROTATE:
        return simple_animation_code(first, scene, names, timing)
    options = timing.args()
    angle = sum(float(anim.params.get("angle", 0.0)) for anim in group if anim.kind == AnimationKind.ROTATE)
    if any(anim.kind == AnimationKind.ROTATE for anim in group) and round(angle, 6) != 0:
        options.append(f"path_arc={py_degrees(angle)}")
    chain = "".join(_modifier_call(anim) for anim in group)
    return f"{_variable(names, first.target_id)}.animate({', '.join(options)}){chain}"


#: Effects that :class:`StudioTransform` can combine with movements.
COMBINABLE = {
    AnimationKind.CREATE: "create",
    AnimationKind.WRITE: "create",
    AnimationKind.DRAW_BORDER_THEN_FILL: "create",
    AnimationKind.UNCREATE: "uncreate",
    AnimationKind.FADE_IN: "fade_in",
    AnimationKind.FADE_OUT: "fade_out",
    AnimationKind.GROW_FROM_CENTER: "grow",
    AnimationKind.INDICATE: "indicate",
}

_SHIFT_VECTORS = {"up": (0.0, 1.0), "down": (0.0, -1.0), "left": (-1.0, 0.0), "right": (1.0, 0.0)}


def _effect_part(anim: Animation, begin: float) -> str:
    kind = COMBINABLE[anim.kind]
    rate = rate_func_code(anim.rate_func)
    timing = f"{fmt_float(begin)}, {fmt_float(anim.run_time)}, {rate}"
    if kind in ("fade_in", "fade_out"):
        dx, dy = _SHIFT_VECTORS.get(str(anim.params.get("shift", "none")), (0.0, 0.0))
        return f'("{kind}", {timing}, {py_point(dx, dy)})'
    if kind == "indicate":
        color = py_color(str(anim.params.get("color", "")))
        return f'("indicate", {timing}, ({color}, {fmt_float(float(anim.params.get("scale_factor", 1.2)))}))'
    return f'("{kind}", {timing}, None)'


def combined_code(animations: list[Animation], scene: Scene, names: dict[str, str], helpers: set[str]) -> str:
    """One :class:`StudioTransform` for an object with effects and movements in one step."""
    helpers.add(STUDIO_TRANSFORM)
    variable = _variable(names, animations[0].target_id)
    parts = []
    for anim in animations:
        _check_allowed(anim, scene, names)
        _check_run_time(anim.run_time)
        parts.append(_studio_part(anim, anim.delay) if anim.kind in MODIFIER_ANIMATIONS else _effect_part(anim, anim.delay))
    total = max(anim.delay + anim.run_time for anim in animations)
    return f"{STUDIO_TRANSFORM}({variable}, [{', '.join(parts)}], run_time={fmt_float(total)})"


def needs_combination(animations: list[Animation]) -> bool:
    """Return ``True`` if one object's animations must be merged into a StudioTransform."""
    modifiers = [anim for anim in animations if anim.kind in MODIFIER_ANIMATIONS]
    effects = [anim for anim in animations if anim.kind in COMBINABLE]
    return bool(modifiers) and bool(effects)


def _check_transform_conflicts(step: Step, names: dict[str, str]) -> None:
    transformed = {anim.target_id for anim in step.animations if anim.kind in TRANSFORM_ANIMATIONS}
    for anim in step.animations:
        if anim.kind in MODIFIER_ANIMATIONS | set(COMBINABLE) and anim.target_id in transformed:
            raise CodegenError("transform_conflict", names.get(anim.target_id, ""))


def _together_codes(step: Step, scene: Scene, names: dict[str, str], helpers: set[str]) -> list[str]:
    _check_transform_conflicts(step, names)
    total = step.duration()
    by_target: dict[str, list[Animation]] = {}
    for anim in step.animations:
        by_target.setdefault(anim.target_id, []).append(anim)
    combined = {target for target, anims in by_target.items() if needs_combination(anims)}
    groups: dict[str, list[Animation]] = {}
    order: list[tuple[str, object]] = []
    for anim in step.animations:
        if anim.target_id in combined:
            if ("combined", anim.target_id) not in order:
                order.append(("combined", anim.target_id))
            continue
        if anim.kind in MODIFIER_ANIMATIONS:
            if anim.target_id not in groups:
                groups[anim.target_id] = []
                order.append(("group", anim.target_id))
            groups[anim.target_id].append(anim)
        else:
            order.append(("single", anim))
    codes: list[str] = []
    for kind, item in order:
        if kind == "combined":
            members = [anim for anim in by_target[str(item)] if anim.kind in MODIFIER_ANIMATIONS or anim.kind in COMBINABLE]
            codes.append(combined_code(members, scene, names, helpers))
            codes += [
                simple_animation_code(anim, scene, names, delayed_timing(anim, total))
                for anim in by_target[str(item)]
                if anim not in members
            ]
        elif kind == "group":
            codes.append(modifier_group_code(groups[str(item)], scene, names, total, helpers))
        else:
            assert isinstance(item, Animation)
            codes.append(simple_animation_code(item, scene, names, delayed_timing(item, total)))
    return codes


def _ordered_codes(step: Step, scene: Scene, names: dict[str, str], helpers: set[str]) -> list[str]:
    """Codes for staggered or sequential steps (each animation separately)."""
    codes: list[str] = []
    seen: set[str] = set()
    for anim in step.animations:
        if step.mode == STEP_SEQUENCE and anim.delay > 0:
            codes.append(f"Wait(run_time={fmt_float(anim.delay)})")
        if anim.kind in MODIFIER_ANIMATIONS:
            _check_allowed(anim, scene, names)
            if anim.target_id in seen:
                codes.append(studio_transform_code([anim], names, [0.0], helpers))
            else:
                codes.append(modifier_group_code([_without_delay(anim)], scene, names, 0.0, helpers))
        else:
            codes.append(simple_animation_code(anim, scene, names))
        seen.add(anim.target_id)
        target = anim.params.get("target")
        if target:
            seen.add(str(target))
    return codes


def _without_delay(anim: Animation) -> Animation:
    return Animation(anim.id, anim.kind, anim.target_id, anim.run_time, anim.rate_func, dict(anim.params), 0.0)


def step_animation_codes(step: Step, scene: Scene, names: dict[str, str], helpers: set[str] | None = None) -> list[str]:
    """Return the expressions passed to ``self.play`` for a play step."""
    helpers = helpers if helpers is not None else set()
    if step.mode in (STEP_LAGGED, STEP_SEQUENCE):
        codes = _ordered_codes(step, scene, names, helpers)
        if not codes:
            return []
        if step.mode == STEP_LAGGED:
            return [_wrap("LaggedStart", codes, [f"lag_ratio={fmt_float(step.lag_ratio)}"])]
        return [_wrap("Succession", codes, [])]
    return _together_codes(step, scene, names, helpers)


def _wrap(function: str, codes: list[str], options: list[str]) -> str:
    single = f"{function}({', '.join(codes + options)})"
    if len(single) + 8 <= MAX_LINE:
        return single
    inner = [f"{INDENT}{code}," for code in codes + options]
    return "\n".join([f"{function}("] + inner + [")"])


def _indent_block(code: str) -> list[str]:
    lines = code.split("\n")
    return [f"{INDENT}{lines[0]}"] + [f"{INDENT}{line}" for line in lines[1:]]


def step_code(step: Step, number: int, scene: Scene, names: dict[str, str], helpers: set[str] | None = None) -> list[str]:
    """Return the lines of one timeline step (comment + ``self.play``/``self.wait``)."""
    header = f"# Step {number}"
    if step.kind == StepKind.WAIT:
        if step.wait_time <= 0:
            raise CodegenError("wait_time_invalid", str(number))
        return [header, f"self.wait({fmt_float(step.wait_time)})"]
    try:
        codes = step_animation_codes(step, scene, names, helpers)
    except LiteralError as error:
        raise CodegenError("value_invalid", f"step {number}: {error}") from None
    if not codes:
        return [f"{header}: no animations"]
    if len(codes) == 1 and "\n" not in codes[0]:
        return [header, f"self.play({codes[0]})"]
    lines = [header, "self.play("]
    for code in codes:
        block = _indent_block(code)
        block[-1] += ","
        lines += block
    return lines + [")"]


#: Source of the helper class, emitted once per script when needed.
STUDIO_TRANSFORM_SOURCE = '''class StudioTransform(Animation):
    """Animate one object with several effects, each with its own timing.

    ``parts`` contains tuples ``(kind, start, duration, rate_func, value)``.
    Geometry (move, scale, rotate), colors and visibility effects (create,
    fade, grow, indicate) are combined, which Manim cannot do with separate
    animations on the same object.
    """

    VISIBILITY = ("create", "uncreate", "fade_in", "fade_out", "grow", "indicate")

    def __init__(self, mobject, parts, **kwargs):
        self.parts = parts
        exits = [part for part in parts if part[0] in ("uncreate", "fade_out")]
        super().__init__(mobject, rate_func=linear, remover=bool(exits), **kwargs)

    def begin(self):
        self.start = self.mobject.copy()
        self.start_center = self.mobject.get_center()
        super().begin()

    def _progress(self, time, start, duration, rate_func):
        if duration <= 0:
            return 1.0
        return rate_func(min(max((time - start) / duration, 0.0), 1.0))

    def _apply(self, time, visibility):
        mobject = self.mobject
        mobject.become(self.start)
        center = np.array(self.start_center)
        for kind, start, duration, rate_func, value in self.parts:
            progress = self._progress(time, start, duration, rate_func)
            if kind == "scale":
                mobject.scale(1 + (value - 1) * progress)
            elif kind == "rotate":
                mobject.rotate(value * progress)
            elif kind == "move":
                center = center + (np.array(value) - self.start_center) * progress
            elif kind == "stroke":
                mobject.set_stroke(color=interpolate_color(self.start.get_stroke_color(), ManimColor(value), progress))
            elif kind == "fill":
                mobject.set_fill(color=interpolate_color(self.start.get_fill_color(), ManimColor(value), progress))
            elif kind == "color":
                mobject.set_color(interpolate_color(self.start.get_color(), ManimColor(value), progress))
            elif visibility and kind == "grow":
                mobject.scale(max(progress, 1e-3))
            elif visibility and kind == "indicate":
                mobject.scale(1 + (value[1] - 1) * progress)
                mobject.set_color(interpolate_color(self.start.get_color(), ManimColor(value[0]), progress))
            elif visibility and kind == "fade_in":
                mobject.fade(1 - progress)
                center = center - np.array(value) * (1 - progress)
            elif visibility and kind == "fade_out":
                mobject.fade(progress)
                center = center + np.array(value) * progress
        mobject.move_to(center)
        if visibility:
            for kind, start, duration, rate_func, _value in self.parts:
                if kind in ("create", "uncreate"):
                    progress = self._progress(time, start, duration, rate_func)
                    shown = progress if kind == "create" else 1 - progress
                    mobject.pointwise_become_partial(mobject.copy(), 0, shown)

    def interpolate_mobject(self, alpha):
        self._apply(alpha * self.run_time, visibility=True)

    def clean_up_from_scene(self, scene):
        super().clean_up_from_scene(scene)
        if self.remover:
            self._apply(self.run_time, visibility=False)'''
