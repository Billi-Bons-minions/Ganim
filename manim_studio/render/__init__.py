"""Running Manim: command lines, progress parsing, environment checks."""

from manim_studio.render.command import (
    QUALITY_PRESETS,
    RenderJob,
    build_arguments,
    find_output,
)
from manim_studio.render.output_parser import ErrorSummary, summarize_error

__all__ = ["QUALITY_PRESETS", "ErrorSummary", "RenderJob", "build_arguments", "find_output", "summarize_error"]
