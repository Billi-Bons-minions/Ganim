"""Tests for command building, output parsing and the QProcess runner."""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import pytest

from manim_studio.codegen import generate_script
from manim_studio.render.command import RenderJob, build_arguments, find_output
from manim_studio.render.output_parser import (
    Progress,
    is_progress_line,
    overall_fraction,
    parse_progress,
    split_output,
    summarize_error,
)
from tests.helpers import acceptance_scene, make_project


def job(tmp_path: Path, **values) -> RenderJob:
    defaults = dict(script_path=tmp_path / "s.py", scene_class="Szene1", media_dir=tmp_path / "media", output_name="out")
    defaults.update(values)
    return RenderJob(**defaults)


def test_preset_quality_arguments(tmp_path) -> None:
    arguments = build_arguments(job(tmp_path, quality="l", format="gif"))
    assert arguments[:3] == ["-m", "manim", "render"]
    assert arguments[arguments.index("-q") + 1] == "l"
    assert arguments[arguments.index("--format") + 1] == "gif"
    assert arguments[-2:] == [str(tmp_path / "s.py"), "Szene1"]


def test_custom_resolution_arguments(tmp_path) -> None:
    arguments = build_arguments(job(tmp_path, quality="custom", width=1000, height=1000, fps=24))
    assert "-q" not in arguments
    assert arguments[arguments.index("-r") + 1] == "1000,1000"
    assert arguments[arguments.index("--fps") + 1] == "24"


def test_find_output_ignores_partial_files(tmp_path) -> None:
    partial = tmp_path / "videos" / "s" / "480p15" / "partial_movie_files" / "Szene1" / "out.mp4"
    final = tmp_path / "videos" / "s" / "480p15" / "out.mp4"
    partial.parent.mkdir(parents=True)
    partial.write_bytes(b"x")
    assert find_output(tmp_path, "out", "mp4") is None
    final.write_bytes(b"x")
    assert find_output(tmp_path, "out", "mp4") == final


def test_split_output_handles_carriage_returns() -> None:
    lines, rest = split_output("a\rb\nc\r\nd")
    assert lines == ["a", "b", "c"] and rest == "d"


def test_progress_parsing() -> None:
    line = "Animation 2: Create(Circle):  40%|████      | 6/15 [00:01<00:01, 5.0it/s]"
    assert parse_progress(line) == Progress(2, 40.0)
    assert is_progress_line(line)
    done = "INFO     Animation 2 : Partial movie file written in"
    assert parse_progress(done) == Progress(2, 100.0)
    assert not is_progress_line(done)
    assert overall_fraction(Progress(2, 50.0), 5) == pytest.approx(0.5)
    assert parse_progress("Combining to Movie file.") is None


@pytest.mark.parametrize(
    ("log", "code"),
    [
        ("Traceback\nModuleNotFoundError: No module named 'manim'", "manim_missing"),
        ("Choose number corresponding to desired scene/arguments.", "scene_not_found"),
        ("! Undefined control sequence.\nl.7 \\foo", "latex_error"),
        ("│ ❱ 83 │ raise OSError(error) │\nOSError: From: /x, could not find /nope.png at either", "file_not_found"),
        ("│ ❱ 11 │ raise ValueError('kaputt') │\nValueError: kaputt", "python_error"),
        ("something strange happened", "unknown"),
    ],
)
def test_error_summary(log: str, code: str) -> None:
    assert summarize_error(log).code == code


def test_latex_error_detail() -> None:
    assert summarize_error("! Missing } inserted.").detail == "Missing } inserted."


def test_latex_error_names_the_formula() -> None:
    log = (
        "[10/12/26 06:04:24] ERROR    LaTeX compilation error: Undefined control sequence.        tex_file_writing.py:320\n"
        "                    ERROR    Context of error:                                           tex_file_writing.py:354\n"
        "                             -> \\special{dvisvgm:raw <g id='unique000'>}\\gibtsnicht x\\special{dvisvgm:raw </g>}\n"
        "                             \\end{align*}\n"
        "ValueError: latex error converting to dvi. See log output above or the log file: m/Tex/d6.log\n"
    )
    summary = summarize_error(log)
    assert summary.code == "latex_error"
    assert summary.detail == "Undefined control sequence. → \\gibtsnicht x"


@pytest.mark.manim
@pytest.mark.skipif(importlib.util.find_spec("manim") is None, reason="Manim is not installed")
def test_runner_renders_and_reports_progress(tmp_path, qapp) -> None:
    from manim_studio.render.runner import ManimRunner

    app = qapp
    script = tmp_path / "szene.py"
    script.write_text(generate_script(make_project(acceptance_scene())), encoding="utf-8")
    render_job = job(tmp_path, script_path=script, total_animations=3)
    runner = ManimRunner()
    results, progress = [], []
    runner.finished.connect(results.append)
    runner.progressChanged.connect(progress.append)
    runner.start(render_job, sys.executable)
    deadline = time.monotonic() + 300
    while not results and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    assert results, "render did not finish"
    result = results[0]
    assert result.success, result.log
    assert result.output is not None and result.output.name == "out.mp4"
    assert progress and progress[-1] == 1.0


@pytest.mark.manim
@pytest.mark.skipif(importlib.util.find_spec("manim") is None, reason="Manim is not installed")
def test_runner_reports_missing_scene_without_hanging(tmp_path, qapp) -> None:
    from manim_studio.render.runner import ManimRunner

    app = qapp
    script = tmp_path / "szene.py"
    second = acceptance_scene()
    second.id = "scene2"
    script.write_text(generate_script(make_project(acceptance_scene(), second)), encoding="utf-8")
    runner = ManimRunner()
    results = []
    runner.finished.connect(results.append)
    runner.start(job(tmp_path, script_path=script, scene_class="GibtEsNicht"), sys.executable)
    deadline = time.monotonic() + 120
    while not results and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    assert results and not results[0].success
    assert results[0].error.code == "scene_not_found"


def _run_until_finished(runner, app, seconds: float) -> list:
    results = []
    runner.finished.connect(results.append)
    deadline = time.monotonic() + seconds
    while not results and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    return results


@pytest.mark.manim
@pytest.mark.skipif(importlib.util.find_spec("manim") is None, reason="Manim is not installed")
def test_runner_can_be_cancelled(tmp_path, qapp) -> None:
    from PySide6.QtCore import QTimer

    from manim_studio.render.runner import ManimRunner
    from tests.helpers import make_animation, play

    app = qapp
    scene = acceptance_scene()
    long_create = make_animation(acceptance_scene().steps[0].animations[0].kind, "c1", "slow")
    long_create.run_time = 60.0
    scene.steps.insert(0, play(long_create))
    script = tmp_path / "szene.py"
    script.write_text(generate_script(make_project(scene)), encoding="utf-8")
    runner = ManimRunner()
    runner.progressChanged.connect(lambda _value: QTimer.singleShot(0, runner.cancel))
    runner.start(job(tmp_path, script_path=script, quality="h", total_animations=4), sys.executable)
    results = _run_until_finished(runner, app, 120)
    assert results and results[0].cancelled and not results[0].success


@pytest.mark.manim
@pytest.mark.skipif(importlib.util.find_spec("manim") is None, reason="Manim is not installed")
@pytest.mark.parametrize("file_format", ["gif", "png"])
def test_runner_exports_gif_and_png(tmp_path, qapp, file_format: str) -> None:
    from manim_studio.render.runner import ManimRunner

    app = qapp
    script = tmp_path / "szene.py"
    script.write_text(generate_script(make_project(acceptance_scene())), encoding="utf-8")
    runner = ManimRunner()
    runner.start(job(tmp_path, script_path=script, format=file_format, quality="custom", width=320, height=180, fps=10), sys.executable)
    results = _run_until_finished(runner, app, 300)
    assert results and results[0].success, results[0].log if results else "timeout"
    assert results[0].output.suffix == f".{file_format}"


@pytest.mark.manim
@pytest.mark.skipif(importlib.util.find_spec("manim") is None, reason="Manim is not installed")
def test_runner_renders_from_a_later_step(tmp_path, qapp) -> None:
    from manim_studio.render.runner import ManimRunner

    script = tmp_path / "szene.py"
    script.write_text(generate_script(make_project(acceptance_scene())), encoding="utf-8")
    runner = ManimRunner()
    progress = []
    runner.progressChanged.connect(progress.append)
    runner.start(job(tmp_path, script_path=script, from_animation=2, total_animations=1), sys.executable)
    results = _run_until_finished(runner, qapp, 300)
    assert results and results[0].success, results[0].log if results else "timeout"
    assert "-n" in results[0].log_lines[0]
    assert progress and max(progress) <= 1.0
