from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from app.assessment.engine.cooldowns import GradeAttemptRecord, grade_test_availability
from app.assessment.engine.irt import Response, posterior, prob_above
from app.assessment.engine.levels import Grade, Thresholds
from app.assessment.engine.rules import AttemptConfig, Decision, ItemResult, evaluate
from app.assessment.engine.selection import instance_seed
from app.config.params import PARAMS

T = Thresholds.from_params(PARAMS)


def _reference_p_above(prior_mean, responses, cut):
    """Та же модель на очень мелкой сетке — эталон для дискретизации."""
    g = np.linspace(-6, 6, 24001)
    logw = -0.5 * (g - prior_mean) ** 2
    for r in responses:
        p = 1 / (1 + np.exp(-(g - r.b)))
        logw += np.log(p) if r.correct else np.log1p(-p)
    w = np.exp(logw - logw.max())
    return float(w[g >= cut].sum() / w.sum())


@pytest.mark.parametrize("grade", list(Grade))
def test_prior_alone_gives_one_half_at_cut(grade):
    cut = T.cut(grade)
    assert prob_above(posterior(cut, PARAMS.prior_sd, []), cut) == pytest.approx(0.5, abs=1e-3)


def test_prob_above_matches_fine_grid():
    cut = T.cut(Grade.middle)
    resp = [Response(0.0, c) for c in [True, True, False] * 5]
    ref = _reference_p_above(cut, resp, cut)
    assert prob_above(posterior(cut, PARAMS.prior_sd, resp), cut) == pytest.approx(ref, abs=2e-3)


def test_border_decision_not_biased_against_candidate():
    pattern = [1, 1, 0] * 5  # 10 из 15 при b=0: истинная P ≈ 0.507 → подтверждён
    items = [ItemResult(i + 1, f"f{i}", "db", 3, 0.0, bool(c), 1) for i, c in enumerate(pattern)]
    ev = evaluate(AttemptConfig(Grade.middle, T, PARAMS.test_max), items)
    assert ev.border is True and ev.decision == Decision.confirmed


def test_instance_seed_parts_cannot_collide_via_separator():
    assert instance_seed(b"k", "a|b", "c", "f") != instance_seed(b"k", "a", "b|c", "f")


def test_attempt_config_rejects_inconsistent_cap():
    with pytest.raises(ValueError):
        AttemptConfig(Grade.middle, T, PARAMS.express_max, express=False)
    with pytest.raises(ValueError):
        AttemptConfig(Grade.middle, T, PARAMS.test_max, express=True)


D0 = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def test_confident_exemption_unlocks_only_next_grade():
    conf_j = GradeAttemptRecord(Grade.junior, D0, Decision.confirmed, True)
    assert grade_test_availability(Grade.middle, [conf_j], Grade.junior, False, D0 + timedelta(days=1)).allowed
    a = grade_test_availability(Grade.senior, [conf_j], Grade.junior, False, D0 + timedelta(days=1))
    assert not a.allowed and "cooldown_up" in a.reasons


def test_failed_grade_blocks_higher_grades_for_cooldown_same():
    failed_m = GradeAttemptRecord(Grade.middle, D0, Decision.not_confirmed, False)
    a = grade_test_availability(Grade.senior, [failed_m], None, False, D0)
    assert not a.allowed and a.available_at == D0 + timedelta(days=PARAMS.cooldown_same_days)
    assert grade_test_availability(Grade.junior, [failed_m], None, False, D0).allowed
