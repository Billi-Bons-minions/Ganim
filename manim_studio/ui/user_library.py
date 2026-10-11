"""The user's own styles, building blocks (components) and scene templates.

Everything is stored as JSON in the application's data folder, so it is
available in every project.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from manim_studio.logging_setup import log
from manim_studio.model.entities import Scene, SceneObject
from manim_studio.model.serialization import object_from_dict, object_to_dict, scene_from_dict, scene_to_dict

STYLE_FIELDS = ("stroke_color", "stroke_width", "stroke_opacity", "fill_color", "fill_opacity")
STYLE_PARAMS = ("font", "font_size", "bold", "italic")


@dataclass(frozen=True)
class Style:
    """A named look: colors, line width, opacity and text settings."""

    name: str
    values: dict[str, Any] = field(default_factory=dict)
    builtin: bool = False


@dataclass(frozen=True)
class Component:
    """A reusable group of objects."""

    name: str
    objects: tuple[dict[str, Any], ...]
    path: Path | None = None

    def create_objects(self) -> list[SceneObject]:
        return [object_from_dict(data) for data in self.objects]


@dataclass(frozen=True)
class Template:
    """A scene that can be added to a project as a starting point."""

    name: str
    scene: dict[str, Any]
    path: Path | None = None

    def create_scene(self) -> Scene:
        return scene_from_dict(self.scene)


BUILTIN_STYLES = (
    Style("highlight", {"stroke_color": "#F7D96F", "fill_color": "#F7D96F", "fill_opacity": 0.3, "stroke_width": 6.0}, True),
    Style("subtle", {"stroke_color": "#888888", "fill_color": "#888888", "fill_opacity": 0.15, "stroke_width": 2.0}, True),
    Style("solid_blue", {"stroke_color": "#58C4DD", "fill_color": "#58C4DD", "fill_opacity": 0.8, "stroke_width": 0.0}, True),
    Style("warning", {"stroke_color": "#FC6255", "fill_color": "#FC6255", "fill_opacity": 0.25, "stroke_width": 4.0}, True),
)


def style_of(obj: SceneObject) -> dict[str, Any]:
    """Collect the style of an object."""
    values: dict[str, Any] = {name: getattr(obj, name) for name in STYLE_FIELDS}
    for key in STYLE_PARAMS:
        if key in obj.params:
            values[key] = obj.params[key]
    return values


def _slug(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_")
    return slug[:60] or "item"


class UserLibrary(QObject):
    """Reads and writes styles, components and templates."""

    changed = Signal()

    def __init__(self, folder: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.folder = folder

    # --- helpers -----------------------------------------------------------------

    def _read(self, path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            log.warning("Could not read %s", path)
            return None

    def _write(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    def _file(self, kind: str, name: str) -> Path:
        folder = self.folder / kind
        path = folder / f"{_slug(name)}.json"
        number = 2
        while path.exists() and (self._read(path) or {}).get("name") != name:
            path = folder / f"{_slug(name)}_{number}.json"
            number += 1
        return path

    # --- styles ---------------------------------------------------------------------

    def styles(self) -> list[Style]:
        data = self._read(self.folder / "styles.json") if (self.folder / "styles.json").exists() else None
        user = [Style(str(item["name"]), dict(item.get("values", {}))) for item in data or [] if isinstance(item, dict) and "name" in item]
        return list(BUILTIN_STYLES) + user

    def save_style(self, name: str, values: dict[str, Any]) -> None:
        user = [style for style in self.styles() if not style.builtin and style.name != name]
        user.append(Style(name, dict(values)))
        self._write(self.folder / "styles.json", [{"name": style.name, "values": style.values} for style in user])
        self.changed.emit()

    def delete_style(self, name: str) -> None:
        user = [style for style in self.styles() if not style.builtin and style.name != name]
        self._write(self.folder / "styles.json", [{"name": style.name, "values": style.values} for style in user])
        self.changed.emit()

    # --- components -------------------------------------------------------------------

    def components(self) -> list[Component]:
        result = []
        for path in sorted((self.folder / "components").glob("*.json")):
            data = self._read(path)
            if isinstance(data, dict) and isinstance(data.get("objects"), list):
                result.append(Component(str(data.get("name", path.stem)), tuple(data["objects"]), path))
        return sorted(result, key=lambda item: item.name.lower())

    def save_component(self, name: str, objects: list[SceneObject]) -> None:
        self._write(self._file("components", name), {"name": name, "objects": [object_to_dict(obj) for obj in objects]})
        self.changed.emit()

    def delete_component(self, component: Component) -> None:
        if component.path is not None:
            component.path.unlink(missing_ok=True)
        self.changed.emit()

    # --- templates ----------------------------------------------------------------------

    def templates(self) -> list[Template]:
        result = []
        for path in sorted((self.folder / "templates").glob("*.json")):
            data = self._read(path)
            if isinstance(data, dict) and isinstance(data.get("scene"), dict):
                result.append(Template(str(data.get("name", path.stem)), data["scene"], path))
        return sorted(result, key=lambda item: item.name.lower())

    def save_template(self, name: str, scene: Scene) -> None:
        self._write(self._file("templates", name), {"name": name, "scene": scene_to_dict(scene)})
        self.changed.emit()

    def delete_template(self, template: Template) -> None:
        if template.path is not None:
            template.path.unlink(missing_ok=True)
        self.changed.emit()
