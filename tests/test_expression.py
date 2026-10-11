"""Tests for the safe function term parser."""

from __future__ import annotations

import math

import pytest

from manim_studio.model.expression import ExpressionError, check_expression, parse_expression


@pytest.mark.parametrize(
    ("text", "code", "x", "value"),
    [
        ("sin(x)", "np.sin(x)", 1.0, math.sin(1.0)),
        ("2x^2 + 3x - 1", "2 * x ** 2 + 3 * x - 1", 2.0, 13.0),
        ("0,5x", "0.5 * x", 4.0, 2.0),
        ("e^x", "np.e ** x", 1.0, math.e),
        ("x(x+1)", "x * (x + 1)", 2.0, 6.0),
        ("2sin(x)cos(x)", "2 * np.sin(x) * np.cos(x)", 0.5, math.sin(1.0)),
        ("-x^2", "-x ** 2", 3.0, -9.0),
        ("sqrt(abs(x))", "np.sqrt(np.abs(x))", -4.0, 2.0),
        ("ln(x)", "np.log(x)", math.e, 1.0),
        ("pi x", "np.pi * x", 1.0, math.pi),
        ("tau", "2 * np.pi + 0 * x", 0.0, math.tau),
        ("3", "3 + 0 * x", 7.0, 3.0),
        ("1.5e2 x", "150.0 * x", 1.0, 150.0),
    ],
)
def test_valid_terms(text: str, code: str, x: float, value: float) -> None:
    expression = parse_expression(text)
    assert expression.to_numpy() == code
    assert expression.evaluate(x) == pytest.approx(value)


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("", "empty"),
        ("   ", "empty"),
        ("__import__('os')", "invalid_character"),
        ("x.real", "invalid_character"),
        ("x[0]", "invalid_character"),
        ("lambda: 1", "invalid_character"),
        ("y + 1", "unknown_name"),
        ("open(x)", "unknown_function"),
        ("sin", "missing_parenthesis"),
        ("sin(x, 2)", "invalid_character"),
        ("2 +", "syntax"),
        ("x == 1", "invalid_character"),
        ("x" * 600, "too_long"),
    ],
)
def test_rejected_terms(text: str, code: str) -> None:
    error = check_expression(text)
    assert isinstance(error, ExpressionError)
    assert error.code == code


def test_deep_nesting_is_rejected() -> None:
    assert check_expression("sin(" * 80 + "x" + ")" * 80) is not None


def test_huge_powers_do_not_hang() -> None:
    expression = parse_expression("9^9^9")
    assert expression.to_numpy().startswith("9.0 ** 9.0 ** 9.0")
    with pytest.raises(OverflowError):
        expression.evaluate(0.0)


def test_undefined_values_raise_arithmetic_errors() -> None:
    with pytest.raises(ValueError):
        parse_expression("sqrt(x)").evaluate(-1.0)
    with pytest.raises(ZeroDivisionError):
        parse_expression("1/x").evaluate(0.0)
