"""Голоса и множитель m (процесс 5): прибавка только вверх, статусы — при чтении.

Модуль без зависимостей от сервисов: его читают подборка (m, бейдж) и тест (VOTES_UNLOCK).
Голос действует только в той категории («специализация × грейд»), в которой его дали: после смены
категории он в архиве навсегда, даже если кандидат вернётся к прежнему грейду.
"""
import calendar
import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.params import PARAMS, Params
from app.hiring.models import Vote

POSITIVE = ("meets", "above")
LEVEL_TITLES = {"below": "ниже ожиданий", "meets": "соответствует ожиданиям", "above": "выше ожиданий",
                "unknown": "пока не могу сказать"}
UNLOCK_LEVELS = ("L2", "L3")


def status_grade(p) -> str | None:
    """Грейд, о котором спрашивают на собеседовании: подтверждённый, а без него — заявленный."""
    return p.confirmed_grade if p.grade_status == "confirmed" else p.claimed_grade


@dataclass(frozen=True)
class Holder:
    """Текущая категория кандидата и время её последней смены."""
    specialization: str | None
    grade: str | None
    changed_at: datetime | None = None


def holder(p) -> Holder:
    return Holder(p.specialization, status_grade(p), p.grade_changed_at)


def add_months(t: datetime, n: int) -> datetime:
    """Календарные месяцы: 31 января + 1 месяц → 28 (29) февраля."""
    y, m = divmod(t.month - 1 + n, 12)
    year, month = t.year + y, m + 1
    return t.replace(year=year, month=month, day=min(t.day, calendar.monthrange(year, month)[1]))


def vote_weight(trust_level: str, params: Params = PARAMS) -> float | None:
    """Вес по уровню доверия компании (процесс 4.1). L0 не голосует: ответ записывается, но голосом не становится."""
    return {"L1": params.vote_w_l1, "L2": params.vote_w_l2, "L3": params.vote_w_l2}.get(trust_level)


def vote_state(v, h: Holder, now: datetime, params: Params = PARAMS) -> str:
    """pending → active через VOTE_DISPUTE; disputed → annulled | upheld (upheld действует сразу);
    другая категория или ответ до её смены — archived (навсегда); через VOTE_TTL после вступления — expired."""
    if v.status in ("annulled", "disputed"):
        return v.status
    if (v.spec_at_vote, v.grade_at_vote) != (h.specialization, h.grade) or (
            h.changed_at is not None and v.answered_at < h.changed_at):
        return "archived"
    if now >= add_months(v.effective_at, params.vote_ttl_months):
        return "expired"
    if v.status == "pending" and now < v.effective_at:
        return "pending"
    return "active"


def interview_m(votes: Iterable[tuple[str, float]], params: Params = PARAMS) -> float:
    """m = 1 + M_BOOST·max(0, 2p̂ − 1), p̂ = (1 + Σ w·v)/(2 + Σ w); v = 1 за «соответствует» и «выше»."""
    vs = list(votes)
    p_hat = (1 + sum(w for v, w in vs if v in POSITIVE)) / (2 + sum(w for _, w in vs))
    return 1 + params.m_boost * max(0.0, 2 * p_hat - 1)


@dataclass(frozen=True)
class VoteStats:
    m: float = 1.0
    positive: int = 0  # действующих «соответствует» и «выше»
    total: int = 0

    def badge(self, params: Params = PARAMS) -> bool:
        """«Подтверждено на собеседованиях (N)»: N ≥ BADGE_MIN и доля положительных ≥ BADGE_SHARE."""
        return self.positive >= params.badge_min and self.positive >= params.badge_share * self.total - 1e-9


def stats(active: list[tuple[str, float]], params: Params = PARAMS) -> VoteStats:
    if not active:
        return VoteStats()
    return VoteStats(interview_m(active, params), sum(1 for v, _ in active if v in POSITIVE), len(active))


def vote_stats(db: Session, holders: Mapping[uuid.UUID, Holder], now: datetime) -> dict[uuid.UUID, VoteStats]:
    """Действующие голоса кандидатов одним запросом."""
    active: dict[uuid.UUID, list[tuple[str, float]]] = defaultdict(list)
    if not holders:
        return {}
    for v in db.scalars(select(Vote).where(Vote.user_id.in_(list(holders)), Vote.status.in_(("pending", "upheld")))):
        if vote_state(v, holders[v.user_id], now) == "active":
            active[v.user_id].append((v.value, v.weight))
    return {uid: stats(vs) for uid, vs in active.items()}


def unlocks_higher_test(db: Session, user_id: uuid.UUID, h: Holder | None, now: datetime,
                        params: Params = PARAMS) -> bool:
    """VOTES_UNLOCK действующих «выше» от компаний L2+ за подтверждённую категорию снимают COOLDOWN_UP (процесс 2.6, 5).

    h — категория с подтверждённым грейдом (None — грейд не подтверждён); уровень компании — из голоса, а не из веса."""
    if h is None:
        return False
    rows = db.scalars(select(Vote).where(Vote.user_id == user_id, Vote.value == "above",
                                         Vote.trust_at_vote.in_(UNLOCK_LEVELS), Vote.status.in_(("pending", "upheld"))))
    return sum(1 for v in rows if vote_state(v, h, now) == "active") >= params.votes_unlock
