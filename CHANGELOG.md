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

- Nonlinear maps of the plane: *Complex map f(z)* (`ApplyComplexFunction`, e.g. `z^2`, `exp(z)`, `1/z` with `i` as imaginary unit) and *Pointwise map* (`ApplyPointwiseFunction` with x′ and y′). The stage bends the outlines point by point; where a map is undefined the point stays, like in the script, so Manim gets no invalid points.
- Number planes can show their numbers, also as a complex plane (`ComplexPlane` with 1, 2 … and i, 2i …, written without LaTeX). Template "Complex map w = z²" (now 17 templates).

- The 3D camera can keep turning (*Camera keeps turning*, Manim's `begin_ambient_camera_rotation`) through all following steps and pauses, about θ or φ; a new speed replaces it, 0 °/s stops it. The template "3D solids with camera move" ends with it.

- 3D solids can move and turn in space (*Move in space* with `move_to` to a point of the 3D axes, *Turn in space* with `Rotate` about the x, y or z axis).
- The stage shades 3D solids and surfaces like Manim's 3D camera: every face gets Manim's light from the lower left front (a gradient between two corners, lighter towards the light), so the stage looks like the video. The cone's base stays unshaded like in Manim.

- Zoom lens (Manim's `ZoomedScene`): a frame and a display that shows it magnified, on the stage like in the video. It pops out (*Fade in*), moves, zooms (*Scale*) and fades out; one per 2D scene, also in the joined video. Template "Zoom lens: locally linear" (now 18 templates).

- Move and Transform on an arc (Manim's `path_arc`, *Arc path (°)*: positive turns counterclockwise). The stage moves every point on its arc like Manim and shows the arc as the motion path of the step; the script import reads `path_arc` and `ClockwiseTransform`/`CounterclockwiseTransform`.

- Color gradients for shapes and lines (*Color gradient*: fill, outline or both, a second color and its direction; Manim's `set_fill([a, b])`, `set_stroke([a, b])` and `set_sheen_direction`). The stage lays the gradient out like Manim (across the bounding box, turning with the object); a color change makes it one color again, a transform blends it. The script import reads two-color `set_fill`/`set_stroke`/`set_color` and `set_sheen_direction`.

- Graph tools work on the integral function F(x) = C + ∫ f(t) dt: point, tangent (its slope is f), secant, area, Riemann sum, zeros, extrema (where f changes sign), inflection points (at the extrema of f), intersections, labels, value table and value labels, also with parameters. Template "Integral function: F′ = f" (now 19 templates): the tangent at F slides along it and its slope is the value of f; the areas above and below the x-axis cancel where F returns to 0.

- The script import reads graph tools made by axes: `plot_derivative_graph`, `plot_antiderivative_graph`, `get_area` (also `bounded_graph`), `get_riemann_rectangles`, `get_secant_slope_group`, `get_graph_label`, points `Dot(ax.i2gp(x, graph))`, and curves from `plot_parametric_curve` and `plot_polar_graph`.

- Lines, arrows, double arrows and dashed lines can run between two objects (coupling *between two objects*: from center to center, `always_redraw(lambda: Line(a.get_center(), b.get_center()))`). When the objects move, the line follows on the stage like in the video, e.g. the sides of a triangle whose corners are dots. The import reads such lines. Template "Thales’ theorem" (now 21 templates): C walks on the circle (on arcs), the sides follow and the angle at C stays 90°.

- Texts can run through a color gradient letter by letter (*Color gradient: Letters*, Manim's `Text(gradient=(a, b))`); the stage colors every character like Pango, spaces and line breaks included. Colored words and a gradient exclude each other (Manim cannot give a letter two colors). The import reads `gradient=`.

- Highlights can mark a cell, a row or a column of a table (*Table row*/*Table column*, 0 = all): frame, background, underline or cross over exactly the cells, like Manim's `Table.get_cell` (`studio_table_cells`). Template "Table of values and graph" (now 20 templates): a frame walks through the columns and each pair of values becomes a point, then the graph joins them.

- Dashed function graphs (also derivatives, integral functions, piecewise, parametric and polar curves): the graph is wrapped in `DashedVMobject`, while areas, Riemann sums, labels, points and *Move along path* keep using the curve itself. The stage cuts the curve like Manim, across the gaps of clipped or piecewise graphs. The import reads dashed graphs back.

- Dashed shapes: circle, ellipse, arc, square, rectangle, triangle, regular polygon, polygon, star and sector can be drawn *Dashed* (outline only) with a number of dashes and a dash ratio (Manim's `DashedVMobject`). The stage cuts the outline like Manim (equal arc lengths, in Manim's order), so every dash lies where it is in the video, also with a gradient (one per dash). Dashed shapes cannot be transformed, used as a path or united in a boolean shape (Manim only has the separate dashes); the import reads `DashedVMobject(…)`.

- README: GIFs of the complex map w = z², the integral function and the zoom lens (rendered from the templates).

### Fixed
- Numbers on the stage are set like Manim's `DecimalNumber`: every character on its own and close together, a minus sign in the middle of the digits. Before, they were up to 8 % too wide.
- A background highlight lies behind its target on the stage too (the script already put it there with `set_z_index`); before, it covered e.g. the entries of a table row.
- Tables on the stage are laid out like Manim's `Table`: every row is as high as its highest entry and every column as wide as its widest one (the ink of the text), the lines lie in the middle of the gaps. Before, rows were all equally high and the table was up to 15 % too large.
- The dashed line on the stage has its dashes where Manim's `DashedLine` puts them (the last dash ends at the end of the line), and a sector runs in Manim's order (*Create* starts at its center like in the video).
- Lines and outlines on the stage end and turn corners like in the video: flat ends and pointed corners (Cairo's defaults, which Manim keeps) instead of round ones; visible with thick lines.
- Manim's `Union` leaves a hole where two shapes drawn in opposite directions overlap (e.g. a sector and a triangle). Generated scripts unite the two areas themselves (`studio_union`), so the video shows the real union like the stage.
- The stage draws texts in Manim's default font (Pango's serif font) instead of the interface font, so texts and labels are as wide as in the video.
- Axes and number lines with an arrow tip no longer show the last tick and number on the stage (Manim leaves them out; the tip sits there); ranges that do not contain 0 start their ticks at the first value like Manim.
- Axis labels (x, y) sit on the stage where Manim puts them: next to the tip (the y label half up, not diagonally) and pushed back onto the screen like `shift_onto_screen`.
- Texts on the stage have Manim's size and line spacing for every font: Pango sizes a `Text` by its em (font size / 72) and puts lines font size / 96 · (1 + spacing) apart, whatever the font. Before, fonts with other proportions (e.g. DejaVu or Liberation Serif) were up to 9 % too wide or too narrow, and lines of multi-line texts were too far apart.
- Axes with numbers: the stage centers them with their numbers like Manim's `move_to` (before, the axes and everything on them were up to 0.25 units off), writes the numbers with the decimals of the step (`1.0`, `1.5`) and sets them like `DecimalNumber` (negative x numbers centered on their digits).
- The stage draws the grid lines of a number plane where Manim does: from the axes outwards, without lines on the far edges (a plane from -7 to 7 has no lines at ±7).
- Fading out a motion trace before it recorded anything (e.g. in the first step) crashed Manim.
- Motion paths along a regular polygon with an even number of corners started at the wrong corner (and a square-shaped one was turned by 45°).
- The label of a point that follows a parameter showed fewer decimals on the stage than in the video.
- Circles, ellipses, dots, squares and rectangles run on the stage in Manim's order (circles from the right counterclockwise, rectangles from the upper right corner). *Create* now starts where it starts in the video, and a Transform pairs the points like Manim: half way from a circle to a square the stage showed a shape that was too small and turned.

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
