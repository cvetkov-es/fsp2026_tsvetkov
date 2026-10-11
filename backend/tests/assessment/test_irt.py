import pytest

from app.assessment.engine.irt import GRID, Response, eap, p_correct, posterior, prob_above


def test_grid_and_logistic():
    assert len(GRID) == 241 and GRID[0] == -6 and GRID[-1] == 6
    assert p_correct(0.0, 0.0) == pytest.approx(0.5)
    assert p_correct(1.0, 0.0) > 0.7


def test_no_responses_gives_prior():
    w = posterior(0.71, 1.0, [])
    theta, se = eap(w)
    assert theta == pytest.approx(0.71, abs=0.01) and se == pytest.approx(1.0, abs=0.02)
    assert prob_above(w, 0.71) == pytest.approx(0.5, abs=0.02)


def test_correct_answers_raise_theta_and_shrink_se():
    w0 = posterior(0.0, 1.0, [])
    w = posterior(0.0, 1.0, [Response(0.0, True)] * 6)
    t0, s0 = eap(w0)
    t, s = eap(w)
    assert t > t0 + 0.5 and s < s0
    assert prob_above(w, 0.0) > 0.9


def test_symmetry_wrong_answers():
    up = eap(posterior(0.0, 1.0, [Response(0.0, True)] * 4))[0]
    down = eap(posterior(0.0, 1.0, [Response(0.0, False)] * 4))[0]
    assert up == pytest.approx(-down, abs=1e-6)
