"""Deterministic conversion of the project model into a Manim script."""

from manim_studio.codegen.errors import CodegenError
from manim_studio.codegen.generator import CodegenOptions, generate_script
from manim_studio.codegen.naming import class_names, variable_names

__all__ = ["CodegenError", "CodegenOptions", "class_names", "generate_script", "variable_names"]
