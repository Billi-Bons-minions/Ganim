"""The zoom lens (Manim's ZoomedScene): code, rules, stage display and rendering."""

from __future__ import annotations

import importlib.util

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model.conflicts import step_conflicts
from manim_studio.model.entities import Scene
from manim_studio.model.schema import animation_allowed
from manim_studio.model.types import AnimationKind, ObjectKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_animation, make_object, make_project, play

HAS_MANIM = importlib.util.find_spec("manim") is not None


def lens_scene() -> Scene:
    circle = make_object(ObjectKind.CIRCLE, "Kreis", "c", -3.0, -1.0)
    text = make_object(ObjectKind.TEXT, "Text", "t", -2.5, -1.2, text="klein", font_size=14.0)
    lens = make_object(ObjectKind.ZOOM_LENS, "Lupe", "z", -2.5, -1.2, zoom=3.0, display_x=4.0, display_y=1.5, display_width=4.0, display_height=2.5)
    steps = [
        play(make_animation(AnimationKind.FADE_IN, "z", "pop")),
        play(make_animation(AnimationKind.MOVE, "z", "move", x=-2.0, y=-0.8)),
        play(make_animation(AnimationKind.SCALE, "z", "zoom", factor=0.5)),
        play(make_animation(AnimationKind.FADE_OUT, "z", "out")),
    ]
    return Scene(id="s", name="Lupe", objects=[circle, text, lens], steps=steps)


def test_code() -> None:
    scene = lens_scene()
    assert not has_errors(validate_scene(scene))
    code = generate_script(make_project(scene))
    assert "class Lupe(ZoomedScene):" in code
    assert "lupe = self.zoomed_camera.frame" in code and "lupe.stretch_to_fit_width(1.333333).stretch_to_fit_height(0.833333)" in code
    assert "self.zoomed_display.move_to([4.0, 1.5, 0.0])" in code
    # popping out: the display starts at the frame and is restored to its place
    assert "self.activate_zooming()" in code and "self.zoomed_display.replace(lupe, stretch=True)" in code and "Restore(self.zoomed_display" in code
    assert "AnimationGroup(FadeOut(lupe), FadeOut(self.zoomed_display)" in code
    # the lens is no mobject of its own: activate_zooming adds frame and display
    assert "self.add(kreis, text)" in code and "self.add(kreis, text, lupe)" not in code


def test_rules() -> None:
    assert animation_allowed(AnimationKind.MOVE, ObjectKind.ZOOM_LENS, {}) and not animation_allowed(AnimationKind.CREATE, ObjectKind.ZOOM_LENS, {})
    scene = lens_scene()
    # popping out and moving at once cannot be combined: the lens gets its own steps
    assert "z" in step_conflicts(scene, [make_animation(AnimationKind.FADE_IN, "z"), make_animation(AnimationKind.MOVE, "z", x=1.0, y=0.0)])
    scene.objects.append(make_object(ObjectKind.ZOOM_LENS, "Lupe 2", "z2"))
    assert "lens_duplicate" in {issue.code for issue in validate_scene(scene)}
    scene.objects.pop()
    scene.objects.append(make_object(ObjectKind.AXES_3D, "Achsen", "ax"))
    assert "lens_needs_2d" in {issue.code for issue in validate_scene(scene)}


def test_one_lens_per_scene(window) -> None:
    controller = window.controller
    first = controller.add_object(ObjectKind.ZOOM_LENS)
    assert controller.add_object(ObjectKind.ZOOM_LENS) == first
    assert sum(1 for obj in window.editor.scene().objects if obj.kind == ObjectKind.ZOOM_LENS) == 1


def test_stage_shows_the_framed_part(qapp) -> None:
    from manim_studio.model.state import states_after
    from manim_studio.ui.stage.drawing import StageResources
    from manim_studio.ui.stage.view import StageView

    scene = lens_scene()
    view = StageView()
    view.set_content(scene, states_after(scene, 1), StageResources(), [], False)
    lens_item = view._items["z"]
    pictures = [primitive for primitive in lens_item.drawing.primitives if primitive.view_source is not None]
    assert pictures and pictures[0].image is not None
    image = pictures[0].image
    # the circle's filling or outline shows up magnified somewhere in the display
    assert any(image.pixelColor(x, y).alpha() > 0 for x in range(0, image.width(), 7) for y in range(0, image.height(), 7))


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_lens_renders(tmp_path) -> None:
    from tests.test_manim_integration import run_manim

    result = run_manim(tmp_path, generate_script(make_project(lens_scene())), "Lupe", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_lens_in_a_joined_video(tmp_path) -> None:
    from manim_studio.codegen.generator import JOINED_CLASS, CodegenOptions
    from tests.test_manim_integration import run_manim

    plain = Scene(id="p", name="Erst", objects=[make_object(ObjectKind.SQUARE, "Q", "q")], steps=[play(make_animation(AnimationKind.CREATE, "q"))])
    script = generate_script(make_project(plain, lens_scene()), CodegenOptions(joined=True))
    assert f"class {JOINED_CLASS}(ZoomedScene):" in script
    result = run_manim(tmp_path, script, JOINED_CLASS, "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
