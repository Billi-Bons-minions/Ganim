"""The main window: wires model, panels, stage and rendering together."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QPoint,
    QProcess,
    QRunnable,
    QStandardPaths,
    Qt,
    QThreadPool,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QTabBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from manim_studio import APP_NAME, __version__
from manim_studio.codegen import CodegenError, CodegenOptions, generate_script
from manim_studio.i18n import tr
from manim_studio.model.assets import relative_asset_path, resolve_asset_path
from manim_studio.model.serialization import FILE_SUFFIX, ProjectFormatError
from manim_studio.model.state import START, states_after
from manim_studio.model.types import ObjectKind, StepKind
from manim_studio.render.environment import EnvironmentReport, check_environment
from manim_studio.render.tex_preview import TexPreviewCache
from manim_studio.ui.controller import EditorController
from manim_studio.ui.dialogs.environment_dialog import EnvironmentDialog
from manim_studio.ui.dialogs.export_dialog import ExportDialog
from manim_studio.ui.dialogs.messages import codegen_error_text
from manim_studio.ui.dialogs.settings_dialog import SettingsDialog
from manim_studio.ui.document import ProjectDocument
from manim_studio.ui.editor_state import EditorState
from manim_studio.ui.icons import app_icon, kind_icon
from manim_studio.ui.panels.library_panel import LIBRARY_ORDER, LibraryPanel
from manim_studio.ui.panels.objects_panel import ObjectsPanel
from manim_studio.ui.panels.output_panels import CodePanel, LogPanel
from manim_studio.ui.panels.player_panel import PlayerPanel
from manim_studio.ui.panels.properties_panel import PropertiesPanel
from manim_studio.ui.panels.timeline_panel import TimelinePanel, build_animation_menu
from manim_studio.ui.render_controller import RenderController
from manim_studio.ui.settings import AppSettings
from manim_studio.ui.stage.drawing import StageResources
from manim_studio.ui.stage.view import StageView

CODE_REFRESH_MS = 250
STATUS_TIMEOUT_MS = 6000


class _EnvironmentSignals(QObject):
    done = Signal(object)


class _EnvironmentJob(QRunnable):
    def __init__(self, python: str, signals: _EnvironmentSignals) -> None:
        super().__init__()
        self.python = python
        self.signals = signals

    def run(self) -> None:
        report = check_environment(self.python)
        try:
            self.signals.done.emit(report)
        except RuntimeError:
            pass


class MainWindow(QMainWindow):
    """Manim Studio's main window."""

    def __init__(self, settings: AppSettings, initial_file: str | None = None) -> None:
        super().__init__()
        self.settings = settings
        self.setWindowIcon(app_icon())
        self.document = ProjectDocument(tr("scene.first_name"), self)
        self.editor = EditorState(self.document, self)
        self.controller = EditorController(self.document, self.editor, settings, self)
        self.environment: EnvironmentReport | None = None
        cache = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)) / "tex"
        self.tex_cache = TexPreviewCache(cache, enabled=settings.latex_preview and shutil.which("latex") is not None, parent=self)
        self.resources = StageResources(tex=self.tex_cache)
        self.render = RenderController(self.document, self.editor, settings, self.latex_available, self)
        self._env_signals = _EnvironmentSignals()
        self._env_signals.done.connect(self._on_environment)
        self._code_timer = QTimer(self, singleShot=True, interval=CODE_REFRESH_MS)
        self._code_timer.timeout.connect(self.refresh_code)
        self._build_central()
        self._build_docks()
        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._build_statusbar()
        self._connect()
        self._restore_window()
        self.refresh_all()
        if initial_file:
            QTimer.singleShot(0, lambda: self.open_file(initial_file))
        QTimer.singleShot(400, self.check_environment)

    # --- construction -----------------------------------------------------------------

    def _build_central(self) -> None:
        self.stage = StageView()
        self.stage.set_policy(self.controller.edit_policy)
        self.stage.set_grid(self.settings.show_grid, self.settings.grid_step, self.settings.snap)
        self.scene_tabs = QTabBar()
        self.scene_tabs.setMovable(True)
        self.scene_tabs.setExpanding(False)
        self.scene_tabs.setDocumentMode(True)
        self.scene_tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        add_scene = QToolButton()
        add_scene.setText("+")
        add_scene.setToolTip(tr("action.new_scene"))
        add_scene.clicked.connect(self.controller.add_scene)
        tabs = QHBoxLayout()
        tabs.setContentsMargins(4, 2, 4, 0)
        tabs.addWidget(self.scene_tabs)
        tabs.addWidget(add_scene)
        tabs.addStretch(1)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(tabs)
        layout.addWidget(self.stage, 1)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

    def _dock(self, key: str, widget: QWidget, area: Qt.DockWidgetArea) -> QDockWidget:
        dock = QDockWidget(tr(f"dock.{key}"), self)
        dock.setObjectName(f"dock_{key}")
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        return dock

    def _build_docks(self) -> None:
        self.library = LibraryPanel()
        self.objects = ObjectsPanel(self.document, self.editor)
        self.properties = PropertiesPanel(self.document, self.editor, self.settings, self.latex_status)
        self.timeline = TimelinePanel(self.document, self.editor, self.controller)
        self.player = PlayerPanel()
        self.code = CodePanel()
        self.log = LogPanel()
        left = Qt.DockWidgetArea.LeftDockWidgetArea
        right = Qt.DockWidgetArea.RightDockWidgetArea
        self.library_dock = self._dock("library", self.library, left)
        self.objects_dock = self._dock("objects", self.objects, left)
        self.properties_dock = self._dock("properties", self.properties, right)
        self.player_dock = self._dock("preview", self.player, right)
        self.code_dock = self._dock("code", self.code, right)
        self.log_dock = self._dock("log", self.log, right)
        self.timeline_dock = self._dock("timeline", self.timeline, Qt.DockWidgetArea.BottomDockWidgetArea)
        self.splitDockWidget(self.library_dock, self.objects_dock, Qt.Orientation.Vertical)
        self.splitDockWidget(self.properties_dock, self.player_dock, Qt.Orientation.Vertical)
        self.tabifyDockWidget(self.player_dock, self.code_dock)
        self.tabifyDockWidget(self.code_dock, self.log_dock)
        self.player_dock.raise_()
        self.resizeDocks([self.library_dock, self.properties_dock], [230, 360], Qt.Orientation.Horizontal)
        self.resizeDocks([self.library_dock, self.objects_dock], [430, 250], Qt.Orientation.Vertical)
        self.resizeDocks([self.properties_dock, self.player_dock], [460, 360], Qt.Orientation.Vertical)

    def _action(self, key: str, slot, shortcut: QKeySequence | str | None = None, checkable: bool = False) -> QAction:
        action = QAction(tr(f"action.{key}"), self)
        if shortcut is not None:
            action.setShortcut(QKeySequence(shortcut))
        action.setCheckable(checkable)
        action.triggered.connect(slot)
        self.addAction(action)
        return action

    def _build_actions(self) -> None:
        std = QKeySequence.StandardKey
        c = self.controller
        self.act_new = self._action("new", self.new_project, std.New)
        self.act_open = self._action("open", self.open_dialog, std.Open)
        self.act_save = self._action("save", self.save, std.Save)
        self.act_save_as = self._action("save_as", self.save_as, std.SaveAs)
        self.act_export_script = self._action("export_script", self.export_script, "Ctrl+Shift+E")
        self.act_export = self._action("export", self.export_media, "Ctrl+E")
        self.act_quit = self._action("quit", self.close, std.Quit)
        stack = self.document.undo_stack
        self.act_undo = self._action("undo", stack.undo, std.Undo)
        self.act_redo = self._action("redo", stack.redo, std.Redo)
        self.act_redo.setShortcuts([QKeySequence(std.Redo), QKeySequence("Ctrl+Shift+Z")])
        stack.canUndoChanged.connect(self.act_undo.setEnabled)
        stack.canRedoChanged.connect(self.act_redo.setEnabled)
        stack.undoTextChanged.connect(lambda text: self.act_undo.setToolTip(f"{tr('action.undo')}: {text}" if text else tr("action.undo")))
        stack.redoTextChanged.connect(lambda text: self.act_redo.setToolTip(f"{tr('action.redo')}: {text}" if text else tr("action.redo")))
        self.act_undo.setEnabled(False)
        self.act_redo.setEnabled(False)
        self.act_cut = self._action("cut", c.cut_objects, std.Cut)
        self.act_copy = self._action("copy", c.copy_objects, std.Copy)
        self.act_paste = self._action("paste", c.paste_objects, std.Paste)
        self.act_duplicate = self._action("duplicate", self.duplicate, "Ctrl+D")
        self.act_delete = self._action("delete", self.delete, std.Delete)
        self.act_select_all = self._action("select_all", c.select_all, std.SelectAll)
        self.act_forward = self._action("bring_forward", lambda: c.change_layer(1), "Ctrl+]")
        self.act_backward = self._action("send_backward", lambda: c.change_layer(-1), "Ctrl+[")
        self.act_settings = self._action("settings", self.open_settings, std.Preferences)
        self.act_new_scene = self._action("new_scene", c.add_scene, "Ctrl+Shift+N")
        self.act_duplicate_scene = self._action("duplicate_scene", c.duplicate_scene)
        self.act_rename_scene = self._action("rename_scene", lambda: c.rename_scene(), "F2")
        self.act_delete_scene = self._action("delete_scene", lambda: c.delete_scene())
        self.act_add_step = self._action("add_step", lambda: c.add_step(StepKind.PLAY), "Ctrl+T")
        self.act_add_wait = self._action("add_wait", lambda: c.add_step(StepKind.WAIT), "Ctrl+W")
        self.act_duplicate_step = self._action("duplicate_step", c.duplicate_step)
        self.act_delete_step = self._action("delete_step", c.delete_step)
        self.act_prev_step = self._action("prev_step", lambda: c.go_to_step(-1), "PgUp")
        self.act_next_step = self._action("next_step", lambda: c.go_to_step(1), "PgDown")
        self.act_start = self._action("go_start", lambda: self.editor.inspect_step(START), "Home")
        self.act_end = self._action("go_end", lambda: self.editor.inspect_step(len(self.editor.scene().steps) - 1), "End")
        self.act_grid = self._action("show_grid", self._on_view_options, "Ctrl+G", checkable=True)
        self.act_grid.setChecked(self.settings.show_grid)
        self.act_snap = self._action("snap", self._on_view_options, "Ctrl+Shift+G", checkable=True)
        self.act_snap.setChecked(self.settings.snap)
        self.act_show_hidden = self._action("show_hidden", self._on_view_options, "Ctrl+H", checkable=True)
        self.act_show_hidden.setChecked(self.settings.show_hidden)
        self.act_fit = self._action("fit", self.stage.fit_frame, "Ctrl+0")
        self.act_zoom_in = self._action("zoom_in", lambda: self.stage.zoom(1.25), std.ZoomIn)
        self.act_zoom_out = self._action("zoom_out", lambda: self.stage.zoom(0.8), std.ZoomOut)
        self.act_preview = self._action("preview", self.render.preview, "F5")
        self.act_cancel = self._action("cancel_render", self.render.cancel, "Shift+F5")
        self.act_cancel.setEnabled(False)
        self.act_environment = self._action("check_environment", lambda: self.check_environment(interactive=True))
        self.act_about = self._action("about", self.show_about)
        self.act_manim_docs = self._action(
            "manim_docs", lambda: QDesktopServices.openUrl(QUrl("https://docs.manim.community/en/stable/"))
        )

    def _build_menus(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu(tr("menu.file"))
        file_menu.addActions([self.act_new, self.act_open])
        self.recent_menu = file_menu.addMenu(tr("menu.recent"))
        self.recent_menu.aboutToShow.connect(self._fill_recent_menu)
        file_menu.addActions([self.act_save, self.act_save_as])
        file_menu.addSeparator()
        file_menu.addActions([self.act_export, self.act_export_script])
        file_menu.addSeparator()
        file_menu.addAction(self.act_quit)
        edit_menu = bar.addMenu(tr("menu.edit"))
        edit_menu.addActions([self.act_undo, self.act_redo])
        edit_menu.addSeparator()
        edit_menu.addActions([self.act_cut, self.act_copy, self.act_paste, self.act_duplicate, self.act_delete, self.act_select_all])
        edit_menu.addSeparator()
        edit_menu.addActions([self.act_forward, self.act_backward])
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_settings)
        insert_menu = bar.addMenu(tr("menu.insert"))
        for kind in LIBRARY_ORDER:
            action = insert_menu.addAction(kind_icon(kind, 20), tr(f"kind.{kind.value}"))
            action.triggered.connect(lambda _checked=False, k=kind: self.controller.add_object(k))
        scene_menu = bar.addMenu(tr("menu.scene"))
        scene_menu.addActions([self.act_new_scene, self.act_duplicate_scene, self.act_rename_scene, self.act_delete_scene])
        timeline_menu = bar.addMenu(tr("menu.timeline"))
        self.animation_menu = timeline_menu.addMenu(tr("menu.add_animation"))
        self.animation_menu.aboutToShow.connect(lambda: build_animation_menu(self.animation_menu, self.controller, False))
        self.simultaneous_menu = timeline_menu.addMenu(tr("menu.add_simultaneous"))
        self.simultaneous_menu.aboutToShow.connect(lambda: build_animation_menu(self.simultaneous_menu, self.controller, True))
        timeline_menu.addSeparator()
        timeline_menu.addActions([self.act_add_step, self.act_add_wait, self.act_duplicate_step, self.act_delete_step])
        timeline_menu.addSeparator()
        timeline_menu.addActions([self.act_start, self.act_prev_step, self.act_next_step, self.act_end])
        view_menu = bar.addMenu(tr("menu.view"))
        view_menu.addActions([self.act_grid, self.act_snap, self.act_show_hidden])
        view_menu.addSeparator()
        view_menu.addActions([self.act_fit, self.act_zoom_in, self.act_zoom_out])
        view_menu.addSeparator()
        panels = view_menu.addMenu(tr("menu.panels"))
        for dock in (self.library_dock, self.objects_dock, self.properties_dock, self.timeline_dock, self.player_dock, self.code_dock, self.log_dock):
            panels.addAction(dock.toggleViewAction())
        render_menu = bar.addMenu(tr("menu.render"))
        render_menu.addActions([self.act_preview, self.act_cancel, self.act_export])
        render_menu.addSeparator()
        render_menu.addAction(self.act_environment)
        help_menu = bar.addMenu(tr("menu.help"))
        help_menu.addActions([self.act_manim_docs, self.act_about])

    def _build_toolbar(self) -> None:
        toolbar = self.addToolBar(tr("toolbar.main"))
        toolbar.setObjectName("toolbar_main")
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        toolbar.addActions([self.act_new, self.act_open, self.act_save])
        toolbar.addSeparator()
        toolbar.addActions([self.act_undo, self.act_redo])
        toolbar.addSeparator()
        animation_button = QToolButton()
        animation_button.setText(tr("timeline.add_animation"))
        animation_button.setMenu(self.animation_menu)
        animation_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        toolbar.addWidget(animation_button)
        toolbar.addSeparator()
        toolbar.addActions([self.act_grid, self.act_snap, self.act_fit])
        toolbar.addSeparator()
        toolbar.addActions([self.act_preview, self.act_export])

    def _build_statusbar(self) -> None:
        status = self.statusBar()
        self.coordinates = QLabel()
        self.environment_label = QLabel(tr("env.checking"))
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setFixedWidth(180)
        self.progress.setVisible(False)
        self.cancel_button = QToolButton()
        self.cancel_button.setText(tr("action.cancel_render"))
        self.cancel_button.clicked.connect(self.render.cancel)
        self.cancel_button.setVisible(False)
        status.addPermanentWidget(self.progress)
        status.addPermanentWidget(self.cancel_button)
        status.addPermanentWidget(self.coordinates)
        status.addPermanentWidget(self.environment_label)

    def _connect(self) -> None:
        self.document.changed.connect(self.refresh_all)
        self.document.dirtyChanged.connect(lambda _dirty: self._update_title())
        self.document.pathChanged.connect(self._update_title)
        self.editor.sceneChanged.connect(self.refresh_all)
        self.editor.cursorChanged.connect(self.refresh_stage)
        self.editor.selectionChanged.connect(lambda: self.stage.set_selection(self.editor.selected_objects))
        self.tex_cache.ready.connect(lambda _latex: self.refresh_stage())
        self.tex_cache.ready.connect(lambda _latex: self.properties.refresh())
        self.stage.selectionEdited.connect(self.editor.select_objects)
        self.stage.moveRequested.connect(self.controller.move_objects)
        self.stage.scaleRequested.connect(self.controller.scale_object)
        self.stage.rotateRequested.connect(self.controller.rotate_object)
        self.stage.dropRequested.connect(lambda kind, x, y: self.controller.add_object(ObjectKind(kind), x, y))
        self.stage.contextMenuRequested.connect(self.show_object_menu)
        self.stage.cursorMoved.connect(lambda x, y: self.coordinates.setText(tr("status.coordinates", x=f"{x:.2f}", y=f"{y:.2f}")))
        self.stage.statusMessage.connect(self.show_status)
        self.objects.contextMenuRequested.connect(self.show_object_menu)
        self.library.objectRequested.connect(lambda kind: self.controller.add_object(ObjectKind(kind)))
        self.controller.statusMessage.connect(self.show_status)
        self.scene_tabs.currentChanged.connect(self._on_tab_changed)
        self.scene_tabs.tabMoved.connect(self._on_tab_moved)
        self.scene_tabs.tabBarDoubleClicked.connect(lambda index: self.controller.rename_scene(self.scene_tabs.tabData(index)))
        self.scene_tabs.customContextMenuRequested.connect(self._show_tab_menu)
        self.code.copyRequested.connect(self.copy_code)
        self.code.exportRequested.connect(self.export_script)
        self.log.saveRequested.connect(self.save_log)
        self.render.busyChanged.connect(self._on_render_busy)
        self.render.progressChanged.connect(lambda value: self.progress.setValue(round(value * 1000)))
        self.render.statusMessage.connect(self.show_status)
        self.render.logLine.connect(self.log.append)
        self.render.logCleared.connect(self.log.clear)
        self.render.aboutToRender.connect(self.player.stop)
        self.render.previewReady.connect(self._on_preview_ready)
        self.render.showLogRequested.connect(lambda: (self.log_dock.show(), self.log_dock.raise_()))

    def _restore_window(self) -> None:
        geometry, state = self.settings.window_state()
        if geometry is not None:
            self.restoreGeometry(geometry)
        else:
            self.resize(1500, 920)
        if state is not None:
            self.restoreState(state)

    # --- refresh -------------------------------------------------------------------

    def refresh_all(self) -> None:
        """Bring every view up to date with the model."""
        self._refresh_tabs()
        self.refresh_stage()
        self._code_timer.start()
        self._update_title()

    def refresh_stage(self) -> None:
        """Redraw the stage at the current timeline position."""
        scene = self.editor.scene()
        self.resources.base_dir = self.document.base_dir
        states = states_after(scene, self.editor.cursor)
        self.stage.set_content(scene, states, self.resources, self.editor.selected_objects, self.act_show_hidden.isChecked())

    def refresh_code(self) -> None:
        """Regenerate the read-only code view."""
        try:
            code = generate_script(self.document.project, CodegenOptions(base_dir=self.document.base_dir))
        except CodegenError as error:
            self.code.show_error(codegen_error_text(error))
            return
        self.code.show_code(code)

    def _refresh_tabs(self) -> None:
        self.scene_tabs.blockSignals(True)
        scenes = self.document.project.scenes
        while self.scene_tabs.count() > len(scenes):
            self.scene_tabs.removeTab(self.scene_tabs.count() - 1)
        while self.scene_tabs.count() < len(scenes):
            self.scene_tabs.addTab("")
        for index, scene in enumerate(scenes):
            self.scene_tabs.setTabText(index, scene.name)
            self.scene_tabs.setTabData(index, scene.id)
            if scene.id == self.editor.scene_id:
                self.scene_tabs.setCurrentIndex(index)
        self.scene_tabs.blockSignals(False)

    def _update_title(self) -> None:
        name = self.document.path.name if self.document.path else tr("window.untitled")
        dirty = "*" if self.document.is_dirty else ""
        self.setWindowTitle(f"{name}{dirty} – {APP_NAME}")

    def show_status(self, message: str) -> None:
        """Show a temporary message in the status bar."""
        if message:
            self.statusBar().showMessage(message, STATUS_TIMEOUT_MS)

    # --- scenes ------------------------------------------------------------------

    def _on_tab_changed(self, index: int) -> None:
        scene_id = self.scene_tabs.tabData(index)
        if scene_id:
            self.editor.set_scene(scene_id)

    def _on_tab_moved(self, _from: int, to: int) -> None:
        scene_id = self.scene_tabs.tabData(to)
        if scene_id:
            self.controller.move_scene(scene_id, to)

    def _show_tab_menu(self, position: QPoint) -> None:
        index = self.scene_tabs.tabAt(position)
        if index < 0:
            return
        scene_id = self.scene_tabs.tabData(index)
        self.editor.set_scene(scene_id)
        menu = QMenu(self)
        menu.addAction(tr("action.rename_scene"), lambda: self.controller.rename_scene(scene_id))
        menu.addAction(tr("action.duplicate_scene"), self.controller.duplicate_scene)
        menu.addAction(tr("action.delete_scene"), lambda: self.controller.delete_scene(scene_id))
        menu.exec(self.scene_tabs.mapToGlobal(position))

    # --- edit dispatch -------------------------------------------------------------------

    def _timeline_has_focus(self) -> bool:
        focus = QApplication.focusWidget()
        return focus is not None and (focus is self.timeline or self.timeline.isAncestorOf(focus))

    def delete(self) -> None:
        """Delete in the focused area: timeline entries or objects."""
        if self._timeline_has_focus():
            self.controller.delete_in_timeline()
        else:
            self.controller.delete_objects()

    def duplicate(self) -> None:
        """Duplicate in the focused area: a step or objects."""
        if self._timeline_has_focus():
            self.controller.duplicate_step()
        else:
            self.controller.duplicate_objects()

    def show_object_menu(self, global_position: QPoint, object_id: str) -> None:
        """Context menu for objects on the stage or in the object list."""
        menu = QMenu(self)
        if object_id:
            animate = menu.addMenu(tr("menu.add_animation"))
            build_animation_menu(animate, self.controller, False)
            simultaneous = menu.addMenu(tr("menu.add_simultaneous"))
            build_animation_menu(simultaneous, self.controller, True)
            menu.addSeparator()
            menu.addActions([self.act_cut, self.act_copy, self.act_paste, self.act_duplicate, self.act_delete])
            menu.addSeparator()
            menu.addActions([self.act_forward, self.act_backward])
        else:
            add = menu.addMenu(tr("menu.insert"))
            scene_pos = self.stage.mapToScene(self.stage.mapFromGlobal(global_position))
            x, y = round(scene_pos.x() / 100.0 * 4) / 4, round(-scene_pos.y() / 100.0 * 4) / 4
            for kind in LIBRARY_ORDER:
                action = add.addAction(kind_icon(kind, 20), tr(f"kind.{kind.value}"))
                action.triggered.connect(lambda _checked=False, k=kind: self.controller.add_object(k, x, y))
            menu.addAction(self.act_paste)
            menu.addAction(self.act_select_all)
        self.act_paste.setEnabled(self.controller.can_paste())
        menu.exec(global_position)
        self.act_paste.setEnabled(True)

    def _on_view_options(self) -> None:
        self.settings.show_grid = self.act_grid.isChecked()
        self.settings.snap = self.act_snap.isChecked()
        self.settings.show_hidden = self.act_show_hidden.isChecked()
        self.stage.set_grid(self.settings.show_grid, self.settings.grid_step, self.settings.snap)
        self.refresh_stage()

    # --- files ---------------------------------------------------------------------------

    def maybe_save(self) -> bool:
        """Ask to save unsaved changes; return ``False`` if the user cancels."""
        if not self.document.is_dirty:
            return True
        answer = QMessageBox.question(
            self,
            tr("dialog.unsaved_title"),
            tr("dialog.unsaved_text"),
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Save:
            return self.save()
        return answer == QMessageBox.StandardButton.Discard

    def new_project(self) -> None:
        """Start an empty project."""
        if not self.maybe_save():
            return
        self.document.new(tr("scene.first_name"))
        self.editor.reset()

    def open_dialog(self) -> None:
        """Ask for a project file and open it."""
        if not self.maybe_save():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, tr("dialog.open_title"), self.settings.last_directory("project"), tr("dialog.project_filter")
        )
        if path:
            self.open_file(path, ask=False)

    def open_file(self, path: str, ask: bool = True) -> None:
        """Open a project file."""
        if ask and not self.maybe_save():
            return
        try:
            self.document.open(path)
        except ProjectFormatError as error:
            QMessageBox.critical(self, tr("dialog.open_failed"), tr("dialog.open_failed_text", path=path, error=str(error)))
            self.settings.remove_recent_file(str(Path(path).resolve()))
            return
        self.editor.reset()
        self.settings.add_recent_file(path)
        self.settings.set_last_directory("project", str(Path(path).parent))
        self.show_status(tr("status.opened", path=path))

    def save(self) -> bool:
        """Save the project (asks for a file name the first time)."""
        if self.document.path is None:
            return self.save_as()
        return self._write(self.document.path)

    def save_as(self) -> bool:
        """Save the project under a new name."""
        default = str(self.document.path or Path(self.settings.last_directory("project")) / f"{tr('window.untitled')}{FILE_SUFFIX}")
        path, _ = QFileDialog.getSaveFileName(self, tr("dialog.save_title"), default, tr("dialog.project_filter"))
        if not path:
            return False
        target = Path(path)
        if target.suffix != FILE_SUFFIX:
            target = target.with_suffix(FILE_SUFFIX)
        self._rebase_image_paths(target.parent)
        return self._write(target)

    def _rebase_image_paths(self, new_base: Path) -> None:
        old_base = self.document.base_dir

        def rebase(project) -> None:
            for scene in project.scenes:
                for obj in scene.objects:
                    if obj.kind == ObjectKind.IMAGE and obj.params.get("path"):
                        absolute = resolve_asset_path(str(obj.params["path"]), old_base)
                        obj.params["path"] = relative_asset_path(str(absolute), new_base)

        self.document.edit_project(tr("undo.rebase_images"), rebase)

    def _write(self, path: Path) -> bool:
        try:
            self.document.save(path)
        except OSError as error:
            QMessageBox.critical(self, tr("dialog.save_failed"), tr("dialog.save_failed_text", path=str(path), error=str(error)))
            return False
        self.settings.add_recent_file(str(path))
        self.settings.set_last_directory("project", str(path.parent))
        self.show_status(tr("status.saved", path=str(path)))
        return True

    def _fill_recent_menu(self) -> None:
        self.recent_menu.clear()
        files = self.settings.recent_files
        for path in files:
            action = self.recent_menu.addAction(path)
            action.triggered.connect(lambda _checked=False, p=path: self.open_file(p))
        if not files:
            empty = self.recent_menu.addAction(tr("menu.recent_empty"))
            empty.setEnabled(False)
        else:
            self.recent_menu.addSeparator()
            self.recent_menu.addAction(tr("menu.recent_clear"), self.settings.clear_recent_files)

    def export_script(self) -> None:
        """Save the generated script as a .py file."""
        try:
            code = generate_script(self.document.project, CodegenOptions(base_dir=self.document.base_dir))
        except CodegenError as error:
            QMessageBox.warning(self, tr("dialog.export_script_failed"), codegen_error_text(error))
            return
        stem = self.document.path.stem if self.document.path else "manim_scene"
        default = str(Path(self.settings.last_directory("script")) / f"{stem}.py")
        path, _ = QFileDialog.getSaveFileName(self, tr("dialog.export_script_title"), default, tr("dialog.python_filter"))
        if not path:
            return
        try:
            Path(path).write_text(code, encoding="utf-8")
        except OSError as error:
            QMessageBox.critical(self, tr("dialog.export_script_failed"), str(error))
            return
        self.settings.set_last_directory("script", str(Path(path).parent))
        self.show_status(tr("status.script_saved", path=path))

    def copy_code(self) -> None:
        """Copy the generated script to the clipboard."""
        QApplication.clipboard().setText(self.code.editor.toPlainText())
        self.show_status(tr("status.code_copied"))

    def save_log(self) -> None:
        """Save the render log as a text file."""
        path, _ = QFileDialog.getSaveFileName(self, tr("log.save"), str(Path.home() / "manim_log.txt"), tr("dialog.text_filter"))
        if path:
            Path(path).write_text(self.log.text(), encoding="utf-8")

    # --- rendering -------------------------------------------------------------------------

    def export_media(self) -> None:
        """Open the export dialog and start the export."""
        default_dir = str(self.document.base_dir or Path(self.settings.last_directory("export")))
        dialog = ExportDialog(self.document.project, self.editor.scene_id, default_dir, self)
        if dialog.exec():
            request = dialog.request()
            self.settings.set_last_directory("export", str(request.target.parent))
            self.render.export(request)

    def _on_render_busy(self, busy: bool) -> None:
        self.progress.setVisible(busy)
        self.progress.setValue(0)
        self.cancel_button.setVisible(busy)
        self.act_cancel.setEnabled(busy)
        self.act_preview.setEnabled(not busy)
        self.act_export.setEnabled(not busy)

    def _on_preview_ready(self, path: Path) -> None:
        self.player_dock.show()
        self.player_dock.raise_()
        self.player.load(path)

    # --- environment -----------------------------------------------------------------------

    def latex_available(self) -> bool:
        """Return whether LaTeX can be used (for MathTex)."""
        if self.environment is not None:
            return self.environment.latex.found
        return shutil.which("latex") is not None and shutil.which("dvisvgm") is not None

    def latex_status(self, latex: str) -> str:
        """Explain why a formula cannot be previewed, if it cannot."""
        if not self.latex_available():
            return tr("prop.latex_missing")
        error = self.tex_cache.error(latex)
        return tr("prop.latex_error", error=error) if error else ""

    def check_environment(self, interactive: bool = False) -> None:
        """Check Manim, FFmpeg and LaTeX in the background."""
        self._interactive_check = interactive
        self.environment_label.setText(tr("env.checking"))
        QThreadPool.globalInstance().start(_EnvironmentJob(self.settings.python_path, self._env_signals))

    def _on_environment(self, report: EnvironmentReport) -> None:
        self.environment = report
        self.library.set_latex_available(report.latex.found)
        self.tex_cache.enabled = self.settings.latex_preview and report.latex.found
        missing = report.missing_names()
        if missing:
            names = ", ".join(tr(f"env.tool.{name}") for name in missing)
            self.environment_label.setText(tr("env.status_missing", names=names))
        else:
            self.environment_label.setText(tr("env.status_ok", version=report.manim.version))
        self.refresh_stage()
        self.properties.refresh()
        key = ",".join(missing)
        interactive = getattr(self, "_interactive_check", False)
        if interactive or (missing and self.settings.hidden_environment_warning != key):
            dialog = EnvironmentDialog(report, show_checkbox=not interactive, parent=self)
            dialog.exec()
            if dialog.dont_show.isChecked():
                self.settings.hidden_environment_warning = key

    # --- misc ---------------------------------------------------------------------------------

    def open_settings(self) -> None:
        """Show the preferences dialog."""
        dialog = SettingsDialog(self.settings, self)
        if not dialog.exec():
            return
        language_changed = dialog.apply()
        self.stage.set_grid(self.settings.show_grid, self.settings.grid_step, self.settings.snap)
        self.tex_cache.enabled = self.settings.latex_preview and self.latex_available()
        self.refresh_stage()
        if language_changed:
            self._offer_restart()

    def _offer_restart(self) -> None:
        answer = QMessageBox.question(self, tr("settings.restart_title"), tr("settings.restart_text"))
        if answer != QMessageBox.StandardButton.Yes or not self.maybe_save():
            return
        arguments = ["-m", "manim_studio"] + ([str(self.document.path)] if self.document.path else [])
        self.document.undo_stack.setClean()
        if QProcess.startDetached(sys.executable, arguments):
            self.close()

    def show_about(self) -> None:
        """Show version information."""
        QMessageBox.about(self, tr("about.title"), tr("about.text", version=__version__))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        if not self.maybe_save():
            event.ignore()
            return
        if self.render.is_busy():
            self.render.cancel()
        self.player.stop()
        self.controller.release_clipboard()
        self.settings.save_window_state(self.saveGeometry(), self.saveState())
        event.accept()
