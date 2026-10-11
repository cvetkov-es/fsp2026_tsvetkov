"""Кулдауны (процесс v4, 2.6): действует самое строгое из применимых правил.

Исключения («уверенно» в фазе 2 последней подтверждённой попытки, голоса VOTES_UNLOCK)
снимают только COOLDOWN_UP, но не COOLDOWN_SAME.
"""
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.assessment.engine.levels import Grade, grade_rank
from app.assessment.engine.rules import Decision
from app.config.params import PARAMS, Params


@dataclass(frozen=True)
class GradeAttemptRecord:
    grade: Grade
    finished_at: datetime
    decision: Decision | None  # None — попытка «не завершена», не учитывается
    confident: bool


@dataclass(frozen=True)
class Availability:
    allowed: bool
    available_at: datetime | None
    reasons: tuple[str, ...]


def grade_test_availability(
    target: Grade,
    history: Sequence[GradeAttemptRecord],
    confirmed: Grade | None,
    votes_unlock: bool,
    now: datetime,
    params: Params = PARAMS,
) -> Availability:
    done = [h for h in history if h.decision is not None]
    constraints: list[tuple[datetime, str]] = []

    same = [h for h in done if Grade(h.grade) == Grade(target)]
    if same:
        last = max(h.finished_at for h in same)
        constraints.append((last + timedelta(days=params.cooldown_same_days), "cooldown_same"))
    # Провал грейда g закрывает и грейды выше g на тот же срок: нельзя «перепрыгнуть» провал
    failed_below = [h for h in done if h.decision == Decision.not_confirmed
                    and grade_rank(h.grade) < grade_rank(target)]
    if failed_below:
        last = max(h.finished_at for h in failed_below)
        constraints.append((last + timedelta(days=params.cooldown_same_days), "cooldown_same"))

    if confirmed is not None and grade_rank(target) > grade_rank(confirmed):
        confirms = [h for h in done if Grade(h.grade) == Grade(confirmed)
                    and h.decision == Decision.confirmed]
        last_conf = max(confirms, key=lambda h: h.finished_at) if confirms else None
        # Исключения открывают только следующий грейд, а не любой выше
        next_grade = grade_rank(target) == grade_rank(confirmed) + 1
        exempt = next_grade and (votes_unlock or (last_conf is not None and last_conf.confident))
        if last_conf is not None and not exempt:
            constraints.append(
                (last_conf.finished_at + timedelta(days=params.cooldown_up_days), "cooldown_up")
            )

    if not constraints:
        return Availability(True, None, ())
    available_at = max(d for d, _ in constraints)
    reasons = tuple(dict.fromkeys(r for d, r in constraints if d == available_at))
    return Availability(now >= available_at, available_at, reasons)


def skill_test_availability(
    last_attempt_at: datetime | None, now: datetime, params: Params = PARAMS
) -> Availability:
    if last_attempt_at is None:
        return Availability(True, None, ())
    at = last_attempt_at + timedelta(days=params.cooldown_skill_days)
    return Availability(now >= at, at, ("cooldown_skill",))
