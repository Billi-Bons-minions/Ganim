"""Start screen: tutorial, new/open project, examples and recent files."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from manim_studio.examples import EXAMPLES
from manim_studio.i18n import tr
from manim_studio.ui.chrome import ChoiceTile
from manim_studio.ui.icon_set import icon
from manim_studio.ui.icons import app_icon
from manim_studio.ui.settings import AppSettings
from manim_studio.ui.theme import current_palette, px

CHOICE_TUTORIAL = "tutorial"
CHOICE_NEW = "new"
CHOICE_OPEN = "open"
EXAMPLE_PREFIX = "example:"
RECENT_PREFIX = "recent:"
MAX_RECENT = 5


class WelcomeDialog(QDialog):
    """Lets the user choose how to start; :attr:`choice` holds the result."""

    def __init__(self, settings: AppSettings, latex_available: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.choice = ""
        self.setWindowTitle(tr("welcome.window_title"))
        self.setMinimumWidth(px(760))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(28), px(24), px(28), px(20))
        layout.setSpacing(px(14))
        layout.addLayout(self._header())
        layout.addLayout(self._start_tiles())
        layout.addWidget(self._section_label(tr("welcome.examples")))
        layout.addLayout(self._examples(latex_available))
        recent = self._recent()
        if recent is not None:
            layout.addWidget(self._section_label(tr("welcome.recent")))
            layout.addWidget(recent)
        footer = QHBoxLayout()
        self.show_again = QCheckBox(tr("welcome.show_on_start"))
        self.show_again.setChecked(settings.show_welcome)
        close = QPushButton(tr("welcome.close"))
        close.clicked.connect(self.reject)
        footer.addWidget(self.show_again)
        footer.addStretch(1)
        footer.addWidget(close)
        layout.addLayout(footer)
        self.finished.connect(lambda _code: setattr(self.settings, "show_welcome", self.show_again.isChecked()))

    def _header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(QSize(px(52), px(52))))
        texts = QVBoxLayout()
        title = QLabel(tr("welcome.title"))
        font = title.font()
        font.setPointSizeF(font.pointSizeF() * 1.6)
        font.setBold(True)
        title.setFont(font)
        subtitle = QLabel(tr("welcome.subtitle"))
        subtitle.setProperty("role", "muted")
        texts.addWidget(title)
        texts.addWidget(subtitle)
        row.addWidget(logo)
        row.addSpacing(px(10))
        row.addLayout(texts, 1)
        return row

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setProperty("role", "section")
        return label

    def _tile(self, icon_name: str, title: str, text: str, choice: str, primary: bool = False) -> ChoiceTile:
        color = current_palette().accent_text if primary else None
        tile = ChoiceTile(icon(icon_name, color), title, text, primary)
        tile.clicked.connect(lambda: self._choose(choice))
        return tile

    def _start_tiles(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(px(10))
        row.addWidget(self._tile("lightbulb", tr("welcome.tutorial"), tr("welcome.tutorial_text"), CHOICE_TUTORIAL, primary=True))
        row.addWidget(self._tile("new", tr("welcome.new"), tr("welcome.new_text"), CHOICE_NEW))
        row.addWidget(self._tile("open", tr("welcome.open"), tr("welcome.open_text"), CHOICE_OPEN))
        return row

    def _examples(self, latex_available: bool) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(px(10))
        for index, example in enumerate(EXAMPLES):
            text = tr(f"example.{example.key}.text")
            if example.needs_latex and not latex_available:
                text = tr("welcome.needs_latex")
            tile = self._tile(example.icon, tr(f"example.{example.key}.name"), text, EXAMPLE_PREFIX + example.key)
            tile.setEnabled(latex_available or not example.needs_latex)
            grid.addWidget(tile, index // 3, index % 3)
        return grid

    def _recent(self) -> QWidget | None:
        files = [path for path in self.settings.recent_files if Path(path).exists()][:MAX_RECENT]
        if not files:
            return None
        box = QWidget()
        column = QVBoxLayout(box)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(px(2))
        for path in files:
            button = QPushButton(icon("open"), f"{Path(path).stem}   —   {Path(path).parent}")
            button.setProperty("variant", "link")
            button.setStyleSheet("text-align: left;")
            button.clicked.connect(lambda _checked=False, p=path: self._choose(RECENT_PREFIX + p))
            column.addWidget(button)
        return box

    def _choose(self, choice: str) -> None:
        self.choice = choice
        self.accept()
