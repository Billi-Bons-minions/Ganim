"""Write the example projects in ``examples/`` (English names).

Run from the repository root after changing templates or the project format::

    python tools/make_examples.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from manim_studio.i18n import set_language  # noqa: E402

set_language("en")

from manim_studio.examples import circle_to_square  # noqa: E402
from manim_studio.model.entities import Project  # noqa: E402
from manim_studio.model.factory import create_animation, create_object, create_play_step, create_project, create_wait_step  # noqa: E402
from manim_studio.model.serialization import save_project  # noqa: E402
from manim_studio.model.types import AnimationKind, ObjectKind  # noqa: E402
from manim_studio.templates import BUILTIN_TEMPLATES  # noqa: E402


def from_templates(name: str, *keys: str) -> Project:
    """A project whose scenes are built-in templates."""
    project = create_project(name)
    project.scenes = [next(t for t in BUILTIN_TEMPLATES if t.key == key).build() for key in keys]
    return project


def coupling() -> Project:
    """A label follows a moving dot; a second dot runs on a circle driven by a parameter."""
    project = create_project("Coupled objects")
    scene = project.scenes[0]

    def add(obj):
        scene.objects.append(obj)
        return obj

    angle = add(create_object(ObjectKind.PARAMETER, "w", symbol="w", value=0.0, minimum=0.0, maximum=7.0))
    circle = add(create_object(ObjectKind.CIRCLE, "Orbit", 2.5, 0.0, radius=2.0))
    circle.stroke_color = "#888888"
    walker = add(create_object(ObjectKind.DOT, "P", -5.0, -2.5, radius=0.12))
    walker.fill_color = "#FC6255"
    label = add(create_object(ObjectKind.TEXT, "Label P", -5.0, -2.0, text="P", font_size=36.0))
    label.params.update(attach="follow", attach_target=walker.id)
    orbiter = add(create_object(ObjectKind.DOT, "Q", 4.5, 0.0, radius=0.12))
    orbiter.fill_color = "#83C167"
    orbiter.params.update(attach="formula", attach_x="2.5 + 2 cos(w)", attach_y="2 sin(w)")
    tag = add(create_object(ObjectKind.TEXT, "Label Q", 5.0, 0.0, text="Q", font_size=36.0))
    tag.params.update(attach="follow", attach_target=orbiter.id)
    scene.steps.append(create_play_step([create_animation(kind, target.id) for kind, target in ((AnimationKind.CREATE, circle), (AnimationKind.FADE_IN, walker), (AnimationKind.FADE_IN, label), (AnimationKind.FADE_IN, orbiter), (AnimationKind.FADE_IN, tag))]))
    scene.steps.append(
        create_play_step(
            [
                create_animation(AnimationKind.MOVE, walker.id, run_time=3.0, x=-1.0, y=2.5),
                create_animation(AnimationKind.SET_VALUE, angle.id, run_time=3.0, value=round(2 * math.pi, 5)),
            ]
        )
    )
    scene.steps.append(create_wait_step(1.0))
    return project


def polar_curves() -> Project:
    """A polar grid with a rose and a cardioid drawn one after the other."""
    project = create_project("Polar curves")
    scene = project.scenes[0]
    plane = create_object(ObjectKind.NUMBER_PLANE, "Polar grid", 0.0, 0.0, grid="polar", azimuth_divisions=12)
    plane.stroke_opacity = 0.6
    rose = create_object(ObjectKind.FUNCTION_GRAPH, "Rose", curve="polar", r_expression="3 cos(2t)", axes_id=plane.id)
    rose.stroke_color = "#FC6255"
    cardioid = create_object(ObjectKind.FUNCTION_GRAPH, "Cardioid", curve="polar", r_expression="1.5 (1 + cos(t))", axes_id=plane.id)
    cardioid.stroke_color = "#F7D96F"
    title = create_object(ObjectKind.TEXT, "Title", -4.4, 3.3, text="r = 3 cos(2θ)", font_size=36.0)
    title.fill_color = "#FC6255"
    title_2 = create_object(ObjectKind.TEXT, "Title 2", -4.4, 3.3, text="r = 1.5 (1 + cos θ)", font_size=36.0)
    title_2.fill_color = "#F7D96F"
    scene.objects += [plane, rose, cardioid, title, title_2]
    scene.steps.append(create_play_step([create_animation(AnimationKind.CREATE, plane.id, run_time=1.5)]))
    scene.steps.append(create_play_step([create_animation(AnimationKind.CREATE, rose.id, run_time=3.0), create_animation(AnimationKind.WRITE, title.id)]))
    scene.steps.append(
        create_play_step(
            [
                create_animation(AnimationKind.REPLACEMENT_TRANSFORM, rose.id, run_time=2.0, target=cardioid.id),
                create_animation(AnimationKind.REPLACEMENT_TRANSFORM, title.id, run_time=2.0, target=title_2.id),
            ]
        )
    )
    scene.steps.append(create_wait_step(1.0))
    return project


def vectors_in_space() -> Project:
    """Two vectors in space, their sum and a point, seen by an orbiting camera."""
    project = create_project("Vectors in space")
    scene = project.scenes[0]
    axes = create_object(ObjectKind.AXES_3D, "Space", 0.0, 0.0)
    a = create_object(ObjectKind.VECTOR_3D, "a", axes_id=axes.id, to_x=3.0, to_y=0.0, to_z=1.5)
    b = create_object(ObjectKind.VECTOR_3D, "b", axes_id=axes.id, from_x=3.0, from_y=0.0, from_z=1.5, to_x=3.0, to_y=3.0, to_z=3.0)
    b.stroke_color = b.fill_color = "#83C167"
    total = create_object(ObjectKind.VECTOR_3D, "a + b", axes_id=axes.id, to_x=3.0, to_y=3.0, to_z=3.0)
    total.stroke_color = total.fill_color = "#F7D96F"
    tip = create_object(ObjectKind.VECTOR_3D, "P", axes_id=axes.id, element="point", to_x=3.0, to_y=3.0, to_z=3.0, radius=0.1)
    tip.stroke_color = "#FFFFFF"
    camera = create_object(ObjectKind.CAMERA, "Camera", 0.0, 0.0)
    scene.objects += [axes, a, b, total, tip, camera]
    scene.steps.append(create_play_step([create_animation(AnimationKind.CREATE, axes.id, run_time=1.5)]))
    scene.steps.append(create_play_step([create_animation(AnimationKind.CREATE, a.id)]))
    scene.steps.append(create_play_step([create_animation(AnimationKind.CREATE, b.id)]))
    scene.steps.append(create_play_step([create_animation(AnimationKind.CREATE, total.id), create_animation(AnimationKind.FADE_IN, tip.id)]))
    scene.steps.append(create_play_step([create_animation(AnimationKind.ORBIT, camera.id, run_time=3.0, phi=65.0, theta=-110.0)]))
    return project


EXAMPLES = {
    "circle-to-square.msproj": circle_to_square,
    "function-analysis.msproj": lambda: from_templates("Function analysis", "analysis", "parameter", "secant"),
    "geometry.msproj": lambda: from_templates("Geometry", "pythagoras", "conics"),
    "graph-theory.msproj": lambda: from_templates("Graph theory", "network"),
    "linear-map.msproj": lambda: from_templates("Linear map", "linear_map"),
    "coupled-objects.msproj": coupling,
    "3d-and-fields.msproj": lambda: from_templates("3D and vector fields", "solids", "flow"),
    "polar-curves.msproj": polar_curves,
    "vectors-in-space.msproj": vectors_in_space,
}


def main() -> None:
    for name, build in EXAMPLES.items():
        save_project(build(), ROOT / "examples" / name)
        print("wrote", name)


if __name__ == "__main__":
    main()
