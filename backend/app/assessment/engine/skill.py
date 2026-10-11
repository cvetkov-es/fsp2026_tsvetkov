"""Тест навыка (процесс 2.5): SKILL_LEN заданий фиксированной длины, решение P(θ ≥ SKILL_CUT) ≥ 0.5.

Ни фаз, ни раннего решения: короткий тест не должен заканчиваться на двух удачных ответах.
"""
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.assessment.engine.irt import eap, log_lik, log_prior, normalize, prob_above
from app.assessment.engine.rules import Decision, ItemResult
from app.config.params import PARAMS, Params

SKILL_BAND = (1, 2, 3, 4)  # уровни вокруг SKILL_CUT = b(d2) + 0.71


@dataclass(frozen=True)
class SkillEvaluation:
    status: Literal["in_progress", "finished"]
    decision: Decision | None
    theta: float
    se: float
    p_pass: float
    n_answered: int


def evaluate_skill(items: Sequence[ItemResult], params: Params = PARAMS) -> SkillEvaluation:
    logw = log_prior(params.skill_cut, params.prior_sd)
    for it in items:
        logw = logw + log_lik(it.b, it.correct)
    w = normalize(logw)
    theta, se = eap(w)
    p = float(prob_above(w, params.skill_cut))
    if len(items) < params.skill_len:
        return SkillEvaluation("in_progress", None, theta, se, p, len(items))
    decision = Decision.confirmed if p >= 0.5 else Decision.not_confirmed
    return SkillEvaluation("finished", decision, theta, se, p, len(items))
