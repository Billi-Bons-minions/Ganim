"""Shows which external tools were found and how to install missing ones."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from manim_studio.i18n import tr
from manim_studio.render.environment import EnvironmentReport, ToolStatus


def platform_key() -> str:
    """Return ``windows``, ``macos`` or ``linux``."""
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def _status_line(tool: ToolStatus) -> str:
    name = tr(f"env.tool.{tool.name}")
    if tool.found:
        version = f" ({tool.version})" if tool.version else ""
        return f"✔ {name}{version}"
    return f"✘ {name} – {tr(f'env.missing.{tool.name}')}"


def report_html(report: EnvironmentReport) -> str:
    """Return a rich-text summary with installation hints."""
    platform = platform_key()
    parts = ["<p>" + "<br>".join(_status_line(tool) for tool in report.tools) + "</p>"]
    for tool in report.tools:
        if tool.found:
            continue
        hint = tr(f"env.hint.{tool.name}.{platform}")
        parts.append(f"<p><b>{tr(f'env.tool.{tool.name}')}</b><br>{hint}</p>")
        if tool.detail and tool.name == "manim":
            parts.append(f"<p><small>{tr('env.detail')}: {tool.detail[:300]}</small></p>")
    if report.all_found:
        parts.append(f"<p>{tr('env.all_ok')}</p>")
    parts.append(f"<p><a href='https://docs.manim.community/en/stable/installation.html'>{tr('env.docs')}</a></p>")
    return "".join(parts)


class EnvironmentDialog(QDialog):
    """Result of the start-up check."""

    def __init__(self, report: EnvironmentReport, show_checkbox: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("env.title"))
        self.setMinimumWidth(520)
        text = QLabel(report_html(report))
        text.setTextFormat(Qt.TextFormat.RichText)
        text.setOpenExternalLinks(True)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.dont_show = QCheckBox(tr("env.dont_show"))
        self.dont_show.setVisible(show_checkbox and not report.all_found)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout = QVBoxLayout(self)
        layout.addWidget(text)
        layout.addWidget(self.dont_show)
        layout.addWidget(buttons)
