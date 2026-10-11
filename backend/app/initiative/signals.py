"""«Хочу к вам» (процесс 2.9, 6.4): SIGNALS_PER_QUARTER в календарный квартал, сигнал действует SIGNAL_TTL.

Сигнал видит только компания-адресат: в подборке её потребностей готовность кандидата поднимается правилом max
(scoring.accept), в кабинете — список «Интерес к компании». Отзыв сигнала слот не возвращает.
"""
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import Consent, User
from app.candidates.models import CandidateProfile
from app.candidates.service import get_or_create_profile
from app.common.clock import MSK, now
from app.common.errors import AppError
from app.config.params import PARAMS
from app.contacts.models import CompanyBlock
from app.contacts.service import _members
from app.employers.models import Company, Need
from app.employers.service import require_company
from app.initiative.models import Signal
from app.matching.service import alias, load_rows
from app.notifications.service import notify


def quarter_start(t: datetime) -> datetime:
    local = t.astimezone(MSK)
    return local.replace(month=3 * ((local.month - 1) // 3) + 1, day=1, hour=0, minute=0, second=0, microsecond=0)


def _active(t: datetime):
    return (Signal.withdrawn_at.is_(None), Signal.created_at > t - timedelta(days=PARAMS.signal_ttl_days))


def _active_signals(db: Session, company_id: uuid.UUID, t: datetime) -> dict[uuid.UUID, datetime]:
    """Действующие сигналы компании; кандидат, скрывший компанию после сигнала, не считается."""
    hidden = select(CompanyBlock.user_id).where(CompanyBlock.company_id == company_id)
    return dict(db.execute(select(Signal.user_id, Signal.created_at).where(
        Signal.company_id == company_id, Signal.user_id.not_in(hidden), *_active(t))).all())


def active_signal_users(db: Session, company_id: uuid.UUID, t: datetime) -> set[uuid.UUID]:
    return set(_active_signals(db, company_id, t))


def _visible(db: Session, p: CandidateProfile) -> bool:
    """Компания видит кандидата, только если грейд проверен тестом и согласие на показ профиля действует (согласие №2)."""
    return p.grade_status in ("confirmed", "not_confirmed") and db.scalar(select(Consent.id).where(
        Consent.user_id == p.user_id, Consent.type == "distribution", Consent.revoked_at.is_(None)).limit(1)) is not None


def _left(db: Session, user_id: uuid.UUID, t: datetime) -> int:
    used = db.scalar(select(func.count()).select_from(Signal).where(Signal.user_id == user_id,
                                                                    Signal.created_at >= quarter_start(t)))
    return max(0, PARAMS.signals_per_quarter - used)


def companies_for_candidate(db: Session, user: User) -> dict:
    """Компании с открытыми потребностями, кроме скрытых кандидатом («Не показывать эту компанию»)."""
    t = now()
    blocked = set(db.scalars(select(CompanyBlock.company_id).where(CompanyBlock.user_id == user.id)))
    open_needs = dict(db.execute(select(Need.company_id, func.count()).where(Need.status == "active")
                                 .group_by(Need.company_id)).all())
    mine = {s.company_id: s.id for s in db.scalars(select(Signal).where(Signal.user_id == user.id, *_active(t)))}
    items = [{"id": str(c.id), "name": c.name, "industry": c.industry, "description": c.description,
              "trust_level": c.trust_level, "open_needs": open_needs.get(c.id, 0),
              "signal_id": str(mine[c.id]) if c.id in mine else None}
             for c in db.scalars(select(Company).order_by(Company.name))
             if c.id not in blocked and open_needs.get(c.id)]
    return {"signals_left": _left(db, user.id, t), "signals_limit": PARAMS.signals_per_quarter, "items": items}


def send_signal(db: Session, user: User, company_id: uuid.UUID) -> dict:
    p = get_or_create_profile(db, user)
    db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user.id).with_for_update())  # лимит без гонок
    company = db.get(Company, company_id)
    if company is None:
        raise AppError(404, "company_not_found", "Компания не найдена")
    if db.get(CompanyBlock, (user.id, company.id)):
        raise AppError(409, "company_blocked", "Эта компания скрыта в ваших настройках")
    t = now()
    if not _visible(db, p):  # сигнал невидимого кандидата никто не прочтёт, а слот квартала он бы потратил
        raise AppError(409, "not_visible", "Сначала пройдите тест и включите показ профиля работодателям",
                       "Без этого компания не увидит отметку интереса")
    if db.scalar(select(Signal.id).where(Signal.user_id == user.id, Signal.company_id == company.id, *_active(t))):
        raise AppError(409, "already_signaled", "Вы уже отметили интерес к этой компании")
    if _left(db, user.id, t) == 0:
        raise AppError(409, "signal_limit", "Отметки на этот квартал закончились. Новые появятся в следующем квартале")
    s = Signal(user_id=user.id, company_id=company.id, created_at=t)
    db.add(s)
    db.flush()
    for uid in _members(db, company.id):
        notify(db, uid, "signal", {"alias": alias(p), "link": "/"}, f"signal:{s.id}:{uid}")
    db.commit()  # сигнал — не «значимое действие» процесса 6.4: активность не обновляет
    return {"signal_id": str(s.id), "signals_left": _left(db, user.id, t)}


def withdraw_signal(db: Session, user: User, signal_id: uuid.UUID) -> dict:
    s = db.get(Signal, signal_id)
    if s is None or s.user_id != user.id:
        raise AppError(404, "signal_not_found", "Отметка интереса не найдена")
    if s.withdrawn_at is None:
        s.withdrawn_at = now()
    db.commit()
    return {"signal_id": str(s.id), "signals_left": _left(db, user.id, now())}


def company_interest(db: Session, user: User) -> list[dict]:
    """Кандидаты с действующим сигналом компании — только те, кто виден в подборке (согласие №2)."""
    company = require_company(db, user)
    t = now()
    signals = _active_signals(db, company.id, t)
    rows = load_rows(db, user_ids=set(signals))
    return [{"ref": r.facts.ref, "alias": alias(r.profile), "specialization": r.facts.specialization,
             "grade": r.facts.confirmed_grade or r.facts.claimed_grade, "grade_status": r.facts.grade_status,
             "at": signals[r.profile.user_id]} for r in sorted(rows, key=lambda r: signals[r.profile.user_id], reverse=True)]
