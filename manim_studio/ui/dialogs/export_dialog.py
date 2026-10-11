"""Dialog for exporting a scene as MP4, GIF or PNG."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from manim_studio.codegen.naming import class_names
from manim_studio.i18n import tr
from manim_studio.model.entities import Project, RenderSettings
from manim_studio.render.command import CUSTOM_QUALITY, OUTPUT_FORMATS, QUALITY_PRESETS
from manim_studio.ui.widgets import ColorButton

_EXTENSIONS = {"mp4": "mp4", "gif": "gif", "png": "png"}


@dataclass(frozen=True)
class ExportRequest:
    """What the user chose in the export dialog."""

    scene_id: str
    settings: RenderSettings
    background: str
    target: Path


class ExportDialog(QDialog):
    """Collects format, quality, background and output location."""

    def __init__(self, project: Project, scene_id: str, default_dir: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("export.title"))
        self.project = project
        settings = project.render
        self.scene_combo = QComboBox()
        for scene in project.scenes:
            self.scene_combo.addItem(scene.name, scene.id)
        self.scene_combo.setCurrentIndex(max(0, self.scene_combo.findData(scene_id)))
        self.format_combo = QComboBox()
        for name in OUTPUT_FORMATS:
            self.format_combo.addItem(tr(f"export.format.{name}"), name)
        self.format_combo.setCurrentIndex(max(0, self.format_combo.findData(settings.format)))
        self.quality_combo = QComboBox()
        for key, (width, height, fps) in QUALITY_PRESETS.items():
            self.quality_combo.addItem(tr(f"export.quality.{key}", width=width, height=height, fps=fps), key)
        self.quality_combo.addItem(tr("export.quality.custom"), CUSTOM_QUALITY)
        self.quality_combo.setCurrentIndex(max(0, self.quality_combo.findData(settings.quality)))
        self.width_spin = self._spin(16, 7680, settings.width)
        self.height_spin = self._spin(16, 4320, settings.height)
        self.fps_spin = self._spin(1, 120, settings.fps)
        self.png_step = QComboBox()
        self.background = ColorButton()
        self.folder_edit = QLineEdit(settings.output_dir or default_dir)
        self.name_edit = QLineEdit()
        self.target_label = QLabel()
        self.target_label.setWordWrap(True)
        self._build_layout()
        self.scene_combo.currentIndexChanged.connect(self._on_scene_changed)
        self.quality_combo.currentIndexChanged.connect(self._update_enabled)
        self.format_combo.currentIndexChanged.connect(self._update_enabled)
        self.folder_edit.textChanged.connect(self._update_target)
        self.name_edit.textChanged.connect(self._update_target)
        self._on_scene_changed()
        self.png_step.setCurrentIndex(max(0, self.png_step.findData(settings.png_after_step)))

    @staticmethod
    def _spin(minimum: int, maximum: int, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        return spin

    def _build_layout(self) -> None:
        form = QFormLayout()
        form.addRow(tr("export.scene"), self.scene_combo)
        form.addRow(tr("export.format"), self.format_combo)
        form.addRow(tr("export.quality"), self.quality_combo)
        size = QHBoxLayout()
        size.addWidget(self.width_spin)
        size.addWidget(QLabel("×"))
        size.addWidget(self.height_spin)
        form.addRow(tr("export.resolution"), size)
        form.addRow(tr("export.fps"), self.fps_spin)
        form.addRow(tr("export.png_step"), self.png_step)
        form.addRow(tr("export.background"), self.background)
        folder = QHBoxLayout()
        folder.addWidget(self.folder_edit, 1)
        browse = QToolButton()
        browse.setText("…")
        browse.clicked.connect(self._browse)
        folder.addWidget(browse)
        form.addRow(tr("export.folder"), folder)
        form.addRow(tr("export.file_name"), self.name_edit)
        form.addRow(tr("export.target"), self.target_label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("export.start"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _scene(self):
        return self.project.scene_by_id(self.scene_combo.currentData())

    def _on_scene_changed(self) -> None:
        scene = self._scene()
        if scene is None:
            return
        self.background.set_color(scene.background_color)
        self.name_edit.setText(class_names(self.project).get(scene.id, "Scene"))
        current = self.png_step.currentData()
        self.png_step.clear()
        self.png_step.addItem(tr("export.png_last"), -1)
        for index in range(len(scene.steps)):
            self.png_step.addItem(tr("export.png_after", step=index + 1), index)
        self.png_step.setCurrentIndex(max(0, self.png_step.findData(current)))
        self._update_enabled()

    def _update_enabled(self) -> None:
        custom = self.quality_combo.currentData() == CUSTOM_QUALITY
        is_png = self.format_combo.currentData() == "png"
        for widget in (self.width_spin, self.height_spin):
            widget.setEnabled(custom)
        self.fps_spin.setEnabled(custom and not is_png)
        self.png_step.setEnabled(is_png)
        if not custom:
            width, height, fps = QUALITY_PRESETS[self.quality_combo.currentData()]
            self.width_spin.setValue(width)
            self.height_spin.setValue(height)
            self.fps_spin.setValue(fps)
        self._update_target()

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, tr("export.folder"), self.folder_edit.text())
        if folder:
            self.folder_edit.setText(folder)

    def target_path(self) -> Path:
        """Return the file that will be written."""
        name = self.name_edit.text().strip() or "scene"
        extension = _EXTENSIONS[self.format_combo.currentData()]
        return Path(self.folder_edit.text().strip() or ".").expanduser() / f"{name}.{extension}"

    def _update_target(self) -> None:
        self.target_label.setText(str(self.target_path()))

    def request(self) -> ExportRequest:
        """Return the chosen settings."""
        settings = RenderSettings(
            quality=self.quality_combo.currentData(),
            width=self.width_spin.value(),
            height=self.height_spin.value(),
            fps=self.fps_spin.value(),
            format=self.format_combo.currentData(),
            output_dir=self.folder_edit.text().strip(),
            png_after_step=int(self.png_step.currentData() if self.png_step.currentData() is not None else -1),
        )
        return ExportRequest(self.scene_combo.currentData(), settings, self.background.color(), self.target_path())
