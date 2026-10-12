"""Networks of vertices and edges (Manim's Graph / DiGraph)."""

from __future__ import annotations

import pytest

from manim_studio.codegen import generate_script
from manim_studio.model.entities import Scene
from manim_studio.model.networks import is_tree, network_edges, network_layout, network_vertices, unknown_vertices
from manim_studio.model.types import ObjectKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_object, make_project


def test_parsing_and_layouts() -> None:
    net = make_object(ObjectKind.NETWORK, "Netz", "n", vertices="A, B,\nC, A", edges="A-B\nB->C, C - A, A-A, X-B")
    assert network_vertices(net) == ["A", "B", "C"]
    assert network_edges(net) == [("A", "B"), ("B", "C"), ("C", "A"), ("X", "B")]
    assert unknown_vertices(net) == ["X"]
    assert not is_tree(["A", "B", "C"], [("A", "B"), ("B", "C"), ("C", "A")]) and is_tree(["A", "B", "C"], [("A", "B"), ("A", "C")])
    net.params.update(edges="A-B\nA-C", layout="tree", layout_scale=2.0)
    layout = network_layout(net)
    assert layout["A"] == pytest.approx((0.0, 2.0)) and layout["B"][1] == pytest.approx(-2.0) and layout["B"][0] < layout["C"][0]
    triangle = make_object(ObjectKind.NETWORK, "Drei", "d", vertices="A, B, C", edges="")
    ys = [y for _, y in network_layout(triangle).values()]
    assert max(ys) == pytest.approx(-min(ys))  # centered on the bounding box like move_to()
    net.params["layout"] = "spring"
    assert network_layout(net) == network_layout(net)  # deterministic (seeded)
    net.params["layout"] = "circular"
    circle = network_layout(net)
    assert layout != circle and circle["A"][0] == pytest.approx(0.0) and circle["A"][1] == max(y for _, y in circle.values())


def test_network_validation_and_code() -> None:
    net = make_object(ObjectKind.NETWORK, "Netz", "n", 1.0, -1.0, vertices="A, B", edges="A->B", directed=True)
    scene = Scene(id="s", name="S", objects=[net])
    assert not has_errors(validate_scene(scene))
    code = generate_script(make_project(scene))
    assert 'netz = DiGraph(' in code and '"A": [1.0, 1.0, 0.0]' in code and '"tip_config"' in code and "Text(v, font_size=28.0" in code
    net.params["edges"] = "A-C"
    assert "network_unknown_vertex" in {issue.code for issue in validate_scene(scene)}
    net.params.update(edges="A-B", vertices="")
    assert has_errors(validate_scene(scene))


def _parts_scene(**params) -> tuple[Scene, object]:
    from manim_studio.model.types import AnimationKind
    from tests.helpers import make_animation, play

    net = make_object(ObjectKind.NETWORK, "Netz", "n")
    anim = make_animation(AnimationKind.NETWORK_PARTS, "n", "h", **params)
    scene = Scene(id="s", name="S", objects=[net], steps=[play(make_animation(AnimationKind.CREATE, "n", "c")), play(anim, step_id="p")])
    return scene, anim


def test_naming_vertices_and_edges() -> None:
    from manim_studio.model.networks import network_parts

    net = make_object(ObjectKind.NETWORK, "Netz", "n", vertices="A, B, C, A-1", edges="A-B\nB-C\nC-A-1")
    parts, unknown = network_parts(net, "A, B-A; C-B, A-1, X, A-X, A-1-C")
    # undirected: B-A is the edge A-B; a vertex name wins over an edge reading
    assert parts == [("v", "A", ""), ("e", "A", "B"), ("e", "B", "C"), ("v", "A-1", "")]
    assert unknown == ["X", "A-X", "A-1-C"]
    net.params["directed"] = True
    assert network_parts(net, "B-A, A->B")[0] == [("e", "A", "B")]
    assert network_parts(net, "B-A")[1] == ["B-A"]


def test_highlighted_parts_on_stage_and_in_validation() -> None:
    from manim_studio.model.playback import state_at_time
    from manim_studio.model.state import part_color, states_after

    scene, anim = _parts_scene(parts="A, A-B", color="#FC6255")
    assert not has_errors(validate_scene(scene))
    before, after = states_after(scene, 0)["n"], states_after(scene, 1)["n"]
    assert before.part_colors == ()
    assert part_color(after, ("v", "A", "")) == "#FC6255" and part_color(after, ("e", "A", "B")) == "#FC6255"
    assert part_color(after, ("v", "B", "")) == after.fill_color and part_color(after, ("e", "B", "C")) == after.stroke_color
    halfway = part_color(state_at_time(scene, 1.5)["n"], ("v", "A", ""))
    assert halfway not in ("#FC6255", before.fill_color.upper())
    anim.params["effect"] = "indicate"
    assert states_after(scene, 1)["n"].part_colors == ()  # lighting up leaves no trace
    assert part_color(state_at_time(scene, 1.5)["n"], ("v", "A", "")) == "#FC6255"  # brightest in the middle
    anim.params["parts"] = "A, Q"
    assert "network_parts_unknown" in {issue.code for issue in validate_scene(scene)}
    anim.params["parts"] = " , "
    assert "network_parts_empty" in {issue.code for issue in validate_scene(scene)}


def test_highlighting_a_hidden_network_warns() -> None:
    from manim_studio.model.types import Visibility

    scene, _anim = _parts_scene()
    scene.steps.pop(0)
    scene.objects[0].visibility = Visibility.HIDDEN
    assert "animated_while_hidden" in {issue.code for issue in validate_scene(scene)}


def test_highlight_code() -> None:
    scene, anim = _parts_scene(parts="B, A-B", color="#FC6255")
    code = generate_script(make_project(scene))
    assert 'netz.vertices["B"].animate(run_time=1.0, rate_func=smooth).set_fill("#FC6255", family=False)' in code
    assert 'netz.edges[("A", "B")].animate(run_time=1.0, rate_func=smooth).set_color("#FC6255")' in code
    anim.params.update(effect="indicate", parts="C")
    assert 'netz.vertices["C"].animate(run_time=1.0, rate_func=lambda t: there_and_back(smooth(t))).scale(1.2)' in generate_script(make_project(scene))
    anim.params.update(effect="flash", parts="C, C-D")
    code = generate_script(make_project(scene))
    assert 'Flash(netz.vertices["C"], color="#FC6255", flash_radius=0.45' in code and 'ShowPassingFlash(netz.edges[("C", "D")].copy()' in code
