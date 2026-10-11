"""Групповые приглашения (процесс 4.5): пакет индивидуальных офферов команде ФСП с общим group_id.

Участник даёт условное согласие: контакты не раскрываются, согласие можно отозвать до срока. По сроку работодатель, если
минимум набран, отправляет индивидуальные офферы v2 согласившимся; принимается оффер обычным путём — с согласием №4.
"""
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.candidates.models import CandidateProfile
from app.common.clock import now
from app.common.errors import AppError
from app.config.params import PARAMS
from app.contacts.models import ACTIVE, CompanyBlock, Contact
from app.contacts.service import (
    _event,
    _members,
    _notify_candidate,
    _own,
    _profile_by_ref,
    _require,
    check_pair,
    minor_terms,
    quota,
    refresh,
)
from app.employers.models import Company, Need
from app.employers.service import get_need, require_company
from app.fsp.teams import prize_teams
from app.groups.models import GroupInvite
from app.groups.schemas import GroupIn
from app.matching.service import alias
from app.notifications.service import notify


def _contacts(db: Session, g: GroupInvite, t: datetime) -> list[Contact]:
    return [refresh(db, c, t) for c in db.scalars(select(Contact).where(Contact.group_id == g.id).order_by(Contact.created_at))]


def _agreed(contacts: list[Contact]) -> int:
    return sum(1 for c in contacts if c.status == "conditionally_accepted")


def group_state(g: GroupInvite, contacts: list[Contact], t: datetime) -> str:
    """Статус вычисляется при чтении: до срока — open; после — набран ли минимум; после v2 или отзыва — closed."""
    if g.finalized_at is not None or g.withdrawn_at is not None:
        return "closed"
    if t < g.deadline:
        return "open"
    return "min_reached" if _agreed(contacts) >= g.min_size else "not_reached"


def group_out(db: Session, g: GroupInvite) -> dict:
    t = now()
    contacts = _contacts(db, g, t)
    return {"id": str(g.id), "team_name": g.team_name, "need_id": str(g.need_id), "need_title": db.get(Need, g.need_id).title,
            "min_size": g.min_size, "size": len(contacts), "deadline": g.deadline,
            "state": group_state(g, contacts, t), "min_reached_now": _agreed(contacts) >= g.min_size,
            "members": [{"contact_id": str(c.id), "alias": alias(db.get(CandidateProfile, c.user_id)), "status": c.status,
                         "salary_from": c.salary_from, "salary_to": c.salary_to, "hours_per_week": c.hours_per_week}
                        for c in contacts]}


def group_brief(db: Session, c: Contact) -> dict | None:
    """Карточка группы для участника: ни состава, ни чужих ответов; статус минимума — только если минимум меньше состава."""
    if c.group_id is None:
        return None
    g = db.get(GroupInvite, c.group_id)
    t = now()
    contacts = _contacts(db, g, t)
    size, state = len(contacts), group_state(g, contacts, t)
    open_minimum = g.min_size < size
    if state in ("min_reached", "not_reached") and not open_minimum:
        state = "ended"  # срок вышел, итог по минимуму участникам не показывается
    return {"team_name": g.team_name, "size": size, "min_size": g.min_size, "deadline": g.deadline, "state": state,
            "min_reached_now": (_agreed(contacts) >= g.min_size) if open_minimum else None}


def create_group(db: Session, user: User, data: GroupIn) -> dict:
    need = get_need(db, user, data.need_id)
    company = require_company(db, user)
    if need.status != "active":
        raise AppError(409, "need_closed", "Потребность закрыта")
    team = next((x for x in prize_teams(db) if x["team_id"] == data.team_id), None)
    if team is None:
        raise AppError(404, "team_not_found", "Команда не найдена среди призовых команд ФСП на платформе")
    refs = [m.ref for m in data.members]
    if len(set(refs)) != len(refs):
        raise AppError(422, "duplicate_member", "Участник указан дважды")
    if not set(refs) <= {m["ref"] for m in team["members"]}:
        raise AppError(422, "member_not_in_team", "Приглашать можно только участников этой команды на платформе")
    if len(refs) < PARAMS.team_min_on_platform:
        raise AppError(422, "team_too_small", f"В командном приглашении не меньше {PARAMS.team_min_on_platform} участников")
    if data.min_size > len(refs):
        raise AppError(422, "bad_min_size", "Минимальный состав больше числа приглашённых")
    t = now()
    if not t < data.deadline <= t + timedelta(days=PARAMS.group_ttl_days):
        raise AppError(422, "bad_deadline", f"Срок должен быть в будущем и не дальше {PARAMS.group_ttl_days} дней")
    # Как и обычные приглашения: пары и квота проверяются под блокировкой строки потребности, до создания контактов
    db.execute(select(Need.id).where(Need.id == need.id).with_for_update())
    prepared = []
    for m in data.members:
        p = _profile_by_ref(db, m.ref)
        if db.get(CompanyBlock, (p.user_id, company.id)):
            raise AppError(409, "candidate_unavailable", "Участник недоступен для приглашений", alias(p))
        hours = minor_terms(db, p, need, m.hours_per_week)
        early = check_pair(db, need, p, t, m.salary_to, data.gross_net)
        prepared.append((p, m, hours, early))
    used, limit = quota(db, need, company)
    if used + len(prepared) > limit:
        raise AppError(409, "quota_exceeded", "Квоты приглашений по этой потребности не хватает на всю команду",
                       f"Ответа ждут {used} из {limit}, для команды нужно {len(prepared)}")
    g = GroupInvite(company_id=company.id, need_id=need.id, team_id=data.team_id, team_name=team["team_name"],
                    min_size=data.min_size, deadline=data.deadline)
    db.add(g)
    db.flush()
    for p, m, hours, early in prepared:
        c = Contact(channel="group_member", group_id=g.id, need_id=need.id, company_id=company.id, user_id=p.user_id,
                    salary_from=m.salary_from, salary_to=m.salary_to, gross_net=data.gross_net, description=data.description,
                    why_you=data.why_you, next_step=data.next_step, contact_method=data.contact_method,
                    hours_per_week=hours, expires_at=data.deadline, early_reinvite=early)
        db.add(c)
        db.flush()
        _event(db, c, "group_sent", "employer", group_id=str(g.id), salary_from=c.salary_from, salary_to=c.salary_to,
               gross_net=c.gross_net)
        notify(db, p.user_id, "group_invitation", {"company": company.name, "team": g.team_name, "link": "/candidate/invitations"},
               f"group_invitation:{c.id}")
    db.commit()
    return group_out(db, g)


def _own_group(db: Session, user: User, group_id: uuid.UUID, lock: bool = False) -> GroupInvite:
    company = require_company(db, user)
    g = db.get(GroupInvite, group_id, with_for_update=lock)
    if g is None or g.company_id != company.id:
        raise AppError(404, "group_not_found", "Командное приглашение не найдено")
    return g


def employer_group(db: Session, user: User, group_id: uuid.UUID) -> dict:
    out = group_out(db, _own_group(db, user, group_id))
    db.commit()
    return out


def employer_groups(db: Session, user: User) -> list[dict]:
    company = require_company(db, user)
    t = now()
    out = []
    for g in db.scalars(select(GroupInvite).where(GroupInvite.company_id == company.id).order_by(GroupInvite.created_at.desc())):
        contacts = _contacts(db, g, t)
        out.append({"id": str(g.id), "team_name": g.team_name, "need_title": db.get(Need, g.need_id).title,
                    "size": len(contacts), "deadline": g.deadline, "state": group_state(g, contacts, t)})
    db.commit()
    return out


def _locked_member(db: Session, user: User, contact_id: uuid.UUID) -> tuple[Contact, GroupInvite]:
    """Порядок блокировок везде один — группа, затем контакт (как в finalize и withdraw)."""
    c = db.get(Contact, contact_id)
    if c is None or c.user_id != user.id:
        raise AppError(404, "contact_not_found", "Приглашение не найдено")
    if c.channel != "group_member" or c.group_id is None:
        raise AppError(409, "not_group_member", "Это не командное приглашение")
    g = db.get(GroupInvite, c.group_id, with_for_update=True)
    return _own(db, user, contact_id), g


def ensure_can_leave(db: Session, c: Contact) -> None:
    """Выйти из условного согласия можно до срока; после срока — только если минимум не набран и оффера не будет."""
    g = db.get(GroupInvite, c.group_id, with_for_update=True)
    t = now()
    if g.finalized_at or g.withdrawn_at:
        raise AppError(409, "group_closed", "Командное приглашение уже закрыто")
    if t >= g.deadline and _agreed(_contacts(db, g, t)) >= g.min_size:
        raise AppError(409, "group_closed", "Срок командного приглашения вышел, согласие уже не отозвать")


def conditional_accept(db: Session, user: User, contact_id: uuid.UUID) -> Contact:
    """Условное согласие: контакты не раскрываются, согласие №4 не записывается, чат закрыт."""
    c, g = _locked_member(db, user, contact_id)
    _require(c, ("sent", "viewed"), "согласиться условно")
    c.status = "conditionally_accepted"
    _event(db, c, "conditionally_accepted", "candidate", group_id=str(g.id))
    contacts = _contacts(db, g, now())
    # минимум набран впервые — работодателю и согласившимся, один раз на группу (дедупликация по ключу) и только если минимум меньше состава
    if g.min_size < len(contacts) and _agreed(contacts) == g.min_size:
        for uid in _members(db, g.company_id):
            notify(db, uid, "group_min_reached", {"team": g.team_name, "link": f"/employer/groups/{g.id}"},
                   f"group_min_reached:{g.id}:{uid}")
        for m in contacts:
            if m.status == "conditionally_accepted":
                notify(db, m.user_id, "group_min_reached", {"team": g.team_name, "link": "/candidate/invitations"},
                       f"group_min_reached:{g.id}:{m.user_id}")
    db.commit()
    return c


def conditional_withdraw(db: Session, user: User, contact_id: uuid.UUID) -> Contact:
    """Отзыв условного согласия — до срока; после срока — только если минимум не набран (оффера не будет)."""
    c, g = _locked_member(db, user, contact_id)
    _require(c, ("conditionally_accepted",), "отозвать условное согласие")
    ensure_can_leave(db, c)
    c.status = "viewed" if c.viewed_at else "sent"
    _event(db, c, "conditional_withdrawn", "candidate", group_id=str(g.id))
    db.commit()
    return c


def finalize(db: Session, user: User, group_id: uuid.UUID) -> dict:
    """Офферы v2 согласившимся — после срока и при набранном минимуме; дальше обычный оффер с согласием №4."""
    g = _own_group(db, user, group_id, lock=True)
    t = now()
    if g.finalized_at is not None or g.withdrawn_at is not None:
        raise AppError(409, "group_closed", "Командное приглашение уже закрыто")
    if t < g.deadline:
        raise AppError(409, "group_open", "Срок командного приглашения ещё не вышел")
    contacts = _contacts(db, g, t)
    if _agreed(contacts) < g.min_size:
        raise AppError(409, "min_not_reached", "Минимальный состав не набран")
    company = db.get(Company, g.company_id)
    for c in contacts:
        if c.status != "conditionally_accepted":
            continue
        c.version += 1
        c.status, c.expires_at, c.viewed_at = "offer_v2", t + timedelta(days=PARAMS.invite_ttl_days), None
        _event(db, c, "group_finalized", "employer", group_id=str(g.id), version=c.version)
        _notify_candidate(db, c, "offer_v2", company)
    g.finalized_at = t
    db.commit()
    return group_out(db, g)


def withdraw(db: Session, user: User, group_id: uuid.UUID) -> dict:
    """Работодатель отзывает приглашение команды: все активные участники — «отозвано», слоты квоты свободны."""
    g = _own_group(db, user, group_id, lock=True)
    t = now()
    if g.finalized_at is not None or g.withdrawn_at is not None:
        raise AppError(409, "group_closed", "Командное приглашение уже закрыто")
    company = db.get(Company, g.company_id)
    for c in _contacts(db, g, t):
        if c.status in ACTIVE:
            c.status = "withdrawn"
            _event(db, c, "withdrawn", "employer", group_id=str(g.id))
            _notify_candidate(db, c, "invitation_withdrawn", company)
    g.withdrawn_at = t
    db.commit()
    return group_out(db, g)
