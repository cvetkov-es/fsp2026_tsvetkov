from datetime import UTC, datetime, timedelta

import pytest

from app.assessment.engine.levels import Grade, Thresholds
from app.assessment.engine.rules import (
    AttemptConfig,
    Decision,
    ItemResult,
    autoclose,
    evaluate,
    strength,
)
from app.config.params import PARAMS

T = Thresholds.from_params(PARAMS)
CUT_M = T.cut(Grade.middle)


def cfg(express=False, target=Grade.middle):
    return AttemptConfig(target=target, thresholds=T,
                         item_cap=PARAMS.express_max if express else PARAMS.test_max, express=express)


def items(pattern, b, phase=1, start=1):
    return [ItemResult(seq=start + i, family_code=f"f{start + i}", area="db", level=3, b=b,
                       correct=bool(c), phase=phase) for i, c in enumerate(pattern)]


def test_no_decision_before_n_min_even_if_all_correct():
    ev = evaluate(cfg(), items([1] * 5, CUT_M))
    assert ev.decision is None and ev.status == "phase1" and ev.n_answered == 5


def test_all_correct_confirms_exactly_at_six():
    ev = evaluate(cfg(), items([1] * 6, CUT_M))
    assert ev.decision == Decision.confirmed and ev.decided_at == 6
    assert ev.status == "transition" and ev.phase2_total == PARAMS.test_min - 6


def test_all_wrong_and_timeouts_not_confirmed_at_six():
    ev = evaluate(cfg(), items([0] * 6, CUT_M))
    assert ev.decision == Decision.not_confirmed and ev.status == "finished" and ev.phase2_total == 0


def test_phase2_does_not_change_decision():
    it = items([1] * 6, CUT_M) + items([0] * 4, T.cut(Grade.senior), phase=2, start=7)
    ev = evaluate(cfg(), it)
    assert ev.decision == Decision.confirmed and ev.decided_at == 6 and ev.status == "finished"
    assert ev.confident is False  # фаза 2 провалена: «уверенно» нет, но статус остался


def test_confident_after_strong_phase2_but_never_for_senior():
    it = items([1] * 6, CUT_M) + items([1] * 4, T.cut(Grade.senior), phase=2, start=7)
    assert evaluate(cfg(), it).confident is True
    cut_s = T.cut(Grade.senior)
    it_s = items([1] * 6, cut_s) + items([1] * 4, T.next_cut(Grade.senior), phase=2, start=7)
    ev_s = evaluate(cfg(target=Grade.senior), it_s)
    assert ev_s.decision == Decision.confirmed and ev_s.confident is False


def test_phase2_in_progress_status():
    it = items([1] * 6, CUT_M) + items([1], T.cut(Grade.senior), phase=2, start=7)
    assert evaluate(cfg(), it).status == "phase2"


def test_express_undecided_at_cap_awaits_continue():
    ev = evaluate(cfg(express=True), items([1, 0] * 4, CUT_M))
    assert ev.decision is None and ev.status == "awaiting_continue"


def test_express_phase2_capped_by_express_max():
    ev = evaluate(cfg(express=True), items([1] * 6, CUT_M))
    assert ev.phase2_total == PARAMS.express_max - 6


def test_full_undecided_at_max_is_border_decision():
    ev = evaluate(cfg(), items([1, 0] * 7 + [1], CUT_M))
    assert ev.border is True and ev.decision is not None and ev.status == "finished"


T0 = datetime(2026, 10, 9, 10, 0, tzinfo=UTC)
LATE = T0 + timedelta(hours=PARAMS.attempt_autoclose_hours, seconds=1)


def test_autoclose_not_due_yet():
    assert autoclose(cfg(), items([1] * 3, CUT_M), T0, T0 + timedelta(hours=1)) is None


def test_autoclose_incomplete_below_n_min():
    r = autoclose(cfg(), items([1], CUT_M), T0, LATE)
    assert r.outcome == "incomplete" and r.decision is None


def test_autoclose_border_decision_when_enough_answers():
    r = autoclose(cfg(), items([1, 0, 1, 0, 1, 0, 1], CUT_M), T0, LATE)
    assert r.outcome == "autoclosed" and r.border is True and r.decision is not None


def test_autoclose_keeps_fixed_status():
    r = autoclose(cfg(), items([1] * 6, CUT_M), T0, LATE)  # подтверждён, фаза 2 не пройдена
    assert r.outcome == "completed" and r.decision == Decision.confirmed and r.border is False


def test_autoclose_finished_attempt_untouched():
    assert autoclose(cfg(), items([0] * 6, CUT_M), T0, LATE) is None


def test_strength_clipped_and_monotonic():
    assert strength(5.0, 0.3, 0.71, 1.71, 0.5) == 1.0
    assert strength(-5.0, 0.3, 0.71, 1.71, 0.5) == 0.0
    assert strength(0.71, 0.0, 0.71, 1.71, 0.5) == pytest.approx(0.5)
    assert strength(1.2, 0.3, 0.71, 1.71, 0.5) < strength(1.4, 0.3, 0.71, 1.71, 0.5)
