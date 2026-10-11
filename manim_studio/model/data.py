"""Data points, regression and bar chart values (pure model logic)."""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass

from manim_studio.model.entities import SceneObject
from manim_studio.model.expression import evaluate_number

REGRESSIONS = ("none", "linear", "quadratic", "exponential")
DATA_STYLES = ("dots", "line", "both")
#: Manim's default bar colors (``BarChart.bar_colors``).
BAR_PALETTE = ("#003F5C", "#58508D", "#BC5090", "#FF6361", "#FFA600")


def data_points(obj: SceneObject) -> list[tuple[float, float]]:
    """Return the valid ``(x, y)`` rows of a data plot."""
    points = []
    for row in obj.params.get("data", []) or []:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        try:
            x, y = float(row[0]), float(row[1])
        except (TypeError, ValueError):
            continue
        if math.isfinite(x) and math.isfinite(y):
            points.append((x, y))
    return points


@dataclass(frozen=True)
class Fit:
    """A regression curve: ``coefficients`` depend on ``kind``."""

    kind: str
    coefficients: tuple[float, ...]
    r_squared: float

    def evaluate(self, x: float) -> float:
        if self.kind == "linear":
            m, b = self.coefficients
            return m * x + b
        if self.kind == "quadratic":
            a, b, c = self.coefficients
            return a * x * x + b * x + c
        a, b = self.coefficients
        return a * math.exp(b * x)

    def code(self, fmt) -> str:
        """Python code of the curve (``fmt`` formats numbers)."""
        if self.kind == "linear":
            m, b = self.coefficients
            return f"{fmt(m)} * x + {fmt(b)}"
        if self.kind == "quadratic":
            a, b, c = self.coefficients
            return f"{fmt(a)} * x ** 2 + {fmt(b)} * x + {fmt(c)}"
        a, b = self.coefficients
        return f"{fmt(a)} * np.exp({fmt(b)} * x)"

    def text(self) -> str:
        """Readable equation, e.g. ``y = 0.5x + 1.2``."""
        def n(value: float) -> str:
            return f"{value:.4g}"

        if self.kind == "linear":
            m, b = self.coefficients
            return f"y = {n(m)}x {'+' if b >= 0 else '-'} {n(abs(b))}"
        if self.kind == "quadratic":
            a, b, c = self.coefficients
            return f"y = {n(a)}x² {'+' if b >= 0 else '-'} {n(abs(b))}x {'+' if c >= 0 else '-'} {n(abs(c))}"
        a, b = self.coefficients
        return f"y = {n(a)}·e^({n(b)}x)"


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float] | None:
    size = len(vector)
    rows = [row[:] + [value] for row, value in zip(matrix, vector)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda r: abs(rows[r][column]))
        if abs(rows[pivot][column]) < 1e-12:
            return None
        rows[column], rows[pivot] = rows[pivot], rows[column]
        for r in range(size):
            if r != column:
                factor = rows[r][column] / rows[column][column]
                rows[r] = [a - factor * b for a, b in zip(rows[r], rows[column])]
    return [rows[i][size] / rows[i][i] for i in range(size)]


def _polynomial(points: list[tuple[float, float]], degree: int) -> list[float] | None:
    size = degree + 1
    sums = [sum(x**k for x, _y in points) for k in range(2 * degree + 1)]
    matrix = [[sums[i + j] for j in range(size)] for i in range(size)]
    vector = [sum(y * x**i for x, y in points) for i in range(size)]
    solution = _solve(matrix, vector)
    return solution[::-1] if solution is not None else None


def regression(points: list[tuple[float, float]], kind: str) -> Fit | None:
    """Least-squares fit of the points (``None`` if not possible)."""
    if kind == "linear" and len(points) >= 2:
        coefficients = _polynomial(points, 1)
    elif kind == "quadratic" and len(points) >= 3:
        coefficients = _polynomial(points, 2)
    elif kind == "exponential" and len(points) >= 2 and all(y > 0 for _x, y in points):
        logs = _polynomial([(x, math.log(y)) for x, y in points], 1)
        coefficients = [math.exp(logs[1]), logs[0]] if logs is not None else None
    else:
        return None
    if coefficients is None:
        return None
    fit = Fit(kind, tuple(round(value, 10) for value in coefficients), 0.0)
    mean = sum(y for _x, y in points) / len(points)
    total = sum((y - mean) ** 2 for _x, y in points)
    residual = sum((y - fit.evaluate(x)) ** 2 for x, y in points)
    r_squared = 1.0 - residual / total if total > 0 else 1.0
    return Fit(kind, fit.coefficients, r_squared)


def parse_table_text(text: str) -> list[list[float]]:
    """Read two numeric columns from CSV/TSV text (header lines are skipped)."""
    sample = text[:2000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t ")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";" if ";" in sample else ("\t" if "\t" in sample else ",")
    rows = []
    for row in csv.reader(io.StringIO(text), delimiter=delimiter):
        cells = [cell.strip() for cell in row if cell.strip()]
        if len(cells) < 2:
            continue
        x, y = evaluate_number(cells[0]), evaluate_number(cells[1])
        if x is not None and y is not None:
            rows.append([x, y])
    return rows


# --- bar charts ---------------------------------------------------------------------------


def bar_values(obj: SceneObject) -> list[tuple[str, float]]:
    """Return ``(name, value)`` of every bar."""
    bars = []
    for row in obj.params.get("bars", []) or []:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        value = evaluate_number(str(row[1]))
        if value is not None:
            bars.append((str(row[0]), value))
    return bars


def nice_step(span: float, ticks: int = 5) -> float:
    """A round tick distance (1, 2 or 5 times a power of ten)."""
    if span <= 0:
        return 1.0
    raw = span / ticks
    power = 10 ** math.floor(math.log10(raw))
    for factor in (1, 2, 5, 10):
        if raw <= factor * power:
            return factor * power
    return 10 * power


def bar_range(obj: SceneObject) -> tuple[float, float, float]:
    """``(y_min, y_max, y_step)`` of a bar chart (automatic unless set)."""
    values = [value for _name, value in bar_values(obj)] or [1.0]
    low = min(0.0, min(values))
    high = max(0.0, max(values))
    step = float(obj.params.get("y_step", 0.0) or 0.0)
    if step <= 0:
        step = nice_step(high - low)
    manual_max = float(obj.params.get("y_max", 0.0) or 0.0)
    bottom = math.floor(low / step + 1e-9) * step
    top = manual_max if manual_max > 0 and manual_max > bottom else math.ceil(high / step - 1e-9) * step
    if top <= bottom:
        top = bottom + step
    return round(bottom, 10), round(top, 10), round(step, 10)


def _rgb(color: str) -> tuple[float, float, float]:
    value = color.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def color_gradient(colors: list[str], count: int) -> list[str]:
    """Colors spread over ``count`` items like Manim's ``color_gradient``."""
    if count <= 0:
        return []
    if len(colors) == 1:
        return [colors[0].upper()] * count
    rgbs = [_rgb(color) for color in colors]
    result = []
    for index in range(count):
        alpha = (len(rgbs) - 1) * index / (count - 1) if count > 1 else 0.0
        floor = min(int(alpha), len(rgbs) - 2)
        part = alpha - floor
        if index == count - 1:
            floor, part = len(rgbs) - 2, 1.0
        mixed = [a * (1 - part) + b * part for a, b in zip(rgbs[floor], rgbs[floor + 1])]
        result.append("#" + "".join(f"{round(channel * 255):02X}" for channel in mixed))
    return result


def bar_colors(obj: SceneObject) -> list[str]:
    """Colors given to Manim (palette or the single fill color)."""
    return list(BAR_PALETTE) if obj.params.get("colors", "palette") == "palette" else [obj.fill_color]
