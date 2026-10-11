"""Enable or disable extensions (plugins)."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from manim_studio.i18n import tr
from manim_studio.plugins import PluginManager
from manim_studio.ui.settings import AppSettings
from manim_studio.ui.theme import color


class PluginsDialog(QDialog):
    """Shows the plugins in the plugin folder with a check box each."""

    def __init__(self, manager: PluginManager, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.manager = manager
        self.settings = settings
        self.setWindowTitle(tr("plugins.title"))
        self.resize(560, 420)
        warning = QLabel(tr("plugins.warning"))
        warning.setWordWrap(True)
        warning.setProperty("role", "warning")
        folder = QLabel(tr("plugins.folder", path=str(manager.folder)))
        folder.setWordWrap(True)
        folder.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        open_folder = QPushButton(tr("plugins.open_folder"))
        open_folder.clicked.connect(self._open_folder)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.addButton(open_folder, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(warning)
        layout.addWidget(folder)
        layout.addWidget(self.list, 1)
        layout.addWidget(buttons)
        self._fill()

    def _fill(self) -> None:
        self.list.clear()
        plugins = self.manager.discover()
        if not plugins:
            empty = QListWidgetItem(tr("plugins.none"))
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(empty)
        for plugin in plugins:
            status = tr("plugins.error", error=plugin.error) if plugin.error else (tr("plugins.loaded") if plugin.loaded else "")
            title = plugin.name + (f"  ({status})" if status else "")
            item = QListWidgetItem(title + (f"\n{plugin.description}" if plugin.description else ""))
            item.setToolTip(str(plugin.path))
            if plugin.error:
                item.setForeground(color("danger"))
            item.setData(Qt.ItemDataRole.UserRole, plugin.name)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if plugin.enabled else Qt.CheckState.Unchecked)
            self.list.addItem(item)

    def _open_folder(self) -> None:
        self.manager.folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.manager.folder)))

    def apply(self) -> bool:
        """Store the choice; returns ``True`` if a plugin was switched off (needs a restart)."""
        enabled = []
        for row in range(self.list.count()):
            item = self.list.item(row)
            name = item.data(Qt.ItemDataRole.UserRole)
            if name and item.checkState() == Qt.CheckState.Checked:
                enabled.append(str(name))
        switched_off = bool(set(self.settings.enabled_plugins) - set(enabled))
        self.settings.enabled_plugins = enabled
        self.manager.load_enabled()
        return switched_off
