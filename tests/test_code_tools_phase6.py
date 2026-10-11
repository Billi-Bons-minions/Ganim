"""Source map, script import (never executed) and round trips."""

from __future__ import annotations

from manim_studio.codegen import generate_script
from manim_studio.codegen.generator import generate_script_with_map
from manim_studio.examples import circle_to_square, motion
from manim_studio.importer import import_script, summary
from manim_studio.model.types import AnimationKind, ObjectKind, Visibility
from tests.helpers import acceptance_scene, make_project


def test_source_map_points_at_object_and_step_code() -> None:
    project = make_project(acceptance_scene())
    text, source_map = generate_script_with_map(project)
    lines = text.split("\n")
    first, last = source_map.objects[("scene1", "c1")]
    assert lines[first].strip().startswith("kreis_1 = Circle(") and "kreis_1.move_to" in lines[last]
    first, _last = source_map.steps[("scene1", project.scenes[0].steps[1].id)]
    assert lines[first].strip() == "# Step 2"
    assert source_map.object_at(first) is None and source_map.step_at(first + 1) == ("scene1", project.scenes[0].steps[1].id)


def test_generated_scripts_round_trip() -> None:
    for project in (make_project(acceptance_scene()), circle_to_square(), motion()):
        original = generate_script(project)
        report = import_script(original)
        assert report.skipped == []
        assert generate_script(report.project) == original


def test_hand_written_script() -> None:
    source = """
from manim import *

class Demo(Scene):
    def construct(self):
        c = Circle(radius=2, color=BLUE).shift(LEFT * 2)
        s = Square(side_length=1.5, fill_opacity=0.5)
        s.move_to([2, 1, 0])
        t = Text("Hallo", font_size=36).next_to(c, UP)
        a = ValueTracker(1)
        self.add(c)
        self.play(FadeIn(s, shift=UP), Write(t))
        self.play(c.animate.move_to(ORIGIN).scale(0.5), a.animate.set_value(3), run_time=2)
        self.wait(0.5)
        self.play(ReplacementTransform(c, s))
"""
    report = import_script(source)
    assert summary(report) == {"scenes": 1, "objects": 4, "steps": 4, "skipped": 1}
    scene = report.project.scenes[0]
    circle = scene.objects[0]
    assert (circle.kind, circle.x, circle.params["radius"], circle.visibility) == (ObjectKind.CIRCLE, -2.0, 2.0, Visibility.SHOWN)
    assert scene.objects[3].kind == ObjectKind.PARAMETER and scene.objects[3].params["symbol"] == "a"
    kinds = [[anim.kind for anim in step.animations] for step in scene.steps]
    assert kinds[1] == [AnimationKind.MOVE, AnimationKind.SCALE, AnimationKind.SET_VALUE]
    assert scene.steps[1].animations[0].run_time == 2.0 and scene.steps[0].animations[0].params["shift"] == "up"


def test_import_never_executes_code(tmp_path) -> None:
    marker = tmp_path / "executed.txt"
    source = f"""
open({str(marker)!r}, "w").write("x")
from manim import *
class Evil(Scene):
    def construct(self):
        __import__("os").system("echo hacked > {marker}")
        c = Circle()
        self.add(c)
"""
    report = import_script(source)
    assert not marker.exists()
    assert len(report.project.scenes[0].objects) == 1 and len(report.skipped) == 1
