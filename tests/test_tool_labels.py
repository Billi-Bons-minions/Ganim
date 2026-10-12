"""Value labels: separate labels of tangents, secants, points and areas."""

from __future__ import annotations

import importlib.util
import math
import re

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model import operations as ops
from manim_studio.model.conflicts import step_conflicts
from manim_studio.model.entities import Scene, Step
from manim_studio.model.schema import animation_allowed
from manim_studio.model.state import parameter_values, states_after
from manim_studio.model.tool_labels import label_text, simpson, tool_label
from manim_studio.model.types import AnimationKind, ObjectKind, StepKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_animation, make_object, make_project, play

HAS_MANIM = importlib.util.find_spec("manim") is not None
TOOLS = ("t", "s", "p", "ar")


def label_scene() -> Scene:
    a = make_object(ObjectKind.PARAMETER, "a", "pa", symbol="a", value=1.0, minimum=-3.0, maximum=3.0)
    axes = make_object(ObjectKind.AXES, "Achsen", "ax")
    f = make_object(ObjectKind.FUNCTION_GRAPH, "f", "f", expression="x^2/2", axes_id="ax")
    tangent = make_object(ObjectKind.TANGENT, "Tangente", "t", graph_id="f", x_parameter="pa")
    secant = make_object(ObjectKind.SECANT, "Sekante", "s", graph_id="f", x_value=-1.0, h=1.0)
    point = make_object(ObjectKind.GRAPH_POINT, "Punkt", "p", graph_id="f", x_parameter="pa")
    area = make_object(ObjectKind.GRAPH_AREA, "Fläche", "ar", graph_id="f", x_min=-1.0, x_max=2.0)
    labels = [make_object(ObjectKind.TOOL_LABEL, f"l{tool}", f"l{tool}", tool_id=tool) for tool in TOOLS]
    return Scene(id="s", name="Werte", objects=[a, axes, f, tangent, secant, point, area, *labels])


def test_texts_and_anchors() -> None:
    scene = label_scene()
    found = {tool: tool_label(scene, scene.object_by_id(f"l{tool}")) for tool in TOOLS}
    assert found["t"].text == "t(x) = 1.00x − 0.50" and (found["t"].x, found["t"].y, found["t"].slope) == pytest.approx((1.0, 0.5, 1.0))
    # the secant through f(-1) = 0.5 and f(0) = 0: the label sits in the middle
    assert found["s"].text == "s(x) = −0.50x + 0.00" and (found["s"].x, found["s"].y) == pytest.approx((-0.5, 0.25))
    assert found["p"].text == "(1.00 | 0.50)" and found["p"].placement == "corner"
    assert found["ar"].text == "A = 1.50" and (found["ar"].x, found["ar"].y) == pytest.approx((0.5, 0.0625))
    # other contents, decimals and a content that does not fit (falls back to the automatic one)
    point_label = scene.object_by_id("lp")
    point_label.params.update(content="function_value", decimals=1)
    assert tool_label(scene, point_label).text == "f(1.0) = 0.5"
    area_label = scene.object_by_id("lar")
    scene.object_by_id("f").params["expression"] = "x"
    area_label.params["content"] = "integral"
    assert tool_label(scene, area_label).text == "∫ f(x) dx = 1.50"  # -1/2 + 2 = 1.5
    area_label.params["content"] = "area"
    assert tool_label(scene, area_label).text == "A = 2.50"  # |x| from -1 to 2
    area_label.params["content"] = "slope"
    assert tool_label(scene, area_label).text == "A = 2.50"
    assert "tool_label_content" in {issue.code for issue in validate_scene(scene)}


def test_script_helper_writes_the_same_texts() -> None:
    import numpy as np

    from manim_studio.codegen.graph_code import STUDIO_INTEGRAL_SOURCE, STUDIO_LABEL_TEXT_SOURCE, STUDIO_TERM_SOURCE

    namespace: dict = {"np": np}
    exec(STUDIO_TERM_SOURCE + "\n" + STUDIO_LABEL_TEXT_SOURCE + "\n" + STUDIO_INTEGRAL_SOURCE, namespace)  # noqa: S102 - our own helper source
    for content in ("term", "equation", "slope", "coordinates", "function_value", "area", "integral"):
        for first, second in ((1.5, -0.25), (-0.004, 0.0), (-2.0, 3.333), (0.0, -0.001)):
            for decimals in (0, 2, 3):
                assert namespace["studio_label_text"](content, decimals, first, second, "g") == label_text(content, decimals, first, second, "g")
    # the stage integrates exactly like the script
    for function, low, high in ((lambda x: x**2, -1.0, 2.0), (lambda x: np.abs(np.sin(3 * x)), 0.0, 2.5)):
        assert simpson(function, low, high) == pytest.approx(namespace["studio_integral"](function, low, high), rel=1e-12)
    assert simpson(lambda x: x**2, 0.0, 3.0) == pytest.approx(9.0)


def test_value_label_follows_its_parameter_and_is_animated_on_its_own() -> None:
    scene = label_scene()
    scene.steps = [play(make_animation(AnimationKind.SET_VALUE, "pa", "set", value=2.0))]
    values = parameter_values(scene, states_after(scene, 0))
    assert tool_label(scene, scene.object_by_id("lt"), values).text == "t(x) = 2.00x − 2.00"
    assert tool_label(scene, scene.object_by_id("lp"), values).text == "(2.00 | 2.00)"
    # fading the label in while its parameter changes would break Manim: it goes into its own step
    assert "lt" in step_conflicts(scene, [*scene.steps[0].animations, make_animation(AnimationKind.FADE_IN, "lt")])
    assert "ls" not in step_conflicts(scene, [*scene.steps[0].animations, make_animation(AnimationKind.FADE_IN, "ls")])
    assert animation_allowed(AnimationKind.INDICATE, ObjectKind.TOOL_LABEL, {}) and animation_allowed(AnimationKind.WRITE, ObjectKind.TOOL_LABEL, {})
    assert not animation_allowed(AnimationKind.MOVE, ObjectKind.TOOL_LABEL, {})
    assert not has_errors(validate_scene(scene))


def test_deleting_the_tool_or_graph_deletes_the_label() -> None:
    scene = label_scene()
    ops.remove_objects(scene, ["t"])
    assert scene.object_by_id("lt") is None and scene.object_by_id("ls") is not None
    ops.remove_objects(scene, ["f"])
    assert not [obj for obj in scene.objects if obj.kind == ObjectKind.TOOL_LABEL]


def test_label_code() -> None:
    code = generate_script(make_project(label_scene()))
    assert "def studio_label_text(content, decimals, first, second, name):" in code and "def studio_term(" in code
    assert "lt = always_redraw(lt_build)" in code and 'studio_label_text("term", 2, slope, y0 - slope * x0, "t")' in code
    assert 'ls = studio_beside(Text("s(x) = −0.50x + 0.00", font_size=24.0' in code
    assert 'lar = Text("A = 1.50", font_size=24.0, color="#F7D96F", fill_opacity=1.0).move_to(achsen.c2p(0.5, 0.0625))\n' in code
    scene = label_scene()
    scene.object_by_id("lar").params["shift_y"] = 0.4
    assert ".move_to(achsen.c2p(0.5, 0.0625)).shift(np.array([0.0, 0.4, 0.0]))" in generate_script(make_project(scene))


def test_value_labels_from_the_app(window, qapp) -> None:
    controller = window.controller
    messages = []
    controller.statusMessage.connect(messages.append)
    window.editor.select_objects([])
    assert controller.add_object(ObjectKind.TOOL_LABEL) is None and "Tangente" in messages[-1]
    controller.add_object(ObjectKind.AXES, 0.0, 0.0)
    graph = controller.add_object(ObjectKind.FUNCTION_GRAPH)
    tangent = controller.add_graph_tool(ObjectKind.TANGENT, graph)
    window.document.edit_scene("l", window.editor.scene_id, lambda s: s.object_by_id(tangent).params.update(label="slope", decimals=1), None)
    label = controller.add_tool_label(tangent)
    scene = window.editor.scene()
    made = scene.object_by_id(label)
    # the separate label takes over the tangent's own label, in one undo step
    assert (made.params["content"], made.params["decimals"], scene.object_by_id(tangent).params["label"]) == ("slope", 1, "none")
    assert made.fill_color == scene.object_by_id(tangent).stroke_color
    window.document.undo_stack.undo()
    scene = window.editor.scene()
    assert scene.object_by_id(label) is None and scene.object_by_id(tangent).params["label"] == "slope"
    # from the library with a selected point
    point = controller.add_graph_tool(ObjectKind.GRAPH_POINT, graph)
    window.editor.select_objects([point])
    made = window.editor.scene().object_by_id(controller.add_object(ObjectKind.TOOL_LABEL))
    assert made.params["tool_id"] == point and not has_errors(validate_scene(window.editor.scene()))
    # the properties of the label and the button on the tool
    from PySide6.QtWidgets import QToolButton

    window.editor.select_objects([made.id])
    qapp.processEvents()
    window.editor.select_objects([point])
    qapp.processEvents()
    buttons = [button for button in window.findChildren(QToolButton) if button.text() == "Wert als eigene Beschriftung" and button.isVisible()]
    assert buttons
    buttons[0].click()
    assert sum(1 for obj in window.editor.scene().objects if obj.kind == ObjectKind.TOOL_LABEL) == 2


def test_stage_places_the_labels(qapp) -> None:
    from manim_studio.model.geometry import axes_to_scene
    from manim_studio.ui.stage.drawing import PX, StageResources, build_drawing

    scene = label_scene()
    states = states_after(scene, -1)
    axes = scene.object_by_id("ax")
    for tool in TOOLS:
        label = scene.object_by_id(f"l{tool}")
        drawing = build_drawing(scene, label, states[label.id], StageResources())
        assert drawing.primitives, tool
        center = drawing.primitives[0].path.boundingRect().center()
        x, y = states[label.id].x + center.x() / PX, states[label.id].y - center.y() / PX
        found = tool_label(scene, label)
        anchor = axes_to_scene(axes, found.x, found.y)
        if found.placement == "center":
            assert (x, y) == pytest.approx(anchor, abs=1e-6)
        else:
            # beside the line or up and right of the point, never on top of it
            assert math.dist((x, y), anchor) > 0.1


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_value_labels_match_manim(tmp_path, qapp) -> None:
    from manim_studio.ui.stage.drawing import PX, StageResources, build_drawing
    from tests.test_manim_integration import run_manim

    scene = label_scene()
    scene.object_by_id("ar").params["mode"] = "below"
    scene.object_by_id("lar").params.update(content="integral", shift_y=0.5)
    scene.object_by_id("lp").params["shift_x"] = -0.3  # moved away from its automatic place
    ids = [f"l{tool}" for tool in TOOLS]
    # always_redraw (become) updates the shape but not the text attribute: read it from the build function
    texts = {"lt": "lt_build().original_text", "lp": "lp_build().original_text", "ls": "ls.original_text", "lar": "lar.original_text"}
    prints = [f"print('LABEL', '{object_id}', round(float({object_id}.get_center()[0]), 4), round(float({object_id}.get_center()[1]), 4), repr({texts[object_id]}))" for object_id in ids]
    scene.steps = [
        play(*(make_animation(AnimationKind.FADE_IN, tool) for tool in TOOLS)),
        play(*(make_animation(AnimationKind.WRITE, object_id) for object_id in ids)),
        play(make_animation(AnimationKind.SET_VALUE, "pa", "set", value=-1.5)),
        Step(id="code", kind=StepKind.CODE, code="\n".join(prints)),
    ]
    assert not has_errors(validate_scene(scene)), [issue.code for issue in validate_scene(scene)]
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Werte", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    printed = {match[0]: (float(match[1]), float(match[2]), match[3]) for match in re.findall(r"LABEL (\w+) (\S+) (\S+) '(.*)'", result.stdout)}
    states = states_after(scene, 2)
    resources = StageResources(values=parameter_values(scene, states))
    for object_id in ids:
        label = scene.object_by_id(object_id)
        x, y, text = printed[object_id]
        assert text == tool_label(scene, label, resources.values).text
        drawing = build_drawing(scene, label, states[object_id], resources)
        center = drawing.primitives[0].path.boundingRect().center()
        # Qt and Pango measure the text a little differently; the centers agree within a few hundredths (measured: < 0.01)
        assert (states[object_id].x + center.x() / PX, states[object_id].y - center.y() / PX) == pytest.approx((x, y), abs=0.04), object_id


@pytest.mark.manim
@pytest.mark.skipif(not HAS_MANIM, reason="Manim is not installed")
def test_value_labels_with_every_animation_render(tmp_path) -> None:
    from manim_studio.model.types import ENTRANCE_ANIMATIONS, EXIT_ANIMATIONS
    from tests.test_manim_integration import run_manim

    scene = label_scene()
    allowed = [kind for kind in AnimationKind if animation_allowed(kind, ObjectKind.TOOL_LABEL, {})]
    entrances = [kind for kind in allowed if kind in ENTRANCE_ANIMATIONS]
    exits = [kind for kind in allowed if kind in EXIT_ANIMATIONS]
    others = [kind for kind in allowed if kind not in ENTRANCE_ANIMATIONS and kind not in EXIT_ANIMATIONS]
    ids = [f"l{tool}" for tool in TOOLS]
    steps = []
    for index, kind in enumerate(entrances):
        target = ids[index % 4]
        steps += [play(make_animation(kind, target, f"in{index}", run_time=0.1)), play(make_animation(AnimationKind.FADE_OUT, target, f"out{index}", run_time=0.1))]
    steps.append(play(*(make_animation(AnimationKind.FADE_IN, target, f"show-{target}", run_time=0.1) for target in ids)))
    steps += [play(make_animation(kind, ids[index % 4], f"o{index}", run_time=0.1)) for index, kind in enumerate(others)]
    steps.append(play(make_animation(AnimationKind.SET_VALUE, "pa", "set", value=-2.0, run_time=0.3)))
    for index, kind in enumerate(exits):
        steps += [play(make_animation(kind, "lt", f"x{index}", run_time=0.1)), play(make_animation(AnimationKind.FADE_IN, "lt", f"back{index}", run_time=0.1))]
    scene.steps = steps
    assert len(entrances) >= 5 and len(exits) >= 3 and len(others) >= 3
    assert not has_errors(validate_scene(scene)), [issue.code for issue in validate_scene(scene)]
    result = run_manim(tmp_path, generate_script(make_project(scene)), "Werte", "--dry_run")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
