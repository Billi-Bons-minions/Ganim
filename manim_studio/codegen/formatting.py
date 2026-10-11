"""Small helpers to lay out generated function calls deterministically."""

from __future__ import annotations

MAX_LINE = 99
INDENT = "    "


def call(func: str, args: list[str], kwargs: list[tuple[str, str]], indent: int = 0) -> list[str]:
    """Format ``func(*args, **kwargs)``; wraps one argument per line if too long."""
    parts = list(args) + [f"{key}={value}" for key, value in kwargs]
    single = f"{func}({', '.join(parts)})"
    if len(INDENT * indent) + len(single) <= MAX_LINE or not parts:
        return [single]
    lines = [f"{func}("]
    lines.extend(f"{INDENT}{part}," for part in parts)
    lines.append(")")
    return lines


def assign(variable: str, expression_lines: list[str]) -> list[str]:
    """Prefix the first line of an expression with ``variable = ``."""
    return [f"{variable} = {expression_lines[0]}"] + expression_lines[1:]


def indent_lines(lines: list[str], level: int) -> list[str]:
    """Indent non-empty lines by ``level`` steps."""
    prefix = INDENT * level
    return [prefix + line if line else "" for line in lines]
