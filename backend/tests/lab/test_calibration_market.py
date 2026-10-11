import pytest

from app.lab.calibration import calibration
from app.lab.market import market


def test_calibration_reduces_error_with_data():
    r = calibration(seed=1, sizes=(30, 300), replicates=40)
    small, big = r["by_n"]
    assert big["calibrated_error"] < small["expert_error"] and big["calibrated_error"] < small["calibrated_error"]


def test_market_variants():
    r = market(seed=2026)  # на малых выборках качество найма шумит; 600 × 30 — около 6 с
    assert set(r) == {"ours", "no_fork_info", "no_quota", "random_order"}
    assert r["ours"]["below_threshold_share"] <= r["no_fork_info"]["below_threshold_share"]
    assert r["no_quota"]["invitations"] >= r["ours"]["invitations"]
    assert r["ours"]["hired_relevance"] >= r["random_order"]["hired_relevance"]


def test_calibration_below_min_n_keeps_expert_threshold():
    """Продукт не калибрует порог, пока голосов меньше CALIB_MIN_N: ошибка равна экспертной."""
    r = calibration(seed=1, sizes=(10,), replicates=20)
    row = r["by_n"][0]
    assert row["applied"] is False and row["calibrated_error"] == pytest.approx(row["expert_error"])


def test_market_reports_how_often_fork_aggregate_raised_the_fork():
    r = market(seed=2026, n_people=150, n_needs=6)
    assert r["no_fork_info"]["fork_raised_share"] == 0 and r["no_quota"]["fork_raised_share"] == 0
    assert 0 <= r["ours"]["fork_raised_share"] <= 1
