"""Семантические тесты Data · метрики и продуктовая аналитика: ключ пересчитывается по данным задания."""
import re

import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family
from app.assessment.bank.families import data_metrics as dm

from .._bank_helpers import area_codes, make

AREA_CODES = area_codes("metrics", "data")


def test_area_volume():
    levels = sorted(REGISTRY[c].level for c in AREA_CODES)
    assert levels == [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5]


@pytest.mark.parametrize("code", AREA_CODES)
def test_family_passes_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)
    assert r.space_estimate >= 50_000, (code, r.space_estimate)


def _num(pattern: str, text: str) -> float:
    return float(re.search(pattern, text).group(1))


def _far(x: float, digits: int) -> bool:
    return abs((x * 10**digits) % 1 - 0.5) > 0.01


# ------------------------------------------------------------------ conversion_rate
def test_conversion_rate_key():
    for seed in range(200):
        inst = make("da.metrics.conversion_rate", seed)
        visitors = _num(r"Посетителей: (\d+)", inst.prompt.text)
        buys = _num(r"покупок: (\d+)", inst.prompt.text)
        value = buys / visitors * 100
        assert inst.answer == round(value, 1) and _far(value, 1)


# ------------------------------------------------------------------ dau_mau
def test_dau_mau_key():
    for seed in range(200):
        inst = make("da.metrics.dau_mau", seed)
        dau = _num(r"DAU — (\d+)", inst.prompt.text)
        mau = _num(r"MAU[^—]*— (\d+)", inst.prompt.text)
        assert dau < mau
        assert inst.answer == round(dau / mau * 100, 1) and _far(dau / mau * 100, 1)


# ------------------------------------------------------------------ funnel_step
def test_funnel_step_key():
    for seed in range(200):
        inst = make("da.metrics.funnel_step", seed)
        steps = [(name, n) for name, n in inst.prompt.tables[0].rows]
        assert all(a[1] >= b[1] for a, b in zip(steps, steps[1:], strict=False))  # воронка не расширяется
        frm, to = re.search(r"с шага «(.+?)» на шаг «(.+?)»", inst.prompt.text).groups()
        names = [s[0] for s in steps]
        i = names.index(frm)
        assert names[i + 1] == to  # соседние шаги
        value = steps[i + 1][1] / steps[i][1] * 100  # от предыдущего шага, а не от входа в воронку
        assert inst.answer == round(value, 1) and _far(value, 1)
        assert round(steps[i + 1][1] / steps[0][1] * 100, 1) != inst.answer or i == 0


# ------------------------------------------------------------------ arppu
def test_arppu_key():
    for seed in range(200):
        inst = make("da.metrics.arppu", seed)
        revenue = _num(r"Выручка за месяц — (\d+)", inst.prompt.text)
        users = _num(r"активных пользователей — (\d+)", inst.prompt.text)
        paying = _num(r"из них платящих — (\d+)", inst.prompt.text)
        assert inst.answer == round(revenue / paying, 2) and _far(revenue / paying, 2)
        assert round(revenue / users, 2) != inst.answer  # ARPU — другой ответ


# ------------------------------------------------------------------ day_n_retention
def test_day_n_retention_key():
    for seed in range(200):
        inst = make("da.metrics.day_n_retention", seed)
        t = inst.prompt.tables[0]
        cohort, day = re.search(r"когорты (\S+) на день (\d+)", inst.prompt.text).groups()
        row = next(r for r in t.rows if r[0] == cohort)
        size, active = row[1], row[t.columns.index(f"день {day}")]
        assert inst.answer == round(active / size * 100, 1) and _far(active / size * 100, 1)


# ------------------------------------------------------------------ simple_ltv
def test_simple_ltv_key():
    for seed in range(200):
        inst = make("da.metrics.simple_ltv", seed)
        arpu = _num(r"ARPU — (\d+) ₽", inst.prompt.text)
        margin = _num(r"маржинальность — (\d+)%", inst.prompt.text)
        churn = _num(r"отток — (\d+(?:\.\d+)?)%", inst.prompt.text)
        ltv = arpu * margin / 100 / (churn / 100)  # средняя жизнь клиента — 1 / отток месяцев
        assert inst.answer == round(ltv) and _far(ltv, 0)


# ------------------------------------------------------------------ rolling_retention
def test_rolling_retention_key():
    for seed in range(200):
        inst = make("da.metrics.rolling_retention", seed)
        n = int(_num(r"дня (\d+) —", inst.prompt.text))
        days = [[int(d) for d in r[1].split(", ")] if r[1] != "—" else [] for r in inst.prompt.tables[0].rows]
        rolling = sum(any(d >= n for d in ds) for ds in days) / len(days) * 100
        classic = sum(n in ds for ds in days) / len(days) * 100
        assert inst.answer == round(rolling, 1) and round(classic, 1) != inst.answer


# ------------------------------------------------------------------ unique_users_definition
def test_unique_users_definition_key():
    for seed in range(200):
        inst = make("da.metrics.unique_users_definition", seed)
        key = inst.prompt.options[inst.answer]
        assert key.startswith("COUNT(DISTINCT")
        assert not any(o.startswith("COUNT(DISTINCT") for i, o in enumerate(inst.prompt.options) if i != inst.answer)


# ------------------------------------------------------------------ cac_payback
def test_cac_payback_key():
    for seed in range(200):
        inst = make("da.metrics.cac_payback", seed)
        cac = _num(r"CAC — (\d+) ₽", inst.prompt.text)
        arpu = _num(r"ARPU — (\d+) ₽", inst.prompt.text)
        margin = _num(r"маржинальность — (\d+)%", inst.prompt.text)
        months = cac / (arpu * margin / 100)  # окупается валовой маржой, а не выручкой
        assert inst.answer == round(months, 1) and _far(months, 1)
        assert round(cac / arpu, 1) != inst.answer


# ------------------------------------------------------------------ guardrail / north_star
@pytest.mark.parametrize(("code", "rows"), [("da.metrics.guardrail", "GUARDRAIL_ROWS"),
                                            ("da.metrics.north_star", "NORTH_STAR_ROWS")])
def test_table_mcq_key(code, rows):
    for seed in range(200):
        inst = make(code, seed)
        row = next(r for r in getattr(dm, rows) if r[0] in inst.prompt.text)
        key = inst.prompt.options[inst.answer]
        assert key == row[1]
        assert all(o in row[2] for i, o in enumerate(inst.prompt.options) if i != inst.answer)


def test_guardrail_target_metric_is_a_distractor():
    """Целевая метрика эксперимента — типичная ошибка выбора guardrail: она есть среди вариантов чаще всего."""
    hits = sum(any(o == next(r for r in dm.GUARDRAIL_ROWS if r[0] in make("da.metrics.guardrail", s).prompt.text)[3]
                   for o in make("da.metrics.guardrail", s).prompt.options) for s in range(100))
    assert hits >= 60


# ------------------------------------------------------------------ mix_shift
def _classify(rows):
    rate = {(seg, per): b / v for seg, per, v, b in rows}
    share = {(seg, per): v / sum(vv for s2, p2, vv, _ in rows if p2 == per) for seg, per, v, _ in rows}
    segs = sorted({seg for seg, *_ in rows})
    drops = [seg for seg in segs if rate[(seg, "текущий")] - rate[(seg, "прошлый")] < -0.005]
    stable = all(abs(rate[(s, "текущий")] - rate[(s, "прошлый")]) < 0.001 for s in segs if s not in drops)
    mix_moved = max(abs(share[(s, "текущий")] - share[(s, "прошлый")]) for s in segs) > 0.1
    assert stable
    if not drops:
        assert mix_moved
        return "mix"
    assert not mix_moved
    return "both" if len(drops) == 2 else f"one:{drops[0]}"


def test_mix_shift_key():
    kinds = set()
    for seed in range(300):
        inst = make("da.metrics.mix_shift", seed)
        kind = _classify(inst.prompt.tables[0].rows)
        key = inst.prompt.options[inst.answer]
        if kind == "mix":
            assert key == dm.MIX_OPTIONS["mix"]
        elif kind == "both":
            assert key == dm.MIX_OPTIONS["both"]
        else:
            assert key == dm.MIX_OPTIONS["one"].format(seg=kind.split(":")[1])
        kinds.add(kind.split(":")[0])
        # общая конверсия действительно упала
        tot = {per: sum(b for _, p, _, b in inst.prompt.tables[0].rows if p == per)
               / sum(v for _, p, v, _ in inst.prompt.tables[0].rows if p == per) for per in ("прошлый", "текущий")}
        assert tot["текущий"] < tot["прошлый"]
    assert kinds == {"mix", "both", "one"}


# ------------------------------------------------------------------ novelty_effect
def test_novelty_effect_key():
    for seed in range(200):
        inst = make("da.metrics.novelty_effect", seed)
        lifts = [r[1] for r in inst.prompt.tables[0].rows]
        assert lifts[0] > lifts[-1] > 0 and lifts[0] >= 2 * lifts[-1]  # прирост затухает
        key = inst.prompt.options[inst.answer]
        assert key in dm.NOVELTY_CORRECT
        assert all(o in dm.NOVELTY_WRONG for i, o in enumerate(inst.prompt.options) if i != inst.answer)



def test_guardrail_text_names_target_and_is_grammatical():
    for seed in range(200):
        inst = make("da.metrics.guardrail", seed)
        t = inst.prompt.text
        i = next(k for k, r in enumerate(dm.GUARDRAIL_ROWS) if r[0] in t)
        assert dm.GUARDRAIL_GOALS[i] in t  # целевая метрика названа в тексте — поэтому она не guardrail
        assert not re.search(r"на (всех|новых)? ?пользователей", t)


def test_metric_texts_have_no_doubled_words_or_nested_quotes():
    for code in ("da.metrics.simple_ltv", "da.metrics.conversion_rate", "da.metrics.cac_payback"):
        for seed in range(100):
            t = make(code, seed).prompt.text
            assert "Подписка «Подписка" not in t and not re.search(r"«[^»]*«", t)


def test_rolling_retention_cells_not_empty():
    for seed in range(100):
        assert all(r[1] for r in make("da.metrics.rolling_retention", seed).prompt.tables[0].rows)
