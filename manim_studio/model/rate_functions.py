"""Python versions of Manim's rate functions (for playback on the stage).

The formulas follow ``manim.utils.rate_functions`` so that the stage preview
moves exactly like the rendered video.
"""

from __future__ import annotations

import math
from typing import Callable

RateFunction = Callable[[float], float]


def _clamp(t: float) -> float:
    return 0.0 if t < 0 else 1.0 if t > 1 else t


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def linear(t: float) -> float:
    return t


def smooth(t: float, inflection: float = 10.0) -> float:
    error = _sigmoid(-inflection / 2)
    return min(max((_sigmoid(inflection * (t - 0.5)) - error) / (1 - 2 * error), 0.0), 1.0)


def rush_into(t: float) -> float:
    return 2 * smooth(t / 2.0)


def rush_from(t: float) -> float:
    return 2 * smooth(t / 2.0 + 0.5) - 1


def slow_into(t: float) -> float:
    t = _clamp(t)
    return math.sqrt(1 - (1 - t) * (1 - t))


def double_smooth(t: float) -> float:
    return 0.5 * smooth(2 * t) if t < 0.5 else 0.5 * (1 + smooth(2 * t - 1))


def there_and_back(t: float) -> float:
    return smooth(2 * t if t < 0.5 else 2 * (1 - t))


def there_and_back_with_pause(t: float, pause_ratio: float = 1.0 / 3) -> float:
    a = 2.0 / (1.0 - pause_ratio)
    if t < 0.5 - pause_ratio / 2:
        return smooth(a * t)
    if t < 0.5 + pause_ratio / 2:
        return 1.0
    return smooth(a - a * t)


def running_start(t: float, pull_factor: float = -0.5) -> float:
    mt = 1 - t
    return (
        15 * t**2 * mt**4 * pull_factor
        + 20 * t**3 * mt**3 * pull_factor
        + 15 * t**4 * mt**2
        + 6 * t**5 * mt
        + t**6
    )


def wiggle(t: float, wiggles: float = 2) -> float:
    if t <= 0 or t >= 1:
        return 0.0
    return there_and_back(t) * math.sin(wiggles * math.pi * t)


def squish(func: RateFunction, a: float, b: float) -> RateFunction:
    """Manim's ``squish_rate_func``: run ``func`` only between ``a`` and ``b``."""

    def result(t: float) -> float:
        if a == b:
            return a
        new_t = 0.0 if t < a else 1.0 if t > b else (t - a) / (b - a)
        return func(new_t)

    return result


def lingering(t: float) -> float:
    return squish(linear, 0, 0.8)(_clamp(t))


def ease_in_sine(t: float) -> float:
    return 1 - math.cos(_clamp(t) * math.pi / 2)


def ease_out_sine(t: float) -> float:
    return math.sin(_clamp(t) * math.pi / 2)


def ease_in_out_sine(t: float) -> float:
    return -(math.cos(math.pi * _clamp(t)) - 1) / 2


def ease_in_quad(t: float) -> float:
    return t * t


def ease_out_quad(t: float) -> float:
    return 1 - (1 - t) * (1 - t)


def ease_in_out_quad(t: float) -> float:
    return 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2


def ease_in_cubic(t: float) -> float:
    return t**3


def ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def ease_in_out_cubic(t: float) -> float:
    return 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


_C1 = 1.70158
_C2 = _C1 * 1.525
_C3 = _C1 + 1


def ease_in_back(t: float) -> float:
    return _C3 * t**3 - _C1 * t * t


def ease_out_back(t: float) -> float:
    return 1 + _C3 * (t - 1) ** 3 + _C1 * (t - 1) ** 2


def ease_in_out_back(t: float) -> float:
    if t < 0.5:
        return ((2 * t) ** 2 * ((_C2 + 1) * 2 * t - _C2)) / 2
    return ((2 * t - 2) ** 2 * ((_C2 + 1) * (t * 2 - 2) + _C2) + 2) / 2


def ease_out_bounce(t: float) -> float:
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        return n1 * (t - 1.5 / d1) ** 2 + 0.75
    if t < 2.5 / d1:
        return n1 * (t - 2.25 / d1) ** 2 + 0.9375
    return n1 * (t - 2.625 / d1) ** 2 + 0.984375


def ease_out_elastic(t: float) -> float:
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi) / 3) + 1


RATE_FUNCTION_IMPLEMENTATIONS: dict[str, RateFunction] = {
    "linear": linear,
    "smooth": smooth,
    "rush_into": rush_into,
    "rush_from": rush_from,
    "slow_into": slow_into,
    "double_smooth": double_smooth,
    "there_and_back": there_and_back,
    "there_and_back_with_pause": there_and_back_with_pause,
    "running_start": running_start,
    "wiggle": wiggle,
    "lingering": lingering,
    "ease_in_sine": ease_in_sine,
    "ease_out_sine": ease_out_sine,
    "ease_in_out_sine": ease_in_out_sine,
    "ease_in_quad": ease_in_quad,
    "ease_out_quad": ease_out_quad,
    "ease_in_out_quad": ease_in_out_quad,
    "ease_in_cubic": ease_in_cubic,
    "ease_out_cubic": ease_out_cubic,
    "ease_in_out_cubic": ease_in_out_cubic,
    "ease_in_back": ease_in_back,
    "ease_out_back": ease_out_back,
    "ease_in_out_back": ease_in_out_back,
    "ease_out_bounce": ease_out_bounce,
    "ease_out_elastic": ease_out_elastic,
}


def rate(name: str, t: float) -> float:
    """Evaluate rate function ``name`` at ``t`` (0…1)."""
    return RATE_FUNCTION_IMPLEMENTATIONS.get(name, smooth)(_clamp(t))
