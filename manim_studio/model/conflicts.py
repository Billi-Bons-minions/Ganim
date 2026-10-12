"""Animations that Manim cannot play in the same step, with knowledge of the scene.

Besides the rules for one object (:func:`manim_studio.model.types.simultaneous_conflicts`),
an object that Manim rebuilds from a parameter (a number shown next to a slider, a graph
``a·sin(x)``, a point with its coordinates ...) must not be animated while that parameter
changes: its parts change in number during the animation (e.g. ``9.99`` → ``10.00``) and
Manim stops with an error.
"""

from __future__ import annotations

from manim_studio.model import groups
from manim_studio.model.entities import Animation, Scene
from manim_studio.model.factory import ANIMATION_REFERENCE_KEYS
from manim_studio.model.types import DETACHED_EFFECTS, AnimationKind, simultaneous_conflicts


def parameter_conflicts(scene: Scene, animations: list[Animation]) -> set[str]:
    """Objects animated in the same step in which a parameter they depend on changes."""
    from manim_studio.model.graphs import parameter_users

    changing = {anim.target_id for anim in animations if anim.kind == AnimationKind.SET_VALUE}
    if not changing:
        return set()
    found: set[str] = set()
    for anim in animations:
        if anim.kind == AnimationKind.SET_VALUE or anim.kind in DETACHED_EFFECTS:
            continue
        involved = [anim.target_id] + [str(anim.params[key]) for key in ANIMATION_REFERENCE_KEYS if anim.params.get(key)]
        for object_id in involved:
            leaves = groups.leaves(scene, object_id) if groups.is_group(scene.object_by_id(object_id)) else [object_id]
            if any((obj := scene.object_by_id(leaf)) is not None and parameter_users(scene, obj) & changing for leaf in leaves):
                found.add(object_id)
    return found


def lens_conflicts(scene: Scene, animations: list[Animation]) -> set[str]:
    """The zoom lens pops out and fades with its own code, so it takes one animation per step."""
    from manim_studio.model.types import ObjectKind

    lenses = [anim.target_id for anim in animations if (obj := scene.object_by_id(anim.target_id)) is not None and obj.kind == ObjectKind.ZOOM_LENS]
    return {object_id for object_id in lenses if lenses.count(object_id) > 1}


def step_conflicts(scene: Scene, animations: list[Animation]) -> set[str]:
    """All objects whose animations cannot run together in one step."""
    return simultaneous_conflicts(animations) | parameter_conflicts(scene, animations) | lens_conflicts(scene, animations)
