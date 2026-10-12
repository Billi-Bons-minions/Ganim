"""Persistent application preferences (stored with ``QSettings``)."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QLocale, QSettings

MAX_RECENT = 8


def _to_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("1", "true", "yes")


#: Quality flags offered for the preview.
PREVIEW_QUALITIES = ("l", "m")

def system_language() -> str:
    """The UI language to start with: German on German systems, English everywhere else."""
    return "de" if QLocale.system().language() == QLocale.Language.German else "en"


class AppSettings:
    """Typed access to the user's preferences."""

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings or QSettings()

    def _get(self, key: str, default: object) -> object:
        value = self._settings.value(key)
        return default if value is None else value

    # --- general -----------------------------------------------------------

    @property
    def language(self) -> str:
        return str(self._get("language", system_language()))

    @language.setter
    def language(self, value: str) -> None:
        self._settings.setValue("language", value)

    @property
    def theme(self) -> str:
        """Color theme: ``dark`` or ``light``."""
        return str(self._get("theme", "dark"))

    @theme.setter
    def theme(self, value: str) -> None:
        self._settings.setValue("theme", value)

    @property
    def ui_scale(self) -> float:
        """Interface scale factor (fonts and controls)."""
        try:
            return float(self._get("ui_scale", 1.0))
        except (TypeError, ValueError):
            return 1.0

    @ui_scale.setter
    def ui_scale(self, value: float) -> None:
        self._settings.setValue("ui_scale", float(value))

    @property
    def show_welcome(self) -> bool:
        """Whether the welcome dialog appears at start-up."""
        return _to_bool(self._settings.value("show_welcome"), True)

    @show_welcome.setter
    def show_welcome(self, value: bool) -> None:
        self._settings.setValue("show_welcome", value)

    def splitter_state(self, key: str) -> object:
        """Return the saved state of a splitter."""
        return self._settings.value(f"layout/{key}")

    def set_splitter_state(self, key: str, state: object) -> None:
        """Remember the state of a splitter."""
        self._settings.setValue(f"layout/{key}", state)

    @property
    def python_path(self) -> str:
        """Interpreter used to run Manim (defaults to the current one)."""
        return str(self._get("python_path", "")) or sys.executable

    @python_path.setter
    def python_path(self, value: str) -> None:
        self._settings.setValue("python_path", "" if value == sys.executable else value)

    @property
    def latex_preview(self) -> bool:
        return _to_bool(self._settings.value("latex_preview"), True)

    @latex_preview.setter
    def latex_preview(self, value: bool) -> None:
        self._settings.setValue("latex_preview", value)

    @property
    def preview_quality(self) -> str:
        """Manim quality flag of the preview: ``"l"`` (fast, 480p15) or ``"m"`` (smooth, 720p30)."""
        value = str(self._get("preview_quality", "l"))
        return value if value in PREVIEW_QUALITIES else "l"

    @preview_quality.setter
    def preview_quality(self, value: str) -> None:
        self._settings.setValue("preview_quality", value if value in PREVIEW_QUALITIES else "l")

    @property
    def hidden_environment_warning(self) -> str:
        return str(self._get("hidden_environment_warning", ""))

    @hidden_environment_warning.setter
    def hidden_environment_warning(self, value: str) -> None:
        self._settings.setValue("hidden_environment_warning", value)

    # --- stage -------------------------------------------------------------

    @property
    def grid_step(self) -> float:
        try:
            return float(self._get("grid_step", 0.5))
        except (TypeError, ValueError):
            return 0.5

    @grid_step.setter
    def grid_step(self, value: float) -> None:
        self._settings.setValue("grid_step", float(value))

    @property
    def snap(self) -> bool:
        return _to_bool(self._settings.value("snap"), True)

    @snap.setter
    def snap(self, value: bool) -> None:
        self._settings.setValue("snap", value)

    @property
    def show_grid(self) -> bool:
        return _to_bool(self._settings.value("show_grid"), True)

    @show_grid.setter
    def show_grid(self, value: bool) -> None:
        self._settings.setValue("show_grid", value)

    @property
    def show_hidden(self) -> bool:
        return _to_bool(self._settings.value("show_hidden"), True)

    @show_hidden.setter
    def show_hidden(self, value: bool) -> None:
        self._settings.setValue("show_hidden", value)

    @property
    def show_rulers(self) -> bool:
        return _to_bool(self._settings.value("show_rulers"), True)

    @show_rulers.setter
    def show_rulers(self, value: bool) -> None:
        self._settings.setValue("show_rulers", value)

    @property
    def enabled_plugins(self) -> list[str]:
        value = self._settings.value("enabled_plugins")
        if not value:
            return []
        items = [value] if isinstance(value, str) else list(value)
        return [str(item) for item in items if item]

    @enabled_plugins.setter
    def enabled_plugins(self, names: list[str]) -> None:
        self._settings.setValue("enabled_plugins", list(names))

    # --- files -------------------------------------------------------------

    @property
    def recent_files(self) -> list[str]:
        value = self._settings.value("recent_files")
        if not value:
            return []
        items = [value] if isinstance(value, str) else list(value)
        return [str(item) for item in items if item]

    def add_recent_file(self, path: str) -> None:
        """Put ``path`` on top of the recent files list."""
        normalized = str(Path(path).resolve())
        files = [normalized] + [item for item in self.recent_files if item != normalized]
        self._settings.setValue("recent_files", files[:MAX_RECENT])

    def remove_recent_file(self, path: str) -> None:
        """Remove ``path`` from the recent files list."""
        self._settings.setValue("recent_files", [item for item in self.recent_files if item != path])

    def clear_recent_files(self) -> None:
        """Forget all recent files."""
        self._settings.setValue("recent_files", [])

    def last_directory(self, purpose: str) -> str:
        """Return the last folder used for ``purpose`` (open, image, export ...)."""
        return str(self._get(f"last_dir/{purpose}", str(Path.home())))

    def set_last_directory(self, purpose: str, folder: str) -> None:
        """Remember the last folder used for ``purpose``."""
        self._settings.setValue(f"last_dir/{purpose}", folder)

    # --- window ------------------------------------------------------------

    def window_state(self) -> tuple[object, object]:
        """Return saved geometry and dock state."""
        return self._settings.value("window/geometry"), self._settings.value("window/state")

    def save_window_state(self, geometry: object, state: object) -> None:
        """Store window geometry and dock state."""
        self._settings.setValue("window/geometry", geometry)
        self._settings.setValue("window/state", state)
