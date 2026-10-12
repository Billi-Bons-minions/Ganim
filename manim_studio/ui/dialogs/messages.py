"""Translated messages for validation issues and render errors."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

from manim_studio.codegen.errors import CodegenError
from manim_studio.i18n import has, tr
from manim_studio.model.entities import Scene
from manim_studio.model.validation import ERROR, Issue
from manim_studio.render.output_parser import ErrorSummary


def issue_text(scene: Scene, issue: Issue) -> str:
    """Return a readable sentence for a validation issue."""
    obj = scene.object_by_id(issue.object_id) if issue.object_id else None
    name = obj.name if obj else ""
    step = (issue.step_index + 1) if issue.step_index is not None else ""
    detail = issue.detail
    if issue.code == "expression_invalid" and detail:
        # "unknown_function: q" -> the readable explanation of the term error
        code, _, rest = str(detail).partition(": ")
        if has(f"expr.{code}"):
            detail = tr(f"expr.{code}", detail=rest)
    message = tr(f"issue.{issue.code}", name=name, step=step, detail=detail)
    prefix = tr("issue.prefix_step", step=step) if issue.step_index is not None else ""
    if name and issue.step_index is None:
        prefix = f"{name}: "
    return f"{prefix}{message}"


def codegen_error_text(error: CodegenError) -> str:
    """Return a readable sentence for a code generation error."""
    return tr(f"codegen.{error.code}", detail=error.detail)


def render_error_text(error: ErrorSummary) -> str:
    """Return a readable sentence for a failed render."""
    return tr(f"render_error.{error.code}", detail=error.detail)


def show_issues(parent: QWidget, scene: Scene, issues: list[Issue]) -> None:
    """Show validation errors that prevent rendering."""
    errors = [issue_text(scene, issue) for issue in issues if issue.severity == ERROR]
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(tr("issues.title"))
    box.setText(tr("issues.text", count=len(errors)))
    box.setInformativeText("\n".join(f"• {line}" for line in errors[:15]))
    box.exec()
