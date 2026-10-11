"""Symbolic derivatives of validated terms and a readable term printer.

The derivative works directly on the whitelisted :mod:`ast` trees produced by
:mod:`manim_studio.model.expression`, so the result is again a safe term that
can be evaluated on the stage and turned into NumPy code.
"""

from __future__ import annotations

import ast
import math

from manim_studio.model.expression import CONSTANTS, Expression, from_tree

Node = ast.expr


# --- tree builders with light simplification -------------------------------------------


def num(value: float) -> Node:
    """A numeric literal (integers stay integers for nicer output)."""
    if float(value).is_integer() and abs(value) < 1e15:
        value = int(value)
    if value < 0:
        return ast.UnaryOp(op=ast.USub(), operand=ast.Constant(-value))
    return ast.Constant(value)


def _value(node: Node) -> float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _value(node.operand)
        return -inner if inner is not None else None
    return None


def _is(node: Node, value: float) -> bool:
    found = _value(node)
    return found is not None and found == value


def neg(node: Node) -> Node:
    value = _value(node)
    if value is not None:
        return num(-value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return node.operand
    return ast.UnaryOp(op=ast.USub(), operand=node)


def add(left: Node, right: Node) -> Node:
    a, b = _value(left), _value(right)
    if a is not None and b is not None:
        return num(a + b)
    if a == 0:
        return right
    if b == 0:
        return left
    if isinstance(right, ast.UnaryOp) and isinstance(right.op, ast.USub):
        return sub(left, right.operand)
    if b is not None and b < 0:
        return sub(left, num(-b))
    if ast.dump(left) == ast.dump(right):
        return mul(num(2), left)
    return ast.BinOp(left=left, op=ast.Add(), right=right)


def sub(left: Node, right: Node) -> Node:
    a, b = _value(left), _value(right)
    if a is not None and b is not None:
        return num(a - b)
    if b == 0:
        return left
    if a == 0:
        return neg(right)
    if ast.dump(left) == ast.dump(right):
        return num(0)
    return ast.BinOp(left=left, op=ast.Sub(), right=right)


def mul(left: Node, right: Node) -> Node:
    a, b = _value(left), _value(right)
    if a is not None and b is not None:
        return num(a * b)
    if a == 0 or b == 0:
        return num(0)
    if a == 1:
        return right
    if b == 1:
        return left
    if a == -1:
        return neg(right)
    if b == -1:
        return neg(left)
    if b is not None:
        return mul(right, left)
    if isinstance(right, ast.BinOp) and isinstance(right.op, ast.Mult) and _value(right.left) is not None:
        inner = _value(right.left)
        if a is not None:
            return mul(num(a * inner), right.right)
        return mul(right.left, mul(left, right.right))
    if isinstance(right, ast.BinOp) and isinstance(right.op, ast.Div) and _is(right.left, 1):
        return div(left, right.right)
    if a is not None and isinstance(right, ast.BinOp) and isinstance(right.op, ast.Div) and _value(right.left) is not None:
        return div(num(a * _value(right.left)), right.right)
    if isinstance(left, ast.UnaryOp) and isinstance(left.op, ast.USub):
        return neg(mul(left.operand, right))
    if isinstance(right, ast.UnaryOp) and isinstance(right.op, ast.USub):
        return neg(mul(left, right.operand))
    return ast.BinOp(left=left, op=ast.Mult(), right=right)


def div(left: Node, right: Node) -> Node:
    a, b = _value(left), _value(right)
    if a == 0:
        return num(0)
    if b == 1:
        return left
    if a is not None and b is not None and b != 0 and (a / b).is_integer():
        return num(a / b)
    if isinstance(left, ast.UnaryOp) and isinstance(left.op, ast.USub):
        return neg(div(left.operand, right))
    if ast.dump(left) == ast.dump(right):
        return num(1)
    if isinstance(left, ast.BinOp) and isinstance(left.op, ast.Div):
        return div(left.left, mul(left.right, right))
    if b is not None and b != 0 and isinstance(left, ast.BinOp) and isinstance(left.op, ast.Mult) and _value(left.left) is not None:
        factor = _value(left.left) / b
        if float(factor).is_integer() or abs(factor) >= 1e-3:
            return mul(num(round(factor, 12)), left.right)
    return ast.BinOp(left=left, op=ast.Div(), right=right)


def power(base: Node, exponent: Node) -> Node:
    b = _value(exponent)
    if b == 0:
        return num(1)
    if b == 1:
        return base
    a = _value(base)
    if a is not None and b is not None and b.is_integer() and abs(b) <= 8 and a != 0:
        return num(a**b)
    if b is not None and isinstance(base, ast.BinOp) and isinstance(base.op, ast.Pow) and _value(base.right) is not None:
        return power(base.left, num(_value(base.right) * b))
    return ast.BinOp(left=base, op=ast.Pow(), right=exponent)


def call(name: str, argument: Node) -> Node:
    if name in ("ln", "log") and isinstance(argument, ast.Name) and argument.id == "e":
        return num(1)
    return ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=[argument], keywords=[])


# --- derivative ----------------------------------------------------------------------------


def _depends(node: ast.AST, variable: str) -> bool:
    return any(isinstance(item, ast.Name) and item.id == variable for item in ast.walk(node))


def _function_derivative(name: str, g: Node) -> Node:
    """Outer derivative of ``name(g)`` (to be multiplied with ``g'``)."""
    one = num(1)
    if name == "sin":
        return call("cos", g)
    if name == "cos":
        return neg(call("sin", g))
    if name == "tan":
        return div(one, power(call("cos", g), num(2)))
    if name in ("asin", "arcsin"):
        return div(one, call("sqrt", sub(one, power(g, num(2)))))
    if name in ("acos", "arccos"):
        return neg(div(one, call("sqrt", sub(one, power(g, num(2))))))
    if name in ("atan", "arctan"):
        return div(one, add(one, power(g, num(2))))
    if name == "sinh":
        return call("cosh", g)
    if name == "cosh":
        return call("sinh", g)
    if name == "tanh":
        return div(one, power(call("cosh", g), num(2)))
    if name == "exp":
        return call("exp", g)
    if name in ("log", "ln"):
        return div(one, g)
    if name == "log10":
        return div(one, mul(g, call("ln", num(10))))
    if name == "log2":
        return div(one, mul(g, call("ln", num(2))))
    if name == "sqrt":
        return div(one, mul(num(2), call("sqrt", g)))
    if name == "abs":
        return call("sign", g)
    return num(0)  # floor, ceil, sign: piecewise constant


def differentiate(node: Node, variable: str) -> Node:
    """Return the derivative of ``node`` with respect to ``variable``."""
    if not _depends(node, variable):
        return num(0)
    if isinstance(node, ast.Name):
        return num(1)
    if isinstance(node, ast.UnaryOp):
        inner = differentiate(node.operand, variable)
        return neg(inner) if isinstance(node.op, ast.USub) else inner
    if isinstance(node, ast.BinOp):
        u, v = node.left, node.right
        du, dv = differentiate(u, variable), differentiate(v, variable)
        if isinstance(node.op, ast.Add):
            return add(du, dv)
        if isinstance(node.op, ast.Sub):
            return sub(du, dv)
        if isinstance(node.op, ast.Mult):
            return add(mul(du, v), mul(u, dv))
        if isinstance(node.op, ast.Div):
            if not _depends(v, variable):
                return div(du, v)
            return div(sub(mul(du, v), mul(u, dv)), power(v, num(2)))
        if isinstance(node.op, ast.Pow):
            if not _depends(v, variable):
                exponent = _value(v)
                lowered = num(exponent - 1) if exponent is not None else sub(v, num(1))
                return mul(mul(v, power(u, lowered)), du)
            if not _depends(u, variable):
                return mul(mul(node, call("ln", u)), dv)
            return mul(node, add(mul(dv, call("ln", u)), div(mul(v, du), u)))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        argument = node.args[0]
        return mul(_function_derivative(node.func.id, argument), differentiate(argument, variable))
    raise ValueError(f"cannot differentiate {type(node).__name__}")


def derivative(expression: Expression, order: int = 1) -> Expression:
    """Return the ``order``-th derivative of a term as a new term."""
    body: Node = expression.tree.body
    for _ in range(max(1, order)):
        body = differentiate(body, expression.variable)
    tree = ast.Expression(body=body)
    ast.fix_missing_locations(tree)
    return from_tree(tree, expression.variable, expression.parameters)


def difference(first: Expression, second: Expression) -> Expression:
    """Return ``first - second`` (e.g. to find intersections)."""
    tree = ast.Expression(body=ast.BinOp(left=first.tree.body, op=ast.Sub(), right=second.tree.body))
    ast.fix_missing_locations(tree)
    parameters = tuple(sorted(set(first.parameters) | set(second.parameters)))
    return from_tree(tree, first.variable, parameters)


# --- printing --------------------------------------------------------------------------------

_PRECEDENCE = {ast.Add: 1, ast.Sub: 1, ast.Mult: 2, ast.Div: 2, ast.Pow: 4}
_SYMBOLS = {ast.Add: " + ", ast.Sub: " - ", ast.Mult: "*", ast.Div: "/", ast.Pow: "^"}


def _number_text(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    for constant, (_code, constant_value) in CONSTANTS.items():
        if math.isclose(value, constant_value):
            return constant
    return f"{value:.6g}"


def to_text(node: ast.AST, parent: int = 0) -> str:
    """Print a term in the input syntax (``^`` for powers, minimal parentheses)."""
    if isinstance(node, ast.Expression):
        return to_text(node.body)
    if isinstance(node, ast.Constant):
        return _number_text(float(node.value))
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.UnaryOp):
        inner = to_text(node.operand, 2)
        text = f"-{inner}" if isinstance(node.op, ast.USub) else inner
        return f"({text})" if parent >= 2 else text
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return f"{node.func.id}({to_text(node.args[0])})"
    if isinstance(node, ast.BinOp):
        precedence = _PRECEDENCE[type(node.op)]
        if isinstance(node.op, ast.Pow):
            left = to_text(node.left, precedence + 1)
            right = to_text(node.right, precedence)
        else:
            left = to_text(node.left, precedence)
            right_precedence = precedence + (1 if isinstance(node.op, (ast.Sub, ast.Div)) else 0)
            right = to_text(node.right, right_precedence)
        text = f"{left}{_SYMBOLS[type(node.op)]}{right}"
        return f"({text})" if precedence < parent else text
    return ast.unparse(node)
