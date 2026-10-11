from datetime import timedelta
from types import SimpleNamespace

from app.common import clock
from app.config.params import PARAMS
from app.hiring.service import can_move
from app.hiring.votes import Holder, add_months, interview_m, stats, vote_state, vote_weight

T = clock.now()


def test_m_only_boosts_and_matches_control_case_3():
    assert interview_m([("below", 1.0)] * 3) == 1.0  # «ниже» не опускают ниже нейтрального
    assert abs(interview_m([("meets", 1.0)] * 3) - 1.12) < 1e-9  # процесс 6.4, случай 3
    assert interview_m([]) == 1.0
    mixed = interview_m([("meets", 1.0), ("below", 1.0), ("meets", 1.0)])
    assert 1 < mixed < interview_m([("meets", 1.0)] * 3)
    assert interview_m([("above", 1.0)] * 50) <= 1 + PARAMS.m_boost


def test_badge_needs_three_positive_and_two_thirds():
    assert stats([("meets", 1.0)] * 3).badge()
    assert not stats([("meets", 1.0)] * 2).badge()
    assert stats([("meets", 1.0)] * 4 + [("below", 1.0)] * 2).badge()  # 4 из 6 — ровно 2/3
    assert not stats([("meets", 1.0)] * 3 + [("below", 1.0)] * 2).badge()  # 3 из 5 < 2/3


def test_weight_by_trust_level():
    assert vote_weight("L0") is None
    assert vote_weight("L1") == PARAMS.vote_w_l1 and vote_weight("L2") == vote_weight("L3") == PARAMS.vote_w_l2


def V(status="pending", eff=None, spec="backend", grade="middle", answered=None):
    eff = eff or T + timedelta(days=PARAMS.vote_dispute_days)
    return SimpleNamespace(status=status, effective_at=eff, spec_at_vote=spec, grade_at_vote=grade,
                           answered_at=answered or eff - timedelta(days=PARAMS.vote_dispute_days))


def test_states_are_computed_at_read_time():
    h = Holder("backend", "middle")
    eff = T + timedelta(days=PARAMS.vote_dispute_days)
    assert vote_state(V(), h, T) == "pending"
    assert vote_state(V(), h, eff) == "active"
    assert vote_state(V("upheld"), h, T) == "active"
    assert vote_state(V("disputed"), h, eff) == "disputed"
    assert vote_state(V(), Holder("backend", "senior"), eff) == "archived"  # смена грейда
    assert vote_state(V(), Holder("frontend", "middle"), eff) == "archived"  # смена специализации
    assert vote_state(V(), Holder("backend", "middle", changed_at=T + timedelta(hours=1)), eff) == "archived"  # навсегда
    assert vote_state(V(), h, add_months(eff, PARAMS.vote_ttl_months)) == "expired"


def test_months_are_calendar_months():
    jan31 = T.replace(year=2027, month=1, day=31)
    assert add_months(jan31, 1).day == 28 and add_months(jan31, 13).month == 2 and add_months(jan31, -2).month == 11


def test_stages_go_forward_and_finals_can_be_reanswered():
    assert can_move(None, "first") and can_move(None, "hired") and can_move("first", "technical")
    assert not can_move("offer", "technical") and not can_move("first", "first")
    assert can_move("technical", "technical") and can_move("offer", "rejected")
    assert can_move("rejected", "rejected") and not can_move("hired", "offer") and not can_move("hired", "rejected")
