"""Timeline panel: transport controls, step settings and the time-based canvas."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from manim_studio.i18n import tr
from manim_studio.model.entities import STEP_LAGGED, STEP_MODES
from manim_studio.model.playback import total_duration
from manim_studio.model.state import START
from manim_studio.model.types import StepKind
from manim_studio.ui.animation_catalog import ANIMATION_GROUPS, ONLY_WHEN_ALLOWED
from manim_studio.ui.chrome import separator
from manim_studio.ui.controller import EditorController
from manim_studio.ui.document import ProjectDocument
from manim_studio.ui.editor_state import INSPECT_ANIMATION, EditorState
from manim_studio.ui.icon_set import icon
from manim_studio.ui.panels.timeline_view import TimelineCanvas
from manim_studio.ui.playback import PlaybackController
from manim_studio.ui.theme import px


#: Order of animations in the menus.
def build_animation_menu(menu: QMenu, controller: EditorController, same_step: bool) -> None:
    """Fill ``menu`` with all animations; unsuitable ones are disabled."""
    menu.clear()
    for group_index, (_key, group) in enumerate(ANIMATION_GROUPS):
        if group_index:
            menu.addSeparator()
        for kind in group:
            if kind in ONLY_WHEN_ALLOWED and not controller.animation_allowed(kind):
                continue
            action = menu.addAction(icon(f"a_{kind.value}"), tr(f"anim.{kind.value}"))
            action.setToolTip(tr(f"anim_help.{kind.value}"))
            action.setEnabled(controller.animation_allowed(kind))
            action.triggered.connect(lambda _checked=False, k=kind: controller.add_animation(k, same_step))
    if not controller.editor.selected_objects:
        menu.addSeparator()
        hint = menu.addAction(tr("status.select_object_first"))
        hint.setEnabled(False)


def format_time(seconds: float) -> str:
    """Return ``m:ss.s``."""
    seconds = max(0.0, seconds)
    return f"{int(seconds // 60)}:{seconds % 60:04.1f}"


class TimelinePanel(QWidget):
    """The bottom panel with transport, step settings and the timeline canvas."""

    def __init__(
        self,
        document: ProjectDocument,
        editor: EditorState,
        controller: EditorController,
        playback: PlaybackController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.document = document
        self.editor = editor
        self.controller = controller
        self.playback = playback
        self.canvas = TimelineCanvas()
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.canvas)
        self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("Panel")
        self._build_toolbar()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(6), px(4), px(6), px(4))
        layout.setSpacing(px(4))
        layout.addLayout(self.toolbar)
        layout.addWidget(self.scroll, 1)
        self._connect()
        self.refresh()

    # --- construction ---------------------------------------------------------------

    def _button(self, icon_name: str, tooltip: str, slot=None, text: str = "", menu: QMenu | None = None) -> QToolButton:
        button = QToolButton()
        button.setIcon(icon(icon_name))
        button.setIconSize(QSize(px(16), px(16)))
        button.setToolTip(tooltip)
        if text:
            button.setText(text)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        if slot is not None:
            button.clicked.connect(slot)
        if menu is not None:
            button.setMenu(menu)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        return button

    def _build_toolbar(self) -> None:
        bar = QHBoxLayout()
        bar.setSpacing(px(2))
        bar.addWidget(self._button("skip_back", tr("timeline.go_start_tip"), self.playback.stop))
        self.play_button = self._button("play", tr("timeline.play_tip"), self.playback.toggle)
        bar.addWidget(self.play_button)
        self.time_label = QLabel()
        self.time_label.setProperty("role", "muted")
        self.time_label.setMinimumWidth(px(96))
        bar.addWidget(self.time_label)
        bar.addWidget(separator(vertical=True))
        menu = QMenu(self)
        menu.aboutToShow.connect(lambda: build_animation_menu(menu, self.controller, False))
        bar.addWidget(self._button("sparkle", tr("timeline.add_animation_tip"), text=tr("timeline.add_animation"), menu=menu))
        self.add_step_button = self._button("plus", tr("timeline.add_step_tip"), lambda: self.controller.add_step(StepKind.PLAY), tr("timeline.add_step"))
        bar.addWidget(self.add_step_button)
        bar.addWidget(self._button("clock", tr("timeline.add_wait_tip"), lambda: self.controller.add_step(StepKind.WAIT), tr("timeline.add_wait")))
        bar.addWidget(self._button("duplicate", tr("timeline.duplicate_tip"), self.controller.duplicate_step))
        bar.addWidget(self._button("trash", tr("timeline.delete_tip"), self.controller.delete_in_timeline))
        bar.addStretch(1)
        self.mode_label = QLabel(tr("timeline.mode"))
        self.mode_label.setProperty("role", "muted")
        self.mode_combo = QComboBox()
        for mode in STEP_MODES:
            self.mode_combo.addItem(tr(f"step_mode.{mode}"), mode)
        self.mode_combo.setToolTip(tr("timeline.mode_tip"))
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.lag_spin = QDoubleSpinBox()
        self.lag_spin.setRange(0.0, 1.0)
        self.lag_spin.setSingleStep(0.05)
        self.lag_spin.setKeyboardTracking(False)
        self.lag_spin.setToolTip(tr("timeline.lag_tip"))
        self.lag_spin.valueChanged.connect(self._on_lag_changed)
        bar.addWidget(self.mode_label)
        bar.addWidget(self.mode_combo)
        bar.addWidget(self.lag_spin)
        bar.addWidget(separator(vertical=True))
        bar.addWidget(self._button("zoom_out", tr("timeline.zoom_out_tip"), lambda: self.canvas.set_zoom(self.canvas.pps / 1.3)))
        bar.addWidget(self._button("zoom_in", tr("timeline.zoom_in_tip"), lambda: self.canvas.set_zoom(self.canvas.pps * 1.3)))
        self.toolbar = bar

    def _connect(self) -> None:
        self.document.changed.connect(self.refresh)
        self.editor.sceneChanged.connect(self.refresh)
        self.editor.cursorChanged.connect(self.refresh)
        self.editor.inspectorChanged.connect(self.refresh)
        self.editor.playheadChanged.connect(self._on_playhead)
        self.playback.playingChanged.connect(self._on_playing)
        canvas = self.canvas
        canvas.stepClicked.connect(self.editor.inspect_step)
        canvas.animationClicked.connect(self.editor.inspect_animation)
        canvas.playheadRequested.connect(self._scrub)
        canvas.timingRequested.connect(self._on_timing)
        canvas.waitRequested.connect(self.controller.set_wait_time)
        canvas.stepsReordered.connect(self.controller.reorder_steps)
        canvas.animationMoved.connect(self.controller.move_animation)
        canvas.animationToNewStep.connect(self.controller.move_animation_to_new_step)
        canvas.stepMenuRequested.connect(self._step_menu)
        canvas.animationMenuRequested.connect(self._animation_menu)

    # --- refresh --------------------------------------------------------------------------

    def refresh(self) -> None:
        """Rebuild the canvas and toolbar state from the model."""
        scene = self.editor.scene()
        kind, entity_id = self.editor.inspected
        selected = entity_id if kind == INSPECT_ANIMATION and entity_id else ""
        names = {obj.id: obj.name for obj in scene.objects}
        self.canvas.set_content(scene, names, self.editor.cursor, selected, self.editor.playhead)
        self._refresh_mode()
        self._on_playhead()

    def _current_step(self):
        steps = self.editor.scene().steps
        cursor = self.editor.cursor
        return steps[cursor] if 0 <= cursor < len(steps) else None

    def _refresh_mode(self) -> None:
        step = self._current_step()
        playable = step is not None and step.kind == StepKind.PLAY
        for widget in (self.mode_label, self.mode_combo):
            widget.setEnabled(playable)
        self.mode_combo.blockSignals(True)
        self.lag_spin.blockSignals(True)
        if playable:
            self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(step.mode)))
            self.lag_spin.setValue(step.lag_ratio)
        self.lag_spin.setVisible(playable and step.mode == STEP_LAGGED)
        self.mode_combo.blockSignals(False)
        self.lag_spin.blockSignals(False)

    def _on_playhead(self) -> None:
        scene = self.editor.scene()
        playhead = self.editor.playhead
        current = playhead if playhead is not None else 0.0
        self.time_label.setText(f"{format_time(current)} / {format_time(total_duration(scene))}")
        self.canvas.set_playhead(playhead)
        if playhead is not None:
            x = int(self.canvas.time_to_x(playhead))
            self.scroll.ensureVisible(x, 0, px(80), 0)

    def _on_playing(self, playing: bool) -> None:
        self.play_button.setIcon(icon("pause" if playing else "play"))

    # --- actions ---------------------------------------------------------------------------

    def _scrub(self, time: float) -> None:
        self.playback.pause()
        self.editor.set_playhead(time)

    def _on_timing(self, animation_id: str, delay: float, run_time: float) -> None:
        self.controller.set_animation_timing(
            animation_id, delay if delay >= 0 else None, run_time if run_time >= 0 else None
        )

    def _on_mode_changed(self) -> None:
        step = self._current_step()
        if step is not None:
            self.controller.set_step_mode(step.id, self.mode_combo.currentData())

    def _on_lag_changed(self, value: float) -> None:
        step = self._current_step()
        if step is not None:
            self.controller.set_step_mode(step.id, step.mode, value)

    def _step_menu(self, position: QPoint, index: int) -> None:
        steps = self.editor.scene().steps
        if not 0 <= index < len(steps):
            return
        step = steps[index]
        menu = QMenu(self)
        if step.kind == StepKind.PLAY:
            modes = menu.addMenu(tr("timeline.mode"))
            for mode in STEP_MODES:
                action = modes.addAction(tr(f"step_mode.{mode}"))
                action.setCheckable(True)
                action.setChecked(step.mode == mode)
                action.triggered.connect(lambda _c=False, m=mode: self.controller.set_step_mode(step.id, m))
        menu.addAction(icon("duplicate"), tr("action.duplicate_step"), self.controller.duplicate_step)
        menu.addAction(icon("trash"), tr("action.delete_step"), self.controller.delete_step)
        menu.exec(position)

    def _animation_menu(self, position: QPoint, animation_id: str) -> None:
        found = self.editor.scene().find_animation(animation_id)
        if found is None:
            return
        index = self.editor.scene().step_index(found[0].id)
        menu = QMenu(self)
        menu.addAction(icon("duplicate"), tr("timeline.duplicate_animation"), lambda: self.controller.duplicate_animation(animation_id))
        menu.addAction(icon("plus"), tr("timeline.to_new_step"), lambda: self.controller.move_animation_to_new_step(animation_id, index + 1))
        menu.addAction(icon("trash"), tr("timeline.remove_animation_tip"), lambda: self.controller.delete_animation(animation_id))
        menu.exec(position)

    def go_start(self) -> None:
        """Select the start of the timeline."""
        self.editor.inspect_step(START)
