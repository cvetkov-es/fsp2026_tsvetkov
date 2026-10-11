"""Помощник к собеседованию (процесс 4.7): вопросы из интервью-пула по слабым областям, специализации и стеку кандидата.

Для компаний L2+, `HELPER_MONTHLY` наборов за 30 дней на компанию. Повторный запрос по тому же контакту в этом окне
возвращает сохранённый набор и лимит не тратит. Отбор детерминирован по `contact_id`.
"""
import random
import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.assessment.bank.areas import AREA_TITLES, AREAS
from app.auth.models import User
from app.candidates.models import CandidateProfile
from app.candidates.service import passed_skills, stack_states
from app.common.clock import now
from app.common.errors import AppError
from app.config.params import PARAMS
from app.contacts.service import _company_contact, chat_open
from app.employers.models import Company
from app.employers.service import require_company
from app.hiring.interview_pool import QUESTIONS
from app.hiring.models import HelperUse, PipelineStage
from app.matching.stack_dict import SKILL_TECHS, SKILL_TITLES

R_WEAK = "слабая область по итогам этапа"
R_AREA = "область специализации"
R_CONFIRMED = "навык подтверждён тестом, спросите глубже"
R_DECLARED = "заявлено без подтверждения, проверьте"


def build_questions(contact_id: uuid.UUID, p: CandidateProfile, weak_areas: list[str], confirmed: set[str],
                    declared_unconfirmed: list[str]) -> list[dict]:
    """Приоритет: слабые области (по 2) → области специализации (по 1) → подтверждённые навыки → заявленные без подтверждения."""
    rng = random.Random(contact_id.int)
    used: set[str] = set()
    out: list[dict] = []

    def take(key: str, n: int, reason: str, title: str) -> None:
        pool = [q for q in QUESTIONS.get(key, ()) if q not in used]
        for q in rng.sample(pool, min(n, len(pool))):
            if len(out) >= PARAMS.helper_questions:
                return
            used.add(q)
            out.append({"text": q, "topic": title, "reason": reason})

    for a in weak_areas:
        take(a, 2, R_WEAK, AREA_TITLES[a])
    for a in AREAS.get(p.specialization or "", ()):
        take(a, 1, R_AREA, AREA_TITLES[a])
    for code in sorted(confirmed):
        take(code, 1, R_CONFIRMED, SKILL_TITLES[code])  # «sql» — и область, и навык: тема по причине вопроса
    for code in declared_unconfirmed:
        take(code, 1, R_DECLARED, SKILL_TITLES[code])
    return out


def _weak_areas(db: Session, contact_id: uuid.UUID) -> list[str]:
    last = db.scalar(select(PipelineStage).where(PipelineStage.contact_id == contact_id)
                     .order_by(PipelineStage.at.desc(), PipelineStage.id.desc()).limit(1))
    return list(last.weak_areas) if last and last.weak_areas else []


def _uses_since(db: Session, company_id: uuid.UUID):
    return (HelperUse.company_id == company_id, HelperUse.at >= now() - timedelta(days=PARAMS.helper_window_days))


def interview_helper(db: Session, user: User, contact_id: uuid.UUID) -> dict:
    company = require_company(db, user)
    if company.trust_level not in ("L2", "L3"):
        raise AppError(403, "trust_required", "Помощник к собеседованию доступен компаниям с уровнем доверия L2 и выше")
    c = _company_contact(db, user, contact_id)
    if c.status != "accepted" or not chat_open(db, c):
        raise AppError(409, "helper_unavailable", "Вопросы доступны, когда приглашение принято и контакты открыты")
    db.execute(select(Company.id).where(Company.id == company.id).with_for_update())  # лимит без гонок
    used = db.scalar(select(func.count()).select_from(HelperUse).where(*_uses_since(db, company.id)))
    again = db.scalar(select(HelperUse).where(HelperUse.contact_id == c.id, *_uses_since(db, company.id))
                      .order_by(HelperUse.at.desc()).limit(1))
    if again is not None:  # повторный запрос по тому же контакту лимит не тратит
        return {"questions": again.questions, "used": used, "limit": PARAMS.helper_monthly, "window_days": PARAMS.helper_window_days}
    if used >= PARAMS.helper_monthly:
        raise AppError(409, "helper_limit", "Лимит вопросов к собеседованию на этот месяц исчерпан",
                       f"Использовано {used} из {PARAMS.helper_monthly} за {PARAMS.helper_window_days} дней")
    p = db.get(CandidateProfile, c.user_id)
    passed = passed_skills(db, c.user_id)
    states = stack_states(db, p)
    declared = [code for code, techs in SKILL_TECHS.items()
                if code not in passed and any(states.get(t) == "declared" for t in techs)]
    questions = build_questions(c.id, p, _weak_areas(db, c.id), passed, declared)
    db.add(HelperUse(company_id=company.id, contact_id=c.id, questions=questions))
    db.commit()
    return {"questions": questions, "used": used + 1, "limit": PARAMS.helper_monthly, "window_days": PARAMS.helper_window_days}
