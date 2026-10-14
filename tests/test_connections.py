"""Lines and arrows between two objects (coupling "between": always_redraw from center to center)."""

from __future__ import annotations

import importlib.util
import math
import re

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model.attach import attach_mode, attach_specs, connection_targets
from manim_studio.model.entities import Scene, Step
from manim_studio.model.playback import state_at_time
from manim_studio.model.schema import animation_allowed
from manim_studio.model.state import states_after
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_animation, make_object, make_project, play

HAS_MANIM = importlib.util.find_spec("manim") is not None


def triangle_scene() -> Scene:
    """A triangle of dots; its sides follow when C moves on an arc."""
    # the sides come first: the script still creates the dots before them
    sides = [
        make_object(ObjectKind.LINE, "Seite c", "ab", attach="between", attach_start="a", attach_end="b"),
        make_object(ObjectKind.ARROW, "Seite a", "bc", attach="between", attach_start="b", attach_end="c"),
        make_object(ObjectKind.DASHED_LINE, "Seite b", "ca", attach="between", attach_start="c", attach_end="a"),
    ]
    dots = [make_object(ObjectKind.DOT, name, key, x, y) for name, key, x, y in (("A", "a", -3.0, -1.5), ("B", "b", 3.0, -1.5), ("C", "c", 0.0, 2.0))]
    move = make_animation(AnimationKind.MOVE, "c", "m", x=2.5, y=1.0, path_arc=-60.0)
    move.rate_func = "linear"
    return Scene(id="s", name="Dreieck", objects=[*sides, *dots], steps=[play(move)])


def ends(state) -> tuple[float, float, float, float]:
    half = state.geometry[0] / 2
    dx, dy = half * math.cos(math.radians(state.rotation)), half * math.sin(math.radians(state.rotation))
    return state.x - dx, state.y - dy, state.x + dx, state.y + dy


def test_model_and_rules() -> None:
    scene = triangle_scene()
    assert not has_errors(validate_scene(scene))
    side = scene.object_by_id("ab")
    assert [end.id for end in connection_targets(scene, side)] == ["a", "b"]
    assert ends(states_after(scene, -1)["ab"]) == pytest.approx((-3.0, -1.5, 3.0, -1.5))
    # half way, side b runs from C (on its arc) to A
    states = state_at_time(scene, 0.5)
    c = states["c"]
    assert ends(states["ca"]) == pytest.approx((c.x, c.y, -3.0, -1.5))
    assert not animation_allowed(AnimationKind.MOVE, ObjectKind.LINE, side.params) and animation_allowed(AnimationKind.CREATE, ObjectKind.LINE, side.params)
    # only lines and arrows can run between objects
    circle = make_object(ObjectKind.CIRCLE, "Kreis", "k", attach="between", attach_start="a", attach_end="b")
    assert attach_mode(circle) == "none" and "between" not in attach_specs(ObjectKind.CIRCLE)[0].choices
    side.params["attach_end"] = "a"
    assert any(issue.code == "attach_between_missing" for issue in validate_scene(scene))


def test_code_and_import() -> None:
    code = generate_script(make_project(triangle_scene()))
    assert "seite_c = always_redraw(lambda: Line(a.get_center(), b.get_center()," in code
    assert "seite_a = always_redraw(lambda: Arrow(b.get_center(), c.get_center(), buff=0," in code
    assert code.index("c = Dot(") < code.index("seite_c = always_redraw")  # the ends exist first
    from manim_studio.importer import import_script

    imported = import_script(code).project.scenes[0]
    side = next(obj for obj in imported.objects if obj.kind == ObjectKind.ARROW)
    names = {obj.id: obj.name for obj in imported.objects}
    assert side.params["attach"] == "between" and (names[side.params["attach_start"]], names[side.params["attach_end"]]) == ("b", "c")


def test_stage_draws_the_current_length(qapp) -> None:
    from manim_studio.ui.stage.drawing import PX, StageResources, build_drawing

    scene = triangle_scene()
    state = state_at_time(scene, 0.5)["ab"]
    drawing = build_drawing(scene, scene.object_by_id("ab"), state, StageResources())
    assert drawing.primitives[0].path.boundingRect().width() == pytest.approx(6.0 * PX, abs=1.0)


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_frames_like_manim(tmp_path) -> None:
    """In every frame the sides run between the dots where the stage has them."""
    from tests.test_manim_integration import run_manim

    scene = triangle_scene()
    record = "\n".join(
        [
            "spur = []",
            "beobachter = Mobject()",
            "beobachter.add_updater(lambda m, dt: dt > 0 and spur.append((self.renderer.num_plays + self.last_t, *[float(v) for side in (seite_c, seite_a, seite_b) for v in (*side.get_start()[:2], *side.get_end()[:2])])))",
            "self.add(beobachter)",
        ]
    )
    report = "for frame in spur:\n    print('FRAME', *[round(v, 5) for v in frame])"
    scene.steps.insert(0, Step(id="record", kind=StepKind.CODE, code=record, wait_time=0.0))
    scene.steps.append(Step(id="report", kind=StepKind.CODE, code=report, wait_time=0.0))
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Dreieck", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    frames = [[float(v) for v in match.split()] for match in re.findall(r"FRAME ([^\n]+)", result.stdout)]
    assert len(frames) > 10
    for time, *values in frames:
        if time <= 1e-6 or time >= 1 - 1e-6:
            continue
        # the updater of the line runs after the dot moved: the line shows the dot of this frame
        states = state_at_time(scene, time)
        ours = [v for key in ("ab", "bc", "ca") for v in ends(states[key])]
        assert values == pytest.approx(ours, abs=2e-3), time


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_gradient_on_a_connected_line(tmp_path, qapp) -> None:
    """The gradient is part of the redrawn line; its direction does not turn with the line."""
    from manim_studio.ui.stage.drawing import StageResources, build_drawing
    from manim_studio.ui.stage.gradients import gradient_points
    from tests.test_manim_integration import run_manim

    scene = triangle_scene()
    scene.steps = []
    side = scene.object_by_id("ca")
    side.kind = ObjectKind.LINE  # the slanted side, as a plain line
    side.params.update(gradient="stroke", gradient_color="#FC6255", gradient_direction="right")
    code = generate_script(make_project(scene))
    assert ".set_stroke([" in code[code.index("seite_b = always_redraw") :].split("\n")[0]
    report = "print('LINE', *[round(float(v), 4) for point in seite_b.get_gradient_start_and_end_points() for v in point[:2]])"
    scene.steps.append(Step(id="report", kind=StepKind.CODE, code=report, wait_time=0.0))
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Dreieck", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    theirs = [float(v) for v in re.search(r"LINE (\S+) (\S+) (\S+) (\S+)", result.stdout).groups()]
    state = states_after(scene, -1)["ca"]
    drawing = build_drawing(scene, side, state, StageResources())
    start, end = gradient_points(drawing.primitives, side, state)
    assert [*start, *end] == pytest.approx(theirs, abs=0.05)


def polygon_scene() -> Scene:
    """A filled triangle through three dots; C moves on an arc."""
    area = make_object(ObjectKind.POLYGON, "Flaeche", "f", attach="corners", attach_corners=["a", "b", "c"])
    area.fill_opacity = 0.5
    dots = [make_object(ObjectKind.DOT, name, key, x, y) for name, key, x, y in (("A", "a", -3.0, -1.5), ("B", "b", 3.0, -1.5), ("C", "c", 0.0, 2.0))]
    move = make_animation(AnimationKind.MOVE, "c", "m", x=-1.0, y=2.5, path_arc=45.0)
    move.rate_func = "linear"
    return Scene(id="p", name="Flaeche", objects=[area, *dots], steps=[play(move)])


def corners_of(state) -> list[tuple[float, float]]:
    return [(state.x + dx, state.y + dy) for dx, dy in state.geometry]


def test_polygon_through_objects() -> None:
    from manim_studio.importer import import_script

    scene = polygon_scene()
    assert not has_errors(validate_scene(scene))
    assert corners_of(states_after(scene, -1)["f"]) == pytest.approx([(-3.0, -1.5), (3.0, -1.5), (0.0, 2.0)])
    c = state_at_time(scene, 0.5)["c"]
    assert corners_of(state_at_time(scene, 0.5)["f"])[2] == pytest.approx((c.x, c.y))
    assert not animation_allowed(AnimationKind.ROTATE, ObjectKind.POLYGON, scene.object_by_id("f").params)
    code = generate_script(make_project(scene))
    assert "flaeche = always_redraw(lambda: Polygon(a.get_center(), b.get_center(), c.get_center()," in code
    imported = import_script(code).project.scenes[0]
    polygon = next(obj for obj in imported.objects if obj.kind == ObjectKind.POLYGON)
    names = {obj.id: obj.name for obj in imported.objects}
    assert polygon.params["attach"] == "corners" and [names[i] for i in polygon.params["attach_corners"]] == ["a", "b", "c"]
    scene.object_by_id("f").params["attach_corners"] = ["a", "b"]
    assert any(issue.code == "attach_corners_missing" for issue in validate_scene(scene))


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_polygon_frames_like_manim(tmp_path) -> None:
    from tests.test_manim_integration import run_manim

    scene = polygon_scene()
    record = "\n".join(
        [
            "spur = []",
            "beobachter = Mobject()",
            "beobachter.add_updater(lambda m, dt: dt > 0 and spur.append((self.renderer.num_plays + self.last_t, *[float(v) for corner in flaeche.get_vertices() for v in corner[:2]])))",
            "self.add(beobachter)",
        ]
    )
    scene.steps.insert(0, Step(id="record", kind=StepKind.CODE, code=record, wait_time=0.0))
    scene.steps.append(Step(id="report", kind=StepKind.CODE, code="for frame in spur:\n    print('FRAME', *[round(v, 5) for v in frame])", wait_time=0.0))
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Flaeche", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    frames = [[float(v) for v in match.split()] for match in re.findall(r"FRAME ([^\n]+)", result.stdout)]
    assert len(frames) > 10
    for time, *values in frames:
        if 1e-6 < time < 1 - 1e-6:
            assert values == pytest.approx([v for corner in corners_of(state_at_time(scene, time)["f"]) for v in corner], abs=2e-3), time


def test_created_from_the_selection(window) -> None:
    controller = window.controller
    dots = [controller.add_object(ObjectKind.DOT, x, y) for x, y in ((-2.0, -1.0), (2.0, -1.0), (0.0, 1.5))]
    window.editor.select_objects(dots[:2])
    line = window.editor.scene().object_by_id(controller.add_object(ObjectKind.LINE))
    assert (line.params["attach"], line.params["attach_start"], line.params["attach_end"]) == ("between", dots[0], dots[1])
    window.editor.select_objects(dots)
    polygon = window.editor.scene().object_by_id(controller.add_object(ObjectKind.POLYGON))
    assert polygon.params["attach"] == "corners" and polygon.params["attach_corners"] == dots
    window.editor.select_objects([])
    free = window.editor.scene().object_by_id(controller.add_object(ObjectKind.LINE))
    assert free.params.get("attach", "none") == "none"
