"""Safe parser for function terms such as ``2x^2 + sin(x)``.

User input is never passed to ``eval``. The text is tokenized, implicit
multiplication is made explicit, the result is parsed with :mod:`ast` and every
node is checked against a strict whitelist. Valid expressions can be evaluated
in pure Python (for the stage preview) and converted into NumPy code (for the
generated Manim script).
"""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass
from typing import Callable

MAX_LENGTH = 500
MAX_DEPTH = 60


def _sign(value: float) -> float:
    return math.copysign(1.0, value) if value != 0 else 0.0


#: Allowed functions: name -> (NumPy name, Python implementation).
FUNCTIONS: dict[str, tuple[str, Callable[[float], float]]] = {
    "sin": ("sin", math.sin),
    "cos": ("cos", math.cos),
    "tan": ("tan", math.tan),
    "asin": ("arcsin", math.asin),
    "arcsin": ("arcsin", math.asin),
    "acos": ("arccos", math.acos),
    "arccos": ("arccos", math.acos),
    "atan": ("arctan", math.atan),
    "arctan": ("arctan", math.atan),
    "sinh": ("sinh", math.sinh),
    "cosh": ("cosh", math.cosh),
    "tanh": ("tanh", math.tanh),
    "exp": ("exp", math.exp),
    "log": ("log", math.log),
    "ln": ("log", math.log),
    "log10": ("log10", math.log10),
    "log2": ("log2", math.log2),
    "sqrt": ("sqrt", math.sqrt),
    "abs": ("abs", abs),
    "floor": ("floor", math.floor),
    "ceil": ("ceil", math.ceil),
    "sign": ("sign", _sign),
}

#: Allowed constants: name -> (Python code, value).
CONSTANTS: dict[str, tuple[str, float]] = {
    "pi": ("np.pi", math.pi),
    "e": ("np.e", math.e),
    "tau": ("(2 * np.pi)", math.tau),
}

VARIABLE = "x"

_TOKEN_RE = re.compile(
    r"\s*(?:"
    r"(?P<number>\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)"
    r"|(?P<name>[A-Za-z_][A-Za-z_0-9]*)"
    r"|(?P<op>\*\*|[-+*/^()])"
    r")"
)


class ExpressionError(ValueError):
    """Raised for invalid function terms.

    ``code`` is a short machine-readable reason used for translated messages,
    ``detail`` names the offending part of the input.
    """

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class _Token:
    kind: str
    text: str


def tokenize(text: str) -> list[_Token]:
    """Split a function term into tokens or raise :class:`ExpressionError`."""
    tokens: list[_Token] = []
    position = 0
    stripped_end = len(text.rstrip())
    while position < stripped_end:
        match = _TOKEN_RE.match(text, position)
        if match is None or match.end() == position:
            offending = text[position:].lstrip()[:1]
            raise ExpressionError("invalid_character", offending)
        kind = match.lastgroup or ""
        value = match.group(kind)
        if kind == "number":
            value = value.replace(",", ".")
        if kind == "op" and value == "^":
            value = "**"
        tokens.append(_Token(kind, value))
        position = match.end()
    return tokens


def _is_value_name(token: _Token) -> bool:
    return token.kind == "name" and (token.text == VARIABLE or token.text in CONSTANTS)


def _ends_operand(token: _Token) -> bool:
    return token.kind == "number" or _is_value_name(token) or token.text == ")"


def _starts_operand(token: _Token) -> bool:
    return token.kind in ("number", "name") or token.text == "("


def _implies_multiplication(previous: _Token, token: _Token) -> bool:
    if not (_ends_operand(previous) and _starts_operand(token)):
        return False
    return not (previous.kind == "name" and token.text == "(" and not _is_value_name(previous))


def insert_implicit_multiplication(tokens: list[_Token]) -> list[_Token]:
    """Insert ``*`` where multiplication is implied, e.g. ``2x``, ``x(x+1)`` or ``(x)(x)``.

    Unknown names directly followed by ``(`` stay calls so that the validator
    can report them as unknown functions.
    """
    result: list[_Token] = []
    for token in tokens:
        if result and _implies_multiplication(result[-1], token):
            result.append(_Token("op", "*"))
        result.append(token)
    return result


def normalize(text: str) -> str:
    """Return the term in explicit Python syntax (before validation)."""
    tokens = insert_implicit_multiplication(tokenize(text))
    return " ".join(token.text for token in tokens)


class _Validator(ast.NodeVisitor):
    """Reject every AST node that is not explicitly allowed."""

    _BIN_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
    _UNARY_OPS = (ast.UAdd, ast.USub)

    def __init__(self) -> None:
        self.depth = 0

    def visit(self, node: ast.AST) -> None:
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise ExpressionError("too_complex")
        super().visit(node)
        self.depth -= 1

    def visit_Expression(self, node: ast.Expression) -> None:
        self.visit(node.body)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if not isinstance(node.op, self._BIN_OPS):
            raise ExpressionError("not_allowed", type(node.op).__name__)
        self.visit(node.left)
        self.visit(node.right)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        if not isinstance(node.op, self._UNARY_OPS):
            raise ExpressionError("not_allowed", type(node.op).__name__)
        self.visit(node.operand)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ExpressionError("not_allowed", repr(node.value))

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == VARIABLE or node.id in CONSTANTS:
            return
        if node.id in FUNCTIONS:
            raise ExpressionError("missing_parenthesis", node.id)
        raise ExpressionError("unknown_name", node.id)

    def visit_Call(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
            name = node.func.id if isinstance(node.func, ast.Name) else "?"
            raise ExpressionError("unknown_function", name)
        if node.keywords or len(node.args) != 1:
            raise ExpressionError("wrong_argument_count", node.func.id)
        self.visit(node.args[0])

    def generic_visit(self, node: ast.AST) -> None:
        raise ExpressionError("not_allowed", type(node).__name__)


class _FloatConstants(ast.NodeTransformer):
    """Turn integer literals into floats so ``9^9^9`` cannot create huge integers."""

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        return ast.copy_location(ast.Constant(float(node.value)), node)


class _NumpyTransformer(ast.NodeTransformer):
    """Map whitelisted names onto NumPy attributes for code generation."""

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        if isinstance(node.op, ast.Pow) and not _mentions_variable(node.left):
            node = _FloatConstants().visit(node)
        self.generic_visit(node)
        return node

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id in CONSTANTS:
            replacement = ast.parse(CONSTANTS[node.id][0], mode="eval").body
            return ast.copy_location(replacement, node)
        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        assert isinstance(node.func, ast.Name)
        numpy_name = FUNCTIONS[node.func.id][0]
        func = ast.Attribute(value=ast.Name(id="np", ctx=ast.Load()), attr=numpy_name, ctx=ast.Load())
        args = [self.visit(arg) for arg in node.args]
        return ast.copy_location(ast.Call(func=func, args=args, keywords=[]), node)


@dataclass(frozen=True)
class Expression:
    """A validated function term in the variable ``x``."""

    source: str
    tree: ast.Expression

    def evaluate(self, x: float) -> float:
        """Evaluate the term for ``x``; raises ``ArithmeticError``/``ValueError`` if undefined."""
        return float(_evaluate(self.tree.body, float(x)))

    def to_numpy(self) -> str:
        """Return Python/NumPy code for the term (the body of ``lambda x: ...``)."""
        tree = _NumpyTransformer().visit(_clone(self.tree))
        ast.fix_missing_locations(tree)
        code = ast.unparse(tree)
        if not _mentions_variable(self.tree):
            code = f"{code} + 0 * x"
        return code


def _clone(tree: ast.Expression) -> ast.Expression:
    return ast.parse(ast.unparse(tree), mode="eval")


def _mentions_variable(tree: ast.AST) -> bool:
    return any(isinstance(node, ast.Name) and node.id == VARIABLE for node in ast.walk(tree))


def _evaluate(node: ast.AST, x: float) -> float:
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        return x if node.id == VARIABLE else CONSTANTS[node.id][1]
    if isinstance(node, ast.UnaryOp):
        value = _evaluate(node.operand, x)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp):
        return _binary(node.op, _evaluate(node.left, x), _evaluate(node.right, x))
    if isinstance(node, ast.Call):
        assert isinstance(node.func, ast.Name)
        return float(FUNCTIONS[node.func.id][1](_evaluate(node.args[0], x)))
    raise ExpressionError("not_allowed", type(node).__name__)


def _binary(op: ast.operator, left: float, right: float) -> float:
    if isinstance(op, ast.Add):
        return left + right
    if isinstance(op, ast.Sub):
        return left - right
    if isinstance(op, ast.Mult):
        return left * right
    if isinstance(op, ast.Div):
        return left / right
    result = left**right
    if isinstance(result, complex):
        raise ValueError("complex result")
    return result


def parse_expression(text: str) -> Expression:
    """Parse and validate a function term or raise :class:`ExpressionError`."""
    if not text or not text.strip():
        raise ExpressionError("empty")
    if len(text) > MAX_LENGTH:
        raise ExpressionError("too_long")
    python_text = normalize(text)
    try:
        tree = ast.parse(python_text, mode="eval")
    except SyntaxError as error:
        raise ExpressionError("syntax", error.msg or "") from None
    _Validator().visit(tree)
    return Expression(source=text, tree=tree)


def check_expression(text: str) -> ExpressionError | None:
    """Return the validation error of a term or ``None`` if it is valid."""
    try:
        parse_expression(text)
    except ExpressionError as error:
        return error
    return None
