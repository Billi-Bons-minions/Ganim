"""Check whether Manim, FFmpeg and LaTeX are available."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass

_PROBE = (
    "import json\n"
    "info = {}\n"
    "try:\n"
    "    import manim\n"
    "    info['manim'] = manim.__version__\n"
    "except Exception as error:\n"
    "    info['manim_error'] = repr(error)\n"
    "try:\n"
    "    import av\n"
    "    info['av'] = av.__version__\n"
    "except Exception:\n"
    "    pass\n"
    "print('MANIM_STUDIO_PROBE' + json.dumps(info))\n"
)
_PROBE_MARKER = "MANIM_STUDIO_PROBE"


@dataclass(frozen=True)
class ToolStatus:
    """Availability of one external tool."""

    name: str
    found: bool
    version: str = ""
    detail: str = ""


@dataclass(frozen=True)
class EnvironmentReport:
    """Result of the start-up check."""

    manim: ToolStatus
    ffmpeg: ToolStatus
    latex: ToolStatus

    @property
    def tools(self) -> tuple[ToolStatus, ToolStatus, ToolStatus]:
        """Return all checked tools."""
        return self.manim, self.ffmpeg, self.latex

    @property
    def all_found(self) -> bool:
        """Return ``True`` if nothing is missing."""
        return all(tool.found for tool in self.tools)

    def missing_names(self) -> list[str]:
        """Return the names of the missing tools."""
        return [tool.name for tool in self.tools if not tool.found]


def _hidden_window_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def run_quiet(command: list[str], timeout: float, cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run a command without console window and capture its output."""
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        creationflags=_hidden_window_flags(),
    )


def probe_python(python: str, timeout: float = 120.0) -> dict[str, str]:
    """Ask the interpreter which Manim and PyAV versions it can import."""
    try:
        result = run_quiet([python, "-c", _PROBE], timeout)
    except (OSError, subprocess.SubprocessError) as error:
        return {"manim_error": str(error)}
    for line in reversed(result.stdout.splitlines()):
        if line.startswith(_PROBE_MARKER):
            try:
                return dict(json.loads(line[len(_PROBE_MARKER):]))
            except json.JSONDecodeError:
                break
    return {"manim_error": (result.stderr or result.stdout).strip()[-500:]}


def _first_line_version(command: list[str]) -> str:
    try:
        result = run_quiet(command, 15.0)
    except (OSError, subprocess.SubprocessError):
        return ""
    lines = (result.stdout or result.stderr).strip().splitlines()
    return lines[0].strip() if lines else ""


def check_latex() -> ToolStatus:
    """Return whether ``latex`` and ``dvisvgm`` are on the PATH."""
    latex = shutil.which("latex")
    dvisvgm = shutil.which("dvisvgm")
    if latex and dvisvgm:
        return ToolStatus("latex", True, _first_line_version([latex, "--version"]))
    missing = [name for name, path in (("latex", latex), ("dvisvgm", dvisvgm)) if not path]
    return ToolStatus("latex", False, detail=", ".join(missing))


def check_environment(python: str | None = None) -> EnvironmentReport:
    """Check all external dependencies (blocking; call from a worker thread)."""
    info = probe_python(python or sys.executable)
    manim_found = "manim" in info
    manim = ToolStatus("manim", manim_found, info.get("manim", ""), info.get("manim_error", ""))
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        ffmpeg = ToolStatus("ffmpeg", True, _first_line_version([ffmpeg_path, "-version"]))
    elif "av" in info:
        ffmpeg = ToolStatus("ffmpeg", True, f"PyAV {info['av']}", "pyav")
    else:
        ffmpeg = ToolStatus("ffmpeg", False)
    return EnvironmentReport(manim, ffmpeg, check_latex())
