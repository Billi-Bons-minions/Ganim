"""The main window: header bar, library, stage, inspector and timeline."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QSplitter,
    QStackedWidget,
    QTabBar,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from manim_studio import APP_NAME, __version__
from manim_studio.codegen import CodegenError, CodegenOptions, generate_script
from manim_studio.examples import EXAMPLES, example_by_key
from manim_studio.i18n import tr
from manim_studio.logging_setup import log
from manim_studio.model.arrange import (
    ALIGN_BOTTOM,
    ALIGN_HCENTER,
    ALIGN_LEFT,
    ALIGN_RIGHT,
    ALIGN_TOP,
    ALIGN_VCENTER,
    DISTRIBUTE_H,
    DISTRIBUTE_MODES,
    DISTRIBUTE_V,
)
from manim_studio.model.assets import relative_asset_path, resolve_asset_path
from manim_studio.model.frame import frame_box, frame_size
from manim_studio.model.package import PACKAGE_SUFFIX, extract_package, save_package
from manim_studio.model.playback import state_at_time, step_start_time
from manim_studio.model.serialization import FILE_SUFFIX, ProjectFormatError
from manim_studio.model.stage_edits import is_recording
from manim_studio.model.state import START, parameter_values, states_after
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind
from manim_studio.ui.chrome import PanelFrame, SegmentedControl, StageBanner, Toast, action_button, separator, tool_button
from manim_studio.ui.context import AppContext, cache_dir
from manim_studio.ui.dialogs.environment_dialog import EnvironmentDialog
from manim_studio.ui.dialogs.export_dialog import ExportDialog
from manim_studio.ui.dialogs.messages import codegen_error_text
from manim_studio.ui.dialogs.settings_dialog import SettingsDialog
from manim_studio.ui.dialogs.shortcuts_dialog import ShortcutsDialog
from manim_studio.ui.dialogs.welcome_dialog import (
    CHOICE_NEW,
    CHOICE_OPEN,
    CHOICE_TUTORIAL,
    EXAMPLE_PREFIX,
    RECENT_PREFIX,
    WelcomeDialog,
)
from manim_studio.ui.icon_set import icon
from manim_studio.ui.icons import app_icon, kind_icon
from manim_studio.ui.panels.library_panel import LIBRARY_ORDER, LibraryPanel
from manim_studio.ui.panels.objects_panel import ObjectsPanel
from manim_studio.ui.panels.output_panels import CodePanel, LogPanel
from manim_studio.ui.panels.player_panel import PlayerPanel
from manim_studio.ui.panels.properties_panel import PropertiesPanel
from manim_studio.ui.panels.timeline_panel import TimelinePanel, build_animation_menu, format_time
from manim_studio.ui.playback import PlaybackController
from manim_studio.ui.stage.drawing import PX, StageResources, camera_size
from manim_studio.ui.stage.ruler import Ruler, RulerCorner
from manim_studio.ui.stage.view import StageView
from manim_studio.ui.still_preview import StillPreview
from manim_studio.ui.theme import current_palette, px
from manim_studio.ui.tutorial import TourStep, TutorialOverlay

CODE_REFRESH_MS = 250
STATUS_TIMEOUT_MS = 6000
MODE_STAGE = 0
MODE_PREVIEW = 1
BOTTOM_TIMELINE = 0
BOTTOM_LOG = 2
#: Align and distribute commands: (mode, icon, shortcut).
ARRANGE_ACTIONS = (
    (ALIGN_LEFT, "align_left", "Ctrl+Alt+Left"),
    (ALIGN_HCENTER, "align_center_h", None),
    (ALIGN_RIGHT, "align_right", "Ctrl+Alt+Right"),
    (ALIGN_TOP, "align_top", "Ctrl+Alt+Up"),
    (ALIGN_VCENTER, "align_center_v", None),
    (ALIGN_BOTTOM, "align_bottom", "Ctrl+Alt+Down"),
    (DISTRIBUTE_H, "distribute_h", None),
    (DISTRIBUTE_V, "distribute_v", None),
)


class MainWindow(QMainWindow):
    """Manim Studio's main window (a view on :class:`AppContext`)."""

    def __init__(self, context: AppContext, on_preferences_changed: Callable[[], None]) -> None:
        super().__init__()
        self.context = context
        self.settings = context.settings
        self.document = context.document
        self.editor = context.editor
        self.controller = context.controller
        self.render = context.render
        self.tex_cache = context.tex_cache
        self._on_preferences_changed = on_preferences_changed
        self._links: list[tuple[Any, Callable]] = []
        self._closing_for_rebuild = False
        self._interactive_check = False
        self._preview_seen = False
        self.setWindowIcon(app_icon())
        self.resources = StageResources(tex=self.tex_cache)
        self.playback = PlaybackController(self.editor, self)
        self.still = StillPreview(self.document, self.editor, self.settings, cache_dir() / "still", self)
        self.still.latex_available = self.context.latex_available
        self._code_timer = QTimer(self, singleShot=True, interval=CODE_REFRESH_MS)
        self._code_timer.timeout.connect(self.refresh_code)
        self._build_actions()
        self._build_menus()
        self._build_layout()
        self._build_statusbar()
        self._connect()
        self._restore_window()
        self.refresh_all()
        self._on_environment()

    # --- signal bookkeeping (context objects outlive the window) -----------------------

    def _link(self, signal: Any, slot: Callable) -> None:
        signal.connect(slot)
        self._links.append((signal, slot))

    def teardown(self) -> None:
        """Disconnect from long-lived objects before the window is replaced."""
        for signal, slot in self._links:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self._links = []
        self.playback.pause()
        self.player.stop()

    # --- actions and menus ----------------------------------------------------------------

    def _action(self, key: str, slot, shortcut: QKeySequence | str | None = None, icon_name: str = "", checkable: bool = False) -> QAction:
        action = QAction(tr(f"action.{key}"), self)
        if icon_name:
            action.setIcon(icon(icon_name))
        if shortcut is not None:
            sequence = QKeySequence(shortcut)
            action.setShortcut(sequence)
            action.setToolTip(f"{tr(f'action.{key}')} ({sequence.toString(QKeySequence.SequenceFormat.NativeText)})")
        action.setCheckable(checkable)
        action.triggered.connect(slot)
        self.addAction(action)
        return action

    def _build_actions(self) -> None:
        std = QKeySequence.StandardKey
        c = self.controller
        self.act_new = self._action("new", self.new_project, std.New, "new")
        self.act_open = self._action("open", self.open_dialog, std.Open, "open")
        self.act_save = self._action("save", self.save, std.Save, "save")
        self.act_save_as = self._action("save_as", self.save_as, std.SaveAs)
        self.act_save_package = self._action("save_package", self.save_package, None, "package")
        self.act_open_package = self._action("open_package", self.open_package_dialog, None, "package")
        self.act_export_script = self._action("export_script", self.export_script, "Ctrl+Shift+E", "code")
        self.act_export = self._action("export", self.export_media, "Ctrl+E", "export")
        self.act_quit = self._action("quit", self.close, std.Quit)
        stack = self.document.undo_stack
        self.act_undo = self._action("undo", stack.undo, std.Undo, "undo")
        self.act_redo = self._action("redo", stack.redo, std.Redo, "redo")
        self.act_redo.setShortcuts([QKeySequence(std.Redo), QKeySequence("Ctrl+Shift+Z")])
        self.act_cut = self._action("cut", c.cut_objects, std.Cut, "cut")
        self.act_copy = self._action("copy", c.copy_objects, std.Copy, "copy")
        self.act_paste = self._action("paste", c.paste_objects, std.Paste, "paste")
        self.act_duplicate = self._action("duplicate", self.duplicate, "Ctrl+D", "duplicate")
        self.act_delete = self._action("delete", self.delete, std.Delete, "trash")
        self.act_select_all = self._action("select_all", c.select_all, std.SelectAll)
        self.act_forward = self._action("bring_forward", lambda: c.change_layer(1), "Ctrl+]")
        self.act_backward = self._action("send_backward", lambda: c.change_layer(-1), "Ctrl+[")
        self.act_settings = self._action("settings", self.open_settings, std.Preferences, "settings")
        self.act_new_scene = self._action("new_scene", c.add_scene, "Ctrl+Shift+N", "plus")
        self.act_duplicate_scene = self._action("duplicate_scene", c.duplicate_scene, None, "duplicate")
        self.act_rename_scene = self._action("rename_scene", lambda: c.rename_scene())
        self.act_rename = self._action("rename", self.rename_selected, "F2")
        self.act_delete_scene = self._action("delete_scene", lambda: c.delete_scene(), None, "trash")
        self.act_add_step = self._action("add_step", lambda: c.add_step(StepKind.PLAY), "Ctrl+T", "plus")
        self.act_add_wait = self._action("add_wait", lambda: c.add_step(StepKind.WAIT), "Ctrl+W", "clock")
        self.act_fade_out_all = self._action("fade_out_all", c.fade_out_all, "Ctrl+Shift+F", "a_fade_out")
        self.act_add_code = self._action("add_code_step", lambda: c.add_step(StepKind.CODE), None, "code")
        self.act_duplicate_step = self._action("duplicate_step", c.duplicate_step, None, "duplicate")
        self.act_delete_step = self._action("delete_step", c.delete_step, None, "trash")
        self.act_prev_step = self._action("prev_step", lambda: c.go_to_step(-1), "PgUp", "chevron_left")
        self.act_next_step = self._action("next_step", lambda: c.go_to_step(1), "PgDown", "chevron_right")
        self.act_start = self._action("go_start", lambda: self.editor.inspect_step(START), "Home", "skip_back")
        self.act_end = self._action("go_end", lambda: self.editor.inspect_step(len(self.editor.scene().steps) - 1), "End", "skip_forward")
        self.act_group = self._action("group", c.group_selection, "Ctrl+G", "group")
        self.act_ungroup = self._action("ungroup", c.ungroup_selection, "Ctrl+Shift+G", "ungroup")
        self.act_lock = self._action("lock", lambda: c.toggle_locked(), "Ctrl+L", "lock")
        self.act_hide = self._action("hide_in_editor", lambda: c.toggle_hidden(), "Ctrl+Shift+H", "eye_off")
        self.arrange_actions: dict[str, QAction] = {}
        for mode, icon_name, shortcut in ARRANGE_ACTIONS:
            action = self._action(f"arrange.{mode}", lambda _checked=False, m=mode: self.arrange(m), shortcut, icon_name)
            self.arrange_actions[mode] = action
        self.act_grid = self._action("show_grid", self._on_view_options, "Ctrl+Alt+G", "grid", checkable=True)
        self.act_grid.setChecked(self.settings.show_grid)
        self.act_snap = self._action("snap", self._on_view_options, "Ctrl+Alt+S", "magnet", checkable=True)
        self.act_snap.setChecked(self.settings.snap)
        self.act_show_hidden = self._action("show_hidden", self._on_view_options, "Ctrl+H", "eye", checkable=True)
        self.act_show_hidden.setChecked(self.settings.show_hidden)
        self.act_exact = self._action("exact_view", self._on_exact_toggled, "Ctrl+Shift+X", "render", checkable=True)
        self.act_rulers = self._action("show_rulers", self._on_view_options, "Ctrl+R", "ruler", checkable=True)
        self.act_camera_view = self._action("camera_view", self._on_camera_view, "Ctrl+Shift+K", "camera", checkable=True)
        self.act_rulers.setChecked(self.settings.show_rulers)
        self.act_fit = self._action("fit", lambda: self.stage.fit_frame(), "Ctrl+0", "fit")
        self.act_zoom_selection = self._action("zoom_selection", self.zoom_to_selection, "Ctrl+Shift+0", "zoom_selection")
        self.act_zoom_in = self._action("zoom_in", lambda: self.stage.zoom(1.25), std.ZoomIn, "zoom_in")
        self.act_zoom_out = self._action("zoom_out", lambda: self.stage.zoom(0.8), std.ZoomOut, "zoom_out")
        self.act_preview = self._action("preview", self.start_preview, "F5", "render")
        self.act_preview_from = self._action("preview_from_step", self.start_preview_from_step, "Ctrl+F5", "render")
        self.act_play = self._action("play_stage", lambda: self.playback.toggle(), "Space", "play")
        self.act_stop_playback = self._action("stop_stage", lambda: self.playback.stop(), "Shift+Space", "stop")
        self.act_cancel = self._action("cancel_render", self.render.cancel, "Shift+F5", "stop")
        self.act_cancel.setEnabled(False)
        self.act_environment = self._action("check_environment", lambda: self.check_environment(interactive=True), None, "info")
        self.act_about = self._action("about", self.show_about, None, "info")
        self.act_manim_docs = self._action(
            "manim_docs", lambda: QDesktopServices.openUrl(QUrl("https://docs.manim.community/en/stable/")), None, "help"
        )
        self.act_open_log_folder = self._action("open_log_folder", self.open_log_folder)
        self.act_welcome = self._action("welcome", self.show_welcome, None, "lightbulb")
        self.act_tutorial = self._action("tutorial", self.start_tutorial, None, "lightbulb")
        self.act_shortcuts = self._action("shortcuts", self.show_shortcuts, "F1", "help")
        stack.canUndoChanged.connect(self.act_undo.setEnabled)
        stack.canRedoChanged.connect(self.act_redo.setEnabled)
        self._links.append((stack.canUndoChanged, self.act_undo.setEnabled))
        self._links.append((stack.canRedoChanged, self.act_redo.setEnabled))
        self.act_undo.setEnabled(stack.canUndo())
        self.act_redo.setEnabled(stack.canRedo())

    def _build_menus(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu(tr("menu.file"))
        file_menu.addActions([self.act_new, self.act_open])
        self.recent_menu = file_menu.addMenu(tr("menu.recent"))
        self.recent_menu.aboutToShow.connect(self._fill_recent_menu)
        file_menu.addActions([self.act_save, self.act_save_as])
        file_menu.addSeparator()
        file_menu.addActions([self.act_save_package, self.act_open_package])
        file_menu.addSeparator()
        file_menu.addActions([self.act_export, self.act_export_script])
        file_menu.addSeparator()
        file_menu.addAction(self.act_quit)
        edit_menu = bar.addMenu(tr("menu.edit"))
        edit_menu.addActions([self.act_undo, self.act_redo])
        edit_menu.addSeparator()
        edit_menu.addActions([self.act_cut, self.act_copy, self.act_paste, self.act_duplicate, self.act_delete, self.act_select_all])
        edit_menu.addSeparator()
        edit_menu.addActions([self.act_rename, self.act_lock, self.act_hide])
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_settings)
        arrange_menu = bar.addMenu(tr("menu.arrange"))
        self._fill_arrange_menu(arrange_menu)
        insert_menu = bar.addMenu(tr("menu.insert"))
        for kind in LIBRARY_ORDER:
            action = insert_menu.addAction(kind_icon(kind), tr(f"kind.{kind.value}"))
            action.triggered.connect(lambda _checked=False, k=kind: self.controller.add_object(k))
        scene_menu = bar.addMenu(tr("menu.scene"))
        scene_menu.addActions([self.act_new_scene, self.act_duplicate_scene, self.act_rename_scene, self.act_delete_scene])
        timeline_menu = bar.addMenu(tr("menu.timeline"))
        self.animation_menu = timeline_menu.addMenu(icon("sparkle"), tr("menu.add_animation"))
        self.animation_menu.aboutToShow.connect(lambda: build_animation_menu(self.animation_menu, self.controller, False))
        self.simultaneous_menu = timeline_menu.addMenu(tr("menu.add_simultaneous"))
        self.simultaneous_menu.aboutToShow.connect(lambda: build_animation_menu(self.simultaneous_menu, self.controller, True))
        timeline_menu.addSeparator()
        timeline_menu.addActions([self.act_add_step, self.act_add_wait, self.act_fade_out_all, self.act_add_code, self.act_duplicate_step, self.act_delete_step])
        timeline_menu.addSeparator()
        timeline_menu.addActions([self.act_start, self.act_prev_step, self.act_next_step, self.act_end])
        timeline_menu.addSeparator()
        timeline_menu.addActions([self.act_play, self.act_stop_playback])
        view_menu = bar.addMenu(tr("menu.view"))
        view_menu.addActions([self.act_grid, self.act_snap, self.act_rulers, self.act_show_hidden, self.act_exact, self.act_camera_view])
        view_menu.addSeparator()
        view_menu.addActions([self.act_fit, self.act_zoom_selection, self.act_zoom_in, self.act_zoom_out])
        self.panels_menu = view_menu.addMenu(tr("menu.panels"))
        render_menu = bar.addMenu(tr("menu.render"))
        render_menu.addActions([self.act_preview, self.act_preview_from, self.act_cancel, self.act_export])
        render_menu.addSeparator()
        render_menu.addAction(self.act_environment)
        help_menu = bar.addMenu(tr("menu.help"))
        help_menu.addActions([self.act_welcome, self.act_tutorial])
        examples_menu = help_menu.addMenu(icon("template"), tr("menu.examples"))
        for example in EXAMPLES:
            action = examples_menu.addAction(icon(example.icon), tr(f"example.{example.key}.name"))
            action.triggered.connect(lambda _checked=False, key=example.key: self.open_example(key))
        help_menu.addSeparator()
        help_menu.addActions([self.act_shortcuts, self.act_manim_docs, self.act_open_log_folder])
        help_menu.addSeparator()
        help_menu.addAction(self.act_about)

    # --- layout -----------------------------------------------------------------------------

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("HeaderBar")
        row = QHBoxLayout(header)
        row.setContentsMargins(px(10), px(6), px(10), px(6))
        row.setSpacing(px(6))
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(QSize(px(22), px(22))))
        self.title_label = QLabel()
        self.title_label.setProperty("role", "title")
        row.addWidget(logo)
        row.addWidget(self.title_label)
        row.addSpacing(px(8))
        for action in (self.act_undo, self.act_redo):
            row.addWidget(action_button(action))
        row.addWidget(separator(vertical=True))
        self.scene_tabs = QTabBar()
        self.scene_tabs.setMovable(True)
        self.scene_tabs.setExpanding(False)
        self.scene_tabs.setDrawBase(False)
        self.scene_tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        row.addWidget(self.scene_tabs)
        row.addWidget(tool_button("plus", tr("action.new_scene"), self.controller.add_scene))
        row.addStretch(1)
        self.environment_button = QToolButton()
        self.environment_button.setProperty("variant", "button")
        self.environment_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.environment_button.clicked.connect(lambda: self.check_environment(interactive=True))
        row.addWidget(self.environment_button)
        row.addWidget(action_button(self.act_export, show_text=True, variant="button"))
        self.preview_button = action_button(self.act_preview, show_text=True, variant="primary")
        row.addWidget(self.preview_button)
        return header

    def _build_stage_area(self) -> QWidget:
        self.stage = StageView()
        self.stage.set_policy(self.controller.edit_policy)
        self.stage.set_grid(self.settings.show_grid, self.settings.grid_step, self.settings.snap)
        self.player = PlayerPanel()
        self.mode_switch = SegmentedControl([("move", tr("center.stage")), ("render", tr("center.preview"))])
        self.mode_switch.changed.connect(self.set_center_mode)
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(px(10), px(6), px(10), px(6))
        toolbar.setSpacing(px(2))
        toolbar.addWidget(self.mode_switch)
        toolbar.addSpacing(px(10))
        self.arrange_tools = QWidget()
        arrange = QHBoxLayout(self.arrange_tools)
        arrange.setContentsMargins(0, 0, 0, 0)
        arrange.setSpacing(px(1))
        for action in (self.act_group, self.act_ungroup):
            arrange.addWidget(action_button(action))
        arrange.addWidget(separator(vertical=True))
        for mode, _icon, _shortcut in ARRANGE_ACTIONS:
            arrange.addWidget(action_button(self.arrange_actions[mode]))
        toolbar.addWidget(self.arrange_tools)
        toolbar.addStretch(1)
        self.stage_tools = QWidget()
        tools = QHBoxLayout(self.stage_tools)
        tools.setContentsMargins(0, 0, 0, 0)
        tools.setSpacing(px(2))
        for action in (self.act_grid, self.act_snap, self.act_rulers, self.act_show_hidden, self.act_exact, self.act_camera_view):
            tools.addWidget(action_button(action))
        tools.addWidget(separator(vertical=True))
        tools.addWidget(action_button(self.act_zoom_out))
        self.zoom_label = QLabel("100 %")
        self.zoom_label.setProperty("role", "muted")
        self.zoom_label.setMinimumWidth(px(46))
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tools.addWidget(self.zoom_label)
        tools.addWidget(action_button(self.act_zoom_in))
        tools.addWidget(action_button(self.act_zoom_selection))
        tools.addWidget(action_button(self.act_fit))
        toolbar.addWidget(self.stage_tools)
        stage_holder = QWidget()
        stage_layout = QGridLayout(stage_holder)
        stage_layout.setContentsMargins(0, 0, 0, 0)
        stage_layout.setSpacing(0)
        self.ruler_corner = RulerCorner()
        self.top_ruler = Ruler(self.stage, Qt.Orientation.Horizontal)
        self.left_ruler = Ruler(self.stage, Qt.Orientation.Vertical)
        stage_layout.addWidget(self.ruler_corner, 0, 0)
        stage_layout.addWidget(self.top_ruler, 0, 1)
        stage_layout.addWidget(self.left_ruler, 1, 0)
        stage_layout.addWidget(self.stage, 1, 1)
        self._show_rulers(self.settings.show_rulers)
        self.banner = StageBanner(self.stage)
        self.toast = Toast(self.stage)
        self.empty_hint = QLabel(self.stage)
        self.empty_hint.setTextFormat(Qt.TextFormat.RichText)
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.empty_hint.setText(tr("stage.empty_hint"))
        self.empty_hint.setStyleSheet(f"color: {current_palette().text_muted}; font-size: {px(15)}px;")
        self.center_stack = QStackedWidget()
        self.center_stack.addWidget(stage_holder)
        self.center_stack.addWidget(self.player)
        area = QWidget()
        area.setObjectName("Panel")
        column = QVBoxLayout(area)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addLayout(toolbar)
        column.addWidget(self.center_stack, 1)
        return area

    def _build_bottom_area(self) -> QTabWidget:
        self.timeline = TimelinePanel(self.document, self.editor, self.controller, self.playback)
        self.code = CodePanel()
        self.log = LogPanel()
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(self.timeline, icon("clock"), tr("dock.timeline"))
        tabs.addTab(self.code, icon("code"), tr("dock.code"))
        tabs.addTab(self.log, icon("render"), tr("dock.log"))
        tabs.setObjectName("Panel")
        self.bottom_tabs = tabs
        return tabs

    def _build_layout(self) -> None:
        self.library = LibraryPanel()
        self.objects = ObjectsPanel(self.document, self.editor, self.controller)
        self.properties = PropertiesPanel(self.document, self.editor, self.settings, self.context.latex_status, self.controller)
        self.left_split = QSplitter(Qt.Orientation.Vertical)
        self.left_split.addWidget(PanelFrame(tr("dock.library"), self.library))
        self.left_split.addWidget(PanelFrame(tr("dock.objects"), self.objects))
        self.left_split.setSizes([px(430), px(260)])
        self.center_split = QSplitter(Qt.Orientation.Vertical)
        self.center_split.addWidget(self._build_stage_area())
        self.center_split.addWidget(self._build_bottom_area())
        self.center_split.setStretchFactor(0, 3)
        self.center_split.setStretchFactor(1, 1)
        self.center_split.setSizes([px(640), px(250)])
        self.inspector_frame = PanelFrame(tr("dock.properties"), self.properties)
        self.main_split = QSplitter(Qt.Orientation.Horizontal)
        self.main_split.addWidget(self.left_split)
        self.main_split.addWidget(self.center_split)
        self.main_split.addWidget(self.inspector_frame)
        self.main_split.setStretchFactor(1, 1)
        self.main_split.setSizes([px(250), px(1000), px(330)])
        for splitter in (self.left_split, self.center_split, self.main_split):
            splitter.setChildrenCollapsible(False)
        central = QWidget()
        column = QVBoxLayout(central)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(self._build_header())
        column.addWidget(self.main_split, 1)
        self.setCentralWidget(central)
        for key, widget in (("library", self.left_split), ("properties", self.inspector_frame), ("timeline", self.bottom_tabs)):
            action = QAction(tr(f"dock.{key}"), self, checkable=True, checked=True)
            action.toggled.connect(widget.setVisible)
            self.panels_menu.addAction(action)

    def _build_statusbar(self) -> None:
        status = self.statusBar()
        self.coordinates = QLabel()
        self.coordinates.setProperty("role", "faint")
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setFixedWidth(px(180))
        self.progress.setVisible(False)
        self.cancel_button = tool_button("stop", tr("action.cancel_render"), self.render.cancel, tr("action.cancel_render"))
        self.cancel_button.setVisible(False)
        status.addPermanentWidget(self.progress)
        status.addPermanentWidget(self.cancel_button)
        status.addPermanentWidget(self.coordinates)

    # --- wiring -------------------------------------------------------------------------------

    def _connect(self) -> None:
        link = self._link
        link(self.document.changed, self.refresh_all)
        link(self.document.dirtyChanged, self._update_title)
        link(self.document.pathChanged, self._update_title)
        link(self.editor.sceneChanged, self.refresh_all)
        link(self.editor.cursorChanged, self._on_cursor_changed)
        link(self.editor.playheadChanged, self._on_playhead_changed)
        link(self.editor.selectionChanged, self._on_selection_changed)
        link(self.tex_cache.ready, self._on_tex_ready)
        link(self.controller.statusMessage, self.show_status)
        link(self.controller.animationRecorded, self.show_toast)
        link(self.context.environmentChanged, self._on_environment)
        link(self.render.busyChanged, self._on_render_busy)
        link(self.render.progressChanged, self._on_render_progress)
        link(self.render.statusMessage, self.show_status)
        link(self.render.logLine, self.log.append)
        link(self.render.logCleared, self.log.clear)
        link(self.render.aboutToRender, self.player.stop)
        link(self.render.previewReady, self._on_preview_ready)
        link(self.render.showLogRequested, self._show_log)
        self.stage.selectionEdited.connect(self.editor.select_objects)
        self.still.imageReady.connect(self._on_exact_image)
        self.still.busyChanged.connect(self._on_exact_busy)
        self.stage.moveRequested.connect(lambda ids, dx, dy: (self._before_stage_edit(), self.controller.move_objects(ids, dx, dy)))
        self.stage.scaleRequested.connect(lambda object_id, f: (self._before_stage_edit(), self.controller.scale_object(object_id, f)))
        self.stage.rotateRequested.connect(lambda object_id, a: (self._before_stage_edit(), self.controller.rotate_object(object_id, a)))
        self.stage.dropRequested.connect(self._on_drop)
        self.stage.contextMenuRequested.connect(self.show_object_menu)
        self.stage.cursorMoved.connect(self._on_cursor_moved)
        self.stage.statusMessage.connect(self.show_status)
        self.stage.zoomChanged.connect(self._on_zoom_changed)
        self.stage.vertexMoved.connect(lambda object_id, index, x, y: (self._before_stage_edit(), self.controller.move_vertex(object_id, index, x, y)))
        self.stage.vertexInserted.connect(lambda object_id, index, x, y: (self._before_stage_edit(), self.controller.insert_vertex(object_id, index, x, y)))
        self.stage.vertexMenuRequested.connect(self._show_vertex_menu)
        self.stage.endpointMoved.connect(lambda object_id, which, x, y: (self._before_stage_edit(), self.controller.set_line_endpoint(object_id, which, x, y)))
        self.objects.contextMenuRequested.connect(self.show_object_menu)
        self.properties.arrangeRequested.connect(self.arrange)
        self.library.objectRequested.connect(self._on_library_request)
        self.scene_tabs.currentChanged.connect(self._on_tab_changed)
        self.scene_tabs.tabMoved.connect(self._on_tab_moved)
        self.scene_tabs.tabBarDoubleClicked.connect(lambda index: self.controller.rename_scene(self.scene_tabs.tabData(index)))
        self.scene_tabs.customContextMenuRequested.connect(self._show_tab_menu)
        self.code.copyRequested.connect(self.copy_code)
        self.code.exportRequested.connect(self.export_script)
        self.log.saveRequested.connect(self.save_log)

    def _restore_window(self) -> None:
        geometry, _state = self.settings.window_state()
        if geometry is not None:
            self.restoreGeometry(geometry)
        else:
            self.resize(px(1560), px(940))
        for key, splitter in (("main", self.main_split), ("left", self.left_split), ("center", self.center_split)):
            state = self.settings.splitter_state(key)
            if state is not None:
                splitter.restoreState(state)

    def save_layout(self) -> None:
        """Remember window geometry and splitter positions."""
        self.settings.save_window_state(self.saveGeometry(), None)
        for key, splitter in (("main", self.main_split), ("left", self.left_split), ("center", self.center_split)):
            self.settings.set_splitter_state(key, splitter.saveState())

    # --- refresh ----------------------------------------------------------------------------------

    def refresh_all(self) -> None:
        """Bring every view up to date with the model."""
        self._refresh_tabs()
        self.refresh_stage()
        self._code_timer.start()
        self._update_title()

    def refresh_stage(self) -> None:
        """Redraw the stage at the current timeline position."""
        scene = self.editor.scene()
        cursor = self.editor.cursor
        self.resources.base_dir = self.document.base_dir
        playhead = self.editor.playhead
        states = state_at_time(scene, playhead) if playhead is not None else states_after(scene, cursor)
        self.resources.values = parameter_values(scene, states)
        self.resources.frame_size = frame_size(self.document.project.aspect)
        self.stage.set_frame_size(*self.resources.frame_size)
        self.stage.set_point_editing(cursor == START and playhead is None)
        self.stage.set_content(scene, states, self.resources, self.editor.selected_objects, self.act_show_hidden.isChecked())
        self.stage.set_motion_paths(self._motion_paths(scene, cursor) if playhead is None else [])
        self.empty_hint.setVisible(not scene.objects)
        self._update_banner()
        self._update_selection_tools()
        self._follow_camera(scene, states)
        if self.act_exact.isChecked():
            if playhead is None:
                self.still.request()
            else:
                self.stage.set_exact_image(None)

    def _motion_paths(self, scene, cursor: int) -> list:
        if not is_recording(scene, cursor):
            return []
        before = states_after(scene, cursor - 1)
        paths = []
        for anim in scene.steps[cursor].animations:
            if anim.kind == AnimationKind.MOVE and anim.target_id in before:
                start = before[anim.target_id]
                end = (float(anim.params.get("x", start.x)), float(anim.params.get("y", start.y)))
                if abs(end[0] - start.x) > 1e-6 or abs(end[1] - start.y) > 1e-6:
                    paths.append(((start.x, start.y), end))
        return paths

    def _update_banner(self) -> None:
        cursor = self.editor.cursor
        if self.editor.playhead is not None:
            self.banner.show_message(tr("banner.playback", time=format_time(self.editor.playhead)), recording=False)
        elif cursor == START:
            self.banner.show_message(tr("banner.start"), recording=False)
        else:
            step = self.editor.scene().steps[cursor]
            key = {StepKind.WAIT: "banner.wait", StepKind.CODE: "banner.code"}.get(step.kind, "banner.step")
            dot = f"<span style='color:{current_palette().record}'>●</span>"
            self.banner.show_message(tr(key, step=cursor + 1, dot=dot), recording=step.kind == StepKind.PLAY)
        self._place_overlays()

    def _place_overlays(self) -> None:
        viewport = self.stage.viewport().geometry()
        self.banner.move(viewport.x() + (viewport.width() - self.banner.width()) // 2, viewport.y() + px(10))
        self.banner.raise_()
        self.toast.adjustSize()
        self.toast.move(viewport.x() + (viewport.width() - self.toast.width()) // 2, viewport.bottom() - self.toast.height() - px(14))
        self.empty_hint.setGeometry(viewport.x(), viewport.y() + viewport.height() // 2 - px(60), viewport.width(), px(120))

    def show_toast(self, text: str) -> None:
        """Show a short notification on the stage."""
        self.toast.show_message(text)
        self._place_overlays()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        QTimer.singleShot(0, self._place_overlays)

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
            self.scene_tabs.setTabIcon(index, icon("scene"))
            self.scene_tabs.setTabData(index, scene.id)
            if scene.id == self.editor.scene_id:
                self.scene_tabs.setCurrentIndex(index)
        self.scene_tabs.blockSignals(False)

    def _update_title(self, *_args: object) -> None:
        name = self.document.path.stem if self.document.path else tr("window.untitled")
        dirty = " •" if self.document.is_dirty else ""
        self.title_label.setText(f"{name}{dirty}")
        self.setWindowTitle(f"{name}{'*' if self.document.is_dirty else ''} – {APP_NAME}")

    def show_status(self, message: str) -> None:
        """Show a temporary message in the status bar."""
        if message:
            self.statusBar().showMessage(message, STATUS_TIMEOUT_MS)

    def _on_cursor_changed(self) -> None:
        self.refresh_stage()
        if self.center_stack.currentIndex() == MODE_PREVIEW and self.editor.playhead is None:
            time = step_start_time(self.editor.scene(), self.editor.cursor) if self.editor.cursor != START else 0.0
            self.player.seek(round((time - self.render.preview_offset) * 1000))

    def _on_playhead_changed(self) -> None:
        self.refresh_stage()
        playhead = self.editor.playhead
        if playhead is not None and self.center_stack.currentIndex() == MODE_PREVIEW and not self.playback.is_playing():
            self.player.seek(round((playhead - self.render.preview_offset) * 1000))

    def _on_exact_toggled(self, checked: bool) -> None:
        self.still.set_enabled(checked)
        if checked:
            self.show_toast(tr("exact.started"))

    def _on_exact_image(self, path: object) -> None:
        if self.act_exact.isChecked() and self.editor.playhead is None:
            self.stage.set_exact_image(path)
        else:
            self.stage.set_exact_image(None)

    def _on_exact_busy(self, busy: bool) -> None:
        if busy:
            self.stage.set_exact_image(None)
            self.show_status(tr("exact.rendering"))

    def _before_stage_edit(self) -> None:
        self.playback.pause()
        self.editor.clear_playhead()

    def _on_selection_changed(self) -> None:
        self.stage.set_selection(self.editor.selected_objects)
        self._update_selection_tools()

    def _update_selection_tools(self) -> None:
        count = len(self.editor.selected_objects)
        self.act_group.setEnabled(self.controller.can_group())
        self.act_ungroup.setEnabled(self.controller.can_ungroup())
        for mode, action in self.arrange_actions.items():
            action.setEnabled(count >= (3 if mode in DISTRIBUTE_MODES else 1))
        for action in (self.act_lock, self.act_hide, self.act_rename, self.act_zoom_selection):
            action.setEnabled(count >= 1)
        rect = self.stage.selection_rect()
        if count and not rect.isNull():
            self.top_ruler.set_selection_range(rect.left() / PX, rect.right() / PX)
            self.left_ruler.set_selection_range(-rect.bottom() / PX, -rect.top() / PX)
        else:
            self.top_ruler.set_selection_range(None, None)
            self.left_ruler.set_selection_range(None, None)

    def selection_boxes(self) -> dict[str, tuple[float, float, float, float]]:
        """Drawn bounds of the selected objects as ``(left, bottom, right, top)`` in Manim units."""
        boxes = {}
        for object_id in self.editor.selected_objects:
            rect = self.stage.item_rect(object_id)
            if not rect.isNull():
                boxes[object_id] = (rect.left() / PX, -rect.bottom() / PX, rect.right() / PX, -rect.top() / PX)
        return boxes

    def arrange(self, mode: str) -> None:
        """Align or distribute the selected objects."""
        self._before_stage_edit()
        self.controller.arrange(mode, self.selection_boxes(), frame_box(self.document.project.aspect))

    def zoom_to_selection(self) -> None:
        """Zoom onto the selected objects."""
        rect = self.stage.selection_rect()
        if not rect.isNull():
            self.set_center_mode(MODE_STAGE)
            self.stage.zoom_to(rect)

    def rename_selected(self) -> None:
        """Rename the selected object inline in the layer list (or the scene)."""
        selected = self.editor.selected_objects
        if len(selected) == 1:
            self.objects.edit_name(selected[0])
        elif not selected:
            self.controller.rename_scene()

    def _fill_arrange_menu(self, menu: QMenu) -> None:
        menu.addActions([self.act_group, self.act_ungroup])
        menu.addSeparator()
        for mode, _icon, _shortcut in ARRANGE_ACTIONS:
            if mode == DISTRIBUTE_MODES[0]:
                menu.addSeparator()
            menu.addAction(self.arrange_actions[mode])
        menu.addSeparator()
        menu.addActions([self.act_forward, self.act_backward])

    def _show_vertex_menu(self, global_position: QPoint, object_id: str, index: int) -> None:
        menu = QMenu(self)
        obj = self.editor.scene().object_by_id(object_id)
        action = menu.addAction(icon("trash"), tr("action.remove_vertex"), lambda: self.controller.remove_vertex(object_id, index))
        action.setEnabled(obj is not None and len(obj.params.get("points", [])) > 3)
        menu.exec(global_position)

    def _camera(self, scene):
        return next((obj for obj in scene.objects if obj.kind == ObjectKind.CAMERA), None)

    def _follow_camera(self, scene, states) -> None:
        camera = self._camera(scene)
        self.act_camera_view.setEnabled(camera is not None)
        if camera is None or not self.act_camera_view.isChecked():
            return
        state = states.get(camera.id)
        if state is None:
            return
        width, height = camera_size(camera, self.resources.frame_size)
        width, height = width * state.scale * PX, height * state.scale * PX
        self.stage.follow_rect(QRectF(state.x * PX - width / 2, -state.y * PX - height / 2, width, height))

    def _on_camera_view(self, checked: bool) -> None:
        if checked:
            self.refresh_stage()
        else:
            self.stage.fit_frame()

    def _show_rulers(self, show: bool) -> None:
        for widget in (self.ruler_corner, self.top_ruler, self.left_ruler):
            widget.setVisible(show)

    def _on_tex_ready(self, _latex: str) -> None:
        self.refresh_stage()
        self.properties.refresh()

    def _on_cursor_moved(self, x: float, y: float) -> None:
        self.coordinates.setText(tr("status.coordinates", x=f"{x:.2f}", y=f"{y:.2f}"))

    def _on_zoom_changed(self, factor: float) -> None:
        self.zoom_label.setText(f"{round(factor * 100)} %")
        QTimer.singleShot(0, self._place_overlays)

    def _on_library_request(self, kind: str) -> None:
        self.set_center_mode(MODE_STAGE)
        self.controller.add_object(ObjectKind(kind))

    def _on_drop(self, kind: str, x: float, y: float) -> None:
        self.controller.add_object(ObjectKind(kind), x, y)

    def set_center_mode(self, mode: int) -> None:
        """Switch the center between stage editing and the rendered preview."""
        self.center_stack.setCurrentIndex(mode)
        self.mode_switch.set_current(mode)
        self.stage_tools.setVisible(mode == MODE_STAGE)

    # --- scenes ---------------------------------------------------------------------------------

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
        menu.addAction(icon("duplicate"), tr("action.duplicate_scene"), self.controller.duplicate_scene)
        menu.addAction(icon("trash"), tr("action.delete_scene"), lambda: self.controller.delete_scene(scene_id))
        menu.exec(self.scene_tabs.mapToGlobal(position))

    # --- edit dispatch ----------------------------------------------------------------------------

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
        """Context menu for objects on the stage or in the layer list."""
        menu = QMenu(self)
        if object_id:
            animate = menu.addMenu(icon("sparkle"), tr("menu.add_animation"))
            build_animation_menu(animate, self.controller, False)
            simultaneous = menu.addMenu(tr("menu.add_simultaneous"))
            build_animation_menu(simultaneous, self.controller, True)
            menu.addSeparator()
            menu.addActions([self.act_cut, self.act_copy, self.act_paste, self.act_duplicate, self.act_delete])
            menu.addSeparator()
            menu.addActions([self.act_rename, self.act_lock, self.act_hide])
            arrange_menu = menu.addMenu(icon("align_left"), tr("menu.arrange"))
            self._fill_arrange_menu(arrange_menu)
        else:
            add = menu.addMenu(icon("plus"), tr("menu.insert"))
            scene_pos = self.stage.mapToScene(self.stage.mapFromGlobal(global_position))
            x, y = round(scene_pos.x() / PX * 4) / 4, round(-scene_pos.y() / PX * 4) / 4
            for kind in LIBRARY_ORDER:
                action = add.addAction(kind_icon(kind), tr(f"kind.{kind.value}"))
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
        self.settings.show_rulers = self.act_rulers.isChecked()
        self._show_rulers(self.settings.show_rulers)
        self.stage.set_grid(self.settings.show_grid, self.settings.grid_step, self.settings.snap)
        self.refresh_stage()

    # --- files -------------------------------------------------------------------------------------

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
        """Open a project file (or unpack and open a package)."""
        if ask and not self.maybe_save():
            return
        if Path(path).suffix == PACKAGE_SUFFIX:
            self.open_package(path)
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
        log.info("Opened %s", path)

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

    def save_package(self) -> None:
        """Save the project together with all images and sounds as one file."""
        default = Path(self.settings.last_directory("project")) / f"{self.document.path.stem if self.document.path else tr('window.untitled')}{PACKAGE_SUFFIX}"
        path, _ = QFileDialog.getSaveFileName(self, tr("dialog.package_save_title"), str(default), tr("dialog.package_filter"))
        if not path:
            return
        target = Path(path)
        if target.suffix != PACKAGE_SUFFIX:
            target = target.with_suffix(PACKAGE_SUFFIX)
        try:
            missing = save_package(self.document.project, target, self.document.base_dir)
        except OSError as error:
            QMessageBox.critical(self, tr("dialog.save_failed"), tr("dialog.save_failed_text", path=str(target), error=str(error)))
            return
        if missing:
            QMessageBox.warning(self, tr("dialog.package_missing_title"), tr("dialog.package_missing", files="\n".join(missing)))
        self.show_status(tr("status.package_saved", path=str(target)))

    def open_package_dialog(self) -> None:
        """Choose a package, unpack it into a folder and open it."""
        if not self.maybe_save():
            return
        path, _ = QFileDialog.getOpenFileName(self, tr("dialog.package_open_title"), self.settings.last_directory("project"), tr("dialog.package_filter"))
        if path:
            self.open_package(path)

    def open_package(self, path: str, folder: str | None = None) -> None:
        """Unpack a package (next to it unless ``folder`` is given) and open the project."""
        package = Path(path)
        if folder is None:
            default = package.parent / package.stem
            folder = QFileDialog.getExistingDirectory(self, tr("dialog.package_folder_title"), str(default.parent)) or ""
            if not folder:
                return
            folder = str(Path(folder) / package.stem)
        try:
            project_file = extract_package(package, folder)
        except (OSError, ProjectFormatError, zipfile.BadZipFile) as error:
            QMessageBox.critical(self, tr("dialog.open_failed"), tr("dialog.open_failed_text", path=path, error=str(error)))
            return
        self.open_file(str(project_file), ask=False)

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

    def open_log_folder(self) -> None:
        """Open the folder with the application log."""
        from manim_studio.ui.context import data_dir

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir() / "logs")))

    # --- rendering -------------------------------------------------------------------------------------

    def start_preview(self) -> None:
        """Render a quick preview of the active scene."""
        self.playback.pause()
        self.render.preview()

    def start_preview_from_step(self) -> None:
        """Render a quick preview starting at the selected step."""
        self.playback.pause()
        self.render.preview(self.editor.cursor if self.editor.cursor > 0 else None)

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

    def _on_render_progress(self, value: float) -> None:
        self.progress.setValue(round(value * 1000))

    def _on_preview_ready(self, path: Path) -> None:
        self._preview_seen = True
        self.set_center_mode(MODE_PREVIEW)
        self.player.load(path)

    def _show_log(self) -> None:
        self.bottom_tabs.setCurrentIndex(BOTTOM_LOG)

    # --- environment --------------------------------------------------------------------------------------

    def check_environment(self, interactive: bool = False) -> None:
        """Run the system check; ``interactive`` always shows the result."""
        self._interactive_check = interactive
        self.environment_button.setText(tr("env.checking"))
        self.environment_button.setIcon(icon("clock"))
        self.context.check_environment()

    def _on_environment(self) -> None:
        report = self.context.environment
        if report is None:
            self.environment_button.setText(tr("env.checking"))
            self.environment_button.setIcon(icon("clock"))
            return
        self.library.set_latex_available(report.latex.found)
        missing = report.missing_names()
        if missing:
            names = ", ".join(tr(f"env.tool.{name}") for name in missing)
            self.environment_button.setText(tr("env.status_missing", names=names))
            self.environment_button.setIcon(icon("warning", current_palette().warning))
        else:
            self.environment_button.setText(tr("env.status_ok", version=report.manim.version))
            self.environment_button.setIcon(icon("check", current_palette().success))
        self.refresh_stage()
        self.properties.refresh()
        key = ",".join(missing)
        interactive = self._interactive_check
        self._interactive_check = False
        if interactive or (missing and self.settings.hidden_environment_warning != key):
            dialog = EnvironmentDialog(report, show_checkbox=not interactive, parent=self)
            dialog.exec()
            if dialog.dont_show.isChecked():
                self.settings.hidden_environment_warning = key

    # --- misc -------------------------------------------------------------------------------------------------

    def open_settings(self) -> None:
        """Show the preferences dialog."""
        dialog = SettingsDialog(self.settings, self)
        if not dialog.exec():
            return
        needs_rebuild = dialog.apply()
        self.stage.set_grid(self.settings.show_grid, self.settings.grid_step, self.settings.snap)
        self.tex_cache.enabled = self.settings.latex_preview and self.context.latex_available()
        self.refresh_stage()
        if needs_rebuild:
            QTimer.singleShot(0, self._on_preferences_changed)

    def show_welcome(self) -> None:
        """Show the start screen and act on the user's choice."""
        dialog = WelcomeDialog(self.settings, self.context.latex_available(), self)
        if not dialog.exec():
            return
        choice = dialog.choice
        if choice == CHOICE_TUTORIAL:
            self.start_tutorial()
        elif choice == CHOICE_NEW:
            self.new_project()
        elif choice == CHOICE_OPEN:
            self.open_dialog()
        elif choice.startswith(EXAMPLE_PREFIX):
            self.open_example(choice[len(EXAMPLE_PREFIX):])
        elif choice.startswith(RECENT_PREFIX):
            self.open_file(choice[len(RECENT_PREFIX):])

    def open_example(self, key: str) -> None:
        """Open a built-in example as a new, unsaved project."""
        example = example_by_key(key)
        if example is None or not self.maybe_save():
            return
        self.document.load(example.build())
        self.editor.reset()
        self.set_center_mode(MODE_STAGE)
        self.show_toast(tr("status.example_opened", name=tr(f"example.{key}.name")))

    def show_shortcuts(self) -> None:
        """Show all keyboard shortcuts."""
        ShortcutsDialog(self.actions(), self).exec()

    def start_tutorial(self) -> None:
        """Run the guided tour on a fresh project."""
        if not self.maybe_save():
            return
        self.document.new(tr("scene.first_name"))
        self.editor.reset()
        self.set_center_mode(MODE_STAGE)
        self.bottom_tabs.setCurrentIndex(BOTTOM_TIMELINE)
        self._preview_seen = False
        scene = lambda: self.editor.scene()  # noqa: E731

        def has_animation(kind: AnimationKind) -> bool:
            return any(anim.kind == kind for step in scene().steps for anim in step.animations)

        steps = [
            TourStep("intro"),
            TourStep("add_circle", lambda: self.library.tiles.get(ObjectKind.CIRCLE),
                     lambda: any(obj.kind == ObjectKind.CIRCLE for obj in scene().objects)),
            TourStep("animate", lambda: self.properties.animation_buttons.get(AnimationKind.CREATE),
                     lambda: has_animation(AnimationKind.CREATE)),
            TourStep("timeline", lambda: self.bottom_tabs),
            TourStep("new_step", lambda: self.timeline.add_step_button, lambda: len(scene().steps) >= 2),
            TourStep("drag", lambda: self.stage, lambda: has_animation(AnimationKind.MOVE)),
            TourStep("preview", lambda: self.preview_button, lambda: self._preview_seen),
            TourStep("done"),
        ]
        self.tour = TutorialOverlay(self, steps)
        self.tour.start()

    def show_about(self) -> None:
        """Show version information."""
        QMessageBox.about(self, tr("about.title"), tr("about.text", version=__version__))

    def close_for_rebuild(self) -> None:
        """Close without asking (the window is replaced by a new one)."""
        self._closing_for_rebuild = True
        self.save_layout()
        self.teardown()
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        if self._closing_for_rebuild:
            event.accept()
            return
        if not self.maybe_save():
            event.ignore()
            return
        self.context.autosaver.discard()
        self.context.autosaver.stop()
        if self.render.is_busy():
            self.render.cancel()
        self.save_layout()
        self.teardown()
        event.accept()
