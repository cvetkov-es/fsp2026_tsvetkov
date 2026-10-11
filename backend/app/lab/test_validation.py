"""Валидация теста на синтетике (процесс 8): матрица ошибок, test-retest, длина, экспресс, «утечка»."""
import random

from app.assessment.bank.areas import AREAS
from app.assessment.engine.irt import p_correct
from app.assessment.engine.levels import Grade
from app.assessment.engine.rules import AttemptConfig, Decision
from app.assessment.engine.simulate import simulate_attempt, synthetic_bank
from app.config.params import PARAMS
from app.lab.metrics import cohen_kappa, mean, quantile, rate
from app.lab.population import make_people, thresholds

DIST_BINS = ((0.0, 0.25), (0.25, 0.5), (0.5, 1.0), (1.0, 99.0))
OC_GRID = [round(-2 + 0.25 * i, 2) for i in range(17)]  # θ − порог для кривой решений


def _run(theta: float, grade: str, spec: str, seed: int, express: bool, banks, p_answer=None):
    cap = PARAMS.express_max if express else PARAMS.test_max
    return simulate_attempt(theta, AttemptConfig(Grade(grade), thresholds(), cap, express), banks[spec],
                            AREAS[spec], rng_seed=seed, p_answer=p_answer)


def validate_test(n: int, seed: int, oc_per_point: int = 120, leak_n: int = 400) -> dict:
    t = thresholds()
    banks = {sp: synthetic_bank(AREAS[sp]) for sp in AREAS}
    people = make_people(n, seed)
    rows = []
    for k, p in enumerate(people):
        above = p.theta >= t.cut(Grade(p.claimed))
        full = _run(p.theta, p.claimed, p.spec, seed * 7919 + k, False, banks)
        retest = _run(p.theta, p.claimed, p.spec, seed * 7919 + k + 10**7, False, banks)
        exp = _run(p.theta, p.claimed, p.spec, seed * 7919 + k + 2 * 10**7, True, banks)
        rows.append({"grade": p.claimed, "above": above, "dist": abs(p.theta - t.cut(Grade(p.claimed))),
                     "full": full.decision == Decision.confirmed, "retest": retest.decision == Decision.confirmed,
                     # экспресс без решения на EXPRESS_MAX не «не подтверждён»: продукт предлагает продолжить тест
                     "express": None if exp.decision is None else exp.decision == Decision.confirmed,
                     "n_full": full.n_answered, "n_express": exp.n_answered, "border": full.border})
    by_grade = {}
    for g in ("junior", "middle", "senior"):
        rs = [r for r in rows if r["grade"] == g]
        below, above_ = [r for r in rs if not r["above"]], [r for r in rs if r["above"]]
        by_grade[g] = {
            "n": len(rs),
            "matrix": {"above_confirmed": sum(r["full"] for r in above_), "above_not": sum(not r["full"] for r in above_),
                       "below_confirmed": sum(r["full"] for r in below), "below_not": sum(not r["full"] for r in below)},
            "false_positive": rate(below, lambda r: r["full"]), "false_negative": rate(above_, lambda r: not r["full"]),
            "len_full": {"mean": mean(r["n_full"] for r in rs), "p50": quantile([r["n_full"] for r in rs], 0.5),
                         "p90": quantile([r["n_full"] for r in rs], 0.9)},
            "len_express": {"mean": mean(r["n_express"] for r in rs), "p90": quantile([r["n_express"] for r in rs], 0.9)},
        }
    kappa_bins = []
    for lo, hi in DIST_BINS:
        rs = [r for r in rows if lo <= r["dist"] < hi]
        kappa_bins.append({"dist_from": lo, "dist_to": None if hi > 50 else hi, "n": len(rs),
                           "agreement": rate(rs, lambda r: r["full"] == r["retest"]),
                           "kappa": cohen_kappa([r["full"] for r in rs], [r["retest"] for r in rs]) if rs else None})
    decided = [r for r in rows if r["express"] is not None]
    return {
        "n": n,
        "accuracy": rate(rows, lambda r: r["full"] == r["above"]),
        "accuracy_by_distance": [{"dist_from": lo, "dist_to": None if hi > 50 else hi,
                                  "n": sum(1 for r in rows if lo <= r["dist"] < hi),
                                  "accuracy": rate([r for r in rows if lo <= r["dist"] < hi], lambda r: r["full"] == r["above"])}
                                 for lo, hi in DIST_BINS],
        "accuracy_far": rate([r for r in rows if r["dist"] >= 0.5], lambda r: r["full"] == r["above"]),
        "accuracy_near": rate([r for r in rows if r["dist"] < 0.25], lambda r: r["full"] == r["above"]),
        "express_decided_share": len(decided) / len(rows) if rows else None,
        "accuracy_express_decided": rate(decided, lambda r: r["express"] == r["above"]),
        "express_agrees_with_full": rate(decided, lambda r: r["express"] == r["full"]),
        "border_share": rate(rows, lambda r: r["border"]),
        "retest_kappa": cohen_kappa([r["full"] for r in rows], [r["retest"] for r in rows]),
        "retest_agreement": rate(rows, lambda r: r["full"] == r["retest"]),
        "kappa_by_distance": kappa_bins,
        "by_grade": by_grade,
        "oc_curve": operating_curve(seed, banks, oc_per_point),
        "leak": leak_experiment(seed, banks, leak_n),
    }


def operating_curve(seed: int, banks, per_point: int = 120) -> list[dict]:
    """P(подтверждён) от расстояния до порога Middle (график 1): полный тест; экспресс — подтверждён сам
    и не решён за EXPRESS_MAX (такому кандидату продукт предлагает продолжить тест до полного)."""
    cut = thresholds().cut(Grade.middle)
    out = []
    for i, d in enumerate(OC_GRID):
        full = [_run(cut + d, "middle", "backend", seed * 31 + i * 1000 + j, False, banks).decision == Decision.confirmed
                for j in range(per_point)]
        exp = [_run(cut + d, "middle", "backend", seed * 37 + i * 1000 + j, True, banks).decision
               for j in range(per_point)]
        out.append({"delta": d, "full": sum(full) / per_point,
                    "express_confirmed": sum(x == Decision.confirmed for x in exp) / per_point,
                    "express_undecided": sum(x is None for x in exp) / per_point})
    return out


def leak_experiment(seed: int, banks, n: int = 400, leaked_share: float = 0.3) -> dict:
    """«Утечка» (процесс 8): треть банка слита. Кандидат на 0.75 ниже порога Middle знает слитые ответы.

    Статичный банк: слитое задание = верный ответ. Наш банк — параметризованные семейства: ответ слитого
    экземпляра совпадает, только если тот же экземпляр выпадет снова (≈ 1 / размер пространства параметров).
    """
    cut = thresholds().cut(Grade.middle)
    rng = random.Random(seed + 99)
    bank = banks["backend"]
    leaked = {f.code for f in rng.sample(bank, int(len(bank) * leaked_share))}
    theta = cut - 0.75
    repeat = 1 / PARAMS.gen_space_min

    def static(f):
        return 1.0 if f.code in leaked else float(p_correct(theta, f.b))

    def generated(f):
        base = float(p_correct(theta, f.b))
        return base + (1 - base) * repeat if f.code in leaked else base

    def fp(p_answer):
        return rate(range(n), lambda j: _run(theta, "middle", "backend", seed * 53 + j, False, banks,
                                              p_answer).decision == Decision.confirmed)

    return {"theta_minus_cut": -0.75, "leaked_share": leaked_share, "honest_false_positive": fp(None),
            "static_bank_false_positive": fp(static), "generated_bank_false_positive": fp(generated)}
