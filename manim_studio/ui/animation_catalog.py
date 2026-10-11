"""Animation kinds offered in menus and in the inspector, grouped by purpose."""

from __future__ import annotations

from manim_studio.model.types import AnimationKind

ANIMATION_GROUPS: tuple[tuple[str, tuple[AnimationKind, ...]], ...] = (
    (
        "appear",
        (
            AnimationKind.CREATE,
            AnimationKind.WRITE,
            AnimationKind.FADE_IN,
            AnimationKind.GROW_FROM_CENTER,
            AnimationKind.SPIN_IN,
            AnimationKind.DRAW_BORDER_THEN_FILL,
            AnimationKind.ADD_LETTERS,
            AnimationKind.GROW_ARROW,
        ),
    ),
    (
        "change",
        (
            AnimationKind.MOVE,
            AnimationKind.SCALE,
            AnimationKind.ROTATE,
            AnimationKind.CHANGE_COLOR,
            AnimationKind.MOVE_ALONG_PATH,
            AnimationKind.SWAP,
            AnimationKind.SET_VALUE,
            AnimationKind.ORBIT,
        ),
    ),
    ("transform", (AnimationKind.TRANSFORM, AnimationKind.REPLACEMENT_TRANSFORM, AnimationKind.FADE_TRANSFORM, AnimationKind.TRANSFORM_MATCHING)),
    (
        "emphasize",
        (
            AnimationKind.INDICATE,
            AnimationKind.CIRCUMSCRIBE,
            AnimationKind.FLASH,
            AnimationKind.WIGGLE,
            AnimationKind.APPLY_WAVE,
            AnimationKind.FOCUS_ON,
        ),
    ),
    ("disappear", (AnimationKind.FADE_OUT, AnimationKind.UNCREATE, AnimationKind.SHRINK_TO_CENTER)),
)

#: Buttons that are hidden (instead of disabled) where they do not apply.
ONLY_WHEN_ALLOWED = frozenset({AnimationKind.SET_VALUE, AnimationKind.ADD_LETTERS, AnimationKind.GROW_ARROW, AnimationKind.ORBIT})
