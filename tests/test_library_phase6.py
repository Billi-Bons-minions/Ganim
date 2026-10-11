"""Styles, building blocks and scene templates."""

from __future__ import annotations

import pytest

from manim_studio.codegen import CodegenOptions, generate_script
from manim_studio.model import operations as ops
from manim_studio.model.entities import Project, Scene
from manim_studio.model.types import ObjectKind
from manim_studio.model.validation import has_errors, validate_scene
from manim_studio.templates import BUILTIN_TEMPLATES
from tests.helpers import make_object


def test_apply_style_only_where_it_fits() -> None:
    circle = make_object(ObjectKind.CIRCLE, "Kreis", "c")
    text = make_object(ObjectKind.TEXT, "Text", "t")
    line = make_object(ObjectKind.LINE, "Linie", "l")
    scene = Scene(id="s", name="S", objects=[circle, text, line])
    group = ops.group_objects(scene, ["c", "t", "l"], "G")
    ops.apply_style(scene, [group], {"fill_color": "#FC6255", "stroke_color": "#83C167", "font_size": 20.0})
    assert (circle.fill_color, circle.stroke_color) == ("#FC6255", "#83C167")
    assert text.fill_color == "#FC6255" and text.params["font_size"] == 20.0
    assert line.stroke_color == "#83C167" and "font_size" not in line.params


def test_user_library_round_trip(tmp_path, qapp) -> None:
    from manim_studio.ui.user_library import UserLibrary, style_of

    library = UserLibrary(tmp_path)
    circle = make_object(ObjectKind.CIRCLE, "Kreis", "c")
    circle.fill_color = "#123456"
    library.save_style("Mein Stil", style_of(circle))
    assert library.styles()[-1].values["fill_color"] == "#123456"
    library.delete_style("Mein Stil")
    assert all(style.builtin for style in library.styles())
    library.save_component("Kreis/Box", [circle])
    component = library.components()[0]
    assert component.name == "Kreis/Box" and component.create_objects()[0].fill_color == "#123456"
    library.delete_component(component)
    assert library.components() == []
    scene = Scene(id="s", name="Vorlage", objects=[circle])
    library.save_template("Meine Vorlage", scene)
    assert library.templates()[0].create_scene() == scene


@pytest.mark.parametrize("template", BUILTIN_TEMPLATES, ids=lambda template: template.key)
def test_builtin_templates_are_valid(template) -> None:
    scene = template.build()
    assert not has_errors(validate_scene(scene, latex_available=False))
    generate_script(Project(scenes=[scene]), CodegenOptions())
