"""Application preferences."""

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

GRID_STEPS = (0.1, 0.25, 0.5, 1.0)


class SettingsDialog(QDialog):
    """Language, Manim interpreter, grid and LaTeX preview."""

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle(tr("settings.title"))
        self.setMinimumWidth(480)
        self.language = QComboBox()
        for code, name in LANGUAGES.items():
            self.language.addItem(name, code)
        self.language.setCurrentIndex(max(0, self.language.findData(settings.language)))
        self.python = QLineEdit(settings.python_path)
        self.grid = QComboBox()
        for step in GRID_STEPS:
            self.grid.addItem(f"{step:g}", step)
        self.grid.setCurrentIndex(max(0, self.grid.findData(settings.grid_step)))
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
        form = QFormLayout()
        form.addRow(tr("settings.language"), self.language)
        form.addRow("", QLabel(tr("settings.language_restart")))
        form.addRow(tr("settings.python"), python_row)
        form.addRow("", QLabel(tr("settings.python_hint")))
        form.addRow(tr("settings.grid"), self.grid)
        form.addRow(tr("settings.latex_preview"), self.latex_preview)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("settings.python"), self.python.text())
        if path:
            self.python.setText(path)

    def apply(self) -> bool:
        """Store the choices; return ``True`` if the language changed."""
        changed_language = self.language.currentData() != self.settings.language
        self.settings.language = self.language.currentData()
        self.settings.python_path = self.python.text().strip() or sys.executable
        self.settings.grid_step = float(self.grid.currentData())
        self.settings.latex_preview = self.latex_preview.isChecked()
        return changed_language
