"""Application preferences (applied live)."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from manim_studio.i18n import LANGUAGES, tr
from manim_studio.ui.settings import AppSettings
from manim_studio.ui.theme import SCALES, THEMES

GRID_STEPS = (0.1, 0.25, 0.5, 1.0)


class SettingsDialog(QDialog):
    """Language, theme, scale, Manim interpreter, grid and LaTeX preview."""

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle(tr("settings.title"))
        self.setMinimumWidth(520)
        self.language = self._combo([(name, code) for code, name in LANGUAGES.items()], settings.language)
        self.theme = self._combo([(tr(f"settings.theme.{name}"), name) for name in THEMES], settings.theme)
        self.scale = self._combo([(f"{round(value * 100)} %", value) for value in SCALES], settings.ui_scale)
        self.python = QLineEdit(settings.python_path)
        self.grid = self._combo([(f"{step:g}", step) for step in GRID_STEPS], settings.grid_step)
        self.latex_preview = QCheckBox(tr("settings.latex_preview_box"))
        self.latex_preview.setChecked(settings.latex_preview)
        browse = QToolButton()
        browse.setText("…")
        browse.clicked.connect(self._browse)
        reset = QToolButton()
        reset.setText(tr("settings.default"))
        reset.clicked.connect(lambda: self.python.setText(sys.executable))
        python_row = QHBoxLayout()
        python_row.addWidget(self.python, 1)
        python_row.addWidget(browse)
        python_row.addWidget(reset)
        hint = QLabel(tr("settings.python_hint"))
        hint.setProperty("role", "muted")
        form = QFormLayout()
        form.addRow(tr("settings.language"), self.language)
        form.addRow(tr("settings.theme"), self.theme)
        form.addRow(tr("settings.scale"), self.scale)
        form.addRow(tr("settings.python"), python_row)
        form.addRow("", hint)
        form.addRow(tr("settings.grid"), self.grid)
        form.addRow(tr("settings.latex_preview"), self.latex_preview)
        self.cache_label = QLabel()
        clear = QToolButton()
        clear.setText(tr("settings.cache_clear"))
        clear.clicked.connect(self._clear_cache)
        cache_row = QHBoxLayout()
        cache_row.addWidget(self.cache_label, 1)
        cache_row.addWidget(clear)
        form.addRow(tr("settings.cache"), cache_row)
        self._show_cache_size()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    @staticmethod
    def _combo(entries: list[tuple[str, object]], current: object) -> QComboBox:
        combo = QComboBox()
        for text, value in entries:
            combo.addItem(text, value)
        index = combo.findData(current)
        combo.setCurrentIndex(max(0, index))
        return combo

    def _show_cache_size(self) -> None:
        from manim_studio.ui.context import cache_size

        self.cache_label.setText(tr("settings.cache_size", size=f"{cache_size() / 1024 / 1024:.1f}"))

    def _clear_cache(self) -> None:
        from manim_studio.ui.context import clear_cache

        clear_cache()
        self._show_cache_size()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("settings.python"), self.python.text())
        if path:
            self.python.setText(path)

    def apply(self) -> bool:
        """Store the choices; return ``True`` if the window must be rebuilt."""
        rebuild = (
            self.language.currentData() != self.settings.language
            or self.theme.currentData() != self.settings.theme
            or float(self.scale.currentData()) != self.settings.ui_scale
        )
        self.settings.language = self.language.currentData()
        self.settings.theme = self.theme.currentData()
        self.settings.ui_scale = float(self.scale.currentData())
        self.settings.python_path = self.python.text().strip() or sys.executable
        self.settings.grid_step = float(self.grid.currentData())
        self.settings.latex_preview = self.latex_preview.isChecked()
        return rebuild
