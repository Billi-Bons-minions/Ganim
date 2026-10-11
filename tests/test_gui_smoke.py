"""Offscreen smoke test of the main window (no rendering)."""

from __future__ import annotations

import importlib.util

import pytest

pytestmark = pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="PySide6 is not installed")


@pytest.fixture()
def window(tmp_path, qapp):
    from PySide6.QtCore import QSettings, QThreadPool

    from manim_studio.i18n import set_language
    from manim_studio.ui.context import AppContext
    from manim_studio.ui.main_window import MainWindow
    from manim_studio.ui.settings import AppSettings
    from manim_studio.ui.theme import apply_theme

    app = qapp
    set_language("de")
    settings = AppSettings(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))
    settings.hidden_environment_warning = "manim,ffmpeg,latex"
    apply_theme(app, "dark", 1.0, tmp_path / "style")
    context = AppContext(settings)
    main = MainWindow(context, lambda: None)
    context.set_window(main)
    main.show()
    app.processEvents()
    yield main
    main.document.undo_stack.setClean()
    main.close()
    QThreadPool.globalInstance().waitForDone(60_000)
    app.processEvents()


def test_acceptance_workflow_without_code(window, tmp_path) -> None:
    from manim_studio.model.types import AnimationKind, ObjectKind

    controller = window.controller
    circle = controller.add_object(ObjectKind.CIRCLE, -3.0, 0.0)
    text = controller.add_object(ObjectKind.TEXT, 2.0, 1.5)
    square = controller.add_object(ObjectKind.SQUARE, -3.0, 0.0)
    window.editor.select_objects([circle])
    controller.add_animation(AnimationKind.CREATE, False)
    window.editor.select_objects([circle, square])
    controller.add_animation(AnimationKind.TRANSFORM, False)
    window.editor.select_objects([text])
    controller.add_animation(AnimationKind.WRITE, False)
    window.refresh_code()
    code = window.code.editor.toPlainText()
    assert "Create(kreis_1" in code and "Transform(kreis_1, quadrat_1" in code and "Write(text_1" in code
    assert window.timeline.steps.count() == 4

    project_file = tmp_path / "test.msproj"
    assert window._write(project_file)
    saved = window.document.project
    window.document.new("x")
    window.open_file(str(project_file), ask=False)
    assert window.document.project == saved
    assert [window.scene_tabs.tabText(i) for i in range(window.scene_tabs.count())] == ["Szene 1"]


def test_undo_redo_and_clipboard(window) -> None:
    from manim_studio.model.types import ObjectKind

    controller = window.controller
    dot = controller.add_object(ObjectKind.DOT)
    window.editor.select_objects([dot])
    controller.copy_objects()
    controller.paste_objects()
    assert [obj.name for obj in window.editor.scene().objects] == ["Punkt 1", "Punkt 2"]
    window.document.undo_stack.undo()
    assert len(window.editor.scene().objects) == 1
    window.document.undo_stack.redo()
    assert len(window.editor.scene().objects) == 2


def test_stage_policy_messages(window) -> None:
    from manim_studio.model.types import AnimationKind, ObjectKind

    controller = window.controller
    circle = controller.add_object(ObjectKind.CIRCLE)
    window.editor.select_objects([circle])
    controller.add_animation(AnimationKind.FADE_IN, False)
    allowed, message = controller.edit_policy("move", [circle])
    assert not allowed and "Bewegen" in message
    window.editor.inspect_step(-1)
    assert controller.edit_policy("move", [circle]) == (True, "")


def test_drop_from_library_creates_object(window) -> None:
    import warnings

    from PySide6.QtCore import QMimeData, QPointF, Qt
    from PySide6.QtGui import QDragEnterEvent, QDropEvent
    from PySide6.QtWidgets import QApplication

    from manim_studio.ui.stage.drawing import pt
    from manim_studio.ui.stage.view import KIND_MIME

    stage = window.stage
    mime = QMimeData()
    mime.setData(KIND_MIME, b"triangle")
    position = QPointF(stage.mapFromScene(pt(2.1, -1.1)))
    buttons, modifiers = Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        enter = QDragEnterEvent(position.toPoint(), Qt.DropAction.CopyAction, mime, buttons, modifiers)
    QApplication.sendEvent(stage.viewport(), enter)
    assert enter.isAccepted()
    event = QDropEvent(position, Qt.DropAction.CopyAction, mime, buttons, modifiers)
    QApplication.sendEvent(stage.viewport(), event)
    objects = window.editor.scene().objects
    assert [obj.kind.value for obj in objects] == ["triangle"]
    assert (objects[0].x, objects[0].y) == (2.0, -1.0)
    assert window.editor.selected_objects == [objects[0].id]


def test_window_rebuild_keeps_project_and_switches_language(window, qapp, monkeypatch) -> None:
    import sys

    from manim_studio.i18n import set_language
    from manim_studio.model.types import ObjectKind
    from manim_studio.ui.main_window import MainWindow

    errors = []
    monkeypatch.setattr(sys, "excepthook", lambda *info: errors.append(info))
    context = window.context
    context.controller.add_object(ObjectKind.CIRCLE)
    window.close_for_rebuild()
    window.deleteLater()
    qapp.processEvents()
    set_language("en")
    rebuilt = MainWindow(context, lambda: None)
    context.set_window(rebuilt)
    rebuilt.show()
    context.controller.add_object(ObjectKind.SQUARE)
    qapp.processEvents()
    assert [obj.name for obj in context.editor.scene().objects] == ["Kreis 1", "Square 1"]
    assert rebuilt.menuBar().actions()[0].text() == "&File"
    assert len(rebuilt.stage._items) == 2
    assert not errors
    rebuilt.document.undo_stack.setClean()
    rebuilt.close()
    set_language("de")
