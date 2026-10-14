"""Build the 2D drawing of an object for the stage (approximation of Manim).

Geometry is produced in scene pixels (``PX`` per Manim unit, y pointing
down) and centered on the object's bounding box, just like Manim's
``move_to`` centers mobjects.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontInfo,
    QFontMetricsF,
    QImage,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QTransform,
)
from PySide6.QtSvg import QSvgRenderer

from manim_studio.model.assets import resolve_asset_path
from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.geometry import (
    AXES_TICK_SIZE,
    AXES_TIP_LENGTH,
    AXIS_NUMBER_BUFF,
    AXIS_NUMBER_SIZE,
    PLANE_NUMBER_BUFF,
    AxesLayout,
    axes_layout,
    axis_number_text,
    origin_shift,
    param_float,
    plane_line_values,
    plane_numbers,
    polar_grid,
    serif_family,
    tick_values,
)
from manim_studio.model.latex import colored_parts, colorize
from manim_studio.model.schema import is_vector_image_path
from manim_studio.model.state import ObjectState
from manim_studio.model.types import GRAPH_TOOL_KINDS, ObjectKind
from manim_studio.render.tex_preview import TexPreviewCache

PX = 100.0
STROKE_UNIT = 0.01 * PX
TEX_UNITS_PER_PT_AT_48 = 0.04998
AXIS_LABEL_SIZE = 24.0
ARROW_TIP = 0.35


@dataclass
class Primitive:
    """One drawable part of an object."""

    path: QPainterPath | None = None
    pen: QPen | None = None
    brush: QBrush | None = None
    image: QImage | None = None
    #: where ``image`` is drawn; without an image it only widens the bounds
    rect: QRectF | None = None
    #: a part of the stage (scene pixels) shown magnified in ``rect`` (the zoom lens's display)
    view_source: QRectF | None = None


@dataclass
class Drawing:
    """All primitives of an object in local coordinates plus their bounds."""

    primitives: list[Primitive] = field(default_factory=list)
    bounds: QRectF = field(default_factory=QRectF)
    hit_path: QPainterPath | None = None
    offset: QPointF = field(default_factory=QPointF)


@dataclass
class StageResources:
    """Shared caches used while drawing."""

    tex: TexPreviewCache | None = None
    base_dir: Path | None = None
    images: dict[tuple[str, float], QImage] = field(default_factory=dict)
    tinted: dict[tuple[str, str, int], QImage] = field(default_factory=dict)
    #: Current parameter values (symbol -> value); ``None`` uses the start values.
    values: dict[str, float] | None = None
    #: Size of the video frame in Manim units (depends on the project's format).
    frame_size: tuple[float, float] = (8.0 * 16 / 9, 8.0)
    #: Orientation of the 3D camera (``None`` for the default view).
    view3d: object = None


def pt(x: float, y: float) -> QPointF:
    """Convert Manim units (y up) into scene pixels (y down)."""
    return QPointF(x * PX, -y * PX)


def _color(hex_color: str, opacity: float = 1.0) -> QColor:
    color = QColor(hex_color)
    if not color.isValid():
        color = QColor("#FFFFFF")
    color.setAlphaF(max(0.0, min(1.0, opacity)))
    return color


def _pen(hex_color: str, width: float, opacity: float, scale: float) -> QPen:
    pen = QPen(_color(hex_color, opacity), max(0.0, width) * STROKE_UNIT / max(scale, 0.01))
    # Cairo's defaults, which Manim keeps: flat ends and pointed corners up to a miter of 10 line widths
    # (Qt measures the miter from the middle of the line, so 10 widths there are 5 here)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    pen.setMiterLimit(5.0)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    return pen


def _shape_primitive(path: QPainterPath, obj: SceneObject, state: ObjectState) -> Primitive:
    brush = QBrush(_color(state.fill_color, obj.fill_opacity)) if obj.fill_opacity > 0 else None
    pen = _pen(state.stroke_color, obj.stroke_width, obj.stroke_opacity, state.scale) if obj.stroke_width > 0 else None
    return Primitive(path=path, pen=pen, brush=brush)


def _stroke_primitive(path: QPainterPath, obj: SceneObject, state: ObjectState) -> Primitive:
    return Primitive(path=path, pen=_pen(state.stroke_color, obj.stroke_width, obj.stroke_opacity, state.scale))


# --- basic shapes ----------------------------------------------------------------


def _polygon(points: list[tuple[float, float]]) -> QPainterPath:
    path = QPainterPath()
    path.moveTo(pt(*points[0]))
    for point in points[1:]:
        path.lineTo(pt(*point))
    path.closeSubpath()
    return path


def _ellipse_path(width: float, height: float) -> QPainterPath:
    """Like Manim's Circle: from the right, counterclockwise (Create starts there, Transform pairs the points so)."""
    path = QPainterPath()
    box = QRectF(-width / 2 * PX, -height / 2 * PX, width * PX, height * PX)
    path.moveTo(box.right(), 0.0)
    path.arcTo(box, 0.0, 360.0)
    path.closeSubpath()
    return path


def _rect_path(width: float, height: float) -> QPainterPath:
    """Like Manim's Rectangle: corners upper right, upper left, lower left, lower right."""
    return _polygon([(width / 2, height / 2), (-width / 2, height / 2), (-width / 2, -height / 2), (width / 2, -height / 2)])


def _triangle_path(radius: float) -> QPainterPath:
    angles = (90.0, 210.0, 330.0)
    return _polygon([(radius * math.cos(math.radians(a)), radius * math.sin(math.radians(a))) for a in angles])


def _line_path(length: float) -> QPainterPath:
    path = QPainterPath(pt(-length / 2, 0))
    path.lineTo(pt(length / 2, 0))
    return path


def _arrow_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    length = param_float(obj.params, "length", 3.0)
    tip = min(ARROW_TIP, 0.25 * length)
    shaft = QPainterPath(pt(-length / 2, 0))
    shaft.lineTo(pt(length / 2 - tip, 0))
    head = _polygon([(length / 2, 0), (length / 2 - tip, tip / 2), (length / 2 - tip, -tip / 2)])
    return [
        _stroke_primitive(shaft, obj, state),
        Primitive(path=head, brush=QBrush(_color(state.stroke_color, obj.stroke_opacity))),
    ]


# --- text ------------------------------------------------------------------------


_MANIM_FAMILY: list[str] = []


def manim_text_font() -> QFont:
    """The font Manim's ``Text`` uses without ``font=``: Pango's default, a serif font (e.g. Noto Serif, Times).

    The interface font (sans serif) would make texts on the stage narrower than in the video.
    """
    if not _MANIM_FAMILY:
        family = serif_family()
        if family is None:
            font = QFont("serif")
            font.setStyleHint(QFont.StyleHint.Serif)
            family = QFontInfo(font).family()
        _MANIM_FAMILY.append(family)
    return QFont(_MANIM_FAMILY[0])


#: Manim's ``Text`` is as big as a font whose em is ``font_size / 72`` units (measured: the same for every font).
EM_PER_POINT = 1.0 / 72.0


def text_font(obj: SceneObject, font_size: float) -> QFont:
    """Return a Qt font as large as Manim's ``Text`` at ``font_size`` (by its em, like Pango)."""
    font = QFont(str(obj.params.get("font"))) if obj.params.get("font") else manim_text_font()
    font.setBold(bool(obj.params.get("bold")))
    font.setItalic(bool(obj.params.get("italic")))
    font.setPixelSize(max(1, round(EM_PER_POINT * font_size * PX)))
    return font


def manim_line_height(font: QFont, line_spacing: float = 0.0) -> float:
    """Distance between the lines of Manim's ``Text``: ``font_size / 96 · (1 + line_spacing)``, 0.3 by default.

    Measured: the same for every font (Pango leaves the font's own line height aside here).
    """
    return font.pixelSize() * 0.75 * (1.0 + (line_spacing if line_spacing > 0 else 0.3))


def text_path(text: str, font: QFont, alignment: str = "left", line_spacing: float = 0.0) -> QPainterPath:
    """Return a vector path for (possibly multi-line) text."""
    path = QPainterPath()
    metrics = QFontMetricsF(font)
    line_height = manim_line_height(font, line_spacing)
    lines = text.split("\n")
    widest = max((metrics.horizontalAdvance(line) for line in lines), default=0.0)
    for index, line in enumerate(lines):
        width = metrics.horizontalAdvance(line)
        offset = {"center": (widest - width) / 2, "right": widest - width}.get(alignment, 0.0)
        path.addText(QPointF(offset, index * line_height), font, line)
    return path


def _colored_segments(line: str, words: list[tuple[str, str]]) -> list[tuple[str, str | None]]:
    segments: list[tuple[str, str | None]] = []
    index = 0
    while index < len(line):
        match = next(((word, color) for word, color in words if word and line.startswith(word, index)), None)
        if match is not None:
            segments.append(match)
            index += len(match[0])
        else:
            if segments and segments[-1][1] is None:
                segments[-1] = (segments[-1][0] + line[index], None)
            else:
                segments.append((line[index], None))
            index += 1
    return segments


def _text_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    font = text_font(obj, param_float(obj.params, "font_size", 48.0))
    text = str(obj.params.get("text", "")) or " "
    alignment = str(obj.params.get("alignment", "left"))
    spacing = param_float(obj.params, "line_spacing", 0.0)
    words = [(str(w), str(c)) for w, c in obj.params.get("colored_words", []) or [] if str(w)]
    base = QBrush(_color(state.fill_color, obj.fill_opacity))
    if state.fill_color2:
        return _letter_primitives(obj, state, text, font, alignment, spacing)
    if not words:
        return [Primitive(path=text_path(text, font, alignment, spacing), brush=base)]
    metrics = QFontMetricsF(font)
    line_height = manim_line_height(font, spacing)
    lines = text.split("\n")
    widest = max(metrics.horizontalAdvance(line) for line in lines)
    paths: dict[str | None, QPainterPath] = {}
    for index, line in enumerate(lines):
        x = {"center": (widest - metrics.horizontalAdvance(line)) / 2, "right": widest - metrics.horizontalAdvance(line)}.get(alignment, 0.0)
        for segment, color in _colored_segments(line, words):
            paths.setdefault(color, QPainterPath()).addText(QPointF(x, index * line_height), font, segment)
            x += metrics.horizontalAdvance(segment)
    return [
        Primitive(path=path, brush=base if color is None else QBrush(_color(color, obj.fill_opacity)))
        for color, path in paths.items()
    ]


def _letter_primitives(obj: SceneObject, state: ObjectState, text: str, font: QFont, alignment: str, spacing: float) -> list[Primitive]:
    """``Text(gradient=…)``: every character its own color; spaces and line breaks count like in Pango."""
    from manim_studio.model.gradients import letter_colors

    metrics = QFontMetricsF(font)
    line_height = manim_line_height(font, spacing)
    lines = text.split("\n")
    widest = max(metrics.horizontalAdvance(line) for line in lines)
    colors = letter_colors(state.fill_color, state.fill_color2, len(text))
    paths: dict[str, QPainterPath] = {}
    index = 0
    for row, line in enumerate(lines):
        left = {"center": (widest - metrics.horizontalAdvance(line)) / 2, "right": widest - metrics.horizontalAdvance(line)}.get(alignment, 0.0)
        for position, character in enumerate(line):
            if not character.isspace():
                # the advance of everything before it keeps the kerning of the whole line
                paths.setdefault(colors[index], QPainterPath()).addText(QPointF(left + metrics.horizontalAdvance(line[:position]), row * line_height), font, character)
            index += 1
        index += 1  # the line break
    return [Primitive(path=path, brush=QBrush(_color(color, obj.fill_opacity))) for color, path in paths.items()]


def _tinted_svg(svg: Path, color: str | None, height_px: float, resources: StageResources) -> QImage | None:
    renderer = QSvgRenderer(str(svg))
    if not renderer.isValid():
        return None
    view = renderer.viewBoxF()
    resolution = max(8, min(2000, round(height_px * 3)))
    key = (str(svg), color, resolution)
    if key not in resources.tinted:
        width = max(1, round(resolution * view.width() / max(view.height(), 0.001)))
        image = QImage(width, resolution, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        if color is not None:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(image.rect(), QColor(color))
        painter.end()
        resources.tinted[key] = image
    return resources.tinted[key]


def tex_image_primitives(
    obj: SceneObject, state: ObjectState, resources: StageResources, source: str, environment: str, tint: bool = True
) -> list[Primitive]:
    """LaTeX rendered to an SVG image (or the source text while it compiles)."""
    font_size = param_float(obj.params, "font_size", 48.0)
    svg = resources.tex.svg_path(source, environment) if resources.tex is not None else None
    if svg is not None:
        view = QSvgRenderer(str(svg)).viewBoxF()
        scale = TEX_UNITS_PER_PT_AT_48 * font_size / 48.0 * PX
        width, height = view.width() * scale, view.height() * scale
        image = _tinted_svg(svg, state.fill_color if tint else None, height, resources)
        if image is not None:
            rect = QRectF(-width / 2, -height / 2, width, height)
            return [Primitive(image=image, rect=rect, brush=QBrush(_color(state.fill_color, obj.fill_opacity)))]
    font = text_font(obj, font_size * 0.8)
    font.setItalic(True)
    color = _color(state.fill_color, obj.fill_opacity * (0.6 if svg is None else 1.0))
    return [Primitive(path=text_path(source or " ", font), brush=QBrush(color))]


def _math_tex_primitives(obj: SceneObject, state: ObjectState, resources: StageResources, scene: Scene | None = None) -> list[Primitive]:
    from manim_studio.model.latex_term import shown_latex

    latex = (shown_latex(scene, obj, resources.values) if scene is not None else None) or str(obj.params.get("latex", ""))
    parts = colored_parts(obj.params)
    if not parts:
        return tex_image_primitives(obj, state, resources, latex, "align*")
    base = QColor(state.fill_color).name()[1:].upper()
    colored = f"{{\\color[HTML]{{{base}}}{colorize(latex, parts)}}}"
    return tex_image_primitives(obj, state, resources, colored, "align*", tint=False)


# --- coordinate systems -------------------------------------------------------------


def _ticks(values_from: float, values_to: float, step: float) -> list[float]:
    if step <= 0 or values_to <= values_from:
        return []
    first = math.ceil(values_from / step - 1e-9)
    last = math.floor(values_to / step + 1e-9)
    if last - first > 400:
        return []
    return [index * step for index in range(first, last + 1)]


def _local_pt(layout: AxesLayout, xv: float, yv: float) -> QPointF:
    return pt(*layout.to_local(xv, yv))


def _axis_lines(layout: AxesLayout) -> QPainterPath:
    path = QPainterPath()
    oy = origin_shift(layout.y_min, layout.y_max)
    ox = origin_shift(layout.x_min, layout.x_max)
    path.moveTo(_local_pt(layout, layout.x_min, oy))
    path.lineTo(_local_pt(layout, layout.x_max, oy))
    path.moveTo(_local_pt(layout, ox, layout.y_min))
    path.lineTo(_local_pt(layout, ox, layout.y_max))
    return path


def _axis_ticks(layout: AxesLayout, x_step: float, y_step: float, tips: bool) -> QPainterPath:
    path = QPainterPath()
    ox, oy = origin_shift(layout.x_min, layout.x_max), origin_shift(layout.y_min, layout.y_max)
    size = AXES_TICK_SIZE
    for xv in tick_values(layout.x_min, layout.x_max, x_step, tips):
        if abs(xv - ox) < 1e-9:
            continue
        lx, ly = layout.to_local(xv, oy)
        path.moveTo(pt(lx, ly - size))
        path.lineTo(pt(lx, ly + size))
    for yv in tick_values(layout.y_min, layout.y_max, y_step, tips):
        if abs(yv - oy) < 1e-9:
            continue
        lx, ly = layout.to_local(ox, yv)
        path.moveTo(pt(lx - size, ly))
        path.lineTo(pt(lx + size, ly))
    return path


def _axis_tips(layout: AxesLayout) -> QPainterPath:
    ox, oy = origin_shift(layout.x_min, layout.x_max), origin_shift(layout.y_min, layout.y_max)
    tip = AXES_TIP_LENGTH
    ex, ey = layout.to_local(layout.x_max, oy)
    tx, ty = layout.to_local(ox, layout.y_max)
    path = _polygon([(ex, ey), (ex - tip, ey + tip / 2), (ex - tip, ey - tip / 2)])
    path.addPath(_polygon([(tx, ty), (tx - tip / 2, ty - tip), (tx + tip / 2, ty - tip)]))
    return path


def decimal_number_path(text: str, font_size: float = AXIS_NUMBER_SIZE) -> tuple[QPainterPath, float]:
    """A number set like Manim's ``DecimalNumber`` of ``Text`` characters, and the width of its first character.

    Each character is a separate glyph with a gap of 0.001 · font size, aligned at the bottom;
    a minus sign moves up to the middle of the next digit.
    """
    font = text_font(SceneObject(id="", kind=ObjectKind.TEXT, name=""), font_size)
    gap = 0.001 * font_size * PX
    glyphs: list[QPainterPath] = []
    cursor = 0.0
    for char in text:
        glyph = QPainterPath()
        glyph.addText(QPointF(0, 0), font, char)
        rect = glyph.boundingRect()
        glyph.translate(cursor - rect.left(), -rect.bottom())
        cursor += rect.width() + gap
        glyphs.append(glyph)
    for index, char in enumerate(text):
        rect = glyphs[index].boundingRect()
        if char == "-" and index + 1 < len(glyphs):
            following = glyphs[index + 1].boundingRect()
            glyphs[index].translate(0, following.top() + following.height() / 2 - rect.top())
        elif char == ",":
            glyphs[index].translate(0, rect.height() / 2)
    path = QPainterPath()
    for glyph in glyphs:
        path.addPath(glyph)
    return path, (glyphs[0].boundingRect().width() if glyphs else 0.0)


def _axis_labels(layout: AxesLayout, x_step: float, y_step: float, tips: bool) -> QPainterPath:
    """The numbers of the axes where Manim puts them (see ``geometry.axis_number_boxes``)."""
    path = QPainterPath()
    ox, oy = origin_shift(layout.x_min, layout.x_max), origin_shift(layout.y_min, layout.y_max)
    for xv in tick_values(layout.x_min, layout.x_max, x_step, tips):
        if abs(xv) < 1e-9:
            continue
        number, first = decimal_number_path(axis_number_text(xv, x_step))
        bounds = number.boundingRect()
        anchor = _local_pt(layout, xv, oy)
        center = anchor.x() - (first / 2 if xv < 0 else 0.0)
        number.translate(center - bounds.center().x(), anchor.y() + AXIS_NUMBER_BUFF * PX - bounds.top())
        path.addPath(number)
    for yv in tick_values(layout.y_min, layout.y_max, y_step, tips):
        if abs(yv) < 1e-9:
            continue
        number, _first = decimal_number_path(axis_number_text(yv, y_step))
        bounds = number.boundingRect()
        anchor = _local_pt(layout, ox, yv)
        number.translate(anchor.x() - AXIS_NUMBER_BUFF * PX - bounds.right(), anchor.y() - bounds.center().y())
        path.addPath(number)
    return path


def _axes_primitives(obj: SceneObject, state: ObjectState, frame_size: tuple[float, float] = (8.0 * 16 / 9, 8.0)) -> list[Primitive]:
    layout = axes_layout(obj)
    x_step, y_step = param_float(obj.params, "x_step", 1.0), param_float(obj.params, "y_step", 1.0)
    pen = _pen(state.stroke_color, obj.stroke_width, 1.0, state.scale)
    tips = bool(obj.params.get("tips", True))
    primitives = [Primitive(path=_axis_lines(layout), pen=pen), Primitive(path=_axis_ticks(layout, x_step, y_step, tips), pen=pen)]
    if tips:
        primitives.append(Primitive(path=_axis_tips(layout), brush=QBrush(_color(state.stroke_color))))
    if obj.params.get("show_numbers"):
        primitives.append(Primitive(path=_axis_labels(layout, x_step, y_step, tips), brush=QBrush(QColor("#FFFFFF"))))
    from manim_studio.ui.stage.drawing_graph import axis_label_primitives

    return primitives + axis_label_primitives(obj, state, layout, frame_size)


def _number_plane_primitives(obj: SceneObject, state: ObjectState) -> list[Primitive]:
    layout = axes_layout(obj)
    x_step, y_step = param_float(obj.params, "x_step", 1.0), param_float(obj.params, "y_step", 1.0)
    grid = QPainterPath()
    polar = polar_grid(obj)
    if polar is not None:
        # circles and rays around the origin, like Manim's PolarPlane behind the plane
        origin = _local_pt(layout, 0.0, 0.0)
        steps = round(polar.radius_max / polar.radius_step)
        for k in range(1, steps + 1):
            radius = k * polar.radius_step * polar.unit * PX
            grid.addEllipse(origin, radius, radius)
        reach = polar.radius_max * polar.unit * PX
        for k in range(polar.divisions):
            angle = 2 * math.pi * k / polar.divisions
            grid.moveTo(origin)
            grid.lineTo(QPointF(origin.x() + reach * math.cos(angle), origin.y() - reach * math.sin(angle)))
    else:
        for xv in plane_line_values(layout.x_min, layout.x_max, x_step):
            grid.moveTo(_local_pt(layout, xv, layout.y_min))
            grid.lineTo(_local_pt(layout, xv, layout.y_max))
        for yv in plane_line_values(layout.y_min, layout.y_max, y_step):
            grid.moveTo(_local_pt(layout, layout.x_min, yv))
            grid.lineTo(_local_pt(layout, layout.x_max, yv))
    grid_pen = _pen(state.stroke_color, obj.stroke_width, obj.stroke_opacity, state.scale)
    axis_pen = _pen("#FFFFFF", 2.0, 1.0, state.scale)
    frame = QPainterPath()
    frame.addRect(QRectF(_local_pt(layout, layout.x_min, layout.y_max), _local_pt(layout, layout.x_max, layout.y_min)))
    primitives = [
        Primitive(path=frame),
        Primitive(path=grid, pen=grid_pen),
        Primitive(path=_axis_lines(layout), pen=axis_pen),
    ]
    numbers = QPainterPath()
    for text, xv, yv, decimal in plane_numbers(obj):
        # next_to(point, DR, buff=SMALL_BUFF): the upper left corner of the number
        path = decimal_number_path(text)[0] if decimal else text_path(text, text_font(SceneObject(id="", kind=ObjectKind.TEXT, name=""), AXIS_NUMBER_SIZE))
        bounds = path.boundingRect()
        anchor = _local_pt(layout, xv, yv)
        path.translate(anchor.x() + PLANE_NUMBER_BUFF * PX - bounds.left(), anchor.y() + PLANE_NUMBER_BUFF * PX - bounds.top())
        numbers.addPath(path)
    if not numbers.isEmpty():
        primitives.append(Primitive(path=numbers, brush=QBrush(QColor("#FFFFFF"))))
    return primitives


# --- images ----------------------------------------------------------------------------


def _load_image(path: Path, resources: StageResources) -> QImage | None:
    try:
        stamp = path.stat().st_mtime
    except OSError:
        return None
    key = (str(path), stamp)
    if key not in resources.images:
        if is_vector_image_path(str(path)):
            renderer = QSvgRenderer(str(path))
            if not renderer.isValid():
                return None
            size = renderer.defaultSize().scaled(800, 800, Qt.AspectRatioMode.KeepAspectRatio)
            image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            renderer.render(painter)
            painter.end()
        else:
            image = QImage(str(path))
        if image.isNull():
            return None
        resources.images[key] = image
    return resources.images[key]


def _image_primitives(obj: SceneObject, resources: StageResources) -> list[Primitive]:
    height = param_float(obj.params, "height", 2.0) * PX
    raw = str(obj.params.get("path", ""))
    image = _load_image(resolve_asset_path(raw, resources.base_dir), resources) if raw else None
    opacity = param_float(obj.params, "opacity", 1.0)
    if image is None:
        width = height * 1.5
        rect = QRectF(-width / 2, -height / 2, width, height)
        path = QPainterPath()
        path.addRect(rect)
        path.moveTo(rect.topLeft())
        path.lineTo(rect.bottomRight())
        path.moveTo(rect.topRight())
        path.lineTo(rect.bottomLeft())
        return [Primitive(path=path, pen=QPen(QColor(200, 80, 80), 2))]
    width = height * image.width() / max(1, image.height())
    rect = QRectF(-width / 2, -height / 2, width, height)
    return [Primitive(image=image, rect=rect, brush=QBrush(QColor(255, 255, 255, round(255 * opacity))))]


# --- assembly ------------------------------------------------------------------------------


def _shape_drawing(obj: SceneObject, state: ObjectState, scene: Scene, resources: StageResources) -> tuple[list[Primitive], bool]:
    from manim_studio.ui.stage.drawing_3d import three_d_primitives
    from manim_studio.ui.stage.drawing_data import bar_chart_primitives, data_primitives
    from manim_studio.ui.stage.drawing_extra import extra_drawing
    from manim_studio.ui.stage.drawing_graph import graph_primitives, label_primitives, tool_primitives

    extra = extra_drawing(scene, obj, state, resources)
    if extra is not None:
        return extra
    params = obj.params
    kind = obj.kind
    if kind == ObjectKind.CIRCLE:
        radius = param_float(params, "radius", 1.0)
        return [_shape_primitive(_ellipse_path(2 * radius, 2 * radius), obj, state)], True
    if kind == ObjectKind.SQUARE:
        side = param_float(params, "side_length", 2.0)
        return [_shape_primitive(_rect_path(side, side), obj, state)], True
    if kind == ObjectKind.RECTANGLE:
        return [_shape_primitive(_rect_path(param_float(params, "width", 4.0), param_float(params, "height", 2.0)), obj, state)], True
    if kind == ObjectKind.ELLIPSE:
        return [_shape_primitive(_ellipse_path(param_float(params, "width", 3.0), param_float(params, "height", 1.5)), obj, state)], True
    if kind == ObjectKind.TRIANGLE:
        return [_shape_primitive(_triangle_path(param_float(params, "radius", 1.0)), obj, state)], True
    if kind == ObjectKind.LINE:
        return [_stroke_primitive(_line_path(param_float(params, "length", 3.0)), obj, state)], True
    if kind == ObjectKind.ARROW:
        return _arrow_primitives(obj, state), True
    if kind == ObjectKind.DOT:
        radius = param_float(params, "radius", 0.08)
        return [Primitive(path=_ellipse_path(2 * radius, 2 * radius), brush=QBrush(_color(state.fill_color, obj.fill_opacity)))], True
    if kind == ObjectKind.TEXT:
        return _text_primitives(obj, state), True
    if kind == ObjectKind.MATH_TEX:
        return _math_tex_primitives(obj, state, resources, scene), True
    if kind == ObjectKind.AXES:
        return _axes_primitives(obj, state, resources.frame_size), False
    if kind == ObjectKind.NUMBER_PLANE:
        return _number_plane_primitives(obj, state), False
    if kind == ObjectKind.FUNCTION_GRAPH:
        return graph_primitives(scene, obj, state, resources.values)
    if kind == ObjectKind.GRAPH_LABEL:
        return label_primitives(scene, obj, state, resources)
    if kind in GRAPH_TOOL_KINDS:
        return tool_primitives(scene, obj, state, resources.values)
    if kind == ObjectKind.PARAMETER:
        return [], False
    if kind == ObjectKind.CAMERA:
        return camera_primitives(obj, resources.frame_size), True
    if kind == ObjectKind.DATA_PLOT:
        return data_primitives(scene, obj, state)
    if kind in (ObjectKind.AXES_3D, ObjectKind.SURFACE, ObjectKind.CURVE_3D, ObjectKind.SOLID, ObjectKind.VECTOR_3D):
        return three_d_primitives(scene, obj, state, resources)
    if kind == ObjectKind.BAR_CHART:
        return bar_chart_primitives(obj, state)
    return _image_primitives(obj, resources), True


def camera_size(obj: SceneObject, frame_size: tuple[float, float]) -> tuple[float, float]:
    """Width and height (Manim units) of what the camera shows; 0 = the whole frame."""
    frame_width, frame_height = frame_size
    width = param_float(obj.params, "width", 0.0) or frame_width
    return width, width * frame_height / frame_width


def camera_primitives(obj: SceneObject, frame_size: tuple[float, float]) -> list[Primitive]:
    """Dashed frame with corner marks showing what the camera sees."""
    width, height = camera_size(obj, frame_size)
    rect = QRectF(-width / 2 * PX, -height / 2 * PX, width * PX, height * PX)
    frame = QPainterPath()
    frame.addRect(rect)
    pen = QPen(QColor(255, 255, 255, 170), 2.0, Qt.PenStyle.DashLine)
    pen.setCosmetic(True)
    corners = QPainterPath()
    size = min(rect.width(), rect.height()) * 0.08
    for corner, dx, dy in (
        (rect.topLeft(), 1, 1),
        (rect.topRight(), -1, 1),
        (rect.bottomLeft(), 1, -1),
        (rect.bottomRight(), -1, -1),
    ):
        corners.moveTo(corner.x() + dx * size, corner.y())
        corners.lineTo(corner)
        corners.lineTo(corner.x(), corner.y() + dy * size)
    corner_pen = QPen(QColor("#FFFFFF"), 3.0)
    corner_pen.setCosmetic(True)
    return [Primitive(path=frame, pen=pen), Primitive(path=corners, pen=corner_pen)]


def _primitive_rect(primitive: Primitive) -> QRectF:
    if primitive.rect is not None:
        return QRectF(primitive.rect)
    if primitive.path is not None:
        return primitive.path.boundingRect()
    return QRectF()


def _translate(primitive: Primitive, dx: float, dy: float) -> None:
    if primitive.path is not None:
        primitive.path = QTransform.fromTranslate(dx, dy).map(primitive.path)
    if primitive.rect is not None:
        primitive.rect = primitive.rect.translated(dx, dy)


def _hit_path(primitives: list[Primitive], bounds: QRectF, kind: ObjectKind) -> QPainterPath:
    if kind in (ObjectKind.LINE, ObjectKind.ARROW, ObjectKind.FUNCTION_GRAPH, ObjectKind.VECTOR, ObjectKind.DOUBLE_ARROW, ObjectKind.DASHED_LINE, ObjectKind.ARC, ObjectKind.CURVED_ARROW, ObjectKind.TANGENT, ObjectKind.SECANT, ObjectKind.CAMERA):
        combined = QPainterPath()
        for primitive in primitives:
            if primitive.path is not None:
                combined.addPath(primitive.path)
        stroker = QPainterPathStroker()
        stroker.setWidth(16)
        return stroker.createStroke(combined)
    path = QPainterPath()
    path.addRect(bounds)
    return path


def build_drawing(scene: Scene, shape: SceneObject, state: ObjectState, resources: StageResources) -> Drawing:
    """Return the centered drawing of ``shape`` with the colors of ``state``."""
    primitives, recenter = _shape_drawing(shape, state, scene, resources)
    bounds = QRectF()
    for primitive in primitives:
        bounds = bounds.united(_primitive_rect(primitive))
    offset = QPointF()
    if recenter and bounds.isValid():
        center = bounds.center()
        for primitive in primitives:
            _translate(primitive, -center.x(), -center.y())
        bounds.translate(-center.x(), -center.y())
        offset = QPointF(center)
    if state.warps:
        from manim_studio.ui.stage.warping import warp_primitives

        primitives = warp_primitives(primitives, state)
        bounds = QRectF()
        for primitive in primitives:
            bounds = bounds.united(_primitive_rect(primitive))
    if (state.fill_color2 or state.stroke_color2) and shape.kind != ObjectKind.TEXT:
        from manim_studio.ui.stage.gradients import apply_gradients

        apply_gradients(primitives, shape, state)
    if bounds.width() < 4 or bounds.height() < 4:
        bounds = bounds.adjusted(-4, -4, 4, 4)
    return Drawing(primitives=primitives, bounds=bounds, hit_path=_hit_path(primitives, bounds, shape.kind), offset=offset)
