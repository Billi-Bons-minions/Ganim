"""Limited 3D: projection, geometry, code and checks."""

from __future__ import annotations

import math

import pytest

from manim_studio.codegen import CodegenOptions, generate_script
from manim_studio.model.entities import Scene
from manim_studio.model.playback import state_at_time
from manim_studio.model.three_d import View, curve_points, is_3d, project, surface_grid, to_space, view_of
from manim_studio.model.types import AnimationKind, ObjectKind
from manim_studio.model.validation import has_errors, validate_scene
from tests.helpers import make_animation, make_object, make_project, play


def space_scene() -> Scene:
    axes = make_object(ObjectKind.AXES_3D, "Achsen", "ax")
    surface = make_object(ObjectKind.SURFACE, "Fläche", "s", axes_id="ax", expression="x y", resolution=4)
    curve = make_object(ObjectKind.CURVE_3D, "Spirale", "k", axes_id="ax")
    title = make_object(ObjectKind.TEXT, "Titel", "t", 0.0, 3.0)
    camera = make_object(ObjectKind.CAMERA, "Kamera", "cam", phi=60.0, theta=-30.0)
    steps = [play(make_animation(AnimationKind.ORBIT, "cam", "o", phi=80.0, theta=30.0, run_time=2.0), make_animation(AnimationKind.CREATE, "s"))]
    return Scene(id="r", name="Raum", objects=[axes, surface, curve, title, camera], steps=steps)


def test_projection_matches_manim_defaults() -> None:
    top = project([(1.0, 2.0, 0.0)], View(phi=0.0, theta=-90.0))
    assert top[0] == pytest.approx((1.0, 2.0))
    tilted = project([(3.0, 0.0, 0.0)], View(phi=60.0, theta=20.0))[0]
    assert tilted == pytest.approx((-1.1689, -1.6060), abs=1e-3)


def test_geometry_and_camera_view() -> None:
    scene = space_scene()
    assert is_3d(scene)
    axes = scene.object_by_id("ax")
    assert to_space(axes, 4.0, 0.0, 3.0) == pytest.approx((3.0, 0.0, 2.0))
    grid = surface_grid(scene, scene.object_by_id("s"))
    assert len(grid) == 10 and grid[0][0][2] == pytest.approx(to_space(axes, 0, 0, 9.0)[2])
    assert len(curve_points(scene, scene.object_by_id("k"))) > 100
    assert view_of(scene) == View(60.0, -30.0, 1.0)
    middle = state_at_time(scene, 1.0)["cam"]
    assert 60.0 < middle.phi < 80.0 and -30.0 < middle.theta < 30.0


def test_three_d_code() -> None:
    code = generate_script(make_project(space_scene()), CodegenOptions())
    assert "class Raum(ThreeDScene):" in code
    assert "self.set_camera_orientation(phi=60.0 * DEGREES, theta=-30.0 * DEGREES)" in code
    assert "achsen = ThreeDAxes(" in code and "lambda x, y: achsen.c2p(x, y, x * y)" in code
    assert "self.renderer.camera.add_fixed_in_frame_mobjects(titel)" in code
    assert "self.move_camera(phi=80.0 * DEGREES, theta=30.0 * DEGREES, run_time=2.0, rate_func=smooth, added_anims=[Create(" in code
    assert "self.camera.frame.animate" not in code and "self.camera.frame.move_to" not in code


def test_three_d_checks() -> None:
    scene = space_scene()
    scene.objects[1].params["axes_id"] = None
    scene.steps.append(play(make_animation(AnimationKind.MOVE, "cam", "m", x=1.0, y=0.0), make_animation(AnimationKind.ROTATE, "cam", "r", angle=20.0)))
    codes = {issue.code for issue in validate_scene(scene)}
    assert "axes_3d_missing" in codes and "camera_rotation_2d" not in codes
    flat = Scene(id="f", name="F", objects=[make_object(ObjectKind.CAMERA, "K", "c")], steps=[play(make_animation(AnimationKind.ORBIT, "c"), make_animation(AnimationKind.ROTATE, "c", "r"))])
    assert {"orbit_needs_3d", "camera_rotation_2d"} <= {issue.code for issue in validate_scene(flat)}
    assert math.isfinite(project([(0.0, 0.0, 100.0)], View())[0][0])


def test_solids() -> None:
    from manim_studio.codegen import generate_script
    from manim_studio.model.schema import animation_allowed
    from manim_studio.model.three_d import solid_quads

    axes = make_object(ObjectKind.AXES_3D, "Achsen", "ax", x_min=-4.0, x_max=4.0, x_length=8.0, y_min=-4.0, y_max=4.0, y_length=8.0)
    shapes = ["sphere", "cube", "prism", "cone", "cylinder", "torus"]
    solids = [make_object(ObjectKind.SOLID, f"K{i}", f"k{i}", axes_id="ax", shape=shape, center_x=1.0, center_z=0.5) for i, shape in enumerate(shapes)]
    scene = Scene(id="s", name="Koerper", objects=[axes, *solids], steps=[play(make_animation(AnimationKind.SCALE, "k0", factor=1.5))])
    sphere = [point for quad in solid_quads(scene, solids[0]) for point in quad]
    assert min(p[0] for p in sphere) == pytest.approx(0.0) and max(p[0] for p in sphere) == pytest.approx(2.0)
    cone = [point for quad in solid_quads(scene, solids[3]) for point in quad]
    center_z = to_space(axes, 1.0, 0.0, 0.5)[2]  # the z axis is scaled by its length
    assert max(p[2] for p in cone) == pytest.approx(center_z + 1.0) and min(p[2] for p in cone) == pytest.approx(center_z - 1.0)
    assert len(solid_quads(scene, solids[1])) == 6
    assert not has_errors(validate_scene(scene))
    code = generate_script(make_project(scene))
    assert "k0 = Sphere(" in code and ".move_to(achsen.c2p(1.0, 0.0, 0.5))" in code and "Cone(" in code and "show_base=True" in code
    assert not animation_allowed(AnimationKind.MOVE, ObjectKind.SOLID, {}) and animation_allowed(AnimationKind.SCALE, ObjectKind.SOLID, {})


@pytest.mark.parametrize(
    ("shape", "faces", "corners", "circumradius"),
    [
        ("tetrahedron", 4, 4, math.sqrt(6) / 4),
        ("octahedron", 8, 6, 1 / math.sqrt(2)),
        ("icosahedron", 20, 12, math.sin(2 * math.pi / 5)),
        ("dodecahedron", 12, 20, math.sqrt(3) * (1 + math.sqrt(5)) / 4),
    ],
)
def test_platonic_solids(shape, faces, corners, circumradius) -> None:
    from manim_studio.model.three_d import solid_quads, solid_vertices

    axes = make_object(ObjectKind.AXES_3D, "Raum", "r")
    solid = make_object(ObjectKind.SOLID, "Körper", "k", axes_id="r", shape=shape, side=2.0, center_x=1.0)
    scene = Scene(id="s", name="S", objects=[axes, solid])
    center = to_space(axes, 1.0, 0.0, 0.0)
    vertices = solid_vertices(scene, solid)
    assert len(solid_quads(scene, solid)) == faces and len(vertices) == corners
    assert all(math.dist(vertex, center) == pytest.approx(2.0 * circumradius) for vertex in vertices)
    # all edges of a face are edges of the solid (length 2)
    for face in solid_quads(scene, solid):
        assert all(math.dist(face[i], face[(i + 1) % len(face)]) == pytest.approx(2.0) for i in range(len(face)))
    code = generate_script(make_project(scene))
    name = shape.capitalize()
    assert f"{name}(" in code and "edge_length=2.0" in code and '"fill_opacity": 0.75' in code
    assert '"vertex_config": {"fill_opacity": 0, "stroke_width": 0}' in code  # corners hidden
    solid.params["show_vertices"] = True
    assert '"vertex_config": {"radius": 0.08, "color": "#29ABCA"}' in generate_script(make_project(scene))
    assert not has_errors(validate_scene(scene))


def test_vectors_lines_and_points_in_space() -> None:
    from manim_studio.model import operations as ops
    from manim_studio.model.graphs import is_bound
    from manim_studio.model.schema import animation_allowed
    from manim_studio.model.three_d import vector_points

    axes = make_object(ObjectKind.AXES_3D, "Raum", "r")
    arrow = make_object(ObjectKind.VECTOR_3D, "v", "v", axes_id="r", to_x=1.0, to_y=2.0, to_z=3.0)
    line = make_object(ObjectKind.VECTOR_3D, "s", "s", axes_id="r", element="line", from_x=1.0)
    point = make_object(ObjectKind.VECTOR_3D, "p", "p", axes_id="r", element="point", to_x=-1.0, to_y=0.0, to_z=1.0)
    scene = Scene(id="s", name="S", objects=[axes, arrow, line, point], steps=[play(make_animation(AnimationKind.CREATE, "v"))])
    assert is_3d(scene) and is_bound(scene, arrow) and not has_errors(validate_scene(scene))
    assert vector_points(scene, arrow) == [to_space(axes, 0.0, 0.0, 0.0), to_space(axes, 1.0, 2.0, 3.0)]
    assert vector_points(scene, point) == [to_space(axes, -1.0, 0.0, 1.0)]
    code = "".join(generate_script(make_project(scene)).split())  # calls may be wrapped over several lines
    assert "v=Arrow3D(start=raum.c2p(0.0,0.0,0.0),end=raum.c2p(1.0,2.0,3.0)" in code
    assert "s=Line3D(start=raum.c2p(1.0,0.0,0.0),end=raum.c2p(2.0,1.0,2.0)" in code
    assert "p=Dot3D(point=raum.c2p(-1.0,0.0,1.0),radius=0.08" in code
    assert not animation_allowed(AnimationKind.MOVE, ObjectKind.VECTOR_3D, {}) and animation_allowed(AnimationKind.SCALE, ObjectKind.VECTOR_3D, {})
    ops.remove_objects(scene, ["r"])  # without its axes a vector cannot exist
    assert scene.objects == []


def test_a_new_3d_vector_brings_its_axes(window) -> None:
    controller = window.controller
    vector = controller.add_object(ObjectKind.VECTOR_3D)
    scene = window.editor.scene()
    axes = [obj for obj in scene.objects if obj.kind == ObjectKind.AXES_3D]
    assert len(axes) == 1 and scene.object_by_id(vector).params["axes_id"] == axes[0].id
