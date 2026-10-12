"""Compute a LaTeX formula: translate simple LaTeX into a term of the expression language.

``\\frac{a}{2} + 3 \\cdot b`` becomes ``((a)/(2)) + 3 * b``. Only what the expression
language knows can be computed; everything else is reported as not computable.
"""

from __future__ import annotations

import re

from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.expression import Expression, ExpressionError, parse_expression
from manim_studio.model.geometry import param_float
from manim_studio.model.types import ObjectKind

_COMMANDS = {r"\cdot": "*", r"\times": "*", r"\div": "/", r"\pi": "pi", r"\left": "", r"\right": "", r"\,": " ", r"\;": " ", r"\!": ""}
_FUNCTIONS = ("arcsin", "arccos", "arctan", "sinh", "cosh", "tanh", "sin", "cos", "tan", "exp", "ln", "log")
_RENAMED = {"arcsin": "asin", "arccos": "acos", "arctan": "atan"}


def latex_to_term(latex: str) -> str:
    """Translate simple LaTeX into the expression language (no checks)."""
    term = latex
    for command, replacement in _COMMANDS.items():
        term = term.replace(command, replacement)
    inner = r"\{([^{}]*)\}"
    while re.search(r"\\[dt]?frac" + inner + inner, term):
        term = re.sub(r"\\[dt]?frac" + inner + inner, r"((\1)/(\2))", term)
    while re.search(r"\\sqrt" + inner, term):
        term = re.sub(r"\\sqrt" + inner, r"sqrt(\1)", term)
    for name in _FUNCTIONS:
        term = term.replace("\\" + name, " " + _RENAMED.get(name, name) + " ")
    return term.replace("{", "(").replace("}", ")")


def result_term(scene: Scene, obj: SceneObject) -> Expression | None:
    """The term of a formula with "compute result" (``None`` if it is off or not computable)."""
    if obj.kind != ObjectKind.MATH_TEX or not obj.params.get("show_result"):
        return None
    from manim_studio.model.attach import FORMULA_VARIABLE
    from manim_studio.model.graphs import parameter_symbols

    symbols = parameter_symbols(scene)
    try:
        expression = parse_expression(latex_to_term(str(obj.params.get("latex", ""))), FORMULA_VARIABLE, symbols)
    except ExpressionError:
        return None
    return None if expression.mentions_variable() and FORMULA_VARIABLE not in symbols else expression


def result_text(value: float, decimals: int) -> str:
    """How the result is written after ``=`` (the script does the same)."""
    return f"{value:.{decimals}f}" if value == value else "?"


def shown_latex(scene: Scene, obj: SceneObject, values: dict[str, float] | None = None) -> str | None:
    """``latex = result`` with the parameter values, or ``None`` without a computable result."""
    from manim_studio.model.graphs import scene_values

    term = result_term(scene, obj)
    if term is None:
        return None
    try:
        value = term.evaluate(0.0, scene_values(scene, values))
    except (ArithmeticError, ValueError):
        value = float("nan")
    decimals = int(param_float(obj.params, "result_decimals", 2.0))
    return f"{obj.params.get('latex', '')} = {result_text(value, decimals)}"
