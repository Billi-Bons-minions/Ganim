"""Networks of vertices and edges (Manim's ``Graph`` / ``DiGraph``).

The app computes the vertex positions itself (with NetworkX if it is
installed, otherwise on a circle) and passes them to Manim as an explicit
layout, so the stage and the video always agree.
"""

from __future__ import annotations

import math
import re

from manim_studio.model.entities import SceneObject
from manim_studio.model.geometry import param_float

LAYOUTS = ("circular", "spring", "kamada_kawai", "shell", "spiral", "tree")

_EDGE = re.compile(r"^\s*(.+?)\s*(->|—|–|-)\s*(.+?)\s*$")


def network_vertices(obj: SceneObject) -> list[str]:
    """Vertex names (separated by commas or new lines; duplicates removed)."""
    names: list[str] = []
    for part in re.split(r"[,\n]", str(obj.params.get("vertices", ""))):
        name = part.strip()
        if name and name not in names:
            names.append(name)
    return names


def network_edges(obj: SceneObject) -> list[tuple[str, str]]:
    """Edges ``A-B`` / ``A->B`` (one per line or separated by commas)."""
    edges: list[tuple[str, str]] = []
    for part in re.split(r"[,\n]", str(obj.params.get("edges", ""))):
        match = _EDGE.match(part)
        if match and match.group(1) != match.group(3):
            edge = (match.group(1), match.group(3))
            if edge not in edges:
                edges.append(edge)
    return edges


def unknown_vertices(obj: SceneObject) -> list[str]:
    """Vertices used in edges that are not in the vertex list."""
    known = set(network_vertices(obj))
    return sorted({name for edge in network_edges(obj) for name in edge if name not in known})


def is_tree(vertices: list[str], edges: list[tuple[str, str]]) -> bool:
    if not vertices or len(edges) != len(vertices) - 1:
        return False
    neighbours: dict[str, set[str]] = {v: set() for v in vertices}
    for a, b in edges:
        if a in neighbours and b in neighbours:
            neighbours[a].add(b)
            neighbours[b].add(a)
    seen, stack = set(), [vertices[0]]
    while stack:
        vertex = stack.pop()
        if vertex in seen:
            continue
        seen.add(vertex)
        stack += list(neighbours[vertex] - seen)
    return len(seen) == len(vertices)


def _circle(vertices: list[str], scale: float) -> dict[str, tuple[float, float]]:
    count = len(vertices)
    return {v: (scale * math.cos(2 * math.pi * i / count + math.pi / 2), scale * math.sin(2 * math.pi * i / count + math.pi / 2)) for i, v in enumerate(vertices)}


def _tree(vertices: list[str], edges: list[tuple[str, str]], scale: float) -> dict[str, tuple[float, float]]:
    """Layered layout from the first vertex downwards (leaves spread evenly)."""
    neighbours: dict[str, list[str]] = {v: [] for v in vertices}
    for a, b in edges:
        neighbours[a].append(b)
        neighbours[b].append(a)
    root = vertices[0]
    depth = {root: 0}
    order = [root]
    children: dict[str, list[str]] = {v: [] for v in vertices}
    for vertex in order:
        for other in neighbours[vertex]:
            if other not in depth:
                depth[other] = depth[vertex] + 1
                children[vertex].append(other)
                order.append(other)
    slot = [0]
    x_of: dict[str, float] = {}

    def place(vertex: str) -> float:
        if not children[vertex]:
            x_of[vertex] = slot[0]
            slot[0] += 1
        else:
            xs = [place(child) for child in children[vertex]]
            x_of[vertex] = (xs[0] + xs[-1]) / 2
        return x_of[vertex]

    place(root)
    width = max(slot[0] - 1, 1)
    height = max(max(depth.values()), 1)
    return {v: (scale * (2 * x_of[v] / width - 1), scale * (1 - 2 * depth[v] / height)) for v in vertices}


def network_layout(obj: SceneObject) -> dict[str, tuple[float, float]]:
    """Vertex positions relative to the network's center (scene units).

    The positions are centered on their bounding box, because Manim's
    ``move_to`` (used by move animations) aligns that box's center.
    """
    positions = _raw_layout(obj)
    if not positions:
        return positions
    xs, ys = [x for x, _ in positions.values()], [y for _, y in positions.values()]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    return {v: (round(x - cx, 6), round(y - cy, 6)) for v, (x, y) in positions.items()}


def _raw_layout(obj: SceneObject) -> dict[str, tuple[float, float]]:
    vertices = network_vertices(obj)
    edges = [edge for edge in network_edges(obj) if edge[0] in vertices and edge[1] in vertices]
    scale = param_float(obj.params, "layout_scale", 2.0)
    layout = str(obj.params.get("layout", "circular"))
    if not vertices:
        return {}
    if len(vertices) == 1:
        return {vertices[0]: (0.0, 0.0)}
    if layout == "tree" and is_tree(vertices, edges):
        return _tree(vertices, edges, scale)
    if layout in ("circular", "tree"):
        return _circle(vertices, scale)
    try:
        import networkx as nx
    except ImportError:
        return _circle(vertices, scale)
    graph = nx.DiGraph() if obj.params.get("directed") else nx.Graph()
    graph.add_nodes_from(vertices)
    graph.add_edges_from(edges)
    functions = {
        "spring": lambda g: nx.spring_layout(g, scale=scale, seed=int(obj.params.get("seed", 1))),
        "kamada_kawai": lambda g: nx.kamada_kawai_layout(g, scale=scale),
        "shell": lambda g: nx.shell_layout(g, scale=scale),
        "spiral": lambda g: nx.spiral_layout(g, scale=scale),
    }
    try:
        positions = functions.get(layout, functions["spring"])(graph)
    except Exception:  # noqa: BLE001 - a layout that cannot handle this graph falls back to a circle
        return _circle(vertices, scale)
    return {v: (round(float(positions[v][0]), 6), round(float(positions[v][1]), 6)) for v in vertices}
