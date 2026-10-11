"""Build Manim command lines and locate the rendered files."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

#: Manim quality flags with resolution and frame rate.
QUALITY_PRESETS: dict[str, tuple[int, int, int]] = {
    "l": (854, 480, 15),
    "m": (1280, 720, 30),
    "h": (1920, 1080, 60),
    "p": (2560, 1440, 60),
    "k": (3840, 2160, 60),
}
CUSTOM_QUALITY = "custom"
OUTPUT_FORMATS = ("mp4", "gif", "png")


@dataclass(frozen=True)
class RenderJob:
    """Everything needed to run one Manim render."""

    script_path: Path
    scene_class: str
    media_dir: Path
    output_name: str
    format: str = "mp4"
    quality: str = "l"
    width: int = 1920
    height: int = 1080
    fps: int = 60
    total_animations: int = 1
    from_animation: int | None = None


def build_arguments(job: RenderJob) -> list[str]:
    """Return the arguments passed to the Python interpreter."""
    arguments = [
        "-m",
        "manim",
        "render",
        "--progress_bar",
        "display",
        "--media_dir",
        str(job.media_dir),
        "-o",
        job.output_name,
        "--format",
        job.format if job.format in OUTPUT_FORMATS else "mp4",
    ]
    if job.quality in QUALITY_PRESETS:
        arguments += ["-q", job.quality]
    else:
        arguments += ["-r", f"{int(job.width)},{int(job.height)}", "--fps", str(int(job.fps))]
    if job.from_animation:
        arguments += ["-n", str(int(job.from_animation))]
    return arguments + [str(job.script_path), job.scene_class]


def render_environment(base: dict[str, str] | None = None) -> dict[str, str]:
    """Return environment variables that keep Manim's output machine-readable."""
    environment = dict(os.environ if base is None else base)
    environment.update(
        {
            "COLUMNS": "200",
            "NO_COLOR": "1",
            "TERM": "dumb",
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    return environment


def find_output(media_dir: Path, output_name: str, file_format: str) -> Path | None:
    """Return the newest rendered file named ``output_name`` (ignoring partial files)."""
    suffix = "png" if file_format == "png" else file_format
    candidates = [
        path
        for path in Path(media_dir).rglob(f"{output_name}.{suffix}")
        if "partial_movie_files" not in path.parts
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)
