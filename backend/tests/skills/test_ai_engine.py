import random
from collections import Counter

from app.assessment.engine.ai_verdicts import (
    VerdictRef,
    VerdictResult,
    choose_verdict,
    evaluate_ai,
    plan_slots,
    slots_needed,
)
from app.assessment.phrases import ai_phrase
from app.config.params import PARAMS

EXPECTED = {"ok": "ok", "defect": "defect", "ambiguous": "clarify"}


def R(truth: str, verdict: str | None, confident: bool = True, correct: bool | None = None) -> VerdictResult:
    return VerdictResult(truth, verdict, confident, EXPECTED[truth] == verdict if correct is None else correct)


PERFECT = [R("ok", "ok")] * 6 + [R("defect", "defect")] * 4 + [R("ambiguous", "clarify")] * 2


def test_plan_has_fixed_areas_and_hidden_random_defect_share():
    flawed = Counter()
    for s in range(500):
        slots = plan_slots(random.Random(s))
        assert len(slots) == PARAMS.ai_verdicts == 12
        assert Counter(x.area for x in slots) == slots_needed() == {"python": 6, "sql": 4, "clarify": 2}
        assert all(x.flawed for x in slots if x.area == "clarify")
        flawed[sum(x.flawed for x in slots)] += 1
    assert set(flawed) == {5, 6, 7}  # 35–65% от 12 — целыми
    assert plan_slots(random.Random(3)) == plan_slots(random.Random(3))


def test_choose_verdict_prefers_unseen_and_spreads_over_whole_pool():
    refs = [VerdictRef(f"ai.py.f{i}", "python") for i in range(8)] + [VerdictRef("ai.sql.a", "sql")]
    rng = random.Random(1)
    picked = Counter(choose_verdict(refs, "python", set(), set(), rng).code for _ in range(400))
    assert len(picked) == 8  # весь пул, а не три первых по алфавиту
    seen = {f"ai.py.f{i}" for i in range(7)}
    assert choose_verdict(refs, "python", set(), seen, rng).code == "ai.py.f7"
    assert choose_verdict(refs, "python", {"ai.py.f7"}, seen, rng).code in seen  # невиданных нет — из виденных
    assert choose_verdict(refs, "sql", {"ai.sql.a"}, set(), rng) is None


def test_perfect_attempt_passes():
    ev = evaluate_ai(PERFECT, time_over=False, elapsed_s=401)
    assert ev.status == "finished" and ev.passed and ev.accuracy == 1 and ev.minutes == 7 and ev.in_time


def test_confident_miss_weighs_double():
    low = PERFECT[:6] + [R("defect", "ok", confident=False)] + PERFECT[7:]
    high = PERFECT[:6] + [R("defect", "ok", confident=True)] + PERFECT[7:]
    ev_low = evaluate_ai(low, time_over=False, elapsed_s=300)
    assert ev_low.miss_weighted == 1 / 6 and ev_low.passed  # 6 решений с изъяном: 4 дефекта и 2 неоднозначных
    ev_high = evaluate_ai(high, time_over=False, elapsed_s=300)
    assert ev_high.miss_weighted == 2 / 6 and ev_high.accuracy == 11 / 12 and not ev_high.passed


def test_false_rejects_cost_accuracy_only():
    three = [R("ok", "defect")] * 3 + PERFECT[3:]
    ev = evaluate_ai(three, time_over=False, elapsed_s=300)
    assert ev.false_reject == 0.5 and ev.accuracy == 0.75 and ev.miss_weighted == 0 and ev.passed
    four = [R("ok", "clarify")] * 4 + PERFECT[4:]
    assert not evaluate_ai(four, time_over=False, elapsed_s=300).passed


def test_rejecting_a_defect_for_a_wrong_reason_is_not_a_miss():
    partial = PERFECT[:6] + [R("defect", "defect", correct=False)] + PERFECT[7:]  # не та строка или вход
    ev = evaluate_ai(partial, time_over=False, elapsed_s=300)
    assert ev.miss_weighted == 0 and ev.correct == 11 and ev.passed


def test_time_over_fails_and_unfinished_is_in_progress():
    assert evaluate_ai(PERFECT[:5], time_over=False, elapsed_s=100).status == "in_progress"
    ev = evaluate_ai(PERFECT[:11], time_over=True, elapsed_s=600)
    assert ev.status == "finished" and not ev.in_time and not ev.passed
    unanswered = PERFECT[:11] + [R("defect", None, correct=False)]  # последний ответ пришёл после таймера
    assert not evaluate_ai(unanswered, time_over=False, elapsed_s=500).in_time


def test_phrase_has_no_gender():
    m = {"minutes": 7, "in_time": True, "correct": 11, "n": 12}
    assert ai_phrase("confirmed", m) == "Работа с ИИ: подтверждено · верных ответов 11 из 12 · 7 мин"
    assert ai_phrase("not_confirmed", m | {"in_time": False, "correct": 6}) == (
        "Работа с ИИ: не подтверждено · верных ответов 6 из 12 · время вышло")
