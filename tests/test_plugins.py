"""Extensions are only loaded when enabled; errors are contained."""

from __future__ import annotations

import shutil
from pathlib import Path

from manim_studio.plugins import PluginContext, PluginManager

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "plugins" / "punktgitter.py"


def test_disabled_plugins_are_not_run(tmp_path, qapp) -> None:
    folder = tmp_path / "plugins"
    folder.mkdir()
    marker = tmp_path / "ran.txt"
    (folder / "spy.py").write_text(f'"""Spion."""\nopen({str(marker)!r}, "w").write("x")\ndef register(api):\n    pass\n', encoding="utf-8")
    enabled: list[str] = []
    manager = PluginManager(folder, lambda: enabled)
    plugins = manager.discover()
    assert [(plugin.name, plugin.description, plugin.enabled) for plugin in plugins] == [("spy", "Spion.", False)]
    manager.load_enabled()
    assert not marker.exists()
    enabled.append("spy")
    manager.load_enabled()
    assert marker.exists() and manager.plugins[0].loaded


def test_broken_plugin_reports_error(tmp_path, qapp) -> None:
    folder = tmp_path / "plugins"
    folder.mkdir()
    (folder / "kaputt.py").write_text("def register(api):\n    raise RuntimeError('oops')\n", encoding="utf-8")
    manager = PluginManager(folder, lambda: ["kaputt"])
    manager.load_enabled()
    assert manager.plugins[0].error == "RuntimeError: oops" and not manager.plugins[0].loaded


def test_example_plugin_in_the_window(window, tmp_path) -> None:
    folder = window.context.plugins.folder
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy(EXAMPLE, folder / EXAMPLE.name)
    window.settings.enabled_plugins = ["punktgitter"]
    window.context.plugins.load_enabled()
    contributions = window.context.plugins.contributions
    assert [text for _plugin, text, _callback in contributions.actions] == ["Punktgitter einfügen"]
    assert any(style.name == "Neon" for style in window.context.library.styles())
    _plugin, _text, callback = contributions.actions[0]
    error = window.context.plugins.run_action(callback, PluginContext(window.controller, window.show_status))
    assert error == "" and len(window.editor.scene().objects) == 15
    window.document.undo_stack.undo()
    assert len(window.editor.scene().objects) == 14
    _plugin, _name, build = contributions.templates[0]
    window.controller.add_scene_from_template(build())
    assert window.editor.scene().name.startswith("Begrüßung")


def test_plugins_dialog_enables_and_disables(window) -> None:
    from PySide6.QtCore import Qt

    from manim_studio.ui.dialogs.plugins_dialog import PluginsDialog

    manager = window.context.plugins
    manager.folder.mkdir(parents=True, exist_ok=True)
    shutil.copy(EXAMPLE, manager.folder / EXAMPLE.name)
    dialog = PluginsDialog(manager, window.settings, window)
    item = dialog.list.item(0)
    assert item.data(Qt.ItemDataRole.UserRole) == "punktgitter" and item.checkState() == Qt.CheckState.Unchecked
    item.setCheckState(Qt.CheckState.Checked)
    assert dialog.apply() is False
    assert window.settings.enabled_plugins == ["punktgitter"] and manager.plugins[0].loaded
    window._fill_plugin_menu()
    assert "Punktgitter einfügen" in [action.text() for action in window.plugin_menu.actions()]
    dialog._fill()
    dialog.list.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert dialog.apply() is True and window.settings.enabled_plugins == []


def test_install_dialog_runs_pip_and_reports(qapp, monkeypatch) -> None:
    import sys

    from manim_studio.ui.dialogs import install_dialog

    assert install_dialog.install_arguments() == ["-m", "pip", "install", "--upgrade", "manim"]
    monkeypatch.setattr(install_dialog, "install_arguments", lambda: ["-c", "print('Successfully installed manim')"])
    dialog = install_dialog.InstallDialog(sys.executable)
    dialog.start()
    assert dialog.process.waitForFinished(30_000)
    qapp.processEvents()
    assert dialog.succeeded and "Successfully installed manim" in dialog.log.toPlainText()
    monkeypatch.setattr(install_dialog, "install_arguments", lambda: ["-c", "raise SystemExit(3)"])
    failing = install_dialog.InstallDialog(sys.executable)
    failing.start()
    assert failing.process.waitForFinished(30_000)
    qapp.processEvents()
    assert not failing.succeeded and "3" in failing.info.text()
