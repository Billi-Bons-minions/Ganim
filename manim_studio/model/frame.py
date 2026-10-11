"""Video formats: frame size in Manim units and pixel sizes for export."""

from __future__ import annotations

ASPECTS: dict[str, tuple[int, int]] = {"16:9": (16, 9), "9:16": (9, 16), "1:1": (1, 1), "4:3": (4, 3)}
DEFAULT_ASPECT = "16:9"
FRAME_HEIGHT = 8.0


def ratio(aspect: str) -> float:
    """Width divided by height."""
    width, height = ASPECTS.get(aspect, ASPECTS[DEFAULT_ASPECT])
    return width / height


def frame_size(aspect: str) -> tuple[float, float]:
    """Visible area in Manim units; the height is always 8 like in Manim."""
    return FRAME_HEIGHT * ratio(aspect), FRAME_HEIGHT


def frame_box(aspect: str) -> tuple[float, float, float, float]:
    """``(left, bottom, right, top)`` of the visible area."""
    width, height = frame_size(aspect)
    return -width / 2, -height / 2, width / 2, height / 2


def pixel_size(landscape: tuple[int, int], aspect: str) -> tuple[int, int]:
    """Turn a 16:9 quality preset (e.g. 1920×1080) into the size for ``aspect``.

    The short side of the preset is kept: 9:16 swaps the sides, 1:1 is square.
    """
    width, height = landscape
    short = min(width, height)
    value = ratio(aspect)
    if value >= 1:
        return _even(short * value), _even(short)
    return _even(short), _even(short / value)


def _even(value: float) -> int:
    """Video encoders need even sizes."""
    number = int(round(value))
    return number + (number % 2)
