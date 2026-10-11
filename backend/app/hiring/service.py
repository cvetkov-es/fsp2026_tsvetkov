"""Доска найма: этапы по принятым приглашениям, вопрос об уровне, голоса; «Мои оценки» и спор (процесс 2.9, 4.7, 5)."""
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.assessment.bank.areas import AREA_TITLES, AREAS
from app.auth.models import User
from app.candidates.models import CandidateProfile
from app.candidates.service import get_or_create_profile
from app.common.clock import now
from app.common.errors import AppError
from app.config.params import PARAMS
from app.config.settings import get_settings
from app.contacts.models import Contact, ContactEvent
from app.contacts.service import _company_contact, chat_open
from app.employers.models import Company
from app.employers.service import get_need
from app.hiring.models import PipelineStage, Vote
from app.hiring.schemas import DisputeIn, StageIn
from app.hiring.votes import Holder, add_months, holder, status_grade, vote_state, vote_weight
from app.integrations.outbox import emit
from app.matching.service import alias
from app.moderation.service import open_case

ORDER = ("first", "technical", "offer")
FINAL = ("hired", "rejected")
ASK_LEVEL = ("technical", "hired", "rejected")  # «на этапе „техническое“ и в финале» (процесс 4.7)
REJECT_REASONS = ("level_below", "stack", "candidate_declined", "other_candidate", "position_closed", "other")
MONTH = timedelta(days=30)


def can_move(current: str | None, target: str) -> bool:
    """Только вперёд; в финал — с любого этапа; на «техническом» и в финале можно переответить."""
    if current in FINAL:
        return target == current
    if target in FINAL or current is None:
        return True
    return ORDER.index(target) > ORDER.index(current) or target == current == "technical"


def _stages(db: Session, contact_id: uuid.UUID) -> list[PipelineStage]:
    return list(db.scalars(select(PipelineStage).where(PipelineStage.contact_id == contact_id)
                           .order_by(PipelineStage.at, PipelineStage.id)))


def _votes_used(db: Session, company_id: uuid.UUID, t: datetime) -> int:
    return db.scalar(select(func.count()).select_from(Vote).where(Vote.company_id == company_id,
                                                                  Vote.created_at > t - MONTH))


def _answer(v: Vote, level: str, weight: float, company: Company, h: Holder, t: datetime) -> None:
    """Последний ответ компании: значение, категория кандидата на момент ответа и новое окно спора."""
    v.value, v.pending_value, v.weight, v.trust_at_vote = level, None, weight, company.trust_level
    v.spec_at_vote, v.grade_at_vote = h.specialization, h.grade
    v.status, v.answered_at, v.effective_at = "pending", t, t + timedelta(days=PARAMS.vote_dispute_days)


def _new_vote_blocked(db: Session, company: Company, user_id: uuid.UUID, h: Holder, t: datetime,
                      exclude: Vote | None) -> str | None:
    """Новый голос: один от компании о кандидате за VOTE_TTL и не больше VOTE_MONTHLY за 30 дней.

    Архивные голоса (по прежней категории кандидата) не мешают оценить новую категорию."""
    since = add_months(t, -PARAMS.vote_ttl_months)
    for other in db.scalars(select(Vote).where(Vote.company_id == company.id, Vote.user_id == user_id,
                                               Vote.status != "annulled", Vote.created_at > since)):
        if other is not exclude and vote_state(other, h, t) != "archived":
            return "duplicate"
    if _votes_used(db, company.id, t) >= PARAMS.vote_monthly:
        return "limit"
    return None


def _record_vote(db: Session, c: Contact, company: Company, p: CandidateProfile, level: str,
                 t: datetime) -> str | None:
    """Ответ «ниже / соответствует / выше» — голос. Возвращает, почему голос не учтён или не изменён, иначе None.

    Последний ответ в процессе перезаписывает прежний (процесс 4.7 [51]): новое значение — с новым окном спора,
    то же значение голос не трогает. Во время спора ответ откладывается до решения модератора."""
    if level not in ("below", "meets", "above"):
        return None  # «пока не могу сказать» ничего не меняет
    weight = vote_weight(company.trust_level)
    if weight is None:
        return "trust"
    h = holder(p)
    v = db.scalar(select(Vote).where(Vote.contact_id == c.id).with_for_update())
    if v is not None:
        state = vote_state(v, h, t)
        if state == "annulled":
            return "annulled"
        if state == "disputed":
            v.pending_value = level
            return "disputed"
        if state not in ("archived", "expired"):
            if v.value != level:
                _answer(v, level, weight, company, h, t)
            return None
    # нового голоса нет или прежний по этому контакту в архиве или истёк — это новый голос со всеми проверками
    note = _new_vote_blocked(db, company, c.user_id, h, t, exclude=v)
    if note:
        return note
    if v is None:
        v = Vote(contact_id=c.id, company_id=company.id, user_id=c.user_id)
        db.add(v)
    _answer(v, level, weight, company, h, t)
    v.created_at = t  # от него считаются VOTE_MONTHLY и VOTE_TTL
    return None


def card(db: Session, c: Contact, p: CandidateProfile, t: datetime) -> dict:
    stages = _stages(db, c.id)
    cur = stages[-1] if stages else None
    level = next((s.level for s in reversed(stages) if s.level and s.level != "unknown"), None)
    v = db.scalar(select(Vote).where(Vote.contact_id == c.id))
    vote = None if v is None else {"value": v.value, "effective_at": v.effective_at, "state": vote_state(v, holder(p), t)}
    return {"contact_id": str(c.id), "alias": alias(p), "grade": status_grade(p), "revoked": c.status == "revoked",
            "stage": cur.stage if cur else None, "stage_at": cur.at if cur else c.contacts_revealed_at,
            "level": level, "reason": cur.reason if cur else None, "weak_areas": cur.weak_areas if cur else [],
            "vote": vote, "vote_note": cur.vote_note if cur else None, "chat_open": chat_open(db, c),
            "area_options": [{"code": a, "title": AREA_TITLES[a]} for a in AREAS.get(p.specialization or "", ())]}


def board(db: Session, user: User, need_id: uuid.UUID) -> dict:
    need = get_need(db, user, need_id)
    company = db.get(Company, need.company_id)
    t = now()
    # Скрывший контакты кандидат остаётся на доске только для чтения: история найма у компании не пропадает
    cards = [card(db, c, db.get(CandidateProfile, c.user_id), t) for c in db.scalars(
        select(Contact).where(Contact.need_id == need.id, Contact.status.in_(("accepted", "revoked")),
                              Contact.contacts_revealed_at.is_not(None))
        .order_by(Contact.updated_at.desc()))]
    return {"need_id": str(need.id), "title": need.title, "trust_level": company.trust_level,
            "vote_weight": vote_weight(company.trust_level), "votes_used": _votes_used(db, company.id, t),
            "votes_limit": PARAMS.vote_monthly, "dispute_days": PARAMS.vote_dispute_days, "cards": cards}


def move_stage(db: Session, user: User, contact_id: uuid.UUID, data: StageIn) -> dict:
    c = _company_contact(db, user, contact_id)
    if c.status != "accepted" or not chat_open(db, c):
        raise AppError(409, "contact_not_open", "Этапы можно отмечать, когда приглашение принято и контакты открыты")
    stages = _stages(db, c.id)
    if not can_move(stages[-1].stage if stages else None, data.stage):
        raise AppError(409, "stage_not_allowed", "На этот этап перейти нельзя: этапы идут только вперёд")
    if data.stage in ASK_LEVEL and data.level is None:
        raise AppError(422, "level_required", "Ответьте на вопрос об уровне. Подойдёт и «пока не могу сказать»")
    if data.stage == "rejected" and data.reason not in REJECT_REASONS:
        raise AppError(422, "reason_required", "Укажите причину отказа")
    p = db.get(CandidateProfile, c.user_id)
    if not set(data.weak_areas) <= set(AREAS.get(p.specialization or "", ())):
        raise AppError(422, "bad_weak_areas", "Слабые области можно выбрать только из областей специализации кандидата")
    company = db.scalar(select(Company).where(Company.id == c.company_id).with_for_update())  # лимит голосов без гонок
    t = now()
    level = data.level if data.stage in ASK_LEVEL else None
    note = _record_vote(db, c, company, p, level, t) if level else None
    db.add(PipelineStage(contact_id=c.id, stage=data.stage, level=level,
                         reason=data.reason if data.stage == "rejected" else None,
                         weak_areas=list(data.weak_areas) if data.stage in FINAL else [], vote_note=note,
                         actor_user_id=user.id, at=t))
    db.add(ContactEvent(contact_id=c.id, type=f"stage_{data.stage}", actor="employer", payload={"level": level}))
    # этап — в ATS компании; уровень и голос не уходят: оценки приватны
    emit(db, c.company_id, "pipeline.stage", {
        "contact_id": str(c.id), "need_id": str(c.need_id), "stage": data.stage, "candidate_ref": p.public_ref, "alias": alias(p),
        "at": t.isoformat(), "contact_url": f"{get_settings().public_base_url.rstrip('/')}/contacts/{c.id}"})
    db.flush()
    out = card(db, c, p, t)
    db.commit()
    return out


def my_reviews(db: Session, user: User) -> list[dict]:
    """«Мои оценки на собеседованиях» — приватный список «компания → оценка → дата» (процесс 2.9)."""
    p = get_or_create_profile(db, user)
    t, h = now(), holder(p)
    out = []
    for v in db.scalars(select(Vote).where(Vote.user_id == user.id).order_by(Vote.answered_at.desc())):
        state = vote_state(v, h, t)
        out.append({"id": str(v.id), "company": db.get(Company, v.company_id).name, "value": v.value,
                    "grade": v.grade_at_vote, "specialization": v.spec_at_vote, "at": v.answered_at,
                    "effective_at": v.effective_at, "state": state, "can_dispute": state == "pending"})
    return out


def dispute(db: Session, user: User, vote_id: uuid.UUID, data: DisputeIn) -> list[dict]:
    """Спор — в течение VOTE_DISPUTE и только по фактам; голос не действует, пока спор не рассмотрен."""
    v = db.get(Vote, vote_id, with_for_update=True)
    if v is None or v.user_id != user.id:
        raise AppError(404, "vote_not_found", "Оценка не найдена")
    p = get_or_create_profile(db, user)
    if vote_state(v, holder(p), now()) != "pending":
        raise AppError(409, "dispute_closed", "Оспорить оценку можно, пока она не вступила в силу")
    if data.answered_at is not None and data.answered_at != v.answered_at:
        raise AppError(409, "vote_changed", "Компания изменила оценку. Обновите страницу и проверьте её")
    v.status, v.dispute_reason, v.dispute_comment = "disputed", data.reason, data.comment
    open_case(db, "vote_dispute", {"vote_id": str(v.id), "contact_id": str(v.contact_id)}, user.id, data.comment)
    db.commit()
    return my_reviews(db, user)
