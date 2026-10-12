"""Random editing sessions through the real controller, then Manim checks.

Each session adds objects, animations and steps, changes parameters, moves,
groups, copies, deletes, undoes and redoes - all through ``MainWindow.controller``
like a user would. Afterwards it checks that

* no exception escaped (Qt slots included),
* saving and loading gives the identical project,
* every scene without validation errors generates code without errors,
* the stage can compute every moment of every scene,
* Manim accepts the generated script (``manim render --dry_run -a``).

Usage (offscreen, from the repository root)::

    QT_QPA_PLATFORM=offscreen python tools/fuzz_sessions.py --sessions 50 --seed 1

Failing sessions are written to ``fuzz_failures/`` (project file, script, log).
"""

from __future__ import annotations

import argparse
import os
import random
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QEvent, QSettings, QThreadPool, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from manim_studio.codegen import generate_script  # noqa: E402
from manim_studio.codegen.errors import CodegenError  # noqa: E402
from manim_studio.i18n import set_language  # noqa: E402
from manim_studio.model import operations as ops  # noqa: E402
from manim_studio.model.animation_builder import allowed_for_objects, reference_candidates  # noqa: E402
from manim_studio.model.attach import set_attach_mode  # noqa: E402
from manim_studio.model.playback import state_at_time, total_duration  # noqa: E402
from manim_studio.model.schema import ParamType, animation_params, kind_info  # noqa: E402
from manim_studio.model.serialization import dumps_project, loads_project  # noqa: E402
from manim_studio.model.types import REFERENCE_PARAMS, AnimationKind, ObjectKind, StepKind  # noqa: E402
from manim_studio.model.validation import has_errors, validate_scene  # noqa: E402
from manim_studio.templates import BUILTIN_TEMPLATES  # noqa: E402

#: Objects that need a file or a dialog are left out.
SKIPPED_KINDS = {ObjectKind.IMAGE}
OBJECT_KINDS = [kind for kind in ObjectKind if kind not in SKIPPED_KINDS]
ANIMATION_KINDS = list(AnimationKind)
COLORS = ["#FC6255", "#83C167", "#58C4DD", "#FFFF00", "#FFFFFF", "#000000", "#9A72AC"]
STRINGS = ["A", "Hallo Welt", "", "  ", 'Zitat "x" \\ y', "ÄÖÜ ß €", "A, B, C", "A-B\nB-C\nC-A", "A, A-B, B", "1\n2\n3", "x", "{}", "%s {0}"]
LATEX = [r"x^2", r"\frac{a}{b}", r"e^{i\pi} + 1 = 0", r"a^2 + b^2 = c^2", r"\sum_{k=1}^n k"]
EXPRESSIONS = ["x", "x^2", "sin(x)", "2x + 1", "sqrt(x)", "1/x", "exp(-x^2)", "a*x", "tan(x)", "abs(x) - 1", "x^2 + y^2 - 4", "cos(t)"]


class Fuzzer:
    def __init__(self, seed: int, window) -> None:
        self.random = random.Random(seed)
        self.window = window
        self.controller = window.controller
        self.log: list[str] = []

    # --- helpers --------------------------------------------------------------------

    def scene(self):
        return self.controller.scene()

    def objects(self):
        return list(self.scene().objects)

    def pick_objects(self, count: int = 1) -> list[str]:
        objects = self.objects()
        if not objects:
            return []
        return [obj.id for obj in self.random.sample(objects, min(count, len(objects)))]

    def value_for(self, spec, scene):
        r = self.random
        if spec.type == ParamType.FLOAT:
            low = spec.minimum if spec.minimum is not None else -10.0
            high = spec.maximum if spec.maximum is not None else 10.0
            low, high = max(low, -50.0), min(high, 50.0)
            return round(r.uniform(low, high), 3)
        if spec.type == ParamType.INT:
            low = int(spec.minimum) if spec.minimum is not None else 0
            high = int(spec.maximum) if spec.maximum is not None else 20
            return r.randint(low, min(high, low + 40))
        if spec.type == ParamType.BOOL:
            return r.random() < 0.5
        if spec.type == ParamType.CHOICE and spec.choices:
            return r.choice(spec.choices)
        if spec.type == ParamType.COLOR:
            return r.choice(COLORS)
        if spec.type in (ParamType.STRING, ParamType.TEXT):
            return r.choice(STRINGS)
        if spec.type == ParamType.LATEX:
            return r.choice(LATEX)
        if spec.type == ParamType.EXPRESSION:
            return r.choice(EXPRESSIONS)
        if spec.type == ParamType.OBJECT_REF:
            candidates = [obj.id for obj in scene.objects if not spec.ref_kinds or obj.kind in spec.ref_kinds]
            return r.choice(candidates) if candidates else None
        return None

    # --- operations -----------------------------------------------------------------

    def op_add_object(self) -> None:
        kind = self.random.choice(OBJECT_KINDS)
        x, y = round(self.random.uniform(-6, 6), 2), round(self.random.uniform(-3.5, 3.5), 2)
        self.log.append(f"add_object {kind.value} {x} {y}")
        self.controller.add_object(kind, x, y)

    def op_select(self) -> None:
        ids = self.pick_objects(self.random.choice((1, 1, 2, 3)))
        self.log.append(f"select {ids}")
        self.window.editor.select_objects(ids)

    def op_animate(self) -> None:
        if not self.window.editor.selected_objects:
            self.op_select()
        kind = self.random.choice(ANIMATION_KINDS)
        ids = list(self.window.editor.selected_objects)
        if not ids or not allowed_for_objects(self.scene(), kind, ids):
            return
        same_step = self.random.random() < 0.3
        if kind in REFERENCE_PARAMS:
            candidates = reference_candidates(self.scene(), kind, ids[0])
            if not candidates:
                return
            other = self.random.choice(candidates).id
            self.log.append(f"reference_animation {kind.value} {ids[0]} -> {other} same={same_step}")
            self.controller.add_reference_animation(kind, ids[0], other, same_step, inspect=False)
        else:
            self.log.append(f"animate {kind.value} {ids} same={same_step}")
            self.controller.add_animation(kind, same_step, inspect=False)

    def op_object_param(self) -> None:
        ids = self.pick_objects()
        if not ids:
            return
        obj = self.scene().object_by_id(ids[0])
        specs = [spec for spec in kind_info(obj.kind).params if spec.type not in (ParamType.POINTS, ParamType.TABLE, ParamType.DATA, ParamType.BARS, ParamType.PIECES, ParamType.WORD_COLORS, ParamType.FILE, ParamType.FONT)]
        if not specs:
            return
        spec = self.random.choice(specs)
        value = self.value_for(spec, self.scene())
        if value is None and spec.type != ParamType.OBJECT_REF:
            return
        self.log.append(f"object_param {obj.kind.value} {spec.key}={value!r}")
        self.window.document.edit_scene("fuzz", self.scene().id, lambda s: ops.set_object_param(s, obj.id, spec.key, value))

    def op_animation_param(self) -> None:
        animations = [anim for step in self.scene().steps for anim in step.animations]
        if not animations:
            return
        anim = self.random.choice(animations)
        specs = [spec for spec in animation_params(anim.kind) if spec.type not in (ParamType.POINTS, ParamType.TABLE)]
        if specs and self.random.random() < 0.8:
            spec = self.random.choice(specs)
            value = self.value_for(spec, self.scene())
            self.log.append(f"animation_param {anim.kind.value} {spec.key}={value!r}")
            self.window.document.edit_scene("fuzz", self.scene().id, lambda s: ops.set_animation_param(s, anim.id, spec.key, value))
        else:
            delay, run_time = round(self.random.uniform(0, 1.5), 2), round(self.random.uniform(0.2, 3), 2)
            self.log.append(f"timing {anim.kind.value} delay={delay} run_time={run_time}")
            self.controller.set_animation_timing(anim.id, delay=delay, run_time=run_time)

    def op_transform_stage(self) -> None:
        ids = self.pick_objects()
        if not ids:
            return
        action = self.random.choice(("move", "scale", "rotate"))
        allowed, _reason = self.controller.edit_policy(action, ids)
        if not allowed:
            return
        self.log.append(f"stage {action} {ids}")
        if action == "move":
            self.controller.move_objects(ids, round(self.random.uniform(-2, 2), 2), round(self.random.uniform(-2, 2), 2))
        elif action == "scale":
            self.controller.scale_object(ids[0], round(self.random.uniform(0.5, 1.8), 2))
        else:
            self.controller.rotate_object(ids[0], round(self.random.uniform(-90, 90), 1))

    def op_attach(self) -> None:
        ids = self.pick_objects()
        if not ids:
            return
        mode = self.random.choice(("none", "follow", "follow", "formula"))
        self.log.append(f"attach {ids[0]} {mode}")
        self.window.document.edit_scene("fuzz", self.scene().id, lambda s: set_attach_mode(s, ids[0], mode))
        obj = self.scene().object_by_id(ids[0])
        if mode == "formula" and obj is not None and self.random.random() < 0.7:
            symbols = [str(o.params.get("symbol")) for o in self.objects() if o.kind == ObjectKind.PARAMETER]
            term = self.random.choice(symbols) if symbols else "1"
            formulas = (f"2 cos({term})", f"sin({term}) - 1") if self.random.random() < 0.8 else ("x", "1/0")
            self.log.append(f"attach formula {formulas}")
            for key, value in zip(("attach_x", "attach_y"), formulas):
                try:
                    self.window.document.edit_scene("fuzz", self.scene().id, lambda s, key=key, value=value: ops.set_object_param(s, ids[0], key, value))
                except ops.ModelError:
                    pass

    def op_cursor(self) -> None:
        index = self.random.randint(-1, len(self.scene().steps) - 1)
        self.log.append(f"cursor {index}")
        self.window.editor.set_cursor(index)

    def op_step(self) -> None:
        choice = self.random.choice(("add", "wait", "duplicate", "delete", "mode"))
        self.log.append(f"step {choice}")
        if choice == "add":
            self.controller.add_step(StepKind.PLAY)
        elif choice == "wait":
            self.controller.add_step(StepKind.WAIT)
        elif choice == "duplicate":
            self.controller.duplicate_step()
        elif choice == "delete":
            self.controller.delete_step()
        else:
            step_id = self.controller.current_step_id()
            if step_id:
                self.controller.set_step_mode(step_id, self.random.choice(("together", "lagged", "sequence")), round(self.random.uniform(0.1, 0.9), 2))

    def op_edit(self) -> None:
        choice = self.random.choice(("delete", "duplicate", "copy_paste", "group", "ungroup", "layer", "hide", "fade_out_all"))
        if not self.window.editor.selected_objects:
            self.op_select()
        self.log.append(f"edit {choice} {list(self.window.editor.selected_objects)}")
        if choice == "delete":
            self.controller.delete_objects()
        elif choice == "duplicate":
            self.controller.duplicate_objects()
        elif choice == "copy_paste":
            self.controller.copy_objects()
            self.controller.paste_objects()
        elif choice == "group" and self.controller.can_group():
            self.controller.group_selection()
        elif choice == "ungroup" and self.controller.can_ungroup():
            self.controller.ungroup_selection()
        elif choice == "layer":
            self.controller.change_layer(self.random.choice((-1, 1)))
        elif choice == "hide":
            self.controller.toggle_hidden()
        elif choice == "fade_out_all":
            self.controller.fade_out_all()

    def op_undo(self) -> None:
        stack = self.window.document.undo_stack
        if self.random.random() < 0.6:
            self.log.append("undo")
            stack.undo()
        else:
            self.log.append("redo")
            stack.redo()

    def op_scene(self) -> None:
        choice = self.random.choice(("template", "add", "duplicate", "switch"))
        self.log.append(f"scene {choice}")
        if choice == "template":
            self.controller.add_scene_from_template(self.random.choice(BUILTIN_TEMPLATES).build())
        elif choice == "add":
            self.controller.add_scene()
        elif choice == "duplicate":
            self.controller.duplicate_scene()
        else:
            scenes = self.window.document.project.scenes
            self.window.editor.set_scene(self.random.choice(scenes).id)

    WEIGHTS = {
        "op_add_object": 14,
        "op_select": 8,
        "op_animate": 16,
        "op_object_param": 12,
        "op_animation_param": 8,
        "op_transform_stage": 6,
        "op_cursor": 5,
        "op_step": 5,
        "op_edit": 7,
        "op_undo": 5,
        "op_scene": 2,
        "op_attach": 4,
    }

    def run(self, steps: int, app) -> None:
        names = list(self.WEIGHTS)
        weights = [self.WEIGHTS[name] for name in names]
        for _ in range(steps):
            getattr(self, self.random.choices(names, weights)[0])()
            app.processEvents()


def make_window(app, folder: Path):
    from manim_studio.ui.context import AppContext
    from manim_studio.ui.main_window import MainWindow
    from manim_studio.ui.settings import AppSettings
    from manim_studio.ui.theme import apply_theme

    settings = AppSettings(QSettings(str(folder / "settings.ini"), QSettings.Format.IniFormat))
    settings.hidden_environment_warning = "manim,ffmpeg,latex"
    apply_theme(app, "dark", 1.0, folder / "style")
    context = AppContext(settings, data_folder=folder / "data")
    window = MainWindow(context, lambda: None)
    context.set_window(window)
    window.show()
    app.processEvents()
    return window


def close_window(app, window) -> None:
    window.document.undo_stack.setClean()
    window.close()
    QThreadPool.globalInstance().waitForDone(60_000)
    window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    app.processEvents()


def latex_rejections(source: str, environment: str) -> str | None:
    """The error of a formula LaTeX rejects (compiled at once; the stage does it in the background)."""
    from manim_studio.render.tex_preview import LatexFailure, compile_latex_to_svg

    with tempfile.TemporaryDirectory(prefix="fuzz_tex_") as folder:
        error = compile_latex_to_svg(source, Path(folder) / "formula.svg", environment=environment)
    return str(error) if isinstance(error, LatexFailure) else None


def check_project(project, work: Path, dry_run: bool) -> list[str]:
    problems: list[str] = []
    if loads_project(dumps_project(project)) != project:
        problems.append("save/load changed the project")
    renderable = []
    for scene in project.scenes:
        for moment in (0.0, 0.37, total_duration(scene) / 2, total_duration(scene) - 0.01, total_duration(scene) + 1):
            state_at_time(scene, max(moment, 0.0))
        # like the app, which knows from the stage which formulas LaTeX rejects
        if not has_errors(validate_scene(scene, True, None, latex_rejections)):
            renderable.append(scene)
    if not renderable:
        return problems
    from copy import deepcopy

    clean = deepcopy(project)
    clean.scenes = [scene for scene in clean.scenes if scene.id in {s.id for s in renderable}]
    try:
        script = generate_script(clean)
    except CodegenError as error:
        return problems + [f"codegen error after clean validation: {error.code} {error.detail}"]
    (work / "script.py").write_text(script, encoding="utf-8")
    if dry_run:
        result = subprocess.run(
            [sys.executable, "-m", "manim", "render", "--dry_run", "-a", "--media_dir", str(work / "media"), str(work / "script.py")],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=work,
            env=dict(os.environ, COLUMNS="200", NO_COLOR="1"),
        )
        if result.returncode != 0:
            tail = "\n".join((result.stdout + result.stderr).strip().splitlines()[-25:])
            problems.append(f"manim --dry_run failed:\n{tail}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sessions", type=int, default=20)
    parser.add_argument("--steps", type=int, default=40, help="operations per session")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--no-manim", action="store_true", help="skip the Manim dry run")
    parser.add_argument("--out", default="fuzz_failures")
    args = parser.parse_args()

    app = QApplication.instance() or QApplication([])
    set_language("de")
    errors: list[str] = []
    sys.excepthook = lambda kind, value, tb: errors.append("".join(traceback.format_exception(kind, value, tb)))
    dialogs: list[str] = []

    def close_dialogs() -> None:
        # a session must not hang on a dialog nobody answers; note which one appeared
        widget = app.activeModalWidget()
        if isinstance(widget, (QDialog, QMessageBox)):
            text = widget.text() if isinstance(widget, QMessageBox) else ""
            dialogs.append(f"{type(widget).__name__}: {widget.windowTitle()} {text}".strip())
            widget.reject()

    watchdog = QTimer()
    watchdog.timeout.connect(close_dialogs)
    watchdog.start(250)
    failures = 0
    for number in range(args.sessions):
        seed = args.seed * 100_000 + number
        errors.clear()
        dialogs.clear()
        with tempfile.TemporaryDirectory(prefix="fuzz_") as folder:
            work = Path(folder)
            window = make_window(app, work)
            fuzzer = Fuzzer(seed, window)
            try:
                fuzzer.run(args.steps, app)
            except Exception:  # noqa: BLE001 - report every crash
                errors.append(traceback.format_exc())
            problems = list(errors)
            if not problems:
                try:
                    problems += check_project(window.document.project, work, not args.no_manim)
                except Exception:  # noqa: BLE001
                    problems.append(traceback.format_exc())
            if problems:
                failures += 1
                target = Path(args.out) / f"session_{seed}"
                target.mkdir(parents=True, exist_ok=True)
                (target / "project.msproj").write_text(dumps_project(window.document.project), encoding="utf-8")
                (target / "log.txt").write_text("\n".join(fuzzer.log) + "\n\n" + "\n\n".join(problems), encoding="utf-8")
                if (work / "script.py").exists():
                    (target / "script.py").write_text((work / "script.py").read_text(encoding="utf-8"), encoding="utf-8")
                print(f"session {seed}: FAILED ({problems[0].splitlines()[-1][:160]})", flush=True)
            else:
                project = window.document.project
                objects = sum(len(scene.objects) for scene in project.scenes)
                steps = sum(len(scene.steps) for scene in project.scenes)
                rendered = "manim ok" if (work / "script.py").exists() and not args.no_manim else "not rendered"
                extra = f", dialogs: {'; '.join(dialogs)}" if dialogs else ""
                print(f"session {seed}: ok ({len(project.scenes)} scenes, {objects} objects, {steps} steps, {rendered}{extra})", flush=True)
            close_window(app, window)
    print(f"{failures} of {args.sessions} sessions failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
