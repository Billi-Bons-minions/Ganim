"""Tests for step timing, playback state and timeline operations."""

from __future__ import annotations

import pytest

from manim_studio.model import operations as ops
from manim_studio.model.entities import STEP_LAGGED, STEP_SEQUENCE, Scene
from manim_studio.model.playback import state_at_time, step_at_time, step_end_time, step_spans, total_duration
from manim_studio.model.rate_functions import RATE_FUNCTION_IMPLEMENTATIONS, rate
from manim_studio.model.state import START, states_after
from manim_studio.model.types import RATE_FUNCTIONS, AnimationKind, ObjectKind
from tests.helpers import make_animation, make_object, play, wait


def scene() -> Scene:
    circle = make_object(ObjectKind.CIRCLE, "K", "c", 0.0, 0.0)
    square = make_object(ObjectKind.SQUARE, "Q", "q", 4.0, 0.0)
    first = play(make_animation(AnimationKind.CREATE, "c", "a1", run_time=1.0), step_id="s1")
    second = play(
        make_animation(AnimationKind.MOVE, "c", "a2", x=2.0, y=0.0, run_time=2.0),
        make_animation(AnimationKind.FADE_IN, "q", "a3", run_time=1.0),
        step_id="s2",
    )
    second.animations[1].delay = 1.0
    return Scene(id="s", name="S", objects=[circle, square], steps=[first, second, wait(0.5, "w")])


def test_step_windows_and_durations() -> None:
    sc = scene()
    assert sc.steps[1].windows() == [(0.0, 2.0), (1.0, 2.0)]
    assert step_spans(sc) == [(0.0, 1.0), (1.0, 3.0), (3.0, 3.5)]
    assert total_duration(sc) == 3.5
    sc.steps[1].mode = STEP_SEQUENCE
    assert sc.steps[1].windows() == [(0.0, 2.0), (3.0, 4.0)]
    sc.steps[1].mode, sc.steps[1].lag_ratio = STEP_LAGGED, 0.5
    assert sc.steps[1].windows() == [(0.0, 2.0), (1.0, 2.0)]
    assert sc.steps[1].duration() == 2.0


def test_step_lookup() -> None:
    sc = scene()
    assert step_at_time(sc, 0.0) == START
    assert step_at_time(sc, 0.5) == 0
    assert step_at_time(sc, 2.9) == 1
    assert step_at_time(sc, 99.0) == 2
    assert step_end_time(sc, 1) == 3.0 and step_end_time(sc, START) == 0.0


def test_state_during_playback() -> None:
    sc = scene()
    half_create = state_at_time(sc, 0.5)["c"]
    assert half_create.visible and half_create.draw == pytest.approx(rate("smooth", 0.5))
    mid_move = state_at_time(sc, 2.0)
    assert mid_move["c"].x == pytest.approx(2.0 * rate("smooth", 0.5))
    assert mid_move["q"].opacity == pytest.approx(0.0)
    late = state_at_time(sc, 2.5)
    assert late["q"].visible and late["q"].opacity == pytest.approx(rate("smooth", 0.5))
    end = state_at_time(sc, 10.0)
    assert end == states_after(sc, 2)


def test_rate_functions_match_manim() -> None:
    assert set(RATE_FUNCTION_IMPLEMENTATIONS) == set(RATE_FUNCTIONS)
    manim_rates = pytest.importorskip("manim.utils.rate_functions")
    for name in RATE_FUNCTIONS:
        reference = getattr(manim_rates, name)
        for t in (0.0, 0.1, 0.33, 0.5, 0.77, 1.0):
            assert rate(name, t) == pytest.approx(float(reference(t)), abs=1e-6), (name, t)


def test_timeline_operations() -> None:
    sc = scene()
    ops.set_animation_timing(sc, "a3", delay=-1.0, run_time=0.01)
    assert (sc.steps[1].animations[1].delay, sc.steps[1].animations[1].run_time) == (0.0, 0.05)
    copy_id = ops.duplicate_animation(sc, "a1")
    assert [a.id for a in sc.steps[0].animations] == ["a1", copy_id]
    ops.move_animation(sc, "a1", "s2")
    ops.move_animation(sc, copy_id, "s2", 0)
    assert [s.id for s in sc.steps] == ["s2", "w"]
    assert [a.id for a in sc.steps[0].animations] == [copy_id, "a2", "a3", "a1"]
    new_step = ops.move_animation_to_new_step(sc, "a3", 0)
    assert sc.steps[0].id == new_step and [a.id for a in sc.steps[0].animations] == ["a3"]
    ops.set_step_mode(sc, new_step, STEP_LAGGED, 2.0)
    assert (sc.steps[0].mode, sc.steps[0].lag_ratio) == (STEP_LAGGED, 1.0)
    with pytest.raises(ops.ModelError):
        ops.move_animation(sc, "a2", "w")
