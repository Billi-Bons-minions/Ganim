"""Derive valid, unique Python identifiers from user-given names."""

from __future__ import annotations

import builtins
import keyword
import re
import unicodedata

from manim_studio.model.entities import Project, Scene
from manim_studio.model.three_d import is_3d
from manim_studio.model.types import RATE_FUNCTIONS, ObjectKind

_TRANSLITERATION = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})

#: Local names of generated build functions and updaters; an object with such a
#: name would be shadowed inside them (``x0 = x0.get_value()``).
BUILD_LOCALS = frozenset({"mob", "x0", "y0", "x1", "y1", "dx", "slope", "left", "right", "curve", "side"})

#: Helper functions the generated script may define next to the scene classes.
HELPER_FUNCTIONS = frozenset(
    {
        "studio_plot",
        "studio_dashed_line",
        "studio_lines_to_point",
        "studio_term",
        "studio_integral",
        "studio_beside",
        "studio_label_text",
        "studio_shape",
        "studio_camera_frame",
        "studio_angle",
        "studio_union",
        "studio_outline",
        "studio_dashed_graph",
        "studio_table_cells",
        "studio_map_point",
        "studio_map_complex",
        "studio_prepare_map",
        "studio_complex_labels",
    }
)

#: Lower-case names used by the generated code or Python itself.
RESERVED_VARIABLES = (
    frozenset(keyword.kwlist)
    | frozenset(keyword.softkwlist)
    | frozenset(RATE_FUNCTIONS)
    | frozenset(name for name in dir(builtins) if name.islower())
    | {"self", "np", "x", "config", "rate_functions", "manim", "numpy"}
    | BUILD_LOCALS
    | HELPER_FUNCTIONS
)

#: Class names the generated code relies on.
RESERVED_CLASSES = frozenset(
    {
        "Scene",
        "Circle",
        "Square",
        "Rectangle",
        "Triangle",
        "Ellipse",
        "Line",
        "Arrow",
        "Dot",
        "Text",
        "MathTex",
        "Axes",
        "NumberPlane",
        "FunctionGraph",
        "ImageMobject",
        "SVGMobject",
        "ManimColor",
        "Create",
        "Write",
        "DrawBorderThenFill",
        "FadeIn",
        "FadeOut",
        "GrowFromCenter",
        "Transform",
        "ReplacementTransform",
        "Rotate",
        "Indicate",
        "Circumscribe",
        "Uncreate",
    }
    | set(keyword.kwlist)
)


def _ascii_words(text: str) -> list[str]:
    ascii_text = unicodedata.normalize("NFKD", text.translate(_TRANSLITERATION))
    ascii_text = ascii_text.encode("ascii", "ignore").decode("ascii")
    return [word for word in re.split(r"[^A-Za-z0-9]+", ascii_text) if word]


def to_variable_name(name: str) -> str:
    """Convert a display name into a snake_case identifier (not yet unique)."""
    words = _ascii_words(name)
    identifier = "_".join(word.lower() for word in words) or "obj"
    if identifier[0].isdigit():
        identifier = "obj_" + identifier
    if identifier in RESERVED_VARIABLES:
        identifier += "_obj"
    return identifier


def to_class_name(name: str) -> str:
    """Convert a display name into a CamelCase class name (not yet unique)."""
    words = _ascii_words(name)
    identifier = "".join(word[:1].upper() + word[1:] for word in words) or "MainScene"
    if identifier[0].isdigit():
        identifier = "Scene" + identifier
    if identifier in RESERVED_CLASSES:
        identifier += "Scene"
    return identifier


def _make_unique(candidate: str, used: set[str], separator: str) -> str:
    if candidate not in used:
        return candidate
    number = 2
    while f"{candidate}{separator}{number}" in used:
        number += 1
    return f"{candidate}{separator}{number}"


#: Code that refers to the camera frame of a ``MovingCameraScene``.
CAMERA_FRAME = "self.camera.frame"
#: Variable of the helper frame that steers the camera of a ``ThreeDScene``.
CAMERA_FRAME_3D = "camera_frame"
#: Default width of the camera frame (Manim's ``frame_width``).
DEFAULT_FRAME_WIDTH = 8.0 * 16.0 / 9.0


def variable_names(scene: Scene) -> dict[str, str]:
    """Map every object id of a scene to a unique variable name."""
    used: set[str] = set()
    names: dict[str, str] = {}
    for obj in scene.objects:
        if obj.kind == ObjectKind.CAMERA:
            names[obj.id] = CAMERA_FRAME_3D if is_3d(scene) else CAMERA_FRAME
            used.add(names[obj.id])
            continue
        name = _make_unique(to_variable_name(obj.name), used, "_")
        used.add(name)
        names[obj.id] = name
    return names


def class_names(project: Project) -> dict[str, str]:
    """Map every scene id of a project to a unique class name."""
    used: set[str] = set()
    names: dict[str, str] = {}
    for scene in project.scenes:
        name = _make_unique(to_class_name(scene.name), used, "_")
        used.add(name)
        names[scene.id] = name
    return names
