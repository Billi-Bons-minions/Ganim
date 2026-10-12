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


_SURFACE_SOLIDS = {"sphere": "Sphere", "cone": "Cone", "cylinder": "Cylinder", "torus": "Torus"}


def solid_code(scene: Scene, obj: SceneObject, names: dict[str, str]) -> list[str]:
    """Sphere, cube, prism, cone, cylinder or torus placed at a point of its 3D axes."""
    axes = _axes_variable(scene, obj, names)
    p = obj.params
    shape = p.get("shape", "sphere")
    point = f"{axes}.c2p({', '.join(fmt_float(param_float(p, key, 0.0)) for key in ('center_x', 'center_y', 'center_z'))})"
    style = [
        ("fill_color", py_color(obj.fill_color)),
        ("fill_opacity", fmt_float(obj.fill_opacity)),
        ("stroke_color", py_color(obj.stroke_color)),
        ("stroke_width", fmt_float(obj.stroke_width)),
    ]
    n = max(4, min(48, int(p.get("resolution", 16))))
    if shape == "cube":
        return _placed(call("Cube", [], [("side_length", fmt_float(param_float(p, "side", 2.0)))] + style, 2), point)
    if shape == "prism":
        dimensions = f"[{', '.join(fmt_float(param_float(p, key, default)) for key, default in (('width', 3.0), ('depth', 2.0), ('height', 1.0)))}]"
        return _placed(call("Prism", [], [("dimensions", dimensions)] + style, 2), point)
    size = {
        "sphere": [("radius", fmt_float(param_float(p, "radius", 1.0))), ("resolution", f"({2 * n}, {n})")],
        "cone": [("base_radius", fmt_float(param_float(p, "radius", 1.0))), ("height", fmt_float(param_float(p, "height", 2.0))), ("show_base", "True"), ("resolution", f"({n}, {2 * n})")],
        "cylinder": [("radius", fmt_float(param_float(p, "radius", 1.0))), ("height", fmt_float(param_float(p, "height", 2.0))), ("resolution", f"(2, {2 * n})")],
        "torus": [("major_radius", fmt_float(param_float(p, "radius", 1.0))), ("minor_radius", fmt_float(param_float(p, "minor_radius", 0.3))), ("resolution", f"({2 * n}, {n})")],
    }[shape if shape in _SURFACE_SOLIDS else "sphere"]
    return _placed(call(_SURFACE_SOLIDS.get(shape, "Sphere"), [], size + [("checkerboard_colors", "False")] + style, 2), point)


def vector_3d_code(scene: Scene, obj: SceneObject, names: dict[str, str]) -> list[str]:
    """``Arrow3D``, ``Line3D`` or ``Dot3D`` between points given in coordinates of the 3D axes."""
    axes = _axes_variable(scene, obj, names)
    p = obj.params

    def point(prefix: str, defaults: tuple[float, float, float]) -> str:
        return f"{axes}.c2p({', '.join(fmt_float(param_float(p, f'{prefix}_{axis}', default)) for axis, default in zip('xyz', defaults))})"

    color = py_color(obj.stroke_color)
    end = point("to", (2.0, 1.0, 2.0))
    element = p.get("element", "arrow")
    if element == "point":
        return call("Dot3D", [], [("point", end), ("radius", fmt_float(param_float(p, "radius", 0.08))), ("color", color)], 2)
    start = point("from", (0.0, 0.0, 0.0))
    # Manim draws 3D lines as thin cylinders; the stroke width sets their thickness
    thickness = fmt_float(round(max(obj.stroke_width, 0.5) * 0.005, 4))
    return call("Arrow3D" if element == "arrow" else "Line3D", [], [("start", start), ("end", end), ("thickness", thickness), ("color", color)], 2)


def _placed(lines: list[str], point: str) -> list[str]:
    """Append ``.move_to(point)`` to a (possibly wrapped) constructor call."""
    return lines[:-1] + [f"{lines[-1]}.move_to({point})"]
