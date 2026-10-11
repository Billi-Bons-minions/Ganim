"""Read-only code view and render log."""

from __future__ import annotations

import keyword
import re

from PySide6.QtCore import QRegularExpression, QTimer, Signal
from PySide6.QtGui import QColor, QFontDatabase, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from manim_studio.i18n import tr

LOG_LIMIT = 20_000


def _format(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    if bold:
        fmt.setFontWeight(700)
    fmt.setFontItalic(italic)
    return fmt


class PythonHighlighter(QSyntaxHighlighter):
    """Minimal Python syntax highlighting for the generated script."""

    def __init__(self, document) -> None:
        super().__init__(document)
        words = "|".join(re.escape(word) for word in keyword.kwlist)
        self._rules = [
            (QRegularExpression(rf"\b({words})\b"), _format("#C678DD", bold=True)),
            (QRegularExpression(r"\b[A-Z][A-Za-z0-9_]*\b"), _format("#E5C07B")),
            (QRegularExpression(r"\b[0-9]+(\.[0-9]+)?\b"), _format("#D19A66")),
            (QRegularExpression(r"\bself\b"), _format("#E06C75", italic=True)),
            (QRegularExpression(r'r?"([^"\\]|\\.)*"'), _format("#98C379")),
            (QRegularExpression(r"#[^\n]*"), _format("#7F848E", italic=True)),
        ]

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt API
        for pattern, fmt in self._rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


def _monospace_editor() -> QPlainTextEdit:
    editor = QPlainTextEdit()
    editor.setReadOnly(True)
    editor.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
    editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
    return editor


class CodePanel(QWidget):
    """Shows the generated Manim script (read-only)."""

    copyRequested = Signal()
    exportRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editor = _monospace_editor()
        self.highlighter = PythonHighlighter(self.editor.document())
        self.status = QLabel()
        self.status.setWordWrap(True)
        copy_button = QPushButton(tr("code.copy"))
        copy_button.clicked.connect(self.copyRequested.emit)
        export_button = QPushButton(tr("code.export"))
        export_button.clicked.connect(self.exportRequested.emit)
        buttons = QHBoxLayout()
        buttons.addWidget(self.status, 1)
        buttons.addWidget(copy_button)
        buttons.addWidget(export_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.editor, 1)
        layout.addLayout(buttons)

    def show_code(self, code: str) -> None:
        """Display a script, keeping the scroll position."""
        if code == self.editor.toPlainText():
            return
        vertical = self.editor.verticalScrollBar().value()
        self.editor.setPlainText(code)
        self.editor.verticalScrollBar().setValue(vertical)
        self.status.setText("")

    def show_error(self, message: str) -> None:
        """Explain why no code could be generated."""
        self.status.setText(message)
        self.status.setStyleSheet("color: #E06C75;")


class LogPanel(QWidget):
    """Complete Manim output of the last render."""

    saveRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editor = _monospace_editor()
        self.editor.setMaximumBlockCount(LOG_LIMIT)
        self._pending: list[str] = []
        self._timer = QTimer(self, interval=100)
        self._timer.timeout.connect(self._flush)
        clear_button = QPushButton(tr("log.clear"))
        clear_button.clicked.connect(self.clear)
        save_button = QPushButton(tr("log.save"))
        save_button.clicked.connect(self.saveRequested.emit)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(clear_button)
        buttons.addWidget(save_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.editor, 1)
        layout.addLayout(buttons)

    def append(self, line: str) -> None:
        """Queue a line (batched to keep the GUI responsive)."""
        self._pending.append(line)
        if not self._timer.isActive():
            self._timer.start()

    def _flush(self) -> None:
        if self._pending:
            self.editor.appendPlainText("\n".join(self._pending))
            self._pending = []
            self.editor.verticalScrollBar().setValue(self.editor.verticalScrollBar().maximum())
        else:
            self._timer.stop()

    def clear(self) -> None:
        """Remove all log lines."""
        self._pending = []
        self.editor.clear()

    def text(self) -> str:
        """Return the complete log."""
        self._flush()
        return self.editor.toPlainText()
