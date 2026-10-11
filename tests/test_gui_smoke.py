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
    assert len(window.timeline.canvas._blocks) == 3

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


def test_stage_records_animations_and_explains_wait_steps(window) -> None:
    from manim_studio.model.types import AnimationKind, ObjectKind, StepKind

    controller = window.controller
    circle = controller.add_object(ObjectKind.CIRCLE)
    window.editor.select_objects([circle])
    controller.add_animation(AnimationKind.FADE_IN, False)
    toasts = []
    controller.animationRecorded.connect(toasts.append)
    assert controller.edit_policy("move", [circle]) == (True, "")
    controller.move_objects([circle], 2.0, 0.0)
    step = window.editor.scene().steps[0]
    assert [anim.kind for anim in step.animations] == [AnimationKind.FADE_IN, AnimationKind.MOVE]
    assert toasts and "Bewegen" in toasts[0]
    controller.add_step(StepKind.WAIT)
    allowed, message = controller.edit_policy("move", [circle])
    assert not allowed and "Warte" in message


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


def test_guided_tour_advances_on_user_actions(window) -> None:
    from manim_studio.model.types import AnimationKind, ObjectKind, StepKind

    window.start_tutorial()
    tour = window.tour
    assert tour.current().key == "intro"
    tour.advance()
    assert tour.current().key == "add_circle" and tour.current().target() is window.library.tiles[ObjectKind.CIRCLE]
    window.library.tiles[ObjectKind.CIRCLE].click()
    tour._poll()
    assert tour.current().key == "animate"
    window.properties.animation_buttons[AnimationKind.CREATE].click()
    tour._poll()
    assert tour.current().key == "timeline"
    tour.advance()
    window.timeline.add_step_button.click()
    tour._poll()
    assert tour.current().key == "drag"
    circle = window.editor.scene().objects[0].id
    window.controller.move_objects([circle], 3.0, 0.0)
    tour._poll()
    assert tour.current().key == "preview"
    steps = window.editor.scene().steps
    assert [anim.kind for anim in steps[1].animations] == [AnimationKind.MOVE] and steps[1].kind == StepKind.PLAY
    window._preview_seen = True
    tour._poll()
    assert tour.current().key == "done"
    tour.advance()
    assert not tour.isVisible()


def test_examples_open_from_window(window) -> None:
    from manim_studio.examples import EXAMPLES

    window.open_example(EXAMPLES[0].key)
    assert window.document.path is None and window.editor.scene().objects
    assert not window.document.is_dirty



def _mouse(canvas, kind, point, buttons):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    event = QMouseEvent(kind, QPointF(point), QPointF(canvas.mapToGlobal(point.toPoint())), Qt.MouseButton.LeftButton, buttons, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(canvas, event)


def _drag(canvas, start, end):
    from PySide6.QtCore import QEvent, Qt

    _mouse(canvas, QEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton)
    for index in range(1, 6):
        _mouse(canvas, QEvent.Type.MouseMove, start + (end - start) * (index / 5), Qt.MouseButton.LeftButton)
    _mouse(canvas, QEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)


def test_timeline_canvas_editing(window) -> None:
    from PySide6.QtCore import QPointF

    from manim_studio.model.types import AnimationKind, ObjectKind

    controller = window.controller
    a = controller.add_object(ObjectKind.CIRCLE)
    b = controller.add_object(ObjectKind.SQUARE, 2.0, 0.0)
    window.editor.select_objects([a])
    controller.add_animation(AnimationKind.CREATE, False)
    window.editor.select_objects([b])
    controller.add_animation(AnimationKind.FADE_IN, False)
    canvas = window.timeline.canvas
    first_bar = canvas._blocks[0].bars[0][1]
    _drag(canvas, first_bar.center(), first_bar.center() + QPointF(canvas.pps * 0.5, 0))
    step0 = window.editor.scene().steps[0]
    assert step0.animations[0].delay == 0.5
    bar = canvas._blocks[0].bars[0][1]
    _drag(canvas, QPointF(bar.right() - 2, bar.center().y()), QPointF(bar.right() - 2 + canvas.pps, bar.center().y()))
    assert window.editor.scene().steps[0].animations[0].run_time == 2.0
    window.document.undo_stack.undo()
    assert window.editor.scene().steps[0].animations[0].run_time == 1.0
    second_bar = canvas._blocks[1].bars[0][1]
    target_header = canvas._blocks[0].header
    _drag(canvas, second_bar.center(), QPointF(target_header.center().x(), second_bar.center().y() + canvas.lane_height * 2))
    steps = window.editor.scene().steps
    assert len(steps) == 1 and [anim.kind for anim in steps[0].animations] == [AnimationKind.CREATE, AnimationKind.FADE_IN]


def test_step_reorder_and_scrubbing(window) -> None:
    from PySide6.QtCore import QPointF

    from manim_studio.model.types import AnimationKind, ObjectKind

    controller = window.controller
    circle = controller.add_object(ObjectKind.CIRCLE)
    window.editor.select_objects([circle])
    controller.add_animation(AnimationKind.CREATE, False)
    controller.add_animation(AnimationKind.MOVE, False)
    canvas = window.timeline.canvas
    ids = [step.id for step in window.editor.scene().steps]
    header = canvas._blocks[1].header
    _drag(canvas, header.center(), QPointF(canvas.time_to_x(0) + 2, header.center().y()))
    assert [step.id for step in window.editor.scene().steps] == list(reversed(ids))
    _drag(canvas, QPointF(canvas.time_to_x(0.2), 5), QPointF(canvas.time_to_x(1.5), 5))
    assert window.editor.playhead == pytest.approx(1.5, abs=0.02)
    item = window.stage._items[circle]
    assert 0.0 < item.effects.draw < 1.0
    window.playback.play()
    window.playback._tick()
    assert window.editor.playhead >= 1.5
    window.playback.stop()
    assert window.editor.playhead is None
