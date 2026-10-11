"""Safe parser for function terms such as ``2x^2 + sin(x)`` or ``a*sin(k t)``.

User input is never passed to ``eval``. The text is tokenized, implicit
multiplication is made explicit, the result is parsed with :mod:`ast` and every
node is checked against a strict whitelist. Valid expressions can be evaluated
in pure Python (for the stage preview) and converted into NumPy code (for the
generated Manim script).

Besides the variable (``x`` for graphs, ``t`` for parametric and polar curves)
a term may use named parameters (Manim ``ValueTracker`` values). Names written
together such as ``ax`` are split into known names (``a * x``).
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
NO_PARAMETERS: tuple[str, ...] = ()

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


def _value_names(variable: str, parameters: tuple[str, ...]) -> frozenset[str]:
    return frozenset({variable, *CONSTANTS, *parameters})


def _is_value_name(token: _Token, values: frozenset[str]) -> bool:
    return token.kind == "name" and token.text in values


def _ends_operand(token: _Token, values: frozenset[str]) -> bool:
    return token.kind == "number" or _is_value_name(token, values) or token.text == ")"


def _starts_operand(token: _Token) -> bool:
    return token.kind in ("number", "name") or token.text == "("


def _implies_multiplication(previous: _Token, token: _Token, values: frozenset[str]) -> bool:
    if not (_ends_operand(previous, values) and _starts_operand(token)):
        return False
    return not (previous.kind == "name" and token.text == "(" and not _is_value_name(previous, values))


def _split_name(name: str, values: frozenset[str], call: bool) -> list[str] | None:
    """Split e.g. ``ax`` into ``["a", "x"]`` (the last part may be a function before ``(``)."""
    if not name:
        return []
    for size in range(len(name), 0, -1):
        head = name[:size]
        rest = name[size:]
        if head in values or (call and not rest and head in FUNCTIONS):
            tail = _split_name(rest, values, call)
            if tail is not None:
                return [head] + tail
    return None


def split_names(tokens: list[_Token], values: frozenset[str]) -> list[_Token]:
    """Replace unknown names that consist of known names by those names."""
    result: list[_Token] = []
    for index, token in enumerate(tokens):
        known = token.text in values or token.text in FUNCTIONS
        if token.kind != "name" or known:
            result.append(token)
            continue
        call = index + 1 < len(tokens) and tokens[index + 1].text == "("
        parts = _split_name(token.text, values, call)
        result += [_Token("name", part) for part in parts] if parts else [token]
    return result


def insert_implicit_multiplication(tokens: list[_Token], values: frozenset[str] | None = None) -> list[_Token]:
    """Insert ``*`` where multiplication is implied, e.g. ``2x``, ``x(x+1)`` or ``(x)(x)``.

    Unknown names directly followed by ``(`` stay calls so that the validator
    can report them as unknown functions.
    """
    values = values if values is not None else _value_names(VARIABLE, NO_PARAMETERS)
    result: list[_Token] = []
    for token in tokens:
        if result and _implies_multiplication(result[-1], token, values):
            result.append(_Token("op", "*"))
        result.append(token)
    return result


def normalize(text: str, variable: str = VARIABLE, parameters: tuple[str, ...] = NO_PARAMETERS) -> str:
    """Return the term in explicit Python syntax (before validation)."""
    values = _value_names(variable, parameters)
    tokens = insert_implicit_multiplication(split_names(tokenize(text), values), values)
    return " ".join(token.text for token in tokens)


class _Validator(ast.NodeVisitor):
    """Reject every AST node that is not explicitly allowed."""

    _BIN_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
    _UNARY_OPS = (ast.UAdd, ast.USub)

    def __init__(self, values: frozenset[str] | None = None) -> None:
        self.depth = 0
        self.values = values if values is not None else _value_names(VARIABLE, NO_PARAMETERS)

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
        if node.id in self.values:
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
    """Map whitelisted names onto NumPy attributes (and parameters onto their code)."""

    def __init__(self, variable: str, rename: dict[str, str]) -> None:
        self.variable = variable
        self.rename = rename

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        if isinstance(node.op, ast.Pow) and not _mentions(node.left, self.variable):
            node = _FloatConstants().visit(node)
        self.generic_visit(node)
        return node

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id in CONSTANTS:
            replacement = ast.parse(CONSTANTS[node.id][0], mode="eval").body
            return ast.copy_location(replacement, node)
        if node.id in self.rename:
            replacement = ast.parse(self.rename[node.id], mode="eval").body
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
    """A validated term in one variable (``x`` or ``t``) and optional parameters."""

    source: str
    tree: ast.Expression
    variable: str = VARIABLE
    parameters: tuple[str, ...] = NO_PARAMETERS

    def evaluate(self, x: float, values: dict[str, float] | None = None) -> float:
        """Evaluate the term; raises ``ArithmeticError``/``ValueError`` if undefined.

        ``values`` holds the current value of every parameter (missing ones are 0).
        """
        names = {name: float(value) for name, value in (values or {}).items()}
        names[self.variable] = float(x)
        return float(_evaluate(self.tree.body, names))

    def to_numpy(self, rename: dict[str, str] | None = None) -> str:
        """Return Python/NumPy code for the term (the body of ``lambda x: ...``).

        ``rename`` maps parameter names onto code, e.g. ``{"a": "a.get_value()"}``.
        """
        tree = _NumpyTransformer(self.variable, rename or {}).visit(_clone(self.tree))
        ast.fix_missing_locations(tree)
        code = ast.unparse(tree)
        if not _mentions(self.tree, self.variable):
            code = f"{code} + 0 * {self.variable}"
        return code

    def used_parameters(self) -> set[str]:
        """Return the parameters that actually occur in the term."""
        return {node.id for node in ast.walk(self.tree) if isinstance(node, ast.Name) and node.id in self.parameters}

    def mentions_variable(self) -> bool:
        """Return ``True`` if the term depends on its variable."""
        return _mentions(self.tree, self.variable)


def _clone(tree: ast.Expression) -> ast.Expression:
    return ast.parse(ast.unparse(tree), mode="eval")


def _mentions(tree: ast.AST, variable: str) -> bool:
    return any(isinstance(node, ast.Name) and node.id == variable for node in ast.walk(tree))


def _mentions_variable(tree: ast.AST) -> bool:
    return _mentions(tree, VARIABLE)


def _evaluate(node: ast.AST, names: dict[str, float]) -> float:
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id in CONSTANTS:
            return CONSTANTS[node.id][1]
        return names.get(node.id, 0.0)
    if isinstance(node, ast.UnaryOp):
        value = _evaluate(node.operand, names)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp):
        return _binary(node.op, _evaluate(node.left, names), _evaluate(node.right, names))
    if isinstance(node, ast.Call):
        assert isinstance(node.func, ast.Name)
        return float(FUNCTIONS[node.func.id][1](_evaluate(node.args[0], names)))
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


def parse_expression(text: str, variable: str = VARIABLE, parameters: tuple[str, ...] | list[str] = NO_PARAMETERS) -> Expression:
    """Parse and validate a term or raise :class:`ExpressionError`."""
    if not text or not text.strip():
        raise ExpressionError("empty")
    if len(text) > MAX_LENGTH:
        raise ExpressionError("too_long")
    parameters = tuple(sorted(set(parameters) - {variable}))
    python_text = normalize(text, variable, parameters)
    try:
        tree = ast.parse(python_text, mode="eval")
    except SyntaxError as error:
        raise ExpressionError("syntax", error.msg or "") from None
    _Validator(_value_names(variable, parameters)).visit(tree)
    return Expression(source=text, tree=tree, variable=variable, parameters=parameters)


def from_tree(tree: ast.Expression, variable: str = VARIABLE, parameters: tuple[str, ...] = NO_PARAMETERS) -> Expression:
    """Wrap an already validated tree (e.g. a derivative) as an expression."""
    from manim_studio.model.calculus import to_text

    return Expression(source=to_text(tree.body), tree=tree, variable=variable, parameters=parameters)


def check_expression(text: str, variable: str = VARIABLE, parameters: tuple[str, ...] | list[str] = NO_PARAMETERS) -> ExpressionError | None:
    """Return the validation error of a term or ``None`` if it is valid."""
    try:
        parse_expression(text, variable, parameters)
    except ExpressionError as error:
        return error
    return None


def is_valid_name(name: str) -> bool:
    """Return ``True`` if ``name`` can be used as a parameter in terms."""
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name)) and name not in FUNCTIONS and name not in CONSTANTS and name not in ("x", "t")


def evaluate_number(text: str) -> float | None:
    """Evaluate a constant term such as ``pi/2`` or ``1,5`` (``None`` if it is not one)."""
    import math

    source = text.strip()
    if not source:
        return None
    if "," in source and "." not in source and source.count(",") == 1:
        source = source.replace(",", ".")
    try:
        expression = parse_expression(source)
    except ExpressionError:
        return None
    if _mentions_variable(expression.tree):
        return None
    try:
        value = expression.evaluate(0.0)
    except (ArithmeticError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None
