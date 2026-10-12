"""Build a self-contained Manim Studio folder with PyInstaller (experimental).

The bundle contains Python, Qt and Manim. LaTeX is not included; formulas need a
LaTeX installation on the computer as before.

    pip install . pyinstaller
    python packaging/build_bundle.py            # -> dist/manim-studio/ (macOS: dist/manim-studio.app)
    python packaging/build_bundle.py --smoke    # build, then render a small scene with the bundle
"""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "manim-studio"

#: Packages whose data files or plugins PyInstaller does not find on its own.
COLLECT_ALL = ["manim", "manimpango", "av", "cloup", "mapbox_earcut", "srt", "isosurfaces"]

SMOKE_SCENE = '''from manim import *


class Smoke(Scene):
    def construct(self):
        circle = Circle(color=BLUE)
        self.play(Create(circle), run_time=0.5)
        self.play(Transform(circle, Square(color=RED)), run_time=0.5)
        self.play(Write(Text("Manim Studio")), run_time=0.5)
'''


def executable() -> Path:
    """The program inside the bundle that answers ``-m manim`` and ``-c``."""
    if platform.system() == "Darwin":
        return ROOT / "dist" / f"{NAME}.app" / "Contents" / "MacOS" / NAME
    suffix = ".exe" if platform.system() == "Windows" else ""
    return ROOT / "dist" / NAME / f"{NAME}{suffix}"


def build() -> None:
    import PyInstaller.__main__

    arguments = [
        str(ROOT / "packaging" / "launcher.py"),
        "--name",
        NAME,
        "--noconfirm",
        "--clean",
        "--windowed",
        "--distpath",
        str(ROOT / "dist"),
        "--workpath",
        str(ROOT / "build"),
        "--specpath",
        str(ROOT / "build"),
        "--collect-submodules",
        "manim_studio",
        "--hidden-import",
        "networkx",
    ]
    for package in COLLECT_ALL:
        arguments += ["--collect-all", package]
    PyInstaller.__main__.run(arguments)


def smoke() -> None:
    """Render a tiny scene with the bundled Manim, like the app does."""
    program = executable()
    probe = subprocess.run([str(program), "-c", "import manim; print('manim', manim.__version__)"], capture_output=True, text=True, timeout=300)
    print(probe.stdout.strip(), probe.stderr.strip()[-2000:])
    if probe.returncode != 0 or "manim" not in probe.stdout:
        raise SystemExit("the bundle cannot import Manim")
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        (work / "smoke.py").write_text(SMOKE_SCENE, encoding="utf-8")
        result = subprocess.run(
            [str(program), "-m", "manim", "render", "-ql", "--media_dir", str(work / "media"), str(work / "smoke.py"), "Smoke"],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=work,
        )
        print(result.stdout[-3000:], result.stderr[-3000:])
        videos = [path for path in (work / "media").rglob("Smoke.mp4") if "partial_movie_files" not in path.parts]
        if result.returncode != 0 or not videos:
            raise SystemExit("the bundle could not render the smoke scene")
        print("smoke test ok:", videos[0].stat().st_size, "bytes")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--smoke", action="store_true", help="render a small scene with the bundle afterwards")
    parser.add_argument("--smoke-only", action="store_true", help="only run the smoke test on an existing bundle")
    args = parser.parse_args()
    if not args.smoke_only:
        build()
    if args.smoke or args.smoke_only:
        smoke()
    print("bundle:", executable(), file=sys.stderr)


if __name__ == "__main__":
    main()
