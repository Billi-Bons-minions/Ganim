"""Errors raised by the code generator."""

from __future__ import annotations


class CodegenError(ValueError):
    """The model cannot be converted into a valid script.

    ``code`` is a short reason that the UI translates, ``detail`` names the
    affected object or value.
    """

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail
