"""The zoom lens: Manim's ``ZoomedScene`` (a frame and a display that shows it magnified).

The object's position is the middle of the magnified area (the zoomed camera's frame);
the display has its own place and size. A scene has at most one lens, only in 2D.
"""

from __future__ import annotations

from dataclasses import dataclass

from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.geometry import param_float
from manim_studio.model.types import ObjectKind


@dataclass(frozen=True)
class Lens:
    """Frame (magnified area) and display, in scene units."""

    frame_width: float
    frame_height: float
    display_x: float
    display_y: float
    display_width: float
    display_height: float


def lens_of(scene: Scene) -> SceneObject | None:
    """The scene's zoom lens (the first one)."""
    return next((obj for obj in scene.objects if obj.kind == ObjectKind.ZOOM_LENS), None)


def lens_geometry(obj: SceneObject, scale: float = 1.0) -> Lens:
    """The frame is the display made ``zoom`` times smaller (``scale`` is a later zoom animation)."""
    width, height = param_float(obj.params, "display_width", 3.0), param_float(obj.params, "display_height", 3.0)
    zoom = max(param_float(obj.params, "zoom", 4.0), 1e-3)
    return Lens(width / zoom * scale, height / zoom * scale, param_float(obj.params, "display_x", 5.11), param_float(obj.params, "display_y", 2.0), width, height)
