"""Extensions (plugins): small Python files that add templates, styles and menu actions.

Plugins are Python code and therefore only loaded after the user explicitly
enabled them in the settings. A plugin is a ``.py`` file (or a folder with
``__init__.py``) in the plugin folder that defines::

    def register(api):
        api.add_template("My scene", build_scene)        # build_scene() -> Scene
        api.add_style("Neon", {"stroke_color": "#39FF14"})
        api.add_action("Add a grid of dots", run)         # run(context)

See ``examples/plugins/`` for a complete example.
"""

from __future__ import annotations

import importlib.util
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal

from manim_studio.logging_setup import log
from manim_studio.model.entities import Scene

API_VERSION = 1


@dataclass
class PluginInfo:
    """A plugin found in the plugin folder."""

    name: str
    path: Path
    description: str = ""
    enabled: bool = False
    loaded: bool = False
    error: str = ""


@dataclass
class Contributions:
    """What all loaded plugins added."""

    templates: list[tuple[str, str, Callable[[], Scene]]] = field(default_factory=list)
    styles: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)
    actions: list[tuple[str, str, Callable[[Any], None]]] = field(default_factory=list)


class PluginAPI:
    """The object a plugin's ``register(api)`` receives."""

    version = API_VERSION

    def __init__(self, name: str, contributions: Contributions) -> None:
        self.name = name
        self._contributions = contributions

    def add_template(self, name: str, build: Callable[[], Scene]) -> None:
        """Offer a scene template (``build()`` returns a new :class:`Scene`)."""
        self._contributions.templates.append((self.name, str(name), build))

    def add_style(self, name: str, values: dict[str, Any]) -> None:
        """Offer a style (keys like ``stroke_color``, ``fill_opacity``, ``font_size``)."""
        self._contributions.styles.append((self.name, str(name), dict(values)))

    def add_action(self, text: str, callback: Callable[[Any], None]) -> None:
        """Add an entry to the "Extensions" menu; ``callback(context)`` runs when chosen."""
        self._contributions.actions.append((self.name, str(text), callback))


class PluginContext:
    """What a plugin action may use: the active scene, selection and undoable edits."""

    def __init__(self, controller: Any, message: Callable[[str], None]) -> None:
        self._controller = controller
        self._message = message

    @property
    def project(self):
        return self._controller.document.project

    def scene(self) -> Scene:
        """The active scene (read it; change it only through :meth:`edit`)."""
        return self._controller.scene()

    def selected_objects(self) -> list[str]:
        return list(self._controller.editor.selected_objects)

    def edit(self, text: str, mutate: Callable[[Scene], Any]) -> Any:
        """Change the active scene as one undo step."""
        return self._controller._edit(text, mutate)

    def add_object(self, kind: Any, x: float = 0.0, y: float = 0.0, **params: Any) -> str | None:
        """Create an object like the library does (returns its id)."""
        from manim_studio.model.types import ObjectKind

        return self._controller.add_object(ObjectKind(kind), x, y, **params)

    def message(self, text: str) -> None:
        """Show a short message in the status bar."""
        self._message(str(text))


def _description(path: Path) -> str:
    source = path / "__init__.py" if path.is_dir() else path
    try:
        text = source.read_text(encoding="utf-8")
    except OSError:
        return ""
    import ast

    try:
        docstring = ast.get_docstring(ast.parse(text)) or ""
    except SyntaxError:
        return ""
    return docstring.strip().split("\n")[0]


class PluginManager(QObject):
    """Finds plugins, loads the enabled ones and collects their contributions."""

    changed = Signal()

    def __init__(self, folder: Path, enabled: Callable[[], list[str]], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.folder = folder
        self._enabled = enabled
        self.contributions = Contributions()
        self.plugins: list[PluginInfo] = []

    def discover(self) -> list[PluginInfo]:
        """List the plugins in the folder (without running them)."""
        found = []
        if self.folder.is_dir():
            for path in sorted(self.folder.iterdir()):
                if path.name.startswith(("_", ".")):
                    continue
                if path.is_file() and path.suffix == ".py":
                    found.append(PluginInfo(path.stem, path, _description(path)))
                elif path.is_dir() and (path / "__init__.py").exists():
                    found.append(PluginInfo(path.name, path, _description(path)))
        enabled = set(self._enabled())
        loaded = {plugin.name: plugin for plugin in self.plugins}
        for plugin in found:
            plugin.enabled = plugin.name in enabled
            if plugin.name in loaded:
                plugin.loaded, plugin.error = loaded[plugin.name].loaded, loaded[plugin.name].error
        return found

    def load_enabled(self) -> None:
        """Run ``register(api)`` of every enabled plugin that is not loaded yet."""
        known = {plugin.name: plugin for plugin in self.plugins}
        for plugin in self.discover():
            if not plugin.enabled or (plugin.name in known and known[plugin.name].loaded):
                continue
            self._load(plugin)
            known[plugin.name] = plugin
        self.plugins = list(known.values())
        self.changed.emit()

    def _load(self, plugin: PluginInfo) -> None:
        source = plugin.path / "__init__.py" if plugin.path.is_dir() else plugin.path
        module_name = f"manim_studio_plugin_{plugin.name}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, source)
            if spec is None or spec.loader is None:
                raise ImportError("cannot load")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            register = getattr(module, "register", None)
            if not callable(register):
                raise AttributeError("register(api) is missing")
            register(PluginAPI(plugin.name, self.contributions))
        except Exception as error:  # noqa: BLE001 - a broken plugin must not break the app
            plugin.error = f"{type(error).__name__}: {error}"
            log.error("Plugin %s failed:\n%s", plugin.name, traceback.format_exc())
            return
        plugin.loaded = True
        log.info("Plugin %s loaded", plugin.name)

    def run_action(self, callback: Callable[[Any], None], context: PluginContext) -> str:
        """Run a plugin action; returns an error text (empty if it worked)."""
        try:
            callback(context)
        except Exception as error:  # noqa: BLE001 - report plugin errors instead of crashing
            log.error("Plugin action failed:\n%s", traceback.format_exc())
            return f"{type(error).__name__}: {error}"
        return ""
