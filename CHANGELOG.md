# Changelog

All notable changes to Manim Studio are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## Unreleased

### Added
- Tangents and secants can show their current term as a label (`t(x) = 1.50x − 0.25`, `y = …` or `m = …`). The label follows the line while a parameter moves it and stays on the side away from the graph (or above/below, as chosen).
- Template "A tangent slides along the graph" (now 15 templates).
- A formula can compute its result (option *Compute result*): `\frac{a^2}{2} + 3` becomes `\frac{a^2}{2} + 3 = 3.50`, live with parameters.
- Parametric surfaces x(u, v), y(u, v), z(u, v) in 3D (e.g. a sphere or a torus from formulas), also with parameters.
- Integral function of a graph: F(x) = C + ∫ f(t) dt from a to x, computed numerically like Manim's `plot_antiderivative_graph` (button *∫ Integral function* on a graph).
- A number can show a formula of parameters (e.g. `a^2/2` or `sin(a) + 1`); it updates live while the parameters change.

- Boolean shapes: union, intersection, difference and exclusion (symmetric difference) of two closed shapes, also nested. They follow their shapes while these move, turn or change (Manim's `Union`, `Intersection`, `Difference`, `Exclusion` with `always_redraw`). Select two shapes and click *Boolean shape*, or get two overlapping circles with it.
- Template "Sets: intersection and difference" with a Venn diagram (now 16 templates).
- The script import reads `Union`, `Intersection`, `Difference` and `Exclusion`.

- Formulas of numbers, positions and computed results can use values of function graphs: a graph named `f` can be called as `f(a)`, also with parameters inside `f` and for derivatives. Term errors in the validation list are now explained in words.

- Value labels: the term, equation or slope of a tangent or secant, the coordinates or function value of a point and the area or integral of an area as an object of its own. It follows its tool (live with parameters) but can appear later, be highlighted or disappear on its own, and it can be shifted away from its automatic place. Button *Value as a separate label* on these tools; the template "A tangent slides along the graph" now writes its term after the tangent appears.

### Fixed
- Manim's `Union` leaves a hole where two shapes drawn in opposite directions overlap (e.g. a sector and a triangle). Generated scripts unite the two areas themselves (`studio_union`), so the video shows the real union like the stage.
- The stage draws texts in Manim's default font (Pango's serif font) instead of the interface font, so texts and labels are as wide as in the video.
- Axes and number lines with an arrow tip no longer show the last tick and number on the stage (Manim leaves them out; the tip sits there); ranges that do not contain 0 start their ticks at the first value like Manim.
- Axis labels (x, y) sit on the stage where Manim puts them: next to the tip (the y label half up, not diagonally) and pushed back onto the screen like `shift_onto_screen`.
- Axes with numbers: the stage centers them with their numbers like Manim's `move_to` (before, the axes and everything on them were up to 0.25 units off), writes the numbers with the decimals of the step (`1.0`, `1.5`) and sets them like `DecimalNumber` (negative x numbers centered on their digits).
- Fading out a motion trace before it recorded anything (e.g. in the first step) crashed Manim.
- Motion paths along a regular polygon with an even number of corners started at the wrong corner (and a square-shaped one was turned by 45°).
- The label of a point that follows a parameter showed fewer decimals on the stage than in the video.

## 0.9.0 – first public pre-release (not yet published)

Everything below was built for this first public version.

### Editor
- Stage in Manim coordinates with grid, snapping, rulers, zoom, selection by frame, handles for moving, scaling and rotating, editing polygon points and line ends, align and distribute, groups, layers (tree with eye and lock), copy and paste between scenes.
- Timeline with steps that play their animations together, staggered or one after another; drag to reorder, set delays and durations, wait steps, code steps for advanced users, section starts, subtitles and sounds per step.
- Playback on the stage without rendering (*Space*); edits at a selected step are recorded as animations.
- Undo/redo for every change, several scenes per project, autosave with recovery after a crash, project packages with images and sounds.
- Video formats 16:9, 9:16, 1:1 and 4:3.
- Dark and light theme, adjustable UI scale, German and English (switchable without restart; the first start follows the system language).
- Welcome dialog with 5 example projects, an interactive tour, animated previews of every animation on hover, a list of keyboard shortcuts (*F1*).
- Own styles, building blocks and templates; plugins (opt-in) with an example in `examples/plugins`.
- Import of simple Manim scripts (basic shapes, lines and arrows, text and formulas, axes, plain function graphs, numbers, groups and common animations; other lines are skipped and listed).

### Objects
- Shapes, lines, arrows, curved arrows (one or two tips, or a plain arc), vectors, braces, dots, images (PNG/JPG/SVG).
- Text with colored words, Markup text, bullet lists, code blocks, tables; with LaTeX formulas (`MathTex`, `Tex`) with colored parts and matrices.
- Highlights that stick to an object (frame, background, underline, strike-through), angle marks between two lines, motion traces.
- Number line, number plane (square or polar grid), axes, function graphs (terms, piecewise, parametric, polar, implicit, derivatives), area, Riemann rectangles, tangent, secant with slope triangle (difference quotient; as h → 0 it becomes the tangent), points on graphs with coordinates, zeros/extrema/inflection points/intersections, graph labels, tables of values, data points with regression, bar charts with CSV import, vector fields (arrows or stream lines).
- Networks of vertices and edges (Manim's `Graph`/`DiGraph`) with circular, spring, Kamada-Kawai, shell, spiral and tree layouts.
- 3D axes, surfaces, 3D curves, solids (sphere, cube, box, cone, cylinder, torus, tetrahedron, octahedron, icosahedron, dodecahedron) and arrows, lines and points in space (`Arrow3D`, `Line3D`, `Dot3D`).
- Parameters (`ValueTracker`) with sliders, usable in all formulas and shown with live numbers.

### Animations
- 38 kinds: appear, change, transform, emphasize and disappear (see the README), each with duration, delay and easing.
- **Linear map** (`ApplyMatrix`): a 2×2 matrix deforms grids, vectors, shapes and texts around the origin.
- **Highlight vertices/edges** of a network: recolor, light up or flash single parts, e.g. a path.
- Rotation around a fixed point, move along a path, swap, change value of a parameter.
- Camera: move and zoom in 2D (also "zoom onto selection"), orbit and moves in 3D.
- **Coupling** (Manim updaters): an object follows another one (e.g. a label next to a moving dot), the 2D camera follows an object, or a position comes from a formula with parameters.

### Preview and export
- Quick preview inside the app (480p or 720p), also from any step.
- Export as MP4, WebM, MOV, GIF or PNG in 480p, 720p, 1080p, 1440p, 4K or a custom size; transparent backgrounds with MOV, WebM and PNG.
- All scenes as separate files or joined into one video (cut or fade), sections as separate clips.
- Export of the generated script; code view with syntax highlighting.
- 14 scene templates, including presentation slide, graph theory (a path), linear map and secant to tangent.

### Robustness
- Check for Manim, FFmpeg and LaTeX at start, with installation hints; Manim can be installed from the app.
- Validation before rendering with understandable messages; render errors are explained (LaTeX errors name the failing formula). Formulas LaTeX already rejected on the stage stop the render before it starts.
- Rules that keep scripts valid: animations Manim cannot play at the same time go into their own step automatically (e.g. a number tied to a parameter while the parameter changes), dependent objects bring their hosts along and disappear with them.
- Random editing sessions (`tools/fuzz_sessions.py`) found and fixed several crashes.
- Dashed helper lines of length 0 (a point on an axis, a secant with h = 0) no longer break rendering with Manim 0.19.
- Objects named like a variable or helper of the generated script (e.g. `x0`, `studio_plot`) are renamed in the script, so they cannot hide it.
- Works with Python 3.10 to 3.13 and Manim 0.19 to 0.22. On Python < 3.12, PySide6 6.12 is excluded because it crashes ("deallocating None").

### Project
- MIT license, CI with GitHub Actions (lint and tests on Python 3.10 and 3.13, including real Manim renders), contributing guide, example projects in `examples/`.
