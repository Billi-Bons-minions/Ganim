"""Aligning, distributing and layer order (pure functions on the model)."""

from __future__ import annotations

from manim_studio.model import groups
from manim_studio.model.entities import Scene
from manim_studio.model.types import FRAME_HEIGHT, FRAME_WIDTH

#: ``(left, bottom, right, top)`` in Manim units.
Box = tuple[float, float, float, float]

ALIGN_LEFT = "left"
ALIGN_HCENTER = "hcenter"
ALIGN_RIGHT = "right"
ALIGN_TOP = "top"
ALIGN_VCENTER = "vcenter"
ALIGN_BOTTOM = "bottom"
DISTRIBUTE_H = "distribute_h"
DISTRIBUTE_V = "distribute_v"
ALIGN_MODES = (ALIGN_LEFT, ALIGN_HCENTER, ALIGN_RIGHT, ALIGN_TOP, ALIGN_VCENTER, ALIGN_BOTTOM)
DISTRIBUTE_MODES = (DISTRIBUTE_H, DISTRIBUTE_V)

FRAME_BOX: Box = (-FRAME_WIDTH / 2, -FRAME_HEIGHT / 2, FRAME_WIDTH / 2, FRAME_HEIGHT / 2)


def _union(boxes: list[Box]) -> Box:
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _align_delta(box: Box, reference: Box, mode: str) -> tuple[float, float]:
    left, bottom, right, top = box
    r_left, r_bottom, r_right, r_top = reference
    if mode == ALIGN_LEFT:
        return r_left - left, 0.0
    if mode == ALIGN_RIGHT:
        return r_right - right, 0.0
    if mode == ALIGN_HCENTER:
        return (r_left + r_right) / 2 - (left + right) / 2, 0.0
    if mode == ALIGN_TOP:
        return 0.0, r_top - top
    if mode == ALIGN_BOTTOM:
        return 0.0, r_bottom - bottom
    return 0.0, (r_bottom + r_top) / 2 - (bottom + top) / 2


def _distribute(boxes: dict[str, Box], horizontal: bool) -> dict[str, tuple[float, float]]:
    """Equal gaps between neighbours; the outermost objects stay in place."""
    low, high = (0, 2) if horizontal else (1, 3)
    ordered = sorted(boxes, key=lambda object_id: (boxes[object_id][low] + boxes[object_id][high]) / 2)
    first, last = boxes[ordered[0]], boxes[ordered[-1]]
    sizes = sum(boxes[object_id][high] - boxes[object_id][low] for object_id in ordered)
    gap = (last[high] - first[low] - sizes) / (len(ordered) - 1)
    deltas: dict[str, tuple[float, float]] = {}
    position = first[low]
    for object_id in ordered:
        box = boxes[object_id]
        shift = round(position - box[low], 6)
        deltas[object_id] = (shift, 0.0) if horizontal else (0.0, shift)
        position += box[high] - box[low] + gap
    return deltas


def arrange_deltas(boxes: dict[str, Box], mode: str, frame: Box | None = None) -> dict[str, tuple[float, float]]:
    """Return the move per object for an align or distribute command.

    A single object is aligned to the video frame; several objects to their
    common bounding box. Distributing needs at least three objects.
    """
    if not boxes:
        return {}
    if mode in DISTRIBUTE_MODES:
        if len(boxes) < 3:
            return {}
        return _distribute(boxes, mode == DISTRIBUTE_H)
    reference = (frame or FRAME_BOX) if len(boxes) == 1 else _union(list(boxes.values()))
    deltas = {}
    for object_id, box in boxes.items():
        dx, dy = _align_delta(box, reference, mode)
        deltas[object_id] = (round(dx, 6), round(dy, 6))
    return deltas


# --- layer order ----------------------------------------------------------------


def drawing_order(scene: Scene) -> list[str]:
    """Return the non-group objects from back to front (``z_index``, then list order)."""
    entries = [(obj.z_index, index, obj.id) for index, obj in enumerate(scene.objects) if not groups.is_group(obj)]
    return [object_id for _z, _index, object_id in sorted(entries)]


def layer_key(scene: Scene, object_id: str, order: list[str] | None = None) -> int:
    """Return the drawing position of an object (groups: their front-most member)."""
    order = order if order is not None else drawing_order(scene)
    positions = [order.index(leaf) for leaf in groups.leaves(scene, object_id) if leaf in order]
    return max(positions, default=-1)


def move_layer(scene: Scene, object_id: str, below_id: str | None, above_id: str | None) -> None:
    """Place an object (or a whole group) directly in front of ``below_id`` or behind ``above_id``.

    Only the moved objects change: they take over the ``z_index`` of the
    reference object and are moved next to it in the object list.
    """
    block = [leaf for leaf in drawing_order(scene) if leaf in set(groups.leaves(scene, object_id))]
    if below_id is not None:
        reference_ids = groups.leaves(scene, below_id)
        order = drawing_order(scene)
        reference = max(reference_ids, key=order.index) if reference_ids else None
        after = True
    elif above_id is not None:
        reference_ids = groups.leaves(scene, above_id)
        order = drawing_order(scene)
        reference = min(reference_ids, key=order.index) if reference_ids else None
        after = False
    else:
        return
    if reference is None or reference in block or not block:
        return
    anchor = scene.object_by_id(reference)
    assert anchor is not None
    moved = [scene.object_by_id(leaf) for leaf in block]
    scene.objects = [obj for obj in scene.objects if obj.id not in block]
    index = scene.objects.index(anchor) + (1 if after else 0)
    for offset, obj in enumerate(moved):
        assert obj is not None
        obj.z_index = anchor.z_index
        scene.objects.insert(index + offset, obj)
