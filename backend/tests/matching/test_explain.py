import random
import time
from datetime import UTC, datetime, timedelta

from app.matching.explain import NO_FSP, counterfactual, counterfactuals, explain
from app.matching.scoring import CandidateFacts, NeedFacts, evaluate_candidate, rank

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
NEED = NeedFacts("backend", ("middle",), ("Python", "Docker"), ("Kafka",), ("remote",), 250000)


def c(ref, s, stack, **kw):
    base = dict(specialization="backend", grade_status="confirmed", confirmed_grade="middle", claimed_grade="middle",
                theta=1.0, se=0.4, open_until=NOW + timedelta(days=3), last_activity_at=NOW)
    base.update(kw)
    return CandidateFacts(ref=ref, s=s, stack=stack, **base)


def test_three_lines_with_facts_and_neutral_no_fsp():
    r = evaluate_candidate(c("a", 0.8, {"Python": "confirmed", "Docker": "declared"}), NEED, NOW)
    e = explain(r, NEED, 82, None)
    assert e.lines[0] == "Middle подтверждён тестом · сильнее 82% категории"
    assert "Python ✓" in e.lines[1] and "Docker (заявлено)" in e.lines[1]
    assert e.lines[2] == NO_FSP
    assert "Docker: заявлено, не подтверждено" in e.missing


def test_missing_salary_format_window_and_readiness_tooltip():
    cand = c("b", 0.6, {"Python": "confirmed"}, formats=("hybrid",), salary_threshold_net=280000,
             open_until=NOW - timedelta(days=2), last_activity_at=NOW - timedelta(days=60))
    e = explain(evaluate_candidate(cand, NEED, NOW), NEED, None, "ФСП: призёр 1 старта из 3")
    assert any(m.startswith("нет: Docker") for m in e.missing)
    assert any("ниже ожиданий" in m for m in e.missing)
    assert any("гибрид" in m for m in e.missing)
    assert "окно поиска истекло" in e.readiness_tooltip and e.lines[2] == "ФСП: призёр 1 старта из 3"
    assert "нет активности дольше 30 дней" in e.readiness_tooltip


def test_unknown_stack_line_mentions_test_confirmed_techs():
    cand = c("u", 0.6, {"SQL": "confirmed", "Python": "confirmed"}, stack_declared=False)
    e = explain(evaluate_candidate(cand, NEED, NOW), NEED, None, None)
    assert e.lines[1] == "Стек не указан; тестом подтверждено: Python, SQL"


def test_counterfactual_names_tech_and_positions():
    cands = [c("x", 0.9, {"Python": "confirmed", "Docker": "confirmed"}),
             c("y", 0.85, {"Python": "confirmed", "Docker": "confirmed"}),
             c("z", 0.95, {"Python": "confirmed", "Docker": "declared"})]
    ranked = rank(cands, NEED, NOW)
    idx = [r.c.ref for r in ranked].index("z")
    assert counterfactual(ranked, idx, NEED, NOW) == "Если подтвердить Docker, кандидат поднимется на 2 позиции"


def test_salary_gap_shown_as_level_not_percent():
    stack = {"Python": "confirmed", "Docker": "confirmed"}
    near = explain(evaluate_candidate(c("n", 0.6, stack, salary_threshold_net=280000), NEED, NOW), NEED, None, None)
    far = explain(evaluate_candidate(c("f", 0.6, stack, salary_threshold_net=400000), NEED, NOW), NEED, None, None)
    assert "%" not in near.readiness_tooltip and not any("%" in m for m in near.missing + far.missing)
    assert "вилка немного ниже ожиданий" in near.readiness_tooltip
    assert "вилка заметно ниже ожиданий" in far.readiness_tooltip


def test_readiness_level_agrees_with_badge_noun():
    e = explain(evaluate_candidate(c("a", 0.8, {"Python": "confirmed"}), NEED, NOW), NEED, None, None)
    assert e.readiness_level in ("высокая", "средняя", "низкая") and e.fit_level in ("высокое", "среднее", "низкое")


def test_window_date_shown_in_moscow_time():
    cand = c("w", 0.6, {"Python": "confirmed"}, open_until=datetime(2026, 10, 17, 22, 30, tzinfo=UTC))
    e = explain(evaluate_candidate(cand, NEED, NOW), NEED, None, None)
    assert "окно поиска открыто до 18.10" in e.readiness_tooltip


def test_counterfactuals_batch_matches_single_and_fits_budget():
    rnd = random.Random(3)
    techs = ("Python", "Docker", "Kafka")
    cands = [c(f"c{i:03d}", rnd.random(), {t: rnd.choice(["confirmed", "declared"]) for t in techs if rnd.random() < 0.7})
             for i in range(200)]
    best = float("inf")
    for _ in range(3):
        t0 = time.perf_counter()
        ranked = rank(cands, NEED, NOW)
        cfs = counterfactuals(ranked, NEED, NOW)
        for r in ranked:
            explain(r, NEED, None, None)
        best = min(best, time.perf_counter() - t0)
    assert best < 0.05, f"подборка на 200 кандидатов: {best * 1000:.0f} мс"
    assert cfs == [counterfactual(ranked, i, NEED, NOW) for i in range(len(ranked))]
