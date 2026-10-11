"""Offscreen smoke test of the main window (no rendering)."""

from __future__ import annotations

import importlib.util

import pytest

pytestmark = pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="PySide6 is not installed")


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


def test_groups_layers_locking_and_hiding(window) -> None:
    from PySide6.QtWidgets import QGraphicsItem

    from manim_studio.model.types import ObjectKind
    from manim_studio.ui.stage.items import GroupItem

    controller = window.controller
    first = controller.add_object(ObjectKind.CIRCLE, -2.0, 0.0)
    second = controller.add_object(ObjectKind.SQUARE, 2.0, 0.0)
    window.editor.select_objects([first, second])
    window.act_group.trigger()
    group = window.editor.selected_objects[0]
    assert window.editor.scene().object_by_id(group).kind == ObjectKind.GROUP
    assert isinstance(window.stage._items[group], GroupItem)
    assert window.stage._selectable_id(first) == group
    assert window.objects.topLevelItemCount() == 1 and window.objects.topLevelItem(0).childCount() == 2
    window.stage._entered_group = group
    assert window.stage._selectable_id(first) == first
    window.editor.select_objects([group])
    window.act_ungroup.trigger()
    assert sorted(window.editor.selected_objects) == sorted([first, second])
    assert window.objects.topLevelItemCount() == 2

    controller.set_locked([first], True)
    assert not window.stage._items[first].flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
    controller.select_all()
    assert window.editor.selected_objects == [second]
    controller.set_hidden([second], True)
    assert not window.stage._items[second].isVisible()
    window.document.undo_stack.undo()
    assert window.stage._items[second].isVisible()

    controller.rename_object(second, "Box")
    assert window.objects.item_for(second).text(0) == "Box"


def test_align_zoom_and_rulers(window) -> None:
    from manim_studio.model.types import ObjectKind

    controller = window.controller
    first = controller.add_object(ObjectKind.CIRCLE, -2.0, 1.0)
    second = controller.add_object(ObjectKind.SQUARE, 2.0, -1.0)
    window.editor.select_objects([first, second])
    window.arrange("left")
    assert window.stage.item_rect(first).left() == pytest.approx(window.stage.item_rect(second).left(), abs=0.5)
    from PySide6.QtWidgets import QToolButton

    from manim_studio.i18n import tr

    button = next(b for b in window.properties.findChildren(QToolButton) if b.toolTip() == tr("action.arrange.right"))
    button.click()
    assert window.stage.item_rect(first).right() == pytest.approx(window.stage.item_rect(second).right(), abs=0.5)
    window.arrange("vcenter")
    assert window.stage.item_rect(first).center().y() == pytest.approx(window.stage.item_rect(second).center().y(), abs=0.5)
    assert window.top_ruler.isVisible()
    window.act_rulers.trigger()
    assert not window.top_ruler.isVisible() and not window.settings.show_rulers
    window.act_rulers.trigger()
    zoom = window.stage.view_scale()
    window.editor.select_objects([first])
    window.zoom_to_selection()
    assert window.stage.view_scale() > zoom
    rect = window.stage.item_rect(second).translated(2 / window.stage.view_scale(), 0)
    correction, guides = window.stage._object_snap(rect, {second})
    assert correction.x() == pytest.approx(-2 / window.stage.view_scale(), abs=1e-6) and guides


def test_polygon_vertices_and_line_endpoints_on_stage(window, qapp) -> None:
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from manim_studio.model.types import ObjectKind
    from manim_studio.ui.stage.items import ROLE_ENDPOINT, ROLE_VERTEX

    controller = window.controller
    polygon = controller.add_object(ObjectKind.POLYGON, 0.0, 0.0)
    qapp.processEvents()
    handles = [handle for handle in window.stage._handles if handle.role == ROLE_VERTEX]
    assert len(handles) == 5
    before = [list(point) for point in window.editor.scene().object_by_id(polygon).params["points"]]
    start = window.stage.mapFromScene(handles[1].scenePos())
    end = start + QPoint(0, -120)
    viewport = window.stage.viewport()
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    QTest.mouseMove(viewport, start + QPoint(0, -60))
    QTest.mouseMove(viewport, end)
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)
    after = window.editor.scene().object_by_id(polygon).params["points"]
    assert after[1][1] > before[1][1] and after[0] == before[0]
    controller.remove_vertex(polygon, 0)
    assert len(window.editor.scene().object_by_id(polygon).params["points"]) == 4

    line = controller.add_object(ObjectKind.LINE, 0.0, 0.0)
    qapp.processEvents()
    assert [handle.role for handle in window.stage._handles] == [ROLE_ENDPOINT, ROLE_ENDPOINT]
    window.stage.endpointMoved.emit(line, 1, 3.0, 2.0)
    obj = window.editor.scene().object_by_id(line)
    from manim_studio.model.operations import line_endpoints

    assert line_endpoints(obj)[1] == pytest.approx((3.0, 2.0), abs=1e-4)


def test_inspector_editors_and_multi_selection(window) -> None:
    from PySide6.QtWidgets import QLabel

    from manim_studio.i18n import tr
    from manim_studio.model.types import ObjectKind
    from manim_studio.ui.data_editors import FontPicker, PointsEditor, TableEditor, WordColorsEditor
    from manim_studio.ui.widgets import SpinBox

    controller = window.controller
    polygon = controller.add_object(ObjectKind.POLYGON, 0.0, 0.0)
    editor = window.properties.findChild(PointsEditor)
    assert editor is not None and editor.table.rowCount() == 5
    editor.table.setCurrentCell(0, 0)
    editor._add()
    assert len(window.editor.scene().object_by_id(polygon).params["points"]) == 6
    assert editor.table.rowCount() == 6

    table = controller.add_object(ObjectKind.TABLE, 3.0, 0.0)
    grid = window.properties.findChild(TableEditor)
    width = grid.table.columnCount()
    grid._add_column()
    rows = window.editor.scene().object_by_id(table).params["rows"]
    assert all(len(row) == width + 1 for row in rows)

    text = controller.add_object(ObjectKind.TEXT, 0.0, 2.0)
    assert window.properties.findChild(FontPicker) is not None
    words = window.properties.findChild(WordColorsEditor)
    words._add()
    assert len(window.editor.scene().object_by_id(text).params["colored_words"]) == 1
    window.refresh_code()
    assert "t2c=" in window.code.editor.toPlainText()

    other = controller.add_object(ObjectKind.TEXT, 0.0, -2.0)
    window.editor.select_objects([text, other])
    labels = {label.text() for label in window.properties.findChildren(QLabel)}
    assert tr("param.font_size") in labels and tr("prop.center_x") in labels

    spin = SpinBox(-10.0, 10.0, 0.1, 3)
    spin.lineEdit().setText("pi/2")
    spin.interpretText()
    assert spin.value() == pytest.approx(1.571, abs=1e-3)


def test_graph_quick_actions_and_parameter_slider(window) -> None:
    from PySide6.QtWidgets import QToolButton

    from manim_studio.i18n import tr
    from manim_studio.model.stage_edits import VALUE, step_animation
    from manim_studio.model.types import ObjectKind
    from manim_studio.ui.parameter_slider import ParameterSlider

    controller = window.controller
    controller.add_object(ObjectKind.AXES, 0.0, 0.0)
    parameter = controller.add_object(ObjectKind.PARAMETER)
    assert window.editor.scene().object_by_id(parameter).name == "a"
    graph = controller.add_object(ObjectKind.FUNCTION_GRAPH)
    controller._edit("term", lambda s: s.object_by_id(graph).params.update(expression="a x^2"))
    window.editor.select_objects([graph])

    def click(key: str) -> None:
        button = next(b for b in window.properties.findChildren(QToolButton) if b.text() == tr(f"graph_action.{key}"))
        button.click()
        window.editor.select_objects([graph])

    click("derivative")
    click("zeros")
    kinds = [(obj.kind, obj.params.get("curve"), obj.params.get("feature")) for obj in window.editor.scene().objects]
    assert (ObjectKind.FUNCTION_GRAPH, "derivative", None) in kinds
    assert (ObjectKind.GRAPH_MARKERS, None, "zeros") in kinds

    window.editor.select_objects([parameter])
    slider = window.properties.findChild(ParameterSlider)
    slider.slider.setValue(slider.slider.maximum())
    assert window.editor.scene().object_by_id(parameter).params["value"] == 5.0
    assert window.resources.values == {"a": 5.0}
    controller.add_step()
    window.editor.select_objects([parameter])
    slider = window.properties.findChild(ParameterSlider)
    slider.slider.setValue(0)
    anim = step_animation(window.editor.scene(), window.editor.cursor, parameter, VALUE)
    assert anim is not None and anim.params["value"] == -5.0


def test_reference_animations_fade_out_all_and_camera(window, qapp) -> None:
    from PySide6.QtWidgets import QMenu, QToolButton

    from manim_studio.i18n import tr
    from manim_studio.model.types import AnimationKind, ObjectKind

    controller = window.controller
    dot = controller.add_object(ObjectKind.DOT, -2.0, 0.0)
    path = controller.add_object(ObjectKind.CIRCLE, 0.0, 0.0)
    window.editor.select_objects([dot])
    button = next(b for b in window.properties.findChildren(QToolButton) if b.text() == tr("anim_short.move_along_path"))
    menu: QMenu = button.menu()
    menu.aboutToShow.emit()
    action = next(a for a in menu.actions() if a.text() == window.editor.scene().object_by_id(path).name)
    action.trigger()
    animations = [anim for step in window.editor.scene().steps for anim in step.animations]
    assert [(a.kind, a.params.get("path")) for a in animations] == [(AnimationKind.MOVE_ALONG_PATH, path)]

    window.act_fade_out_all.trigger()
    last = window.editor.scene().steps[-1]
    assert sorted(a.target_id for a in last.animations) == sorted([dot, path])
    assert {a.kind for a in last.animations} == {AnimationKind.FADE_OUT}

    camera = controller.add_object(ObjectKind.CAMERA)
    assert controller.add_object(ObjectKind.CAMERA) == camera
    assert window.act_camera_view.isEnabled()
    window.act_camera_view.trigger()
    qapp.processEvents()
    assert window.stage.view_scale() > 0
    window.act_camera_view.trigger()


def test_open_package_from_window(window, tmp_path) -> None:
    from manim_studio.model.package import save_package
    from manim_studio.model.types import ObjectKind

    window.controller.add_object(ObjectKind.CIRCLE)
    package = tmp_path / "kreis.mspkg"
    save_package(window.document.project, package, None)
    window.document.new("leer")
    window.open_package(str(package), str(tmp_path / "entpackt"))
    assert window.document.path == (tmp_path / "entpackt" / "project.msproj").resolve()
    assert [obj.kind for obj in window.editor.scene().objects] == [ObjectKind.CIRCLE]


def test_components_templates_and_styles(window) -> None:
    from manim_studio.model.types import ObjectKind
    from manim_studio.templates import BUILTIN_TEMPLATES

    controller = window.controller
    circle = controller.add_object(ObjectKind.CIRCLE, 1.0, 1.0)
    window.context.library.save_component("Kreis", [window.editor.scene().object_by_id(circle)])
    assert len(window.library.component_tiles) == 1
    window.library.component_tiles[0].click()
    assert len(window.editor.scene().objects) == 2
    controller.insert_component(window.context.library.components()[0], -3.0, 2.0)
    newest = window.editor.scene().object_by_id(window.editor.selected_objects[0])
    assert (newest.x, newest.y) == (-3.0, 2.0)

    controller.apply_style({"fill_color": "#FC6255", "fill_opacity": 0.5}, [circle])
    assert window.editor.scene().object_by_id(circle).fill_color == "#FC6255"

    scenes_before = len(window.document.project.scenes)
    controller.add_scene_from_template(BUILTIN_TEMPLATES[1].build())
    assert len(window.document.project.scenes) == scenes_before + 1
    assert any(obj.kind == ObjectKind.GRAPH_MARKERS for obj in window.editor.scene().objects)


def test_code_view_follows_selection_and_history(window, qapp) -> None:
    from manim_studio.model.types import ObjectKind

    controller = window.controller
    circle = controller.add_object(ObjectKind.CIRCLE)
    square = controller.add_object(ObjectKind.SQUARE)
    window.refresh_code()
    window.bottom_tabs.setCurrentWidget(window.code)
    window.editor.select_objects([circle])
    selections = window.code.editor.extraSelections()
    assert selections and "Circle(" in selections[0].cursor.selectedText()
    first, _last = window._source_map.objects[(window.editor.scene_id, square)]
    window._on_code_line(first)
    assert window.editor.selected_objects == [square]
    assert window.history.stack() is window.document.undo_stack and window.document.undo_stack.count() >= 2
