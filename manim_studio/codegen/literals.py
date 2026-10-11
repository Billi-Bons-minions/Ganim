"""Turn Python values into safe, deterministic source code literals."""

from __future__ import annotations

import math
import re

_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}


class LiteralError(ValueError):
    """Raised when a value cannot be represented safely."""


def fmt_float(value: float) -> str:
    """Format a number as a short, deterministic float literal (``1.0``, ``-0.25``)."""
    number = float(value)
    if not math.isfinite(number):
        raise LiteralError(f"not a finite number: {value!r}")
    rounded = round(number, 6)
    if rounded == 0:
        rounded = 0.0
    text = repr(rounded)
    if "e" in text or "E" in text:
        text = f"{rounded:.6f}".rstrip("0")
        if text.endswith("."):
            text += "0"
    return text


def fmt_int(value: int) -> str:
    """Format an integer literal."""
    return str(int(value))


def _escape_char(char: str) -> str:
    if char in _ESCAPES:
        return _ESCAPES[char]
    code = ord(char)
    if code < 0x20 or 0x7F <= code < 0xA0 or char in "  ":
        return f"\\u{code:04x}"
    return char


def _raw_safe(text: str) -> bool:
    if '"' in text or text.endswith("\\"):
        return False
    return all(ord(char) >= 0x20 and not 0x7F <= ord(char) < 0xA0 and char not in "  " for char in text)


def py_str(text: str, prefer_raw: bool = False) -> str:
    """Return a double-quoted string literal that evaluates exactly to ``text``.

    With ``prefer_raw`` a raw string (``r"..."``) is produced when that is
    possible, which keeps LaTeX readable.
    """
    if prefer_raw and "\\" in text and _raw_safe(text):
        return f'r"{text}"'
    return '"' + "".join(_escape_char(char) for char in text) + '"'


def py_color(color: str) -> str:
    """Return a validated color literal such as ``"#58C4DD"``."""
    if not isinstance(color, str) or not _HEX_COLOR.match(color):
        raise LiteralError(f"invalid color: {color!r}")
    return f'"{color.upper()}"'


def py_point(x: float, y: float) -> str:
    """Return a 3D point literal ``[x, y, 0.0]``."""
    return f"[{fmt_float(x)}, {fmt_float(y)}, 0.0]"


def fmt_number(value: float) -> str:
    """Format a number as int literal if it is integral, else as float literal.

    Manim derives the decimal places of axis labels from the range values, so
    ``[-5, 5, 1]`` gives labels ``1`` while ``[-5.0, 5.0, 1.0]`` gives ``1.0``.
    """
    text = fmt_float(value)
    return text[:-2] if text.endswith(".0") else text


def py_range(low: float, high: float, step: float | None = None) -> str:
    """Return a range list such as ``[-5, 5, 1]`` or ``[-2.5, 2.5, 0.5]``."""
    items = [fmt_number(low), fmt_number(high)]
    if step is not None:
        items.append(fmt_number(step))
    return "[" + ", ".join(items) + "]"


def py_bool(value: object) -> str:
    """Return ``True`` or ``False``."""
    return "True" if bool(value) else "False"


def py_degrees(angle: float) -> str:
    """Return an angle expression in degrees, e.g. ``45.0 * DEGREES``."""
    return f"{fmt_float(angle)} * DEGREES"
