"""Import Manim scripts into a project (limited, never executes the script).

The script is read with :mod:`ast`. Scenes, common objects, positions,
``self.add``, ``self.play`` (including ``.animate``) and ``self.wait`` are
recognised – in particular everything Manim Studio itself generates. Lines
that cannot be translated are reported, so the user knows what is missing.
"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass, field
from typing import Any

from manim_studio.model.entities import Animation, Project, Scene, SceneObject
from manim_studio.model.factory import create_animation, create_object, create_play_step, create_scene, create_wait_step
from manim_studio.model.types import MANIM_COLORS, AnimationKind, ObjectKind, StepKind, Visibility

SCENE_BASES = {"Scene", "MovingCameraScene", "ThreeDScene", "ZoomedScene"}

DIRECTIONS = {
    "ORIGIN": (0.0, 0.0),
    "UP": (0.0, 1.0),
    "DOWN": (0.0, -1.0),
    "LEFT": (-1.0, 0.0),
    "RIGHT": (1.0, 0.0),
    "UL": (-1.0, 1.0),
    "UR": (1.0, 1.0),
    "DL": (-1.0, -1.0),
    "DR": (1.0, -1.0),
}
EXTRA_COLORS = {
    "BLUE_A": "#C7E9F1", "BLUE_B": "#9CDCEB", "BLUE_C": "#58C4DD", "BLUE_D": "#29ABCA", "BLUE_E": "#236B8E",
    "GREEN_A": "#C9E2AE", "GREEN_B": "#A6CF8C", "GREEN_C": "#83C167", "GREEN_D": "#77B05D", "GREEN_E": "#699C52",
    "RED_A": "#F7A1A3", "RED_B": "#FF8080", "RED_C": "#FC6255", "RED_D": "#E65A4C", "RED_E": "#CF5044",
    "YELLOW_A": "#FFF1B6", "YELLOW_B": "#FFEA94", "YELLOW_C": "#F7D96F", "YELLOW_D": "#F4D345", "YELLOW_E": "#E8C11C",
    "PURE_RED": "#FF0000", "PURE_GREEN": "#00FF00", "PURE_BLUE": "#0000FF", "DARK_GRAY": "#444444", "LIGHT_GRAY": "#BBBBBB",
    "DARK_BLUE": "#236B8E", "DARK_BROWN": "#8B4513", "LIGHT_BROWN": "#CD853F", "GREY": "#888888",
}

SIMPLE_ANIMATIONS = {
    "Create": AnimationKind.CREATE,
    "Write": AnimationKind.WRITE,
    "DrawBorderThenFill": AnimationKind.DRAW_BORDER_THEN_FILL,
    "FadeIn": AnimationKind.FADE_IN,
    "FadeOut": AnimationKind.FADE_OUT,
    "GrowFromCenter": AnimationKind.GROW_FROM_CENTER,
    "Uncreate": AnimationKind.UNCREATE,
    "Indicate": AnimationKind.INDICATE,
    "Circumscribe": AnimationKind.CIRCUMSCRIBE,
    "SpinInFromNothing": AnimationKind.SPIN_IN,
    "AddTextLetterByLetter": AnimationKind.ADD_LETTERS,
    "GrowArrow": AnimationKind.GROW_ARROW,
    "ShrinkToCenter": AnimationKind.SHRINK_TO_CENTER,
    "Flash": AnimationKind.FLASH,
    "Wiggle": AnimationKind.WIGGLE,
    "ApplyWave": AnimationKind.APPLY_WAVE,
    "FocusOn": AnimationKind.FOCUS_ON,
}
TWO_OBJECT_ANIMATIONS = {
    "Transform": (AnimationKind.TRANSFORM, "target"),
    "ReplacementTransform": (AnimationKind.REPLACEMENT_TRANSFORM, "target"),
    "FadeTransform": (AnimationKind.FADE_TRANSFORM, "target"),
    "TransformMatchingShapes": (AnimationKind.TRANSFORM_MATCHING, "target"),
    "TransformMatchingTex": (AnimationKind.TRANSFORM_MATCHING, "target"),
    "MoveAlongPath": (AnimationKind.MOVE_ALONG_PATH, "path"),
    "Swap": (AnimationKind.SWAP, "partner"),
}
NUMPY_TO_TERM = {"arcsin": "asin", "arccos": "acos", "arctan": "atan", "log": "ln"}


class ImportProblem(ValueError):
    """Raised for a statement that cannot be translated."""


@dataclass
class ImportReport:
    """Result of an import: the project and the lines that were skipped."""

    project: Project
    skipped: list[tuple[int, str]] = field(default_factory=list)


# --- values -------------------------------------------------------------------------------


def _number(node: ast.AST, names: dict[str, float] | None = None) -> float:
    """Evaluate simple numeric expressions (numbers, PI, DEGREES, + - * /)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.Name):
        constants = {"PI": math.pi, "TAU": math.tau, "DEGREES": math.pi / 180, **(names or {})}
        if node.id in constants:
            return float(constants[node.id])
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "np":
        if node.attr in ("pi", "e"):
            return math.pi if node.attr == "pi" else math.e
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _number(node.operand, names)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp):
        left, right = _number(node.left, names), _number(node.right, names)
        operations = {ast.Add: left + right, ast.Sub: left - right, ast.Mult: left * right}
        if type(node.op) in operations:
            return operations[type(node.op)]
        if isinstance(node.op, ast.Div) and right != 0:
            return left / right
        if isinstance(node.op, ast.Pow):
            return left**right
    raise ImportProblem("number")


def _vector(node: ast.AST) -> tuple[float, float]:
    """``[x, y, 0]``, ``np.array([...])``, ``UP * 2 + LEFT`` … as (x, y)."""
    if isinstance(node, (ast.List, ast.Tuple)) and len(node.elts) >= 2:
        return _number(node.elts[0]), _number(node.elts[1])
    if isinstance(node, ast.Call) and _call_name(node) in ("np.array", "array") and node.args:
        return _vector(node.args[0])
    if isinstance(node, ast.Name) and node.id in DIRECTIONS:
        return DIRECTIONS[node.id]
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, (ast.Add, ast.Sub)):
            (ax, ay), (bx, by) = _vector(node.left), _vector(node.right)
            sign = 1 if isinstance(node.op, ast.Add) else -1
            return ax + sign * bx, ay + sign * by
        if isinstance(node.op, ast.Mult):
            try:
                factor, vector = _number(node.left), _vector(node.right)
            except ImportProblem:
                vector, factor = _vector(node.left), _number(node.right)
            return vector[0] * factor, vector[1] * factor
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        x, y = _vector(node.operand)
        return -x, -y
    raise ImportProblem("vector")


def _color(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("#"):
        return node.value.upper()
    if isinstance(node, ast.Name):
        if node.id in MANIM_COLORS:
            return MANIM_COLORS[node.id]
        if node.id in EXTRA_COLORS:
            return EXTRA_COLORS[node.id]
    if isinstance(node, ast.Call) and _call_name(node) == "ManimColor" and node.args:
        return _color(node.args[0])
    raise ImportProblem("color")


def _string(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    raise ImportProblem("string")


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_call_name(node.value)}.{node.attr}"
    return ""


def _kwargs(node: ast.Call) -> dict[str, ast.AST]:
    return {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg}


class _TermWriter(ast.NodeTransformer):
    """Turn NumPy code from a lambda back into a term (``np.sin(x)`` → ``sin(x)``)."""

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        if isinstance(node.value, ast.Name) and node.value.id == "np":
            if node.attr == "pi":
                return ast.Name(id="pi", ctx=ast.Load())
            if node.attr == "e":
                return ast.Name(id="e", ctx=ast.Load())
            return ast.Name(id=NUMPY_TO_TERM.get(node.attr, node.attr), ctx=ast.Load())
        return self.generic_visit(node)


def _term(node: ast.AST) -> tuple[str, str]:
    """``lambda x: ...`` → ``("x", "term")``."""
    if not isinstance(node, ast.Lambda) or len(node.args.args) != 1:
        raise ImportProblem("function")
    variable = node.args.args[0].arg
    body = _TermWriter().visit(ast.parse(ast.unparse(node.body), mode="eval"))
    ast.fix_missing_locations(body)
    text = ast.unparse(body).replace("**", "^")
    text = text.replace(" + 0 * x", "").replace(" + 0 * t", "")
    if variable not in ("x", "t"):
        text = text.replace(variable, "x")
        variable = "x"
    return variable, text


# --- objects -------------------------------------------------------------------------------


def _style(obj: SceneObject, kwargs: dict[str, ast.AST]) -> None:
    for key, attribute in (("stroke_color", "stroke_color"), ("fill_color", "fill_color")):
        if key in kwargs:
            setattr(obj, attribute, _color(kwargs[key]))
    if "color" in kwargs:
        color = _color(kwargs["color"])
        obj.stroke_color = color
        obj.fill_color = color
    for key in ("stroke_width", "stroke_opacity", "fill_opacity"):
        if key in kwargs:
            setattr(obj, key, _number(kwargs[key]))


def _set(obj: SceneObject, kwargs: dict[str, ast.AST], mapping: dict[str, str]) -> None:
    for source, target in mapping.items():
        if source in kwargs:
            obj.params[target] = _number(kwargs[source])


def _length_between(args: list[ast.AST]) -> tuple[float, float, float, float]:
    (x0, y0), (x1, y1) = _vector(args[0]), _vector(args[1])
    return math.hypot(x1 - x0, y1 - y0), (x0 + x1) / 2, (y0 + y1) / 2, math.degrees(math.atan2(y1 - y0, x1 - x0))


def build_object(call: ast.Call, name: str, objects: dict[str, SceneObject]) -> SceneObject:
    """Create a model object for a Manim constructor call."""
    function = _call_name(call)
    kwargs = _kwargs(call)
    simple = {
        "Circle": (ObjectKind.CIRCLE, {"radius": "radius"}),
        "Square": (ObjectKind.SQUARE, {"side_length": "side_length"}),
        "Rectangle": (ObjectKind.RECTANGLE, {"width": "width", "height": "height"}),
        "Ellipse": (ObjectKind.ELLIPSE, {"width": "width", "height": "height"}),
        "Triangle": (ObjectKind.TRIANGLE, {"radius": "radius"}),
        "Dot": (ObjectKind.DOT, {"radius": "radius"}),
        "RegularPolygon": (ObjectKind.REGULAR_POLYGON, {"n": "n", "radius": "radius"}),
        "Star": (ObjectKind.STAR, {"n": "n", "outer_radius": "outer_radius", "inner_radius": "inner_radius"}),
        "Arc": (ObjectKind.ARC, {"radius": "radius"}),
        "Sector": (ObjectKind.SECTOR, {"radius": "radius"}),
        "Annulus": (ObjectKind.ANNULUS, {"inner_radius": "inner_radius", "outer_radius": "outer_radius"}),
    }
    if function in simple:
        kind, mapping = simple[function]
        obj = create_object(kind, name)
        _set(obj, kwargs, mapping)
        for key in ("start_angle", "angle"):
            if key in kwargs and kind in (ObjectKind.ARC, ObjectKind.SECTOR):
                obj.params[key] = round(math.degrees(_number(kwargs[key])), 6)
        if function == "RegularPolygon" and call.args:
            obj.params["n"] = int(_number(call.args[0]))
        if function == "Dot" and "color" in kwargs:
            obj.fill_color = _color(kwargs["color"])
            obj.fill_opacity = 1.0
            kwargs = {key: value for key, value in kwargs.items() if key != "color"}
        _style(obj, kwargs)
        return obj
    if function in ("Line", "Arrow", "DoubleArrow", "DashedLine"):
        kinds = {"Line": ObjectKind.LINE, "Arrow": ObjectKind.ARROW, "DoubleArrow": ObjectKind.DOUBLE_ARROW, "DashedLine": ObjectKind.DASHED_LINE}
        obj = create_object(kinds[function], name)
        if len(call.args) >= 2:
            length, x, y, angle = _length_between(call.args)
            obj.params["length"], obj.x, obj.y, obj.rotation = round(length, 6), round(x, 6), round(y, 6), round(angle, 6)
        _style(obj, kwargs)
        return obj
    if function in ("Text", "MarkupText", "MathTex", "Tex"):
        kinds = {"Text": ObjectKind.TEXT, "MarkupText": ObjectKind.MARKUP_TEXT, "MathTex": ObjectKind.MATH_TEX, "Tex": ObjectKind.TEX}
        key = {"Text": "text", "MarkupText": "markup", "MathTex": "latex", "Tex": "tex"}[function]
        obj = create_object(kinds[function], name)
        if call.args:
            obj.params[key] = " ".join(_string(arg) for arg in call.args)
        _set(obj, kwargs, {"font_size": "font_size"})
        if "font" in kwargs:
            obj.params["font"] = _string(kwargs["font"])
        if "color" in kwargs:
            obj.fill_color = _color(kwargs["color"])
        if "fill_opacity" in kwargs:
            obj.fill_opacity = _number(kwargs["fill_opacity"])
        return obj
    if function in ("Axes", "NumberPlane"):
        obj = create_object(ObjectKind.AXES if function == "Axes" else ObjectKind.NUMBER_PLANE, name)
        for axis in ("x", "y"):
            values = kwargs.get(f"{axis}_range")
            if isinstance(values, (ast.List, ast.Tuple)) and len(values.elts) >= 2:
                obj.params[f"{axis}_min"], obj.params[f"{axis}_max"] = _number(values.elts[0]), _number(values.elts[1])
                if len(values.elts) > 2:
                    obj.params[f"{axis}_step"] = _number(values.elts[2])
            if f"{axis}_length" in kwargs:
                obj.params[f"{axis}_length"] = _number(kwargs[f"{axis}_length"])
        if "tips" in kwargs and isinstance(kwargs["tips"], ast.Constant):
            obj.params["tips"] = bool(kwargs["tips"].value)
        return obj
    if function == "ValueTracker":
        obj = create_object(ObjectKind.PARAMETER, name, symbol=name)
        obj.params["value"] = _number(call.args[0]) if call.args else 0.0
        return obj
    if function == "DecimalNumber":
        obj = create_object(ObjectKind.DECIMAL_NUMBER, name)
        if call.args:
            obj.params["value"] = _number(call.args[0])
        _set(obj, kwargs, {"font_size": "font_size"})
        if "num_decimal_places" in kwargs:
            obj.params["decimals"] = int(_number(kwargs["num_decimal_places"]))
        return obj
    if function == "FunctionGraph" and call.args:
        variable, term = _term(call.args[0])
        obj = create_object(ObjectKind.FUNCTION_GRAPH, name, expression=term)
        _graph_range(obj, kwargs)
        _style(obj, kwargs)
        return obj
    if function.endswith(".plot") and call.args:
        axes = objects.get(function.rsplit(".", 1)[0])
        _variable, term = _term(call.args[0])
        obj = create_object(ObjectKind.FUNCTION_GRAPH, name, expression=term, axes_id=axes.id if axes else None)
        _graph_range(obj, kwargs)
        _style(obj, kwargs)
        return obj
    if function == "VGroup":
        members = [objects[arg.id].id for arg in call.args if isinstance(arg, ast.Name) and arg.id in objects]
        if len(members) == len(call.args) and members:
            return create_object(ObjectKind.GROUP, name, members=members)
    raise ImportProblem(f"object {function}")


def _graph_range(obj: SceneObject, kwargs: dict[str, ast.AST]) -> None:
    values = kwargs.get("x_range")
    if isinstance(values, (ast.List, ast.Tuple)) and len(values.elts) >= 2:
        obj.params["x_min"], obj.params["x_max"] = _number(values.elts[0]), _number(values.elts[1])


# --- scenes -------------------------------------------------------------------------------------


class _SceneReader:
    def __init__(self, scene: Scene, report: ImportReport) -> None:
        self.scene = scene
        self.report = report
        self.objects: dict[str, SceneObject] = {}
        self.added: set[str] = set()
        self._pending_section = ""

    def _new_step(self, step) -> None:
        if self._pending_section:
            step.section, self._pending_section = self._pending_section, ""
        self.scene.steps.append(step)

    def statement(self, node: ast.stmt) -> None:
        try:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                self._assign(node)
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                self._call(node.value)
            elif isinstance(node, (ast.Pass, ast.Import, ast.ImportFrom)):
                return
            else:
                raise ImportProblem("statement")
        except ImportProblem:
            self.report.skipped.append((getattr(node, "lineno", 0), ast.unparse(node).split("\n")[0][:120]))

    def _assign(self, node: ast.Assign) -> None:
        target = node.targets[0]
        if isinstance(target, ast.Attribute) and ast.unparse(target) == "self.camera.background_color":
            self.scene.background_color = _color(node.value)
            return
        if not isinstance(target, ast.Name) or not isinstance(node.value, ast.Call):
            raise ImportProblem("assignment")
        call = node.value
        chain: list[ast.Call] = []
        while isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Call):
            chain.append(call)
            call = call.func.value
        obj = build_object(call, target.id, self.objects)
        self.objects[target.id] = obj
        self.scene.objects.append(obj)
        for method in reversed(chain):
            try:
                self._apply_method(obj, method.func.attr, method)
            except ImportProblem:
                self.report.skipped.append((getattr(node, "lineno", 0), f"{target.id}.{method.func.attr}(…)"))

    def _apply_method(self, obj: SceneObject, method: str, call: ast.Call) -> None:
        if method == "move_to" and call.args:
            obj.x, obj.y = (round(value, 6) for value in _vector(call.args[0]))
        elif method == "shift" and call.args:
            dx, dy = _vector(call.args[0])
            obj.x, obj.y = round(obj.x + dx, 6), round(obj.y + dy, 6)
        elif method == "rotate" and call.args:
            obj.rotation = round(obj.rotation + math.degrees(_number(call.args[0])), 6)
        elif method == "set_color" and call.args:
            obj.stroke_color = obj.fill_color = _color(call.args[0])
        elif method == "set_z_index" and call.args:
            obj.z_index = int(_number(call.args[0]))
        elif method == "scale" and call.args:
            from manim_studio.model.operations import _scale_params

            _scale_params(obj, _number(call.args[0]))
        else:
            raise ImportProblem(method)

    def _call(self, call: ast.Call) -> None:
        name = _call_name(call)
        if name == "self.add":
            for arg in call.args:
                if isinstance(arg, ast.Name) and arg.id in self.objects:
                    self.added.add(self.objects[arg.id].id)
            return
        if name == "self.wait":
            seconds = _number(call.args[0]) if call.args else 1.0
            self._new_step(create_wait_step(seconds))
            return
        if name == "self.play":
            animations = []
            kwargs = _kwargs(call)
            run_time = _number(kwargs["run_time"]) if "run_time" in kwargs else None
            for arg in call.args:
                animations += self._animations(arg, run_time)
            step = create_play_step(animations)
            if "subcaption" in kwargs:
                step.subcaption = _string(kwargs["subcaption"])
            self._new_step(step)
            return
        parts = name.split(".")
        if len(parts) == 2 and parts[0] in self.objects:
            self._apply_method(self.objects[parts[0]], parts[1], call)
            return
        if name == "self.next_section" and call.args:
            self._pending_section = _string(call.args[0])
            return
        raise ImportProblem("call")

    def _timing(self, anim: Animation, kwargs: dict[str, ast.AST], run_time: float | None) -> Animation:
        if "run_time" in kwargs:
            anim.run_time = _number(kwargs["run_time"])
        elif run_time is not None:
            anim.run_time = run_time
        rate = kwargs.get("rate_func")
        if rate is not None:
            text = ast.unparse(rate).replace("rate_functions.", "")
            from manim_studio.model.types import RATE_FUNCTIONS

            if text in RATE_FUNCTIONS:
                anim.rate_func = text
        return anim

    def _target(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name) and node.id in self.objects:
            return self.objects[node.id].id
        raise ImportProblem("target")

    def _animations(self, node: ast.AST, run_time: float | None) -> list[Animation]:
        if not isinstance(node, ast.Call):
            raise ImportProblem("animation")
        name = _call_name(node)
        kwargs = _kwargs(node)
        if name in SIMPLE_ANIMATIONS and node.args:
            anim = create_animation(SIMPLE_ANIMATIONS[name], self._target(node.args[0]))
            if name in ("FadeIn", "FadeOut") and "shift" in kwargs:
                vector = _vector(kwargs["shift"])
                for key, value in DIRECTIONS.items():
                    if value == vector and key in ("UP", "DOWN", "LEFT", "RIGHT"):
                        anim.params["shift"] = key.lower()
            if "color" in kwargs:
                anim.params["color"] = _color(kwargs["color"])
            return [self._timing(anim, kwargs, run_time)]
        if name in TWO_OBJECT_ANIMATIONS and len(node.args) >= 2:
            kind, key = TWO_OBJECT_ANIMATIONS[name]
            anim = create_animation(kind, self._target(node.args[0]), **{key: self._target(node.args[1])})
            return [self._timing(anim, kwargs, run_time)]
        if name == "Rotate" and node.args:
            angle = math.degrees(_number(kwargs["angle"])) if "angle" in kwargs else 180.0
            anim = create_animation(AnimationKind.ROTATE, self._target(node.args[0]), angle=round(angle, 6))
            return [self._timing(anim, kwargs, run_time)]
        return self._animate_chain(node, run_time)

    def _animate_chain(self, node: ast.Call, run_time: float | None) -> list[Animation]:
        """``obj.animate(run_time=…).move_to(…).scale(…)`` → Move/Scale/Rotate/Color."""
        chain: list[ast.Call] = []
        current: ast.AST = node
        while isinstance(current, ast.Call) and isinstance(current.func, ast.Attribute) and current.func.attr != "animate":
            chain.append(current)
            current = current.func.value
        options: dict[str, ast.AST] = {}
        if isinstance(current, ast.Call) and isinstance(current.func, ast.Attribute) and current.func.attr == "animate":
            options = _kwargs(current)
            current = current.func.value
        elif isinstance(current, ast.Attribute) and current.attr == "animate":
            current = current.value
        else:
            raise ImportProblem("animation")
        target = self._target(current)
        result = []
        for call in reversed(chain):
            method = call.func.attr
            if method == "move_to":
                x, y = _vector(call.args[0])
                anim = create_animation(AnimationKind.MOVE, target, x=round(x, 6), y=round(y, 6))
            elif method == "shift":
                raise ImportProblem("shift animation")
            elif method == "scale":
                anim = create_animation(AnimationKind.SCALE, target, factor=_number(call.args[0]))
            elif method == "rotate":
                anim = create_animation(AnimationKind.ROTATE, target, angle=round(math.degrees(_number(call.args[0])), 6))
            elif method in ("set_color", "set_fill", "set_stroke"):
                color_node = call.args[0] if call.args else _kwargs(call).get("color")
                apply_to = {"set_fill": "fill", "set_stroke": "stroke"}.get(method, "both")
                anim = create_animation(AnimationKind.CHANGE_COLOR, target, color=_color(color_node), apply_to=apply_to)
            elif method == "set_value":
                anim = create_animation(AnimationKind.SET_VALUE, target, value=_number(call.args[0]))
            else:
                raise ImportProblem(method)
            result.append(self._timing(anim, options, run_time))
        return result

    def finish(self) -> None:
        """Objects that are neither added nor animated in are hidden like in Manim."""
        animated = {anim.target_id for step in self.scene.steps for anim in step.animations}
        targets = {anim.params.get("target") for step in self.scene.steps for anim in step.animations}
        for obj in self.scene.objects:
            if obj.kind in (ObjectKind.PARAMETER, ObjectKind.GROUP):
                continue
            if obj.id not in self.added and obj.id not in animated and obj.id not in targets:
                obj.visibility = Visibility.HIDDEN
            elif obj.id in self.added:
                obj.visibility = Visibility.SHOWN


def import_script(source: str) -> ImportReport:
    """Read Manim scenes from a script (raises ``SyntaxError`` for invalid Python)."""
    tree = ast.parse(source)
    report = ImportReport(Project(scenes=[]))
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {_call_name(base) for base in node.bases}
        if not bases & SCENE_BASES:
            continue
        construct = next((item for item in node.body if isinstance(item, ast.FunctionDef) and item.name == "construct"), None)
        if construct is None:
            continue
        scene = create_scene(node.name)
        reader = _SceneReader(scene, report)
        for statement in construct.body:
            reader.statement(statement)
        reader.finish()
        _drop_empty_steps(scene)
        report.project.scenes.append(scene)
    return report


def _drop_empty_steps(scene: Scene) -> None:
    scene.steps = [step for step in scene.steps if step.kind != StepKind.PLAY or step.animations]


def summary(report: ImportReport) -> dict[str, Any]:
    """Counts for the status message."""
    return {
        "scenes": len(report.project.scenes),
        "objects": sum(len(scene.objects) for scene in report.project.scenes),
        "steps": sum(len(scene.steps) for scene in report.project.scenes),
        "skipped": len(report.skipped),
    }
