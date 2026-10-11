from app.lab.test_validation import validate_test


def test_validate_test_small_population():
    r = validate_test(n=90, seed=3, oc_per_point=12, leak_n=80)
    assert 0.7 <= r["accuracy"] <= 1 and -1 <= r["retest_kappa"] <= 1
    assert set(r["by_grade"]) == {"junior", "middle", "senior"}
    assert r["by_grade"]["middle"]["len_full"]["p90"] <= 15
    assert len(r["oc_curve"]) == 17 and r["oc_curve"][0]["full"] < r["oc_curve"][-1]["full"]
    assert 0 < r["express_decided_share"] <= 1 and r["accuracy_by_distance"][-1]["accuracy"] >= r["accuracy"]
    leak = r["leak"]
    assert leak["static_bank_false_positive"] > leak["generated_bank_false_positive"]
