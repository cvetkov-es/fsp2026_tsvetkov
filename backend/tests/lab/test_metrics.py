import math

import pytest

from app.lab.metrics import bootstrap_ci, cohen_kappa, kendall_tau, mrr, ndcg_at_k, precision_at_k


def test_kappa():
    assert cohen_kappa([1, 1, 0, 0], [1, 1, 0, 0]) == 1.0
    assert cohen_kappa([1, 0, 1, 0], [0, 1, 0, 1]) == pytest.approx(-1.0)
    assert cohen_kappa([1, 1, 1, 0], [1, 1, 0, 0]) == pytest.approx(0.5)


def test_ranking_metrics():
    assert ndcg_at_k([3, 2, 1, 0], 4) == pytest.approx(1.0)
    assert ndcg_at_k([0, 1, 2, 3], 4) < 0.7
    assert precision_at_k([3, 0, 2, 1], 4) == 0.5 and mrr([0, 1, 2], relevant=2) == pytest.approx(1 / 3)
    assert ndcg_at_k([0, 0], 2) == 0.0


def test_bootstrap_and_tau():
    m, lo, hi = bootstrap_ci([0.5, 0.6, 0.7, 0.8], n=500)
    assert lo <= m <= hi and m == pytest.approx(0.65)
    assert math.isnan(bootstrap_ci([])[0])
    assert kendall_tau("abcd", "abcd") == 1.0 and kendall_tau("abcd", "dcba") == -1.0
