"""Small LaTeX helpers (coloring parts of a formula)."""

from __future__ import annotations

import re

_COMMAND = re.compile(r"\\[A-Za-z]+|\\.")


def _hex(color: str) -> str:
    return color.lstrip("#").upper()


def colorize(latex: str, parts: list[tuple[str, str]]) -> str:
    """Wrap every occurrence of the parts in ``\\textcolor[HTML]{RRGGBB}{...}``.

    LaTeX commands such as ``\\frac`` are never split, so coloring ``a`` does
    not touch ``\\frac``; longer parts win over shorter ones.
    """
    parts = sorted(((text, color) for text, color in parts if text), key=lambda item: -len(item[0]))
    if not parts:
        return latex
    result: list[str] = []
    index = 0
    while index < len(latex):
        command = _COMMAND.match(latex, index)
        if command is not None:
            result.append(command.group(0))
            index = command.end()
            continue
        match = next(((text, color) for text, color in parts if latex.startswith(text, index)), None)
        if match is not None:
            text, color = match
            result.append(f"\\textcolor[HTML]{{{_hex(color)}}}{{{text}}}")
            index += len(text)
        else:
            result.append(latex[index])
            index += 1
    return "".join(result)


def colored_parts(params: dict) -> list[tuple[str, str]]:
    """Valid ``(text, color)`` pairs of a formula."""
    return [(str(text), str(color)) for text, color in params.get("colored_parts", []) or [] if str(text)]
