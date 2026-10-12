# Contributing to Manim Studio

Thanks for helping! Bug reports, ideas and pull requests are welcome.

## Reporting a bug

Please open an issue with
- what you did (ideally the project file: *File → Save* or *Save as package*),
- what happened and what you expected,
- the render log if rendering failed (*Render Log* tab) and the app log (*Help → Open Log Folder*),
- your system, Python version and Manim version (*Render → System Check …*).

## Development setup

```bash
git clone https://github.com/Billi-Bons-minions/Ganim.git
cd Ganim
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m manim_studio
```

You need the system libraries Manim needs (Cairo, Pango, see the README). LaTeX is optional; tests that need it are skipped without it.

## Tests and lint

```bash
QT_QPA_PLATFORM=offscreen pytest -q                  # everything, including real Manim renders (a few minutes)
QT_QPA_PLATFORM=offscreen pytest -q -m "not manim"   # fast: no Manim renders (about a minute)
ruff check manim_studio tests tools examples packaging   # only real errors (F) and import order (I)
```

Please do not reformat code: `ruff` is configured to check, not to restyle. CI runs the same commands on Python 3.10 (without LaTeX) and 3.13 (with LaTeX).

For larger changes, run the fuzzer as well. It plays random editing sessions through the real app and checks saving/loading, the stage, code generation and `manim --dry_run`:

```bash
QT_QPA_PLATFORM=offscreen python tools/fuzz_sessions.py --sessions 30 --seed 1
```

Failing sessions are saved to `fuzz_failures/` with the project, the script and a log of the operations.

## How the code is organized

```
manim_studio/
├── model/      data model (single source of truth, no Qt): objects, steps, animations,
│               parameters, graphs, validation, state of the scene at any time, serialization
├── codegen/    model → Manim script (deterministic, no eval of user input)
├── render/     runs Manim with QProcess, parses progress and errors, checks the system
├── ui/         main window, stage, panels, dialogs, theme (no Manim logic)
├── i18n/       all texts: de.py and en.py
├── templates.py, examples.py   built-in templates and example projects
├── importer.py                 reads Manim scripts back into a project
└── plugins.py                  opt-in extensions
tools/          fuzzer, generator for examples/
tests/          pytest; tests marked "manim" render for real
```

Principles:
- **The UI only changes the model** (through `ProjectDocument.edit_scene`/`edit_project`, so that every change can be undone). Stage, code view and timeline are rebuilt from the model.
- **Stage and video must agree.** Whatever the stage draws (positions, colors, layouts, labels …) is computed so that Manim draws the same. Check new drawings against a real render.
- **Never generate code that Manim cannot play.** Rules that prevent it live in the model (`validation.py`, `model/conflicts.py`, `schema.animation_allowed`) and are used by validation, code generation and the editor alike.
- User input is embedded as checked literals; formulas are parsed by `model/expression.py` and translated, never evaluated with `eval`.

## Adding an animation

A new `AnimationKind` touches these places (look at an existing kind such as `BROADCAST` or `APPLY_MATRIX`):

1. `model/types.py`: the enum value (and the sets it belongs to: entrance, exit, emphasis …).
2. `model/schema.py`: its parameters in `ANIMATION_PARAMS` and, if needed, rules in `animation_allowed`.
3. `model/state.py` (`apply_animation`) and `model/playback.py` (`apply_partial`): what it does to the stage at the end and while it plays.
4. `codegen/animations.py`: the generated Manim call.
5. `importer.py`: reading the call back, if possible.
6. `i18n/de.py` and `i18n/en.py`: `anim.*`, `anim_short.*`, `anim_help.*`, `aparam.*`, `choice.*` (a test checks that both languages are complete).
7. `ui/animation_catalog.py` (menu group), `ui/icon_set.py` (`a_<kind>` icon), `ui/animation_preview.py` (`_draw_<kind>` hover preview), `ui/panels/timeline_view.py` (bar color).
8. Tests: model/state, code, and a real render in `tests/test_manim_integration.py`.

## Adding an object kind

Similar: `ObjectKind` in `model/types.py`, `KIND_INFO` in `model/schema.py`, extents in `model/extents.py`, drawing in `ui/stage/drawing*.py`, code in `codegen/objects*.py`, icon in `ui/icons.py`, library entry in `ui/panels/library_panel.py`, texts in both languages, validation, and tests including a real render. Objects that refer to others (axes, graphs, targets) list their reference keys in `OBJECT_REFERENCE_KEYS` (`model/factory.py`) so that copying and deleting keep them consistent.

## Texts

All user-visible texts live in `manim_studio/i18n/de.py` and `en.py` with the same keys. Write short, plain sentences; error messages should say what happened and what to do.

## Commits and pull requests

- Small commits with a clear message (what and why).
- Run the tests and `ruff check` before pushing.
- Describe in the pull request what you changed and how you tested it (e.g. which scene you rendered).

By contributing you agree that your contribution is licensed under the MIT License of this project.
