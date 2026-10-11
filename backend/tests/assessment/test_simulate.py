from statistics import mean

from app.assessment.engine.levels import Grade, Thresholds
from app.assessment.engine.rules import AttemptConfig, Decision
from app.assessment.engine.simulate import simulate_attempt, synthetic_bank
from app.config.params import PARAMS

T = Thresholds.from_params(PARAMS)
AREAS = ("lang", "http", "db", "arch", "debug")
BANK = synthetic_bank(AREAS)


def run(theta, express=False, n=150, target=Grade.middle):
    cfg = AttemptConfig(target, T, PARAMS.express_max if express else PARAMS.test_max, express)
    return [simulate_attempt(theta, cfg, BANK, AREAS, rng_seed=s) for s in range(n)]


def test_strong_candidates_confirmed_weak_rejected():
    cut = T.cut(Grade.middle)
    strong = run(cut + 1.0)
    weak = run(cut - 1.0)
    assert mean(e.decision == Decision.confirmed for e in strong) >= 0.9
    assert mean(e.decision == Decision.not_confirmed for e in weak) >= 0.9


def test_lengths_within_bounds():
    full = run(T.cut(Grade.middle) + 0.3)
    assert all(PARAMS.n_min_decide <= e.n_answered <= PARAMS.test_max + PARAMS.test_min for e in full)
    assert 6 <= mean(e.n_answered for e in full) <= 15
    express = run(T.cut(Grade.middle) + 1.0, express=True)
    assert all(e.n_answered <= PARAMS.express_max for e in express)


def test_p_answer_hook_overrides_rasch():
    """Лаборатория подменяет вероятность ответа: всегда верно — подтверждён даже при низком θ."""
    cfg = AttemptConfig(Grade.middle, T, PARAMS.test_max, False)
    low = T.cut(Grade.middle) - 3.0
    evs = [simulate_attempt(low, cfg, BANK, AREAS, rng_seed=s, p_answer=lambda f: 1.0) for s in range(20)]
    assert all(e.decision == Decision.confirmed for e in evs)
