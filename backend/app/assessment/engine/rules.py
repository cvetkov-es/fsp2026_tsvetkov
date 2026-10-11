"""Правила попытки (процесс v4, 2.4). Без скрытого состояния: всё по списку ответов."""
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal

import numpy as np

from app.assessment.engine.irt import eap, log_lik, log_prior, normalize, prob_above
from app.assessment.engine.levels import Grade, Thresholds
from app.config.params import PARAMS, Params


class Decision(StrEnum):
    confirmed = "confirmed"
    not_confirmed = "not_confirmed"


@dataclass(frozen=True)
class ItemResult:
    seq: int
    family_code: str
    area: str
    level: int
    b: float
    correct: bool  # тайм-аут = False
    phase: int  # 1 или 2


@dataclass(frozen=True)
class AttemptConfig:
    target: Grade
    thresholds: Thresholds
    item_cap: int  # предел фазы 1: TEST_MAX (полный) или EXPRESS_MAX (экспресс)
    express: bool = False
    params: Params = PARAMS

    def __post_init__(self) -> None:
        expected = self.params.express_max if self.express else self.params.test_max
        if self.item_cap != expected:
            raise ValueError(f"item_cap={self.item_cap} не соответствует режиму (ожидается {expected})")


Status = Literal["phase1", "transition", "phase2", "awaiting_continue", "finished"]


@dataclass(frozen=True)
class Evaluation:
    status: Status
    decision: Decision | None
    decided_at: int | None
    border: bool
    confident: bool
    theta: float
    se: float
    p_confirm: float
    s: float
    n_answered: int
    phase2_total: int


def strength(theta: float, se: float, cut_g: float, cut_next: float, se_penalty: float) -> float:
    x = (theta - se_penalty * se - cut_g) / (cut_next - cut_g)
    return 0.5 + 0.5 * max(-1.0, min(1.0, x))


def _phase2_total(cfg: AttemptConfig, n1: int) -> int:
    base = cfg.params.express_max if cfg.express else cfg.params.test_min
    return max(0, base - n1)


def evaluate(cfg: AttemptConfig, items: Sequence[ItemResult]) -> Evaluation:
    p = cfg.params
    cut = cfg.thresholds.cut(cfg.target)
    nxt = cfg.thresholds.next_cut(cfg.target)
    ordered = sorted(items, key=lambda i: i.seq)
    phase1 = [i for i in ordered if i.phase == 1]
    phase2 = [i for i in ordered if i.phase == 2]

    prior = log_prior(cut, p.prior_sd)
    decision: Decision | None = None
    decided_at: int | None = None
    border = False
    logw = prior.copy()
    for k, it in enumerate(phase1, start=1):
        logw = logw + log_lik(it.b, it.correct)
        if k < p.n_min_decide:
            continue
        pk = prob_above(normalize(logw), cut)
        if pk >= p.p_decide:
            decision, decided_at = Decision.confirmed, k
            break
        if pk <= 1 - p.p_decide:
            decision, decided_at = Decision.not_confirmed, k
            break

    if decision is None and len(phase1) >= cfg.item_cap and not cfg.express:
        p1 = prob_above(normalize(logw), cut)
        decision = Decision.confirmed if p1 >= 0.5 else Decision.not_confirmed
        decided_at, border = len(phase1), True

    all_logw = prior + sum((log_lik(i.b, i.correct) for i in ordered), np.zeros_like(prior))
    w_all = normalize(all_logw)
    theta, se = eap(w_all)
    p_confirm = prob_above(w_all, cut)

    phase2_total = 0
    if decision is None:
        status: Status = (
            "awaiting_continue" if cfg.express and len(phase1) >= cfg.item_cap else "phase1"
        )
    elif decision == Decision.not_confirmed:
        status = "finished"
    else:
        phase2_total = 0 if border else _phase2_total(cfg, decided_at or len(phase1))
        if len(phase2) >= phase2_total:
            status = "finished"
        elif not phase2:
            status = "transition"
        else:
            status = "phase2"

    confident = (
        decision == Decision.confirmed
        and status == "finished"
        and Grade(cfg.target) != Grade.senior
        and prob_above(w_all, nxt) >= 0.5
    )
    return Evaluation(
        status=status, decision=decision, decided_at=decided_at, border=border,
        confident=confident, theta=theta, se=se, p_confirm=p_confirm,
        s=strength(theta, se, cut, nxt, p.se_penalty),
        n_answered=len(ordered), phase2_total=phase2_total,
    )


@dataclass(frozen=True)
class Autoclose:
    outcome: Literal["completed", "autoclosed", "incomplete"]
    decision: Decision | None
    border: bool


def autoclose(
    cfg: AttemptConfig, items: Sequence[ItemResult], last_activity_at: datetime, now: datetime
) -> Autoclose | None:
    if now - last_activity_at < timedelta(hours=cfg.params.attempt_autoclose_hours):
        return None
    ev = evaluate(cfg, items)
    if ev.status == "finished":
        return None
    if ev.decision is not None:
        return Autoclose("completed", ev.decision, ev.border)
    if ev.n_answered >= cfg.params.n_min_decide:
        d = Decision.confirmed if ev.p_confirm >= 0.5 else Decision.not_confirmed
        return Autoclose("autoclosed", d, True)
    return Autoclose("incomplete", None, False)
