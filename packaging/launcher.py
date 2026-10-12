"""Entry point of the bundled app (PyInstaller).

Manim Studio renders by starting ``<python> -m manim render …`` and checks the
system with ``<python> -c …``. In a bundled app there is no separate Python, so
the app's own executable answers these calls: it runs Manim (which is bundled)
or the given code, and otherwise starts the user interface.
"""

from __future__ import annotations

import multiprocessing
import sys


def main() -> int:
    arguments = sys.argv[1:]
    if arguments[:2] == ["-m", "manim"]:
        from manim.__main__ import main as manim_main

        sys.argv = ["manim", *arguments[2:]]
        try:
            manim_main()
        except SystemExit as stop:
            return int(stop.code or 0) if not isinstance(stop.code, str) else 1
        return 0
    if arguments[:1] == ["-c"] and len(arguments) > 1:
        sys.argv = ["-c", *arguments[2:]]
        exec(compile(arguments[1], "<string>", "exec"), {"__name__": "__main__"})  # noqa: S102 - the app's own probe code
        return 0
    from manim_studio.app import main as studio_main

    return studio_main()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
