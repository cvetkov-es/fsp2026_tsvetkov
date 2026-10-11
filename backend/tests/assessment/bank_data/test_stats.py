"""Семантические тесты Data · статистика и эксперименты: ключ сверяется с numpy / math по конвенции из текста."""
import math
import re
import statistics

import numpy as np
import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.checks import check_family
from app.assessment.bank.families import data_stats as st

from .._bank_helpers import area_codes, make

AREA_CODES = area_codes("stats", "data")


def test_area_volume():
    levels = sorted(REGISTRY[c].level for c in AREA_CODES)
    assert levels == [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5]


@pytest.mark.parametrize("code", AREA_CODES)
def test_family_passes_pipeline(code):
    r = check_family(REGISTRY[code], subprocess_probe=False)
    assert r.ok, (code, r.errors)
    assert r.space_estimate >= 50_000, (code, r.space_estimate)


def _ints(text: str) -> list[int]:
    return [int(x) for x in re.findall(r"-?\d+", text)]


def _far_from_rounding(x: float, digits: int) -> bool:
    return abs((x * 10**digits) % 1 - 0.5) > 0.01


# ------------------------------------------------------------------ mean_median
def test_mean_median_key():
    asked = set()
    for seed in range(200):
        inst = make("da.stats.mean_median", seed)
        xs = _ints(re.search(r"\[(.+)\]", inst.prompt.code).group(1))
        assert inst.kind == "number" and 7 <= len(xs) <= 11  # число: «52,5» и «52.50» засчитываются одинаково
        if "медиан" in inst.prompt.text:
            assert inst.answer == round(float(np.median(xs)), 2)
            asked.add("median")
        else:
            assert "среднее арифметическое" in inst.prompt.text
            assert inst.answer == round(float(np.mean(xs)), 2) and _far_from_rounding(float(np.mean(xs)), 2)
            asked.add("mean")
    assert asked == {"mean", "median"}


# ------------------------------------------------------------------ percent_change
def test_percent_change_key():
    signs = set()
    for seed in range(200):
        inst = make("da.stats.percent_change", seed)
        was, now = (int(x) for x in re.search(r"было (\d+), стало (\d+)", inst.prompt.text).groups())
        change = (now - was) / was * 100
        assert inst.answer == round(change, 1) and _far_from_rounding(change, 1)
        signs.add(change > 0)
    assert signs == {True, False}


# ------------------------------------------------------------------ population_std
def test_population_std_key():
    for seed in range(200):
        inst = make("da.stats.population_std", seed)
        assert "генеральной совокупности" in inst.prompt.text  # конвенция названа: делим на n
        xs = _ints(re.search(r"\[(.+)\]", inst.prompt.code).group(1))
        sigma = float(np.std(xs))  # ddof=0 — генеральная совокупность
        assert inst.answer == round(sigma, 2) and _far_from_rounding(sigma, 2)
        assert round(statistics.stdev(xs), 2) != inst.answer  # выборочное σ дало бы другой ответ


# ------------------------------------------------------------------ conditional_probability
def test_conditional_probability_key():
    forms = set()
    for seed in range(200):
        inst = make("da.stats.conditional_probability", seed)
        t = inst.prompt.tables[0]
        (a_yes, a, b), (a_no, c, d) = t.rows
        b_yes = t.columns[1]
        m = re.search(r"что пользователь (.+?), если он (.+?)\?", inst.prompt.text)
        event, given = m.groups()
        cells = {(a_yes, b_yes): a, (a_yes, t.columns[2]): b, (a_no, b_yes): c, (a_no, t.columns[2]): d}
        if event == b_yes:  # P(B | A=given)
            num = cells[(given, b_yes)]
            den = num + cells[(given, t.columns[2])]
            forms.add("b|a")
        else:  # P(A | B=given)
            assert event == a_yes and given == b_yes
            num, den = a, a + c
            forms.add("a|b")
        assert inst.answer == round(num / den, 2) and _far_from_rounding(num / den, 2)
    assert forms == {"b|a", "a|b"}


# ------------------------------------------------------------------ weighted_average
def test_weighted_average_key():
    for seed in range(200):
        inst = make("da.stats.weighted_average", seed)
        t = inst.prompt.tables[0]
        values, weights = [r[0] for r in t.rows], [r[1] for r in t.rows]
        w = float(np.average(values, weights=weights))
        assert inst.answer == round(w, 2) and _far_from_rounding(w, 2)
        assert round(statistics.mean(values), 2) != inst.answer  # невзвешенное среднее — другой ответ


# ------------------------------------------------------------------ simpsons_paradox
def test_simpsons_paradox_key():
    paradox = 0
    for seed in range(200):
        inst = make("da.stats.simpsons_paradox", seed)
        rows = inst.prompt.tables[0].rows
        rate = {(v, s): conv / n for v, s, n, conv in rows}
        segs = sorted({s for _, s, _, _ in rows})
        seg_winner = {max(("A", "B"), key=lambda v, s=s: rate[(v, s)]) for s in segs}
        assert len(seg_winner) == 1  # в обоих сегментах побеждает один вариант
        total = {v: sum(conv for vv, _, _, conv in rows if vv == v) / sum(n for vv, _, n, _ in rows if vv == v)
                 for v in ("A", "B")}
        sw, tw = seg_winner.pop(), max(total, key=total.get)
        key = inst.prompt.options[inst.answer]
        if sw == tw:
            assert key.startswith(f"{sw} лучше и в каждом сегменте")
        else:
            assert key.startswith(f"{sw} лучше в каждом сегменте, но {tw}")
            paradox += 1
        assert all(abs(rate[("A", s)] - rate[("B", s)]) > 0.002 for s in segs) and abs(total["A"] - total["B"]) > 0.002
    assert 100 <= paradox <= 180


# ------------------------------------------------------------------ srm_check
def test_srm_check_key():
    seen = set()
    for seed in range(200):
        inst = make("da.stats.srm_check", seed)
        n_a, n_b = (int(x) for x in re.search(r"группы A — (\d+), группы B — (\d+)", inst.prompt.text).groups())
        expected = (n_a + n_b) / 2
        chi2 = ((n_a - expected) ** 2 + (n_b - expected) ** 2) / expected
        p = math.erfc(math.sqrt(chi2 / 2))  # χ² с одной степенью свободы, независимо от scipy
        key = inst.prompt.options[inst.answer]
        assert key == (st.SRM_YES if p < 0.001 else st.SRM_NO)
        assert not 0.0005 < p < 0.002  # далеко от порога
        seen.add(p < 0.001)
    assert seen == {True, False}


# ------------------------------------------------------------------ ci_halfwidth
def test_ci_halfwidth_key():
    for seed in range(200):
        inst = make("da.stats.ci_halfwidth", seed)
        n, k = (int(x) for x in re.search(r"Посетителей: (\d+), покупок: (\d+)\.", inst.prompt.text).groups())
        assert "1.96" in inst.prompt.text
        p = k / n
        h = 1.96 * math.sqrt(p * (1 - p) / n)
        assert inst.answer == round(h, 4) and _far_from_rounding(h, 4)


# ------------------------------------------------------------------ ab_z_test
def test_ab_z_test_key():
    seen = set()
    for seed in range(300):
        inst = make("da.stats.ab_z_test", seed)
        (n_a, c_a), (n_b, c_b) = (tuple(r[1:]) for r in inst.prompt.tables[0].rows)
        p = (c_a + c_b) / (n_a + n_b)
        z = (c_b / n_b - c_a / n_a) / math.sqrt(p * (1 - p) * (1 / n_a + 1 / n_b))
        key = inst.prompt.options[inst.answer]
        if abs(z) > 1.96:
            want = "B лучше A" if z > 0 else "A лучше B"
            assert key.startswith("Различие значимо") and want in key
        else:
            assert key.startswith("Различие не значимо")
        assert not 1.8 < abs(z) < 2.15
        seen.add("ns" if abs(z) <= 1.96 else "b" if z > 0 else "a")
    assert seen == {"ns", "a", "b"}


# ------------------------------------------------------------------ bonferroni_count
def test_bonferroni_count_key():
    for seed in range(200):
        inst = make("da.stats.bonferroni_count", seed)
        alpha = float(re.search(r"α = (0\.\d+)", inst.prompt.text).group(1))
        ps = [r[1] for r in inst.prompt.tables[0].rows]
        threshold = alpha / len(ps)
        assert inst.answer == sum(p < threshold for p in ps)
        assert all(abs(p - threshold) > 0.1 * threshold for p in ps)
        assert sum(p < alpha for p in ps) != inst.answer  # без поправки ответ другой


# ------------------------------------------------------------------ peeking
def test_peeking_key():
    for seed in range(200):
        inst = make("da.stats.peeking", seed)
        key = inst.prompt.options[inst.answer]
        assert key in st.PEEKING_CORRECT
        assert all(o in st.PEEKING_WRONG for i, o in enumerate(inst.prompt.options) if i != inst.answer)


# ------------------------------------------------------------------ sample_size
def test_sample_size_key():
    for seed in range(200):
        inst = make("da.stats.sample_size", seed)
        p1 = float(re.search(r"базовая конверсия (0\.\d+)", inst.prompt.text).group(1))
        mde = float(re.search(r"MDE (0\.\d+)", inst.prompt.text).group(1))
        assert "1.96" in inst.prompt.text and "0.84" in inst.prompt.text  # формула и z приведены в тексте
        p2 = p1 + mde
        n = (1.96 + 0.84) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2)) / mde**2
        assert inst.answer == math.ceil(n)
        assert 0.01 < n % 1 < 0.99  # далеко от целого: округление вверх однозначно


# ------------------------------------------------------------------ regression_to_mean
def test_regression_to_mean_key():
    for seed in range(200):
        inst = make("da.stats.regression_to_mean", seed)
        key = inst.prompt.options[inst.answer]
        assert key in st.RTM_CORRECT and "контрольн" in key
        assert all(o in st.RTM_WRONG for i, o in enumerate(inst.prompt.options) if i != inst.answer)
        assert "худш" in inst.prompt.text or "слаб" in inst.prompt.text  # отбор по крайнему результату



def test_peeking_text_has_no_nested_quotes():
    for seed in range(100):
        assert not re.search(r"«[^»]*«", make("da.stats.peeking", seed).prompt.text)
