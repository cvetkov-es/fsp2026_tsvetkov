from app.lab.matching_validation import validate_matching


def test_validate_matching_small():
    r = validate_matching(n_people=240, n_needs=9, seed=4)
    ours, rnd = r["rankers"]["ours"]["all"]["ndcg"]["mean"], r["rankers"]["random"]["all"]["ndcg"]["mean"]
    assert ours > rnd
    assert set(r["rankers"]) == {"ours", "random", "test_only", "stack_keywords", "self_description", "fsp_only"}
    assert set(r["ablation"]) == {"no_fsp", "no_stack", "no_accept", "no_confirmation", "no_blocks"}
    assert all(c["passed"] for c in r["paired"])
    assert r["blocks"] == {"each_candidate_one_block": True, "unconfirmed_never_above_confirmed": True}
    assert r["invariance"]["city_changed_same_order_share"] == 1.0
    assert len(r["sensitivity"]) == 24


def test_block_rule_catches_blocks_that_depend_on_the_pool(monkeypatch):
    """Блок — свойство кандидата и потребности: если он зависит от соседей по выдаче, проверка это ловит."""
    from dataclasses import replace

    import app.lab.matching_validation as mv
    from app.lab.population import make_needs, make_people, observe

    people = observe(make_people(60, seed=8), seed=8)
    pools = {sp: [p for p in people if p.spec == sp] for sp in ("backend", "frontend", "data")}
    needs = make_needs(3, seed=8)
    assert mv.block_rule(pools, needs)["each_candidate_one_block"] is True
    real_rank = mv.rank
    monkeypatch.setattr(mv, "rank", lambda cands, need, now, *a: [replace(r, block=1 + i % 2) for i, r in
                                                                  enumerate(real_rank(cands, need, now, *a))])
    assert mv.block_rule(pools, needs)["each_candidate_one_block"] is False


def test_invariance_covers_pseudonym_and_sensitivity_reports_overlap():
    r = validate_matching(n_people=120, n_needs=3, seed=6)
    assert r["invariance"]["pseudonym_changed_same_order_share"] == 1.0
    assert all(0 <= s["top10_overlap"] <= 1 for s in r["sensitivity"])


def test_pseudonym_invariance_ignores_order_inside_exact_ties():
    """Псевдоним — только последний тай-брейк: у двух одинаковых кандидатов порядок между ними не значим."""
    from dataclasses import replace

    import app.lab.matching_validation as mv
    from app.lab.population import SynthNeed, make_people, observe
    from app.matching.scoring import NeedFacts

    p = observe(make_people(1, seed=11), seed=11)[0]
    twin = replace(p, ref=p.ref + "-twin", facts=replace(p.facts, ref=p.ref + "-twin"))
    need = SynthNeed("n", NeedFacts(p.spec, (p.claimed,), tuple(sorted(p.techs))[:2]))
    r = mv.invariance({p.spec: [p, twin]}, [need])
    assert r["pseudonym_changed_same_order_share"] == 1.0
