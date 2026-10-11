import random
from datetime import UTC, datetime, timedelta

import pytest

from app.config.params import PARAMS
from app.matching.scoring import (
    CandidateFacts,
    NeedFacts,
    accept,
    evaluate_candidate,
    fit,
    rank,
    stack_score,
    strength_r,
    to_net,
)

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


def cand(ref="c", status="confirmed", grade="middle", s=0.6, f=0.0, stack=None, **kw):
    kw.setdefault("open_until", NOW + timedelta(days=5))
    kw.setdefault("last_activity_at", NOW - timedelta(days=1))
    return CandidateFacts(ref=ref, specialization="backend", grade_status=status,
                          confirmed_grade=grade if status == "confirmed" else None, claimed_grade=grade,
                          theta=1.0, se=0.4, s=s, fsp_f=f, stack=stack or {}, **kw)


NEED = NeedFacts("backend", ("middle",), ("Python", "PostgreSQL", "Docker"), ("Kafka",), ("remote",), to_net(300000, "gross"))


def test_case1_strong_test_without_fsp_beats_weak_test_with_fsp():
    a, b = cand(s=0.79), cand(s=0.51, f=0.74)
    assert strength_r(a) == pytest.approx(0.79) and strength_r(b) == pytest.approx(0.61, abs=0.01)


def test_case2_confirmed_two_of_three_beats_declared_full_stack():
    s_for_r = 0.55 * PARAMS.r_max  # R̂ = 0.55 при f = 0, m = 1
    c = cand(s=s_for_r, stack={"Python": "confirmed", "PostgreSQL": "confirmed"})
    d = cand(s=s_for_r, stack={"Python": "declared", "PostgreSQL": "declared", "Docker": "declared"})
    need = NeedFacts("backend", ("middle",), ("Python", "PostgreSQL", "Docker"))
    fc, fd = fit(c, need, stack_score(c, need)), fit(d, need, stack_score(d, need))
    assert fc == pytest.approx(0.547, abs=0.002) and fd == pytest.approx(0.525, abs=0.002) and fc > fd


def test_unknown_stack_neutral_no_penalty_no_conflict():
    r = evaluate_candidate(cand(), NEED, NOW)
    assert r.stack.value == PARAMS.stack_unknown and r.block == 1 and r.conflicts == ()


def test_undeclared_stack_is_unknown_even_with_test_confirmed_core():
    c = cand(stack={"SQL": "confirmed", "Python": "confirmed"}, stack_declared=False)
    r = evaluate_candidate(c, NEED, NOW)
    assert not r.stack.known and r.stack.value == PARAMS.stack_unknown and r.conflicts == ()


def test_two_missing_must_is_hard_conflict_block4():
    r = evaluate_candidate(cand(stack={"Python": "declared"}), NEED, NOW)
    assert r.block == 4 and "must" in r.conflicts


def test_format_conflict_and_hybrid_compatibility():
    office_only = cand(formats=("office",))
    assert evaluate_candidate(office_only, NEED, NOW).conflicts == ("format",)
    hybrid = cand(formats=("hybrid",))
    r = evaluate_candidate(hybrid, NEED, NOW)
    assert r.conflicts == () and r.accept.format == PARAMS.format_compatible


def test_salary_gap_linear_and_conflict():
    fork_net = to_net(300000, "gross")
    ok = accept(cand(salary_threshold_net=fork_net), NEED, NOW)
    assert ok.salary == 1.0
    mid = accept(cand(salary_threshold_net=round(fork_net / 0.9)), NEED, NOW)
    assert 0 < mid.salary < 1
    far = evaluate_candidate(cand(salary_threshold_net=fork_net * 2), NEED, NOW)
    assert far.block == 4 and "salary" in far.conflicts


def test_need_without_must_or_formats_works():
    need = NeedFacts("backend", ("middle",), ())
    r = evaluate_candidate(cand(stack={"Python": "declared"}), need, NOW)
    assert r.block == 1 and r.stack.value == pytest.approx(PARAMS.stack_unknown) and r.accept.format is None


def test_signal_raises_accept_floor():
    c = cand(open_until=NOW - timedelta(days=1), last_activity_at=NOW - timedelta(days=90), signal_to_company=True)
    assert accept(c, NEED, NOW).value >= PARAMS.signal_floor_ok


def test_blocks_and_subblocks_multi_grade_need():
    need = NeedFacts("backend", ("middle", "senior"), ())
    sen, mid = cand("s", grade="senior", s=0.3), cand("m", grade="middle", s=0.9)
    jun, unc = cand("j", grade="junior", s=0.99), cand("u", status="not_confirmed", grade="middle", s=0.99)
    order = [r.c.ref for r in rank([unc, jun, mid, sen], need, NOW)]
    assert order == ["s", "m", "j", "u"]


def test_unconfirmed_never_above_confirmed_property():
    rnd = random.Random(7)
    cands = [cand(f"c{i}", status=rnd.choice(["confirmed", "not_confirmed"]), s=rnd.random(),
                  f=rnd.random(), grade=rnd.choice(["junior", "middle", "senior"])) for i in range(200)]
    ranked = rank(cands, NeedFacts("backend", ("middle",), ()), NOW)
    blocks = [r.block for r in ranked]
    assert blocks == sorted(blocks)
    first_unconf = next((i for i, r in enumerate(ranked) if r.c.grade_status == "not_confirmed"), len(ranked))
    assert all(r.c.grade_status == "confirmed" for r in ranked[:first_unconf])


def test_not_tested_and_far_grades_excluded():
    need = NeedFacts("backend", ("senior",), ())
    assert evaluate_candidate(cand(grade="junior"), need, NOW) is None
    assert evaluate_candidate(cand(status="not_tested"), need, NOW) is None


def test_ndfl_comes_from_params():
    from app.matching import scoring

    assert scoring.NDFL == PARAMS.ndfl == 0.13 and to_net(100000, "gross") == 87000
