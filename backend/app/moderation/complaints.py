"""Обращения по жалобам: на работодателя со штрафом к квоте (4.4), на задание теста (2.3) и возражение по ст. 16 152-ФЗ (7).

Модуль регистрирует свои типы в реестре и не импортирует `moderation.service` на уровне модуля: `open_case` подгружается
внутри функций, поэтому `contacts.service` и роутеры могут импортировать отсюда без цикла.
"""
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assessment.models import Attempt, AttemptItem, ItemFamilyRow
from app.assessment.phrases import GRADE_TITLES
from app.candidates.models import CandidateProfile
from app.common.clock import now
from app.common.errors import AppError
from app.config.params import PARAMS
from app.contacts.models import Contact
from app.employers.models import Company
from app.matching.service import alias
from app.moderation.models import Case
from app.moderation.schemas import ObjectionIn, ReportIn
from app.moderation.types import CaseType, register, row

ITEM_REASONS = {"wrong_key": "ключ ответа неверен", "unclear": "условие непонятно", "typo": "опечатка", "other": "другое"}


def _open(db: Session, type_: str, refs: dict, user_id: uuid.UUID, comment: str) -> Case:
    from app.moderation.service import open_case

    return open_case(db, type_, refs, user_id, comment)


def _day(dt) -> str:
    return dt.strftime("%d.%m.%Y")


# --- жалоба на работодателя: отказ с причиной «спам или не соответствует описанию»

def penalize(db: Session, company: Company, contact: Contact) -> None:
    """Жалоба «спам или не соответствует описанию» (процесс 4.4): штраф к квоте и обращение модератору."""
    t = now()
    active = company.quota_penalty_until is not None and company.quota_penalty_until > t
    company.quota_penalty_slots = (company.quota_penalty_slots if active else 0) + PARAMS.complaint_quota_penalty
    company.quota_penalty_until = t + timedelta(days=PARAMS.complaint_penalty_days)
    # срок штрафа этого обращения: annul снимает слот, только пока штраф именно этой жалобы жив, а не чужой, более новый
    _open(db, "employer_complaint", {"contact_id": str(contact.id), "company_id": str(company.id),
                                     "penalty_until": company.quota_penalty_until.isoformat()},
          contact.user_id, contact.decline_comment or "")


def _complaint_summary(db: Session, case: Case) -> list[dict]:
    company = db.get(Company, uuid.UUID(case.refs["company_id"]))
    contact = db.get(Contact, uuid.UUID(case.refs["contact_id"]))
    if company is None or contact is None:
        return [row("Жалоба", "приглашение или компания удалены. Обращение можно закрыть")]
    until = company.quota_penalty_until
    penalty = f"−{PARAMS.complaint_quota_penalty} к квоте на {PARAMS.complaint_penalty_days} дн."
    if until is not None and until > now():
        penalty += f", действует до {_day(until)}"
    return [row("Компания", f"{company.name} (уровень {company.trust_level})"),
            row("Кандидат", alias(db.get(CandidateProfile, contact.user_id))),
            row("Причина отказа", "спам или не соответствует описанию"), row("Штраф", penalty)]


def _complaint_apply(db: Session, case: Case, action: str) -> str:
    company = db.get(Company, uuid.UUID(case.refs["company_id"]), with_for_update=True)
    if company is None:
        return "компания уже удалена"
    if action != "annul":
        return "жалоба признана обоснованной, штраф остаётся"
    own = case.refs.get("penalty_until")
    alive = (datetime.fromisoformat(own) if own else company.quota_penalty_until)
    if alive is not None and alive > now() and company.quota_penalty_until is not None:  # истёкший штраф снимать нечего
        company.quota_penalty_slots = max(0, company.quota_penalty_slots - PARAMS.complaint_quota_penalty)
        if company.quota_penalty_slots == 0:
            company.quota_penalty_until = None
    return "жалоба отклонена, штраф снят"


register("employer_complaint", CaseType(
    title="Жалоба на работодателя", actions={"uphold": "Оставить штраф", "annul": "Снять штраф"},
    summary=_complaint_summary, apply=_complaint_apply, link="/candidate/invitations"))


# --- проблема в задании теста

def _own_attempt(db: Session, user_id: uuid.UUID, attempt_id: uuid.UUID) -> Attempt:
    a = db.get(Attempt, attempt_id, with_for_update=True)
    if a is None or a.user_id != user_id:
        raise AppError(404, "attempt_not_found", "Попытка не найдена")
    return a


def report_item(db: Session, user_id: uuid.UUID, attempt_id: uuid.UUID, seq: int, data: ReportIn) -> None:
    a = _own_attempt(db, user_id, attempt_id)
    item = db.scalar(select(AttemptItem).where(AttemptItem.attempt_id == a.id, AttemptItem.seq == seq))
    if item is None:
        raise AppError(404, "item_not_found", "Такого задания в этой попытке не было")
    if db.scalar(select(Case.id).where(Case.type == "item_problem", Case.opened_by == user_id,
                                       Case.refs["attempt_id"].astext == str(a.id), Case.refs["seq"].astext == str(seq))):
        raise AppError(409, "already_reported", "Вы уже сообщили о проблеме в этом задании")
    _open(db, "item_problem", {"attempt_id": str(a.id), "seq": seq, "family_code": item.family_code, "reason": data.reason},
          user_id, data.comment)
    db.commit()


def _item_summary(db: Session, case: Case) -> list[dict]:
    item = db.scalar(select(AttemptItem).where(AttemptItem.attempt_id == uuid.UUID(case.refs["attempt_id"]),
                                               AttemptItem.seq == case.refs["seq"]))
    reason = row("Причина", ITEM_REASONS.get(case.refs.get("reason", ""), case.refs.get("reason", "")))
    if item is None:
        return [row("Задание", "попытка удалена. Обращение можно закрыть"), reason]
    return [row("Семейство", item.family_code), row("Область и уровень", f"{item.area}, уровень {item.level}"),
            row("Задание", (item.instance.get("public", {}).get("prompt", {}) or {}).get("text", "—")),
            row("Ответ кандидата", item.response if item.response is not None else "нет ответа"),
            row("Ключ ответа", item.instance.get("answer", "—")), reason]


def _item_apply(db: Session, case: Case, action: str) -> str:
    if action != "suspend":
        return "жалоба отклонена, задание остаётся в тесте"
    fam = db.get(ItemFamilyRow, case.refs["family_code"], with_for_update=True)
    if fam is None:
        return "задание уже убрано из теста"
    fam.status = "suspended"  # sync_bank этот статус не перезаписывает
    return "задание убрано из теста, спасибо"


register("item_problem", CaseType(
    title="Проблема в задании теста", actions={"suspend": "Снять семейство с выдачи", "dismiss": "Отклонить"},
    summary=_item_summary, apply=_item_apply, link="/candidate/profile"))


# --- возражение против автоматического решения (ст. 16 152-ФЗ)

def object_to_decision(db: Session, user_id: uuid.UUID, attempt_id: uuid.UUID, data: ObjectionIn) -> dict:
    a = _own_attempt(db, user_id, attempt_id)
    if a.kind != "grade" or a.decision is None:
        raise AppError(409, "no_decision", "Возразить можно против принятого решения по грейду")
    if db.scalar(select(Case.id).where(Case.type == "art16", Case.refs["attempt_id"].astext == str(a.id))):
        raise AppError(409, "already_objected", "Возражение по этой попытке уже отправлено")
    case = _open(db, "art16", {"attempt_id": str(a.id)}, user_id, data.comment)
    db.commit()
    return {"case_id": str(case.id), "due_at": case.created_at + timedelta(days=PARAMS.art16_days)}


def _art16_summary(db: Session, case: Case) -> list[dict]:
    a = db.get(Attempt, uuid.UUID(case.refs["attempt_id"]))
    if a is None:
        return [row("Попытка", "удалена. Обращение можно закрыть")]
    verdict = f"{GRADE_TITLES.get(a.target_grade, a.target_grade)} {'подтверждён' if a.decision == 'confirmed' else 'не подтверждён'}"
    answered = db.scalars(select(AttemptItem).where(AttemptItem.attempt_id == a.id, AttemptItem.answered_at.is_not(None))).all()
    return [row("Автоматическое решение", verdict), row("Попытка", f"{a.specialization}, {_day(a.started_at)}"),
            row("Решено заданий", f"{sum(1 for i in answered if i.correct)} из {len(answered)}"),
            row("Граница порога", "да, решение пограничное" if a.border else "нет")]


def _art16_apply(db: Session, case: Case, action: str) -> str:
    if action != "reset":
        return "решение оставлено в силе"
    a = db.get(Attempt, uuid.UUID(case.refs["attempt_id"]))
    p = db.get(CandidateProfile, a.user_id) if a is not None else None
    if p is None:
        return "кандидат уже удалён"
    p.cooldown_reset_at = now()  # как демо-сброс, но только для этого кандидата
    return "пересдать тест можно уже сейчас"


register("art16", CaseType(
    title="Возражение по ст. 16 152-ФЗ", actions={"uphold": "Оставить решение в силе", "reset": "Разрешить пересдачу сейчас"},
    summary=_art16_summary, apply=_art16_apply, link="/candidate/profile", due_days=PARAMS.art16_days))
