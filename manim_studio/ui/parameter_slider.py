"""Slider for parameters: drag to change a value and watch dependent graphs update."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget

from manim_studio.i18n import tr
from manim_studio.model.geometry import param_float
from manim_studio.model.stage_edits import is_recording
from manim_studio.model.state import states_after
from manim_studio.ui.controller import EditorController
from manim_studio.ui.editor_state import EditorState
from manim_studio.ui.theme import px

STEPS = 1000


class ParameterSlider(QWidget):
    """Shows a parameter's value at the current timeline position.

    At the start the slider sets the start value; in an animation step it
    records a "change value" animation (like dragging objects on the stage).
    """

    def __init__(self, editor: EditorState, controller: EditorController, object_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editor = editor
        self.controller = controller
        self.object_id = object_id
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, STEPS)
        self.slider.setMinimumWidth(px(160))
        self.slider.valueChanged.connect(self._on_moved)
        self.value_label = QLabel()
        self.value_label.setProperty("role", "title")
        self.value_label.setMinimumWidth(px(70))
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.low_label = QLabel()
        self.high_label = QLabel()
        for label in (self.low_label, self.high_label):
            label.setProperty("role", "faint")
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setProperty("role", "muted")
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(self.slider, 1)
        top.addWidget(self.value_label)
        bounds = QHBoxLayout()
        bounds.setContentsMargins(0, 0, 0, 0)
        bounds.addWidget(self.low_label)
        bounds.addStretch(1)
        bounds.addWidget(self.high_label)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(px(2))
        column.addLayout(top)
        column.addLayout(bounds)
        column.addWidget(self.hint)
        self._updating = False
        self.refresh()

    def _bounds(self) -> tuple[float, float]:
        obj = self.editor.scene().object_by_id(self.object_id)
        if obj is None:
            return 0.0, 1.0
        low, high = param_float(obj.params, "minimum", -5.0), param_float(obj.params, "maximum", 5.0)
        return (low, high) if high > low else (low, low + 1.0)

    def current_value(self) -> float:
        """Return the parameter's value after the selected step."""
        states = states_after(self.editor.scene(), self.editor.cursor)
        state = states.get(self.object_id)
        return state.value if state is not None else 0.0

    def refresh(self) -> None:
        """Show the model value (unless the user is dragging)."""
        if self.slider.isSliderDown():
            return
        low, high = self._bounds()
        value = self.current_value()
        self._updating = True
        self.slider.setValue(round((min(max(value, low), high) - low) / (high - low) * STEPS))
        self._updating = False
        self.value_label.setText(f"{value:.3g}" if abs(value) < 1e4 else f"{value:.3e}")
        self.low_label.setText(f"{low:g}")
        self.high_label.setText(f"{high:g}")
        recording = is_recording(self.editor.scene(), self.editor.cursor)
        self.hint.setText(tr("parameter.hint_recording", step=self.editor.cursor + 1) if recording else tr("parameter.hint_start"))

    def _on_moved(self, position: int) -> None:
        if self._updating:
            return
        low, high = self._bounds()
        value = round(low + (high - low) * position / STEPS, 4)
        self.value_label.setText(f"{value:.3g}")
        self.controller.set_value(self.object_id, value, merge_key=f"value:{self.object_id}:{self.editor.cursor}")
