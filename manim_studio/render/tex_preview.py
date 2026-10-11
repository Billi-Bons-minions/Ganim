"""Render LaTeX formulas to SVG for the stage preview (in a worker thread)."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from manim_studio.render.environment import run_quiet

#: Same document template Manim uses for ``MathTex`` (``align*``) and ``Tex`` (``center``).
TEX_TEMPLATE = r"""\documentclass[preview]{standalone}
\usepackage[english]{babel}
\usepackage{amsmath}
\usepackage{amssymb}
\begin{document}
\begin{%(env)s}
%(body)s
\end{%(env)s}
\end{document}
"""


def latex_key(latex: str, environment: str = "align*") -> str:
    """Return a stable cache key for a formula."""
    return hashlib.sha1(f"{environment}\n{latex}".encode("utf-8")).hexdigest()[:20]


def compile_latex_to_svg(latex: str, target: Path, timeout: float = 30.0, environment: str = "align*") -> str | None:
    """Compile a formula to ``target``; return an error message or ``None``."""
    latex_binary, dvisvgm = shutil.which("latex"), shutil.which("dvisvgm")
    if not latex_binary or not dvisvgm:
        return "latex/dvisvgm not found"
    with tempfile.TemporaryDirectory(prefix="manim_studio_tex_") as folder:
        work = Path(folder)
        (work / "formula.tex").write_text(TEX_TEMPLATE % {"env": environment, "body": latex}, encoding="utf-8")
        try:
            result = run_quiet([latex_binary, "-interaction=batchmode", "-halt-on-error", "formula.tex"], timeout, folder)
            if result.returncode != 0 or not (work / "formula.dvi").exists():
                log = (work / "formula.log").read_text(encoding="utf-8", errors="replace") if (work / "formula.log").exists() else ""
                errors = [line[2:] for line in log.splitlines() if line.startswith("! ")]
                return errors[0] if errors else "LaTeX error"
            result = run_quiet([dvisvgm, "formula.dvi", "-n", "-v", "0", "-o", "formula.svg"], timeout, folder)
        except (OSError, subprocess.SubprocessError) as error:
            return str(error)
        if result.returncode != 0 or not (work / "formula.svg").exists():
            return "dvisvgm error"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(work / "formula.svg", target)
    return None


class _Signals(QObject):
    done = Signal(str, str)


class _TexJob(QRunnable):
    def __init__(self, latex: str, target: Path, signals: _Signals, environment: str) -> None:
        super().__init__()
        self.latex = latex
        self.target = target
        self.signals = signals
        self.environment = environment

    def run(self) -> None:
        error = compile_latex_to_svg(self.latex, self.target, environment=self.environment)
        try:
            self.signals.done.emit(self.latex, error or "")
        except RuntimeError:
            pass


class TexPreviewCache(QObject):
    """Cache of formula SVGs; emits :attr:`ready` when a formula finished compiling."""

    ready = Signal(str)

    def __init__(self, cache_dir: Path, enabled: bool = True, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.cache_dir = cache_dir
        self.enabled = enabled
        self._pending: set[str] = set()
        self._errors: dict[str, str] = {}
        self._signals = _Signals()
        self._signals.done.connect(self._on_done)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(2)

    def svg_path(self, latex: str, environment: str = "align*") -> Path | None:
        """Return the SVG of a formula if available; otherwise start compiling it."""
        if not self.enabled or not latex.strip():
            return None
        target = self.cache_dir / f"{latex_key(latex, environment)}.svg"
        if target.exists():
            return target
        if latex not in self._pending and latex not in self._errors:
            self._pending.add(latex)
            self._pool.start(_TexJob(latex, target, self._signals, environment))
        return None

    def error(self, latex: str) -> str | None:
        """Return the compile error of a formula, if any."""
        return self._errors.get(latex)

    def _on_done(self, latex: str, error: str) -> None:
        self._pending.discard(latex)
        if error:
            self._errors[latex] = error
        self.ready.emit(latex)
