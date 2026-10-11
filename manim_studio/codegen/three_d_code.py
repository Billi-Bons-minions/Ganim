"""Code generation for the limited 3D support (``ThreeDScene``)."""

from __future__ import annotations

from manim_studio.codegen.errors import CodegenError
from manim_studio.codegen.formatting import call
from manim_studio.codegen.literals import fmt_float, py_color, py_range
from manim_studio.model import graphs
from manim_studio.model.entities import Animation, Scene, SceneObject
from manim_studio.model.geometry import param_float
from manim_studio.model.three_d import DEFAULT_PHI, DEFAULT_THETA, axes_of, surface_expression
from manim_studio.model.types import ObjectKind


def orientation_line(phi: float, theta: float) -> str:
    return f"self.set_camera_orientation(phi={fmt_float(phi)} * DEGREES, theta={fmt_float(theta)} * DEGREES)"


def camera_setup(scene: Scene) -> list[str]:
    """Initial 3D camera orientation (from the camera object or the default)."""
    camera = next((obj for obj in scene.objects if obj.kind == ObjectKind.CAMERA), None)
    if camera is None:
        return [orientation_line(DEFAULT_PHI, DEFAULT_THETA)]
    return [orientation_line(param_float(camera.params, "phi", DEFAULT_PHI), param_float(camera.params, "theta", DEFAULT_THETA))]


def axes_3d_code(obj: SceneObject) -> list[str]:
    kwargs = []
    for axis in ("x", "y", "z"):
        kwargs.append((f"{axis}_range", py_range(param_float(obj.params, f"{axis}_min", -4.0), param_float(obj.params, f"{axis}_max", 4.0), param_float(obj.params, f"{axis}_step", 1.0))))
    for axis in ("x", "y", "z"):
        kwargs.append((f"{axis}_length", fmt_float(param_float(obj.params, f"{axis}_length", 6.0))))
    kwargs.append(("axis_config", f'{{"color": {py_color(obj.stroke_color)}, "stroke_width": {fmt_float(obj.stroke_width)}}}'))
    return call("ThreeDAxes", [], kwargs, 2)


def _axes_variable(scene: Scene, obj: SceneObject, names: dict[str, str]) -> str:
    axes = axes_of(scene, obj)
    if axes is None or axes.id not in names:
        raise CodegenError("axes_3d_missing", obj.name)
    return names[axes.id]


def surface_code(scene: Scene, obj: SceneObject, names: dict[str, str], rename: dict[str, str]) -> list[str]:
    axes = _axes_variable(scene, obj, names)
    expression = surface_expression(obj, graphs.parameter_symbols(scene))
    if expression is None:
        raise CodegenError("expression_invalid", obj.name)
    code = expression.to_numpy(rename)
    if "y" not in code:
        code = f"{code} + 0 * y"
    steps = int(param_float(obj.params, "resolution", 24))
    kwargs = [
        ("u_range", py_range(param_float(obj.params, "x_min", -3.0), param_float(obj.params, "x_max", 3.0))),
        ("v_range", py_range(param_float(obj.params, "y_min", -3.0), param_float(obj.params, "y_max", 3.0))),
        ("resolution", f"({steps}, {steps})"),
        ("checkerboard_colors", "False"),
        ("fill_color", py_color(obj.fill_color)),
        ("fill_opacity", fmt_float(obj.fill_opacity)),
        ("stroke_color", py_color(obj.stroke_color)),
        ("stroke_width", fmt_float(obj.stroke_width)),
    ]
    return call("Surface", [f"lambda x, y: {axes}.c2p(x, y, {code})"], kwargs, 2)


def curve_3d_code(scene: Scene, obj: SceneObject, names: dict[str, str], rename: dict[str, str]) -> list[str]:
    axes = _axes_variable(scene, obj, names)
    parts = []
    for key in ("x_expression", "y_expression", "z_expression"):
        expression = graphs.parse(scene, str(obj.params.get(key, "")), "t")
        if expression is None:
            raise CodegenError("expression_invalid", obj.name)
        parts.append(expression.to_numpy(rename))
    kwargs = [
        ("t_range", py_range(param_float(obj.params, "t_min", -6.2832), param_float(obj.params, "t_max", 6.2832))),
        ("color", py_color(obj.stroke_color)),
        ("stroke_width", fmt_float(obj.stroke_width)),
    ]
    return call(f"{axes}.plot_parametric_curve", [f"lambda t: np.array([{', '.join(parts)}])"], kwargs, 2)


def orbit_call(anim: Animation, timing_args: list[str], added: list[str]) -> str:
    """``self.move_camera(...)`` for a camera orbit, other animations of the step run along."""
    arguments = [
        f"phi={fmt_float(float(anim.params.get('phi', DEFAULT_PHI)))} * DEGREES",
        f"theta={fmt_float(float(anim.params.get('theta', DEFAULT_THETA)))} * DEGREES",
    ] + timing_args
    if added:
        arguments.append(f"added_anims=[{', '.join(added)}]")
    return f"self.move_camera({', '.join(arguments)})"
