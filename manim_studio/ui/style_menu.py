"""Menu to apply, save and delete styles."""

from __future__ import annotations

from PySide6.QtWidgets import QMenu

from manim_studio.i18n import tr
from manim_studio.ui.icon_set import icon
from manim_studio.ui.widgets import color_icon


def style_title(style) -> str:
    """Display name of a style (built-in styles are translated)."""
    return tr(f"style.builtin.{style.name}") if style.builtin else style.name


def fill_style_menu(menu: QMenu, controller, library, object_id: str) -> None:
    """Apply a style to the selection; save the look of ``object_id`` as a new style."""
    menu.clear()
    if library is None:
        return
    header = menu.addAction(tr("style.apply"))
    header.setEnabled(False)
    for style in library.styles():
        color = str(style.values.get("fill_color") or style.values.get("stroke_color") or "#FFFFFF")
        action = menu.addAction(color_icon(color), style_title(style))
        action.triggered.connect(lambda _checked=False, values=dict(style.values): controller.apply_style(values))
    menu.addSeparator()
    save = menu.addAction(icon("save"), tr("style.save"))
    save.setEnabled(bool(object_id))
    save.triggered.connect(lambda: controller.save_style(object_id))
    user = [style for style in library.styles() if not style.builtin]
    if user:
        delete = menu.addMenu(icon("trash"), tr("style.delete"))
        for style in user:
            delete.addAction(style.name, lambda name=style.name: library.delete_style(name))
