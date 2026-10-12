"""Run generated scripts with the real Manim CLI (skipped if Manim is missing)."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model.entities import Scene
from manim_studio.model.types import AnimationKind, ObjectKind
from tests.helpers import acceptance_scene, make_animation, make_object, make_project, play, wait

pytestmark = [
    pytest.mark.manim,
    pytest.mark.skipif(importlib.util.find_spec("manim") is None, reason="Manim is not installed"),
]


def run_manim(tmp_path, script: str, scene_name: str, *extra: str) -> subprocess.CompletedProcess:
    script_path = tmp_path / "szene.py"
    script_path.write_text(script, encoding="utf-8")
    command = [sys.executable, "-m", "manim", "render", "-ql", "--media_dir", str(tmp_path / "media"), *extra,
               str(script_path), scene_name]
    environment = dict(os.environ, COLUMNS="200", NO_COLOR="1")
    return subprocess.run(command, capture_output=True, text=True, timeout=300, cwd=tmp_path, env=environment)


def test_acceptance_script_renders_mp4(tmp_path) -> None:
    result = run_manim(tmp_path, generate_script(make_project(acceptance_scene())), "Szene1")
    assert result.returncode == 0, result.stdout + result.stderr
    assert list((tmp_path / "media").rglob("Szene1.mp4"))


def test_all_animations_execute(tmp_path) -> None:
    objects = [
        make_object(ObjectKind.CIRCLE, "Kreis", "c", -3.0, 0.0),
        make_object(ObjectKind.SQUARE, "Quadrat", "q", 3.0, 0.0),
        make_object(ObjectKind.TRIANGLE, "Dreieck", "d", 0.0, 2.0),
        make_object(ObjectKind.ARROW, "Pfeil", "p", 0.0, -2.0),
        make_object(ObjectKind.TEXT, "Text", "t", 0.0, 3.0, text="Ä \"Ö\" \\ Ü"),
        make_object(ObjectKind.AXES, "Achsen", "a", show_numbers=True),
        make_object(ObjectKind.FUNCTION_GRAPH, "Graph", "g", expression="0,5x^2 - 1", axes_id="a"),
        make_object(ObjectKind.FUNCTION_GRAPH, "Frei", "f", 2.0, -2.0, expression="sin(x)", x_min=-2.0, x_max=2.0),
        make_object(ObjectKind.NUMBER_PLANE, "Ebene", "e"),
        make_object(ObjectKind.ELLIPSE, "Ellipse", "el"),
        make_object(ObjectKind.LINE, "Linie", "l"),
        make_object(ObjectKind.DOT, "Punkt", "pt"),
        make_object(ObjectKind.RECTANGLE, "Rechteck", "r"),
    ]
    quick = {"run_time": 0.2}
    steps = [
        play(*(make_animation(AnimationKind.CREATE, o.id, **quick) for o in objects[:4])),
        play(make_animation(AnimationKind.WRITE, "t", **quick), make_animation(AnimationKind.DRAW_BORDER_THEN_FILL, "r", **quick)),
        play(make_animation(AnimationKind.GROW_FROM_CENTER, "el", **quick), make_animation(AnimationKind.FADE_IN, "l", shift="left", **quick)),
        play(make_animation(AnimationKind.TRANSFORM, "c", target="q", **quick)),
        play(make_animation(AnimationKind.REPLACEMENT_TRANSFORM, "d", target="pt", **quick)),
        play(
            make_animation(AnimationKind.MOVE, "p", "m", x=1.0, y=1.0, **quick),
            make_animation(AnimationKind.ROTATE, "p", "r1", angle=90.0, **quick),
            make_animation(AnimationKind.SCALE, "p", "s1", factor=0.5, **quick),
            make_animation(AnimationKind.CHANGE_COLOR, "p", "k1", color="#FF0000", **quick),
            make_animation(AnimationKind.ROTATE, "r", "r2", angle=360.0, **quick),
        ),
        wait(0.1),
        play(make_animation(AnimationKind.INDICATE, "t", **quick), make_animation(AnimationKind.CIRCUMSCRIBE, "a", **quick)),
        play(make_animation(AnimationKind.UNCREATE, "c", **quick), make_animation(AnimationKind.FADE_OUT, "g", shift="down", **quick)),
    ]
    scene = Scene(id="s", name="Alles", objects=objects, steps=steps)
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Alles", "--dry_run")
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(shutil.which("latex") is None or shutil.which("dvisvgm") is None, reason="LaTeX is not installed")
def test_math_tex_renders_last_frame(tmp_path) -> None:
    formula = make_object(ObjectKind.MATH_TEX, "Formel", "f", latex=r"\int_0^1 x^2\,dx = \frac{1}{3}")
    scene = Scene(id="s", name="Formel", objects=[formula], steps=[play(make_animation(AnimationKind.WRITE, "f"))])
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Formel", "--format", "png")
    assert result.returncode == 0, result.stdout + result.stderr
    assert list((tmp_path / "media").rglob("*.png"))


def test_timing_features_execute_and_end_in_the_right_state(tmp_path) -> None:
    from manim import Circle, Square, tempconfig

    from manim_studio.model.entities import STEP_LAGGED, STEP_SEQUENCE

    circle = make_object(ObjectKind.CIRCLE, "Kreis", "c", -2.0, 0.0, radius=1.0)
    square = make_object(ObjectKind.SQUARE, "Quadrat", "q", 2.0, 0.0)
    together = play(
        make_animation(AnimationKind.CREATE, "c", "cc", run_time=0.4),
        make_animation(AnimationKind.MOVE, "c", "m", x=1.0, y=1.0, run_time=0.4),
        make_animation(AnimationKind.SCALE, "c", "s", factor=2.0, run_time=0.2),
        step_id="together",
    )
    together.animations[2].delay = 0.2
    lagged = play(make_animation(AnimationKind.FADE_IN, "q", run_time=0.3), make_animation(AnimationKind.ROTATE, "c", "r", angle=90.0, run_time=0.3), step_id="lag")
    lagged.mode = STEP_LAGGED
    sequence = play(
        make_animation(AnimationKind.MOVE, "q", "m2", x=-3.0, y=-1.0, run_time=0.3),
        make_animation(AnimationKind.SCALE, "q", "s2", factor=0.5, run_time=0.3),
        step_id="seq",
    )
    sequence.mode = STEP_SEQUENCE
    sequence.animations[1].delay = 0.1
    scene_model = Scene(id="s", name="Timing", objects=[circle, square], steps=[together, lagged, sequence])
    namespace: dict = {}
    exec(compile(generate_script(make_project(scene_model)), "timing.py", "exec"), namespace)
    with tempconfig({"dry_run": True, "quality": "low_quality", "media_dir": str(tmp_path)}):
        scene = namespace["Timing"]()
        scene.render()
    family = [member for top in scene.mobjects for member in top.get_family()]
    rendered_circle = next(m for m in family if isinstance(m, Circle))
    rendered_square = next(m for m in family if isinstance(m, Square))
    assert rendered_circle.get_center()[:2] == pytest.approx([1.0, 1.0], abs=1e-6)
    assert rendered_circle.width == pytest.approx(4.0, abs=1e-3)
    assert rendered_square.get_center()[:2] == pytest.approx([-3.0, -1.0], abs=1e-6)
    assert rendered_square.width == pytest.approx(1.0, abs=1e-3)


def test_effects_combined_with_movement_keep_the_object_usable(tmp_path) -> None:
    from manim import Circle, tempconfig

    circle = make_object(ObjectKind.CIRCLE, "Kreis", "c", -2.0, 0.0, radius=1.0)
    circle.fill_opacity = 0.5
    steps = [
        play(make_animation(AnimationKind.CREATE, "c", "a1", run_time=0.3), make_animation(AnimationKind.MOVE, "c", "a2", x=0.0, y=1.0, run_time=0.3)),
        play(make_animation(AnimationKind.FADE_OUT, "c", "b1", run_time=0.3), make_animation(AnimationKind.SCALE, "c", "b2", factor=2.0, run_time=0.3)),
        play(make_animation(AnimationKind.FADE_IN, "c", "c1", run_time=0.3)),
    ]
    namespace: dict = {}
    exec(compile(generate_script(make_project(Scene(id="s", name="Combo", objects=[circle], steps=steps))), "combo.py", "exec"), namespace)
    with tempconfig({"dry_run": True, "quality": "low_quality", "media_dir": str(tmp_path)}):
        scene = namespace["Combo"]()
        scene.render()
    family = [member for top in scene.mobjects for member in top.get_family()]
    rendered = next(m for m in family if isinstance(m, Circle))
    assert rendered.get_center()[:2] == pytest.approx([0.0, 1.0], abs=1e-6)
    assert rendered.width == pytest.approx(4.0, abs=1e-3)
    assert rendered.get_fill_opacity() == pytest.approx(0.5, abs=1e-3)
    assert rendered.get_stroke_opacity() == pytest.approx(1.0, abs=1e-3)


def test_all_new_object_kinds_render(tmp_path) -> None:
    from manim_studio.model.factory import create_animation, create_object

    def obj(kind, name, x=0.0, y=0.0, **params):
        item = create_object(kind, name, x, y, **params)
        return item

    square = obj(ObjectKind.SQUARE, "Quadrat", -5.0, 2.0)
    objects = [
        square,
        obj(ObjectKind.NUMBER_LINE, "Zahlenstrahl", 0.0, -3.0, length=8.0),
        obj(ObjectKind.VECTOR, "Vektor", -5.0, -1.0),
        obj(ObjectKind.DOUBLE_ARROW, "Doppelpfeil", -2.0, -1.0, length=2.0),
        obj(ObjectKind.DASHED_LINE, "Gestrichelt", 1.0, -1.0, length=2.0),
        obj(ObjectKind.BRACE, "Klammer", target=square.id, label="Seite a"),
        obj(ObjectKind.BRACE, "Freie Klammer", 4.0, 3.0, direction="right", label="frei"),
        obj(ObjectKind.POLYGON, "Polygon", -2.0, 2.0),
        obj(ObjectKind.REGULAR_POLYGON, "Sechseck", 1.0, 2.0, n=6, radius=0.8),
        obj(ObjectKind.STAR, "Stern", 3.5, 1.5),
        obj(ObjectKind.ARC, "Bogen", -5.0, -2.0),
        obj(ObjectKind.SECTOR, "Sektor", -3.0, -2.0),
        obj(ObjectKind.ANNULUS, "Ring", 5.0, -2.0),
        obj(ObjectKind.DECIMAL_NUMBER, "Zahl", 0.0, 3.3, value=3.14159, decimals=2, unit="cm", show_sign=True),
        obj(ObjectKind.TABLE, "Tabelle", 5.0, 0.0, rows=[["x", "y"], ["1"]]),
        obj(ObjectKind.CODE, "Code", 0.0, 0.5),
        obj(ObjectKind.MARKUP_TEXT, "Markup", 0.0, -2.0, font_size=28.0),
        obj(ObjectKind.TEXT, "Absatz", 2.5, -2.0, text="Zeile eins\nzwei", alignment="center", line_spacing=1.2,
            colored_words=[["eins", "#FC6255"]], font_size=28.0),
    ]
    group = obj(ObjectKind.GROUP, "Gruppe", members=[objects[2].id, objects[3].id])
    objects.append(group)
    steps = [
        play(*(create_animation(AnimationKind.FADE_IN, item.id, run_time=0.2) for item in objects if item.kind != ObjectKind.GROUP)),
        play(create_animation(AnimationKind.MOVE, group.id, run_time=0.2, x=-3.5, y=0.0),
             create_animation(AnimationKind.ROTATE, objects[9].id, run_time=0.2, angle=36.0)),
    ]
    if shutil.which("latex") and shutil.which("dvisvgm"):
        objects.append(obj(ObjectKind.TEX, "Tex", 0.0, -3.6, font_size=30.0))
        objects.append(obj(ObjectKind.MATRIX, "Matrix", 5.0, 3.0))
        steps.append(play(create_animation(AnimationKind.WRITE, objects[-2].id, run_time=0.2), create_animation(AnimationKind.CREATE, objects[-1].id, run_time=0.2)))
    scene = Scene(id="s", name="Neu", objects=objects, steps=steps)
    script = generate_script(make_project(scene))
    result = run_manim(tmp_path, script, "Neu", "--format", "png")
    assert result.returncode == 0, result.stdout + result.stderr + script
    assert list((tmp_path / "media").rglob("*.png"))


def graph_feature_scene() -> Scene:
    """Every graph feature in one scene (used by the render test)."""
    def obj(kind, name, object_id, **params):
        return make_object(kind, name, object_id, **params)

    objects = [
        obj(ObjectKind.AXES, "Achsen", "ax", x_label="x", y_label="y"),
        obj(ObjectKind.PARAMETER, "a", "pa", symbol="a", value=1.0),
        obj(ObjectKind.FUNCTION_GRAPH, "Graph", "g", expression="x^3/3 - x", axes_id="ax"),
        obj(ObjectKind.FUNCTION_GRAPH, "Ableitung", "d", curve="derivative", derive_from="g", axes_id="ax"),
        obj(ObjectKind.FUNCTION_GRAPH, "Stueck", "pw", curve="piecewise", axes_id="ax"),
        obj(ObjectKind.FUNCTION_GRAPH, "Kurve", "pc", curve="parametric", axes_id="ax"),
        obj(ObjectKind.FUNCTION_GRAPH, "Rose", "po", curve="polar", axes_id="ax"),
        obj(ObjectKind.FUNCTION_GRAPH, "Tangens", "tn", expression="tan(x)", axes_id="ax"),
        obj(ObjectKind.FUNCTION_GRAPH, "Welle", "w", expression="a sin(x)", axes_id="ax"),
        obj(ObjectKind.FUNCTION_GRAPH, "Frei", "fr", expression="a x^2", x_min=-1.0, x_max=1.0),
        obj(ObjectKind.GRAPH_AREA, "Flaeche", "ar", graph_id="g"),
        obj(ObjectKind.GRAPH_AREA, "Zwischen", "ab", graph_id="g", mode="between", other_graph_id="d"),
        obj(ObjectKind.GRAPH_AREA, "Oben", "aa", graph_id="w", mode="above", x_min=-3.0, x_max=-1.0),
        obj(ObjectKind.RIEMANN, "Riemann", "ri", graph_id="g"),
        obj(ObjectKind.TANGENT, "Tangente", "t1", graph_id="g", x_value=0.5),
        obj(ObjectKind.TANGENT, "Tangente2", "t2", graph_id="w", x_parameter="pa"),
        obj(ObjectKind.GRAPH_POINT, "Punkt", "p1", graph_id="g", show_label=True),
        obj(ObjectKind.GRAPH_POINT, "Wanderpunkt", "p2", graph_id="w", x_parameter="pa", show_label=True),
        obj(ObjectKind.GRAPH_MARKERS, "Nullstellen", "m1", graph_id="g"),
        obj(ObjectKind.GRAPH_MARKERS, "Extrema", "m2", graph_id="g", feature="extrema"),
        obj(ObjectKind.GRAPH_MARKERS, "Schnitt", "m3", graph_id="g", feature="intersections", other_graph_id="d"),
        obj(ObjectKind.GRAPH_LABEL, "Label", "lb", graph_id="g"),
        obj(ObjectKind.DECIMAL_NUMBER, "Zahl", "n", parameter_id="pa"),
    ]
    steps = [
        play(make_animation(AnimationKind.CREATE, "g", run_time=0.2), make_animation(AnimationKind.FADE_IN, "t2", run_time=0.2)),
        play(make_animation(AnimationKind.SET_VALUE, "pa", "v", value=2.0, run_time=0.3)),
    ]
    return Scene(id="s", name="Graphen", objects=objects, steps=steps)


def test_graph_features_render(tmp_path) -> None:
    script = generate_script(make_project(graph_feature_scene()))
    result = run_manim(tmp_path, script, "Graphen", "--format", "png")
    assert result.returncode == 0, result.stdout + result.stderr + script
    assert list((tmp_path / "media").rglob("*.png"))


def test_parameter_animation_moves_dependent_objects(tmp_path) -> None:
    import math

    from manim import DecimalNumber, Dot, tempconfig

    namespace: dict = {}
    exec(compile(generate_script(make_project(graph_feature_scene())), "graphen.py", "exec"), namespace)
    with tempconfig({"dry_run": True, "quality": "low_quality", "media_dir": str(tmp_path)}):
        scene = namespace["Graphen"]()
        scene.render()
    family = [member for top in scene.mobjects for member in top.get_family()]
    dots = [m.get_center()[:2] for m in family if isinstance(m, Dot)]
    assert any(abs(x - 2.0) < 1e-3 and abs(y - 2.0 * math.sin(2.0)) < 1e-3 for x, y in dots)
    number = next(m for m in family if isinstance(m, DecimalNumber))
    assert number.get_value() == pytest.approx(2.0)


def test_data_plots_and_bar_charts_render(tmp_path) -> None:
    axes = make_object(ObjectKind.AXES, "Achsen", "ax", -3.0, 0.0, x_length=6.0, y_length=6.0, show_numbers=True)
    objects = [
        axes,
        make_object(ObjectKind.DATA_PLOT, "Punkte", "d1", axes_id="ax", regression="linear"),
        make_object(ObjectKind.DATA_PLOT, "Linie", "d2", axes_id="ax", display="both", regression="quadratic", data=[[-4, 2.5], [0, -1], [4, 2.8]]),
        make_object(ObjectKind.DATA_PLOT, "Wachstum", "d3", axes_id="ax", display="line", regression="exponential", data=[[0, 0.5], [1, 0.9], [2, 1.8]]),
        make_object(ObjectKind.BAR_CHART, "Balken", "b", 3.5, 0.0, show_values=True, bars=[["Mo", "3"], ["Di", "-2"], ["Mi", "4"]]),
    ]
    steps = [play(*(make_animation(AnimationKind.CREATE, item.id, run_time=0.2) for item in objects[1:]))]
    script = generate_script(make_project(Scene(id="s", name="Daten", objects=objects, steps=steps)))
    result = run_manim(tmp_path, script, "Daten", "--format", "png")
    assert result.returncode == 0, result.stdout + result.stderr + script


def test_new_animations_camera_and_colored_formula(tmp_path) -> None:
    from manim import Circle, Square, Text, tempconfig

    objects = [
        make_object(ObjectKind.CIRCLE, "Kreis", "c", -3.0, 0.0, radius=0.5),
        make_object(ObjectKind.SQUARE, "Quadrat", "q", 3.0, 0.0, side_length=1.0),
        make_object(ObjectKind.CIRCLE, "Bahn", "path", 0.0, 0.0, radius=2.0),
        make_object(ObjectKind.ARROW, "Pfeil", "a", 0.0, -3.0),
        make_object(ObjectKind.TEXT, "Text", "t", 0.0, 3.0, text="Hallo"),
        make_object(ObjectKind.TRIANGLE, "Dreieck", "tri", -5.0, 3.0),
        make_object(ObjectKind.STAR, "Stern", "st", 5.0, 3.0),
        make_object(ObjectKind.CAMERA, "Kamera", "cam"),
    ]
    steps = [
        play(
            make_animation(AnimationKind.SPIN_IN, "c", run_time=0.2),
            make_animation(AnimationKind.GROW_ARROW, "a", run_time=0.2),
            make_animation(AnimationKind.ADD_LETTERS, "t", run_time=0.2),
        ),
        play(
            make_animation(AnimationKind.SWAP, "c", "swap", partner="q", run_time=0.2),
            make_animation(AnimationKind.FLASH, "a", run_time=0.2),
            make_animation(AnimationKind.WIGGLE, "t", run_time=0.2),
            make_animation(AnimationKind.MOVE, "cam", "cm", x=1.0, y=0.5, run_time=0.2),
        ),
        play(
            make_animation(AnimationKind.MOVE_ALONG_PATH, "q", "along", path="path", run_time=0.2),
            make_animation(AnimationKind.APPLY_WAVE, "t", run_time=0.2),
            make_animation(AnimationKind.FOCUS_ON, "a", run_time=0.2),
            make_animation(AnimationKind.SCALE, "cam", "cs", factor=1.5, run_time=0.2),
        ),
        play(
            make_animation(AnimationKind.FADE_TRANSFORM, "tri", "ft", target="st", run_time=0.2),
            make_animation(AnimationKind.SHRINK_TO_CENTER, "a", run_time=0.2),
        ),
        play(make_animation(AnimationKind.TRANSFORM_MATCHING, "st", "tm", target="tri", run_time=0.2)),
    ]
    if shutil.which("latex") and shutil.which("dvisvgm"):
        objects.append(make_object(ObjectKind.MATH_TEX, "Formel", "f", 0.0, -1.5, latex=r"\frac{a}{b} + a^2", colored_parts=[["a", "#FC6255"]]))
    scene_model = Scene(id="s", name="Neu", objects=objects, steps=steps)
    script = generate_script(make_project(scene_model))
    assert "class Neu(MovingCameraScene):" in script and "self.camera.frame.animate" in script
    namespace: dict = {}
    exec(compile(script, "neu.py", "exec"), namespace)
    with tempconfig({"dry_run": True, "quality": "low_quality", "media_dir": str(tmp_path)}):
        scene = namespace["Neu"]()
        scene.render()
    family = [member for top in scene.mobjects for member in top.get_family()]
    circle = next(m for m in family if isinstance(m, Circle) and m.width < 1.5)
    square = next(m for m in family if isinstance(m, Square))
    assert circle.get_center()[:2] == pytest.approx([3.0, 0.0], abs=1e-3)
    assert square.get_center()[:2] == pytest.approx([2.0, 0.0], abs=1e-3)
    assert any(isinstance(m, Text) for m in family)
    assert scene.camera.frame.get_center()[:2] == pytest.approx([1.0, 0.5], abs=1e-3)
    result = run_manim(tmp_path, script, "Neu", "--format", "png")
    assert result.returncode == 0, result.stdout + result.stderr + script


def test_portrait_joined_video_with_subtitles_and_sound(tmp_path) -> None:
    import wave

    import av

    sound = tmp_path / "ton.wav"
    with wave.open(str(sound), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * 4000)
    first = Scene(id="a", name="Erste", objects=[make_object(ObjectKind.CIRCLE, "Kreis", "c")], steps=[play(make_animation(AnimationKind.CREATE, "c", run_time=0.3))])
    first.steps[0].section, first.steps[0].subcaption, first.steps[0].sound = "Start", "Ein Kreis", "ton.wav"
    second = Scene(id="b", name="Zweite", objects=[make_object(ObjectKind.SQUARE, "Quadrat", "q")], steps=[play(make_animation(AnimationKind.FADE_IN, "q", run_time=0.3))])
    project = make_project(first, second)
    project.aspect = "9:16"
    from manim_studio.codegen import CodegenOptions

    script = generate_script(project, CodegenOptions(base_dir=tmp_path, joined=True, transition="fade"))
    result = run_manim(tmp_path, script, "AllScenes", "--save_sections", "-o", "gesamt")
    assert result.returncode == 0, result.stdout + result.stderr + script
    video = next(path for path in (tmp_path / "media").rglob("gesamt.mp4") if "partial" not in str(path))
    with av.open(str(video)) as container:
        stream = container.streams.video[0]
        assert (stream.width, stream.height) == (480, 854)
        assert container.streams.audio
    assert video.with_suffix(".srt").exists()
    assert list(video.parent.glob("sections/*.mp4"))


def test_builtin_templates_run_in_manim(tmp_path) -> None:
    from manim_studio.templates import BUILTIN_TEMPLATES

    project = make_project(*(template.build() for template in BUILTIN_TEMPLATES))
    from manim_studio.codegen import CodegenOptions

    script = generate_script(project, CodegenOptions(joined=True))
    result = run_manim(tmp_path, script, "AllScenes", "--dry_run")
    assert result.returncode == 0, result.stdout + result.stderr + script


def test_three_d_scene_renders(tmp_path) -> None:
    from tests.test_three_d import space_scene

    script = generate_script(make_project(space_scene()))
    result = run_manim(tmp_path, script, "Raum", "--format", "png")
    assert result.returncode == 0, result.stdout + result.stderr + script


@pytest.mark.parametrize(("output_format", "transparent", "extension"), [("mp4", True, "mov"), ("webm", True, "webm"), ("mov", False, "mov")])
def test_video_formats_and_transparency(tmp_path, output_format, transparent, extension) -> None:
    from manim_studio.render.command import RenderJob, build_arguments, find_output, render_environment

    script = tmp_path / "szene.py"
    script.write_text(generate_script(make_project(acceptance_scene())), encoding="utf-8")
    job = RenderJob(script, "Szene1", tmp_path / "media", "clip", format=output_format, quality="l", transparent=transparent)
    result = subprocess.run([sys.executable, *build_arguments(job)], capture_output=True, text=True, timeout=300, cwd=tmp_path, env=render_environment())
    assert result.returncode == 0, result.stdout + result.stderr
    output = find_output(job.media_dir, "clip", job.extension())
    assert output is not None and output.suffix == f".{extension}"
    import av

    with av.open(str(output)) as container:
        stream = container.streams.video[0]
        # VP9 keeps alpha in a side channel that is announced by the alpha_mode tag
        has_alpha = "a" in stream.codec_context.pix_fmt.replace("yuv", "") or stream.metadata.get("alpha_mode") == "1"
    assert has_alpha == transparent


def test_fuzzing_regressions_render(tmp_path) -> None:
    """Arrow turned into a group, path along a dashed line, group with a parameter."""
    arrow = make_object(ObjectKind.ARROW, "Pfeil", "a1", -2.0, 1.0)
    bars = make_object(ObjectKind.BAR_CHART, "Balken", "b1", 2.0, 0.0)
    dashed = make_object(ObjectKind.DASHED_LINE, "Strich", "d1", 0.0, -2.0)
    dot = make_object(ObjectKind.DOT, "Punkt", "p1", -1.5, -2.0)
    parameter = make_object(ObjectKind.PARAMETER, "a", "k1", symbol="a")
    group = make_object(ObjectKind.GROUP, "Gruppe", "g1", members=["p1", "k1", "d1"])
    scene = Scene(
        id="s",
        name="Regression",
        objects=[arrow, bars, dashed, dot, parameter, group],
        steps=[
            play(make_animation(AnimationKind.TRANSFORM, "a1", target="b1")),
            play(make_animation(AnimationKind.FADE_OUT, "a1"), make_animation(AnimationKind.MOVE_ALONG_PATH, "p1", path="d1")),
            play(make_animation(AnimationKind.SCALE, "g1", factor=0.5)),
        ],
    )
    script = generate_script(make_project(scene))
    assert "studio_shape(pfeil)" in script and "Line(strich.get_start(), strich.get_end())" in script
    result = run_manim(tmp_path, script, "Regression", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
