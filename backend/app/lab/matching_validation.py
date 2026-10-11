"""Валидация подбора без замкнутого круга (процесс 8; исследование 03, §3).

Релевантность — рубрика по скрытой истине (lab.rubric), ранжирование видит только наблюдаемое.
"""
import random
from dataclasses import replace

from app.config.params import PARAMS, Params
from app.hiring.votes import interview_m
from app.lab.metrics import bootstrap_ci, kendall_tau, mean, mrr, ndcg_at_k, precision_at_k, rate
from app.lab.population import NOW, Person, make_needs, make_people, observe, thresholds
from app.lab.rubric import relevance
from app.matching.scoring import (
    CandidateFacts,
    NeedFacts,
    Ranked,
    evaluate_candidate,
    rank,
    sort_key,
    strength_r,
)

K = 10
HOLDOUT_SHARE = 0.3


def _ours(params: Params = PARAMS, blocks: bool = True):
    def ranker(pool: list[Person], need: NeedFacts, rng: random.Random) -> list[str]:
        ranked = rank((p.facts for p in pool), need, NOW, params)
        order = [r.c.ref for r in (ranked if blocks else sorted(ranked, key=lambda r: -r.score))]
        rest = [p.ref for p in pool if p.ref not in set(order)]
        rng.shuffle(rest)  # исключённые продуктом (грейд далеко) — в конце в случайном порядке
        return order + rest
    return ranker


def _by(key):
    def ranker(pool: list[Person], need: NeedFacts, rng: random.Random) -> list[str]:
        shuffled = list(pool)
        rng.shuffle(shuffled)  # ничьи — случайно
        return [p.ref for p in sorted(shuffled, key=lambda p: key(p, need), reverse=True)]
    return ranker


BASELINES = {
    "random": _by(lambda p, n: 0),
    "test_only": _by(lambda p, n: p.facts.theta),
    "stack_keywords": _by(lambda p, n: sum(1 for x in n.must if x in p.declared)),
    # «по самоописанию»: заявленный грейд совпал + сколько всего заявлено технологий (полнота профиля)
    "self_description": _by(lambda p, n: (p.claimed in n.grades, len(p.declared))),
    "fsp_only": _by(lambda p, n: p.fsp_f),
}


def _no_confirmation(pool: list[Person]) -> list[Person]:
    out = []
    for p in pool:
        q = replace(p)
        q.facts = replace(p.facts, stack={x: "declared" for x in p.facts.stack})
        out.append(q)
    return out


def _evaluate(rankers: dict, pools: dict, needs, t, seed: int) -> dict:
    """rankers: имя → (функция ранжирования, преобразование пула или None)."""
    res = {}
    for name, (ranker, transform) in rankers.items():
        per_need = []
        for i, n in enumerate(needs):
            pool = pools[n.facts.specialization]
            order = ranker(transform(pool) if transform else pool, n.facts, random.Random(seed * 7 + i))
            rel = {p.ref: relevance(p, n.facts, t) for p in pools[n.facts.specialization]}
            rels = [rel[r] for r in order]
            per_need.append({"need": n.key, "ndcg": ndcg_at_k(rels, K), "p_at_k": precision_at_k(rels, K),
                             "mrr": mrr(rels), "order": order[:K]})
        res[name] = per_need
    return res


def _summary(per_need: list[dict], keys: set[str]) -> dict:
    rows = [r for r in per_need if r["need"] in keys]
    out = {}
    for metric in ("ndcg", "p_at_k", "mrr"):
        m, lo, hi = bootstrap_ci([r[metric] for r in rows])
        out[metric] = {"mean": m, "ci_low": lo, "ci_high": hi}
    return out


def validate_matching(n_people: int, n_needs: int, seed: int) -> dict:
    t = thresholds()
    people = observe(make_people(n_people, seed + 1000), seed + 1000)
    pools = {sp: [p for p in people if p.spec == sp] for sp in ("backend", "frontend", "data")}
    needs = make_needs(n_needs, seed)
    rng = random.Random(seed)
    holdout = set(rng.sample([n.key for n in needs], int(len(needs) * HOLDOUT_SHARE)))
    dev = {n.key for n in needs} - holdout
    rankers = {"ours": (_ours(), None), **{k: (v, None) for k, v in BASELINES.items()}}
    ablations = {
        "no_fsp": (_ours(Params(fsp_weight=0.0)), None),
        "no_stack": (_ours(Params(fit_w_stack=0.0, fit_w_r=1.0, must_missing_penalty=1.0)), None),
        "no_accept": (_ours(Params(score_base=1.0)), None),
        "no_confirmation": (_ours(), _no_confirmation),
        "no_blocks": (_ours(blocks=False), None),
    }
    main = _evaluate(rankers, pools, needs, t, seed)
    abl = _evaluate(ablations, pools, needs, t, seed)
    all_keys = {n.key for n in needs}
    return {
        "n_people": n_people, "n_needs": n_needs, "k": K, "holdout_needs": len(holdout),
        "rankers": {name: {"all": _summary(r, all_keys), "dev": _summary(r, dev), "holdout": _summary(r, holdout)}
                    for name, r in main.items()},
        "ablation": {name: _summary(r, all_keys)["ndcg"] for name, r in abl.items()},
        "sensitivity": sensitivity(pools, needs, t, seed, main["ours"]),
        "invariance": invariance(pools, needs),
        "paired": paired_cases(),
        "blocks": block_rule(pools, needs),
        "fairness": fairness(pools, needs),
    }


SENSITIVE = ("fsp_weight", "stack_declared", "fit_w_stack", "must_missing_penalty", "score_base", "format_compatible")


def sensitivity(pools, needs, t, seed, base_rows) -> list[dict]:
    """Каждый вес ±25% и ±50% (fit_w_r перенормируется): изменение nDCG (tornado) и устойчивость топ-10.

    top10_overlap — доля прежнего топ-10, оставшаяся в топ-10; top10_tau — τ Кендалла только по этому
    пересечению (порядок внутри общих кандидатов), поэтому читать его надо вместе с overlap.
    """
    base_ndcg = mean(r["ndcg"] for r in base_rows)
    base_top = {r["need"]: r["order"] for r in base_rows}
    out = []
    for name in SENSITIVE:
        for factor in (0.5, 0.75, 1.25, 1.5):
            value = min(1.0, getattr(PARAMS, name) * factor)
            kw = {name: value}
            if name == "fit_w_stack":
                kw["fit_w_r"] = 1 - value
            rows = _evaluate({"x": (_ours(Params(**kw)), None)}, pools, needs, t, seed)["x"]
            out.append({"param": name, "factor": factor, "value": value,
                        "ndcg_delta": mean(r["ndcg"] for r in rows) - base_ndcg,
                        "top10_tau": mean(kendall_tau(base_top[r["need"]], r["order"]) for r in rows),
                        "top10_overlap": mean(len(set(base_top[r["need"]]) & set(r["order"])) / max(1, len(base_top[r["need"]]))
                                              for r in rows)})
    return out


def _tie_groups(ranked: list[Ranked], back: dict[str, str] | None = None) -> list[set[str]]:
    """Порядок с точностью до полных ничьих: ref — последний тай-брейк sort_key, внутри ничьей порядок не значим."""
    groups: list[tuple[tuple, set[str]]] = []
    for r in ranked:
        key, ref = sort_key(r)[:-1], (back or {}).get(r.c.ref, r.c.ref)
        if groups and groups[-1][0] == key:
            groups[-1][1].add(ref)
        else:
            groups.append((key, {ref}))
    return [g for _, g in groups]


def invariance(pools, needs) -> dict:
    """Город (потребность его не требует) и псевдоним не должны менять порядок (исследование 03, §3c)."""
    same_city, same_alias = [], []
    for n in needs:
        pool = pools[n.facts.specialization]
        ranked = rank((p.facts for p in pool), n.facts, NOW)
        base = [r.c.ref for r in ranked]
        moved = [replace(p.facts, city="Владивосток" if p.facts.city != "Владивосток" else "Москва") for p in pool]
        same_city.append(base == [r.c.ref for r in rank(moved, n.facts, NOW)])
        # Псевдонимы в обратном лексикографическом порядке переставляют полные ничьи — это не зависимость от
        # псевдонима, поэтому сравниваем порядок групп равных кандидатов
        alias = {p.ref: f"z{len(pool) - i:06d}" for i, p in enumerate(pool)}
        back = {v: k for k, v in alias.items()}
        renamed = [replace(p.facts, ref=alias[p.ref]) for p in pool]
        same_alias.append(_tie_groups(ranked) == _tie_groups(rank(renamed, n.facts, NOW), back))
    return {"city_changed_same_order_share": sum(same_city) / len(same_city),
            "pseudonym_changed_same_order_share": sum(same_alias) / len(same_alias)}


def paired_cases() -> list[dict]:
    """Контрольные случаи процесса 6.4 и парные тесты на порядок (исследование 03, §3b)."""
    def cand(**kw) -> CandidateFacts:
        base = dict(ref="x", specialization="backend", grade_status="confirmed", confirmed_grade="middle",
                    claimed_grade="middle", theta=1.0, se=0.4, s=0.6, open_until=NOW, last_activity_at=NOW)
        return CandidateFacts(**{**base, **kw})

    need = NeedFacts("backend", ("middle",), ("Python", "PostgreSQL", "Docker"))

    def score(c: CandidateFacts) -> float:
        return next(r.score for r in rank([c], need, NOW))

    s_for_r = 0.55 * PARAMS.r_max
    cases = [
        ("Сильный тест без ФСП выше слабого теста с ФСП (случай 1)",
         strength_r(cand(s=0.79)) > strength_r(cand(s=0.51, fsp_f=0.74))),
        ("Подтверждённые 2 из 3 must выше заявленных 3 из 3 (случай 2)",
         score(cand(s=s_for_r, stack={"Python": "confirmed", "PostgreSQL": "confirmed"}))
         > score(cand(s=s_for_r, stack={"Python": "declared", "PostgreSQL": "declared", "Docker": "declared"}))),
        ("Три «ниже» дают m = 1, три «соответствует» дают m ≈ 1.12 (случай 3)",
         interview_m([("below", 1.0)] * 3) == 1 and abs(interview_m([("meets", 1.0)] * 3) - 1.12) < 1e-9),
        ("Добавили must-технологию: кандидат выше",
         score(cand(stack={"Python": "confirmed", "PostgreSQL": "confirmed", "Docker": "confirmed"}))
         > score(cand(stack={"Python": "confirmed", "PostgreSQL": "confirmed"}))),
        ("Добавили ФСП при равном тесте: кандидат выше",
         score(cand(fsp_f=0.6, stack={"Python": "confirmed"})) > score(cand(stack={"Python": "confirmed"}))),
        ("Экспресс и полный тест при равном θ̂ различаются мягко (случай 4)",
         abs(score(cand(s=0.62, express=True)) - score(cand(s=0.6))) < 0.05),
    ]
    return [{"case": c, "passed": bool(ok)} for c, ok in cases]


def block_rule(pools, needs) -> dict:
    """Процесс 6.4 и спецификация 5.2: каждый кандидат ровно в одном блоке, и блок — свойство самого кандидата
    и потребности (тот же, если оценить кандидата отдельно от выдачи); неподтверждённый не выше подтверждённого."""
    one_block, no_inversion = True, True
    for n in needs:
        ranked = rank((p.facts for p in pools[n.facts.specialization]), n.facts, NOW)
        refs = [r.c.ref for r in ranked]
        one_block &= len(refs) == len(set(refs)) and all(
            evaluate_candidate(r.c, n.facts, NOW).block == r.block for r in ranked)
        main = [r for r in ranked if r.block <= 3]
        first_unconf = next((i for i, r in enumerate(main) if r.c.grade_status != "confirmed"), len(main))
        no_inversion &= all(r.c.grade_status == "confirmed" for r in main[:first_unconf]) and all(
            r.c.grade_status != "confirmed" for r in main[first_unconf:])
    return {"each_candidate_one_block": one_block, "unconfirmed_never_above_confirmed": no_inversion}


def fairness(pools, needs) -> dict:
    """Условный selection ratio «без ФСП / с ФСП» внутри одной трети по силе теста (исследование 03, §3.8).

    ФСП по ТЗ даёт преимущество, поэтому ratio < 1 ожидаем; ориентир «четыре пятых» (0.8) — для сведения.
    Плюс фармеры онлайн-отборов: их доля в топе против доли среди релевантных.
    """
    t = thresholds()
    rows = []
    farmers_top, farmers_rel = [], []
    for n in needs:
        pool = pools[n.facts.specialization]
        top = {r.c.ref for r in rank((p.facts for p in pool), n.facts, NOW)[:K]}
        ss = sorted(p.facts.s for p in pool)
        cuts = (ss[len(ss) // 3], ss[2 * len(ss) // 3])
        for p in pool:
            tier = 0 if p.facts.s < cuts[0] else 1 if p.facts.s < cuts[1] else 2
            rows.append((tier, p.fsp_f > 0, p.ref in top))
            if p.ref in top:
                farmers_top.append(p.farmer)
            if relevance(p, n.facts, t) >= 2:
                farmers_rel.append(p.farmer)
    out = []
    for tier in (0, 1, 2):
        no = [r for r in rows if r[0] == tier and not r[1]]
        yes = [r for r in rows if r[0] == tier and r[1]]
        r_no, r_yes = rate(no, lambda r: r[2]), rate(yes, lambda r: r[2])
        out.append({"test_tier": tier, "rate_no_fsp": r_no, "rate_fsp": r_yes,
                    "ratio": (r_no / r_yes) if r_yes else None})
    return {"by_test_tier": out, "farmers_share_top10": mean(farmers_top), "farmers_share_relevant": mean(farmers_rel)}
