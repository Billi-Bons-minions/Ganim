"""All built-in examples must produce valid scripts (and render with Manim)."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys

import pytest

from manim_studio.codegen import class_names, generate_script
from manim_studio.examples import EXAMPLES
from manim_studio.model.validation import has_errors, validate_scene


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda example: example.key)
def test_example_is_valid(example) -> None:
    project = example.build()
    for scene in project.scenes:
        assert not has_errors(validate_scene(scene, latex_available=True))
    compile(generate_script(project), "example.py", "exec")


@pytest.mark.manim
@pytest.mark.skipif(importlib.util.find_spec("manim") is None, reason="Manim is not installed")
@pytest.mark.parametrize("example", EXAMPLES, ids=lambda example: example.key)
def test_example_renders(example, tmp_path) -> None:
    if example.needs_latex and (shutil.which("latex") is None or shutil.which("dvisvgm") is None):
        pytest.skip("LaTeX is not installed")
    project = example.build()
    script = tmp_path / "example.py"
    script.write_text(generate_script(project), encoding="utf-8")
    scene_class = class_names(project)[project.scenes[0].id]
    result = subprocess.run(
        [sys.executable, "-m", "manim", "render", "-ql", "--dry_run", "--media_dir", str(tmp_path / "media"), str(script), scene_class],
        capture_output=True, text=True, timeout=300, cwd=tmp_path, env=dict(os.environ, COLUMNS="200"),
    )
    assert result.returncode == 0, result.stdout + result.stderr
