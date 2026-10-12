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
