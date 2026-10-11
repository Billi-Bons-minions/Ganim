"""Video formats, joined export, sections, sound, subtitles and code steps."""

from __future__ import annotations

from pathlib import Path

from manim_studio.codegen import CodegenOptions, generate_script
from manim_studio.model.entities import Project, RenderSettings, Scene
from manim_studio.model.frame import frame_box, pixel_size
from manim_studio.model.serialization import dumps_project, loads_project
from manim_studio.model.stage_edits import MOVE, check_edit
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind
from manim_studio.model.validation import validate_scene
from manim_studio.render.command import RenderJob, build_arguments
from tests.helpers import make_animation, make_object, play, wait


def two_scenes() -> Project:
    first = Scene(id="a", name="Erste", objects=[make_object(ObjectKind.CIRCLE, "Kreis", "c")], steps=[play(make_animation(AnimationKind.CREATE, "c"))])
    second = Scene(id="b", name="Zweite", objects=[make_object(ObjectKind.SQUARE, "Quadrat", "q")], steps=[play(make_animation(AnimationKind.FADE_IN, "q"))])
    return Project(scenes=[first, second])


def test_formats() -> None:
    assert pixel_size((1920, 1080), "9:16") == (1080, 1920)
    assert pixel_size((854, 480), "1:1") == (480, 480)
    assert frame_box("9:16") == (-2.25, -4.0, 2.25, 4.0)
    project = two_scenes()
    project.aspect = "9:16"
    code = generate_script(project, CodegenOptions())
    assert "config.frame_width = 4.5" in code and "config.pixel_width, config.pixel_height = config.pixel_height, config.pixel_width" in code
    project.aspect = "4:3"
    assert "config.pixel_width = round(config.pixel_height * 4 / 3)" in generate_script(project, CodegenOptions())
    project.aspect = "16:9"
    assert "config.frame_width" not in generate_script(project, CodegenOptions())


def test_joined_class() -> None:
    code = generate_script(two_scenes(), CodegenOptions(joined=True, transition="fade"))
    assert "class AllScenes(Scene):" in code
    assert "for scene_class in (Erste, Zweite,):" in code and "scene_class.construct(self)" in code
    assert "FadeOut(mobject) for mobject in self.mobjects" in code and "self.clear()" in code
    assert "# Render with: manim -pql <this file> AllScenes" in code


def test_step_details_and_code_steps(tmp_path) -> None:
    project = two_scenes()
    scene = project.scenes[0]
    step = scene.steps[0]
    step.section, step.subcaption, step.sound, step.sound_gain = "Anfang", "Ein Kreis", "ton.wav", -3.0
    pause = wait(2.0)
    pause.subcaption = "Pause"
    code_step = wait(1.5, step_id="code")
    code_step.kind, code_step.code = StepKind.CODE, "    self.play(Indicate(kreis))\n    self.wait(0.5)"
    scene.steps += [pause, code_step]
    code = generate_script(project, CodegenOptions(base_dir=tmp_path, scene_ids=("a",)))
    assert 'self.next_section("Anfang")' in code
    assert f'self.add_sound(r"{(tmp_path / "ton.wav").as_posix()}", gain=-3.0)' in code or f'self.add_sound("{(tmp_path / "ton.wav").as_posix()}", gain=-3.0)' in code
    assert 'subcaption="Ein Kreis",' in code and "subcaption_duration=1.0," in code
    assert 'self.add_subcaption("Pause", duration=2.0)' in code
    assert "# Step 3: own code\n        self.play(Indicate(kreis))\n        self.wait(0.5)" in code
    assert check_edit(scene, 2, ["c"], MOVE).reason == "code_step"
    code_step.code = "self.play(("
    assert "code_syntax" in {issue.code for issue in validate_scene(scene)}
    restored = loads_project(dumps_project(project))
    assert restored == project


def test_render_flags() -> None:
    job = RenderJob(Path("s.py"), "S", Path("m"), "out", format="mp4", transparent=True, save_sections=True)
    arguments = build_arguments(job)
    assert "--transparent" in arguments and "--save_sections" in arguments
    assert job.extension() == "mov"
    assert RenderJob(Path("s.py"), "S", Path("m"), "out", format="png", transparent=True).extension() == "png"
    assert RenderSettings().scenes == "current"
