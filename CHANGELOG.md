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

### Fixed
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
