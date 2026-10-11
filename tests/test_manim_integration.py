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
