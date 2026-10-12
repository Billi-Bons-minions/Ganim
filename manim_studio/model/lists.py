"""Bulleted and numbered lists (built from ``Text`` lines, no LaTeX needed)."""

from __future__ import annotations

from manim_studio.model.entities import SceneObject


def bullet(style: str, index: int) -> str:
    """The marker in front of item ``index`` (0-based)."""
    if style == "dash":
        return "–"
    if style == "number":
        return f"{index + 1}."
    if style == "letter":
        letters = "abcdefghijklmnopqrstuvwxyz"
        return f"{letters[index % 26]})"
    if style == "none":
        return ""
    return "•"


def list_lines(obj: SceneObject) -> list[str]:
    """The lines of a list including their markers (empty lines are skipped)."""
    items = [item.strip() for item in str(obj.params.get("items", "")).split("\n") if item.strip()]
    style = str(obj.params.get("bullet", "dot"))
    return [f"{bullet(style, index)} {item}".strip() for index, item in enumerate(items)]
