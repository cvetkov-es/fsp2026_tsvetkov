from collections import Counter

from app.assessment.engine.selection import (
    FamilyRef,
    choose_next,
    instance_seed,
    selection_rng,
    target_level,
)
from app.config.params import PARAMS

SECRET = b"test-secret"
AREAS = ("lang", "http", "db", "arch", "debug")
BANK = [FamilyRef(f"{a}-{lv}-{i}", a, lv, PARAMS.b_levels[lv - 1]) for a in AREAS
        for lv in range(1, 6) for i in range(3)]


def pick(seq, used=frozenset(), seen=frozenset(), counts=None, families=BANK, theta=0.7):
    return choose_next(families=families, areas=AREAS, used_in_attempt=set(used),
                       area_counts=counts or Counter(), seen=set(seen), band=(2, 3, 4),
                       theta=theta, b_levels=PARAMS.b_levels, rng=selection_rng(SECRET, "att-1", seq),
                       k=PARAMS.randomesque_k)


def test_target_level_nearest_b():
    assert target_level(0.7, (2, 3, 4), PARAMS.b_levels) == 4
    assert target_level(0.2, (2, 3, 4), PARAMS.b_levels) == 3


def test_deterministic_for_same_attempt_and_seq():
    assert pick(1) == pick(1)


def test_covers_all_areas_in_ten_items():
    used, counts = set(), Counter()
    for seq in range(1, 11):
        f = pick(seq, used=used, counts=counts)
        used.add(f.code)
        counts[f.area] += 1
    assert set(counts) == set(AREAS) and all(v == 2 for v in counts.values())


def test_excludes_seen_then_relaxes_but_never_repeats_in_attempt():
    only_db = [f for f in BANK if f.area == "db" and f.level in (2, 3, 4)]
    seen = {f.code for f in only_db}
    f = pick(1, seen=seen, families=only_db)
    assert f is not None and f.code in seen  # банк исчерпан → разрешили виденные
    assert pick(1, used={x.code for x in only_db}, seen=seen, families=only_db) is None


def test_exposure_weighting_prefers_fresh_families():
    trio = [FamilyRef("a", "db", 4, 1.0, 0), FamilyRef("b", "db", 4, 1.0, 0), FamilyRef("c", "db", 4, 1.0, 200)]
    hits = Counter(
        choose_next(families=trio, areas=("db",), used_in_attempt=set(), area_counts=Counter(), seen=set(),
                    band=(4,), theta=1.0, b_levels=PARAMS.b_levels,
                    rng=selection_rng(SECRET, f"att-{i}", 1), k=3).code
        for i in range(600)
    )
    assert hits["c"] < 0.05 * 600 and hits["a"] > 200 and hits["b"] > 200


def test_instance_seed_same_on_reload_differs_between_candidates():
    s1 = instance_seed(SECRET, "cand-1", "att-1", "be.db.x")
    assert s1 == instance_seed(SECRET, "cand-1", "att-1", "be.db.x")
    assert s1 != instance_seed(SECRET, "cand-2", "att-1", "be.db.x")
    assert s1 != instance_seed(b"other-secret", "cand-1", "att-1", "be.db.x")
