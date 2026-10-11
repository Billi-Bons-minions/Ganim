"""Interpret Manim's console output: progress and error messages."""

from __future__ import annotations

import re
from dataclasses import dataclass

_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_PROGRESS = re.compile(r"Animation (\d+):.*?(\d{1,3})%\|")
_PARTIAL_DONE = re.compile(r"Animation (\d+) : Partial movie file written")
_EXCEPTION = re.compile(r"^([A-Za-z_][\w.]*(?:Error|Exception|Exit)): (.*)$")
_LATEX_LINE = re.compile(r"^! (.+)$")


@dataclass(frozen=True)
class Progress:
    """Progress of the current animation."""

    animation: int
    percent: float


@dataclass(frozen=True)
class ErrorSummary:
    """A short, translatable description of why rendering failed."""

    code: str
    detail: str = ""


def strip_ansi(text: str) -> str:
    """Remove terminal color codes."""
    return _ANSI.sub("", text)


def split_output(buffer: str) -> tuple[list[str], str]:
    """Split a buffer at ``\\r``/``\\n``; return complete lines and the remainder."""
    parts = re.split(r"\r\n|\r|\n", buffer)
    return parts[:-1], parts[-1]


def parse_progress(line: str) -> Progress | None:
    """Read the progress-bar state from one line of output."""
    match = _PROGRESS.search(line)
    if match:
        return Progress(int(match.group(1)), float(match.group(2)))
    done = _PARTIAL_DONE.search(line)
    if done:
        return Progress(int(done.group(1)), 100.0)
    return None


def is_progress_line(line: str) -> bool:
    """Return ``True`` for transient progress-bar lines (not worth logging)."""
    return bool(_PROGRESS.search(line)) and "Partial movie" not in line


def overall_fraction(progress: Progress, total_animations: int) -> float:
    """Combine animation index and percentage into a value between 0 and 1."""
    total = max(1, total_animations)
    fraction = (progress.animation + progress.percent / 100.0) / total
    return max(0.0, min(1.0, fraction))


def _clean(line: str) -> str:
    return strip_ansi(line).strip().strip("│").strip()


def _last_exception(lines: list[str]) -> tuple[str, str] | None:
    for index in range(len(lines) - 1, -1, -1):
        match = _EXCEPTION.match(lines[index])
        if match:
            continuation = " ".join(lines[index + 1 : index + 3]).strip()
            message = match.group(2).strip()
            if continuation and not _EXCEPTION.match(continuation):
                message = f"{message} {continuation}".strip()
            return match.group(1), message
    return None


def summarize_error(log: str) -> ErrorSummary:
    """Derive a user-friendly reason from a failed Manim run."""
    lines = [_clean(line) for line in log.splitlines()]
    lines = [line for line in lines if line]
    text = "\n".join(lines)
    if "No module named manim" in text or "No module named 'manim'" in text:
        return ErrorSummary("manim_missing")
    if "Choose number corresponding to desired scene" in text or "is not in the script" in text:
        return ErrorSummary("scene_not_found")
    latex_lines = [match.group(1) for line in lines if (match := _LATEX_LINE.match(line))]
    if latex_lines or "LaTeX compilation error" in text or "latex error converting" in text.lower():
        return ErrorSummary("latex_error", latex_lines[0] if latex_lines else "")
    exception = _last_exception(lines)
    if exception is not None:
        name, message = exception
        if name in ("FileNotFoundError", "OSError") and ("could not find" in message or "No such file" in message):
            return ErrorSummary("file_not_found", message)
        if name == "MemoryError":
            return ErrorSummary("out_of_memory")
        if name == "SyntaxError":
            return ErrorSummary("syntax_error", message)
        return ErrorSummary("python_error", f"{name}: {message}")
    tail = " ".join(lines[-3:])
    return ErrorSummary("unknown", tail)
