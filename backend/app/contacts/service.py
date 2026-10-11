"""Приглашения и контакт (процесс 2.8, 4.4, 9): квота, защита скрытого порога, встречное условие, согласие №4, чат.

Время-зависимые статусы (истечение приглашения и встречного условия) считаются лениво: при любом чтении
и записи (техдизайн, решение 4). Worker только ускоряет это и рассылает письма.
"""
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit.service import audit
from app.auth.consents import ConsentType, record_consent
from app.auth.models import Consent, User
from app.candidates.models import CandidateProfile
from app.common.clock import MSK, now
from app.common.errors import AppError
from app.config.params import PARAMS
from app.config.settings import get_settings
from app.contacts.models import (
    ACTIVE,
    CompanyBlock,
    Contact,
    ContactEvent,
    Message,
    effective_status,
)
from app.contacts.schemas import (
    DECLINE_TITLES,
    AcceptIn,
    CounterIn,
    CounterResponseIn,
    DeclineIn,
    InviteIn,
)
from app.employers.models import Company, CompanyMember, Need
from app.employers.service import get_need, require_company
from app.integrations.outbox import emit
from app.junior.rules import minor_hours_limit
from app.matching.scoring import NDFL, rank, to_net
from app.matching.service import alias, load_rows, need_facts
from app.matching.summary import candidate_card, facts_of, template_text
from app.moderation.complaints import penalize
from app.notifications.service import notify

OPEN_CHAT = ("accepted",)


def _event(db: Session, c: Contact, type_: str, actor: str, **payload) -> None:
    db.add(ContactEvent(contact_id=c.id, type=type_, actor=actor, payload=payload))
    # то же событие — в outbox для ATS компании; payload псевдонимен: ссылка кандидата, псевдоним, статус, адрес контакта
    p = db.get(CandidateProfile, c.user_id)
    emit(db, c.company_id, f"contact.{type_}", {
        "contact_id": str(c.id), "need_id": str(c.need_id), "channel": c.channel, "candidate_ref": p.public_ref if p else None,
        "alias": alias(p) if p else None, "actor": actor, "status": c.status, "version": c.version,
        "at": now().isoformat(), "contact_url": f"{get_settings().public_base_url.rstrip('/')}/contacts/{c.id}"})


def refresh(db: Session, c: Contact, t: datetime | None = None) -> Contact:
    """Ленивое истечение: приглашение — по expires_at, встречное условие — по counter_expires_at."""
    if effective_status(c, t or now()) == "expired" and c.status != "expired":
        was = c.status
        c.status = "expired"
        _event(db, c, "expired", "system")
        if was == "countered":  # компания не ответила на встречное условие
            _notify_candidate(db, c, "counter_expired", db.get(Company, c.company_id))
        else:  # кандидат не ответил на приглашение
            _notify_company(db, c, "invitation_expired", alias(db.get(CandidateProfile, c.user_id)))
    return c


def _members(db: Session, company_id: uuid.UUID) -> list[uuid.UUID]:
    return list(db.scalars(select(CompanyMember.user_id).where(CompanyMember.company_id == company_id)))


def _notify_company(db: Session, c: Contact, kind: str, alias_: str, suffix: str = "") -> None:
    for uid in _members(db, c.company_id):
        notify(db, uid, kind, {"alias": alias_, "link": f"/employer/needs/{c.need_id}/invitations"},
               f"{kind}:{c.id}:{c.version}{suffix}:{uid}")


def _notify_candidate(db: Session, c: Contact, kind: str, company: Company, suffix: str = "") -> None:
    notify(db, c.user_id, kind, {"company": company.name, "link": "/candidate/invitations",
                                 "expires": f"{c.expires_at.astimezone(MSK):%d.%m %H:%M}"},
           f"{kind}:{c.id}:{c.version}{suffix}")


def quota(db: Session, need: Need, company: Company) -> tuple[int, int]:
    """Квота — активные неотвеченные приглашения на потребность (процесс 4.4) минус штраф за жалобы."""
    limit = {"L0": PARAMS.quota_l0, "L1": PARAMS.quota_l1}.get(company.trust_level, PARAMS.quota_l2)
    if company.quota_penalty_until and company.quota_penalty_until > now():
        limit = max(0, limit - company.quota_penalty_slots)
    t = now()
    used = sum(1 for c in db.scalars(select(Contact).where(Contact.need_id == need.id, Contact.status.in_(ACTIVE)))
               if refresh(db, c, t).status in ACTIVE)
    return used, limit


def _profile_by_ref(db: Session, ref: str) -> CandidateProfile:
    p = db.scalar(select(CandidateProfile).where(CandidateProfile.public_ref == ref))
    if p is None:
        raise AppError(404, "candidate_not_found", "Кандидат не найден")
    return p


def _hours_limit(db: Session, ref: str, need: Need) -> int | None:
    """Предел часов в неделю, если кандидату нет 18 (ст. 92 ТК РФ); взрослому — None."""
    p = _profile_by_ref(db, ref)
    u = db.get(User, p.user_id)
    return minor_hours_limit(u.birth_date, u.birth_year, need.employment, now().date())


def invite_draft(db: Session, user: User, need_id: uuid.UUID, ref: str) -> dict:
    """Предзаполнение (процесс 2.8): «почему вы» — из объяснения подборки, вилка, gross/net и связь — из потребности."""
    need = get_need(db, user, need_id)
    company = require_company(db, user)
    card, _, _ = candidate_card(db, user, need_id, ref)
    used, limit = quota(db, need, company)
    db.commit()
    return {"ref": ref, "alias": card["alias"], "minor_hours_limit": _hours_limit(db, ref, need), "salary_from": need.salary_from, "salary_to": need.salary_to,
            "gross_net": need.gross_net, "description": company.description or "",
            "why_you": template_text(facts_of(card)), "next_step": "Знакомство по видео, 30 минут",
            "contact_method": need.contact_method, "quota_used": used, "quota_limit": limit}


def _history(db: Session, need_id: uuid.UUID, user_id: uuid.UUID, t: datetime) -> list[Contact]:
    return [refresh(db, c, t) for c in db.scalars(select(Contact).where(
        Contact.need_id == need_id, Contact.user_id == user_id).order_by(Contact.created_at))]


def ensure_no_contact(db: Session, need_id: uuid.UUID, user_id: uuid.UUID, *, by_candidate: bool = False) -> None:
    """Отклик на вакансию и приглашение — один путь к контакту: на пару «потребность — кандидат» не заводим второй
    (иначе доска показывает кандидата дважды, а приглашение держит слот квоты). Вызывать под блокировкой потребности."""
    history = _history(db, need_id, user_id, now())
    if any(c.status in ACTIVE for c in history):
        raise AppError(409, "invite_exists", "У вас уже есть приглашение от этой компании по этой потребности. "
                       "Ответьте на него" if by_candidate else "Приглашение этому кандидату уже ждёт ответа. "
                       "Дождитесь ответа или отзовите его")
    if any(c.status == "accepted" for c in history):
        raise AppError(409, "already_in_contact", "Вы уже в контакте с этой компанией по этой потребности. "
                       "Пишите в чат" if by_candidate else "Кандидат уже принял приглашение. Пишите в чат")


def check_pair(db: Session, need: Need, p: CandidateProfile, t: datetime, salary_to: int, gross_net: str) -> bool:
    """Правила пары «потребность — кандидат» (процесс 4.4): активное и принятое приглашение, повтор раньше срока.
    Возвращает True, если это досрочный повтор. Вызывать под блокировкой строки потребности."""
    history = _history(db, need.id, p.user_id, t)
    if any(c.status in ACTIVE for c in history):
        raise AppError(409, "invite_exists", "Приглашение этому кандидату уже ждёт ответа")
    if any(c.status == "accepted" for c in history):
        raise AppError(409, "already_in_contact", "Кандидат уже принял приглашение. Пишите в чат")
    recent = [c for c in history if c.created_at >= t - timedelta(days=PARAMS.reinvite_days)]
    early = bool(recent)
    if early:
        last = recent[-1]
        higher = to_net(salary_to, gross_net) > to_net(last.salary_to, last.gross_net)
        if not higher or any(c.early_reinvite for c in recent):
            raise AppError(409, "reinvite_too_early", "Пригласить этого кандидата повторно пока нельзя",
                           f"Повторить можно через {PARAMS.reinvite_days} дней после прошлого приглашения. "
                           "Раньше срока можно один раз, если вилка строго выше")
    return early


def minor_terms(db: Session, p: CandidateProfile, need: Need, hours: int | None) -> int | None:
    """Юниорские условия приглашения (2.10): согласие представителя, не полная занятость, часы в неделю не больше лимита
    ст. 92 ТК РФ. Возвращает часы для записи в контакт; взрослому — None."""
    u = db.get(User, p.user_id)
    cap = minor_hours_limit(u.birth_date, u.birth_year, need.employment, now().date())
    if cap is None:
        return None
    if p.guardian_consent_at is None:
        raise AppError(409, "guardian_consent_required", "Профиль кандидата пока черновик: нужно согласие законного представителя")
    if need.employment == "full":
        raise AppError(409, "minor_full_employment", "Несовершеннолетним доступны только стажировка и каникулярная работа")
    if hours is None:
        raise AppError(422, "hours_required", "Для кандидата младше 18 лет укажите часы в неделю",
                       f"Не больше {cap} ч в неделю (ст. 92 ТК РФ)")
    if hours > cap:
        raise AppError(422, "hours_over_limit", "Часов в неделю больше, чем допускает закон для возраста кандидата",
                       f"Не больше {cap} ч в неделю (ст. 92 ТК РФ)")
    return hours


def invite(db: Session, user: User, need_id: uuid.UUID, data: InviteIn) -> Contact:
    need = get_need(db, user, need_id)
    company = require_company(db, user)
    p = _profile_by_ref(db, data.ref)
    in_selection = any(r.c.ref == data.ref for r in rank(
        (row.facts for row in load_rows(db, need.specialization, need.company_id)), need_facts(need), now()))
    if not in_selection:
        raise AppError(404, "candidate_not_found", "Кандидата нет в подборке этой потребности")
    if db.get(CompanyBlock, (p.user_id, company.id)):
        raise AppError(409, "candidate_unavailable", "Кандидат недоступен для приглашений")
    hours = minor_terms(db, p, need, data.hours_per_week)
    t = now()
    # Приглашения по одной потребности сериализуются: квоту и пару проверяем под блокировкой строки потребности
    db.execute(select(Need.id).where(Need.id == need.id).with_for_update())
    early = check_pair(db, need, p, t, data.salary_to, data.gross_net)
    used, limit = quota(db, need, company)
    if used >= limit:
        raise AppError(409, "quota_exceeded", "Квота приглашений по этой потребности исчерпана",
                       f"Ответа ждут {used} из {limit}")
    c = Contact(need_id=need.id, company_id=company.id, user_id=p.user_id, salary_from=data.salary_from,
                salary_to=data.salary_to, gross_net=data.gross_net, description=data.description,
                why_you=data.why_you, next_step=data.next_step, contact_method=data.contact_method,
                hours_per_week=hours,
                expires_at=t + timedelta(days=PARAMS.invite_ttl_days), early_reinvite=early)
    db.add(c)
    try:
        db.flush()
    except IntegrityError as e:  # uq_contacts_active_pair: параллельный запрос успел первым
        db.rollback()
        raise AppError(409, "invite_exists", "Приглашение этому кандидату уже ждёт ответа") from e
    _event(db, c, "sent", "employer", salary_from=c.salary_from, salary_to=c.salary_to, gross_net=c.gross_net)
    _notify_candidate(db, c, "invitation", company)
    db.commit()
    return c


# --- кандидат

def _own(db: Session, user: User, contact_id: uuid.UUID) -> Contact:
    c = db.get(Contact, contact_id, with_for_update=True)
    if c is None or c.user_id != user.id:
        raise AppError(404, "contact_not_found", "Приглашение не найдено")
    return refresh(db, c)


def _require(c: Contact, allowed: tuple[str, ...], action: str) -> None:
    if c.status not in allowed:
        raise AppError(409, "invalid_transition", f"Нельзя {action}: статус «{c.status}»")


def my_invitations(db: Session, user: User) -> list[Contact]:
    t = now()
    rows = [refresh(db, c, t) for c in db.scalars(select(Contact).where(Contact.user_id == user.id)
                                                   .order_by(Contact.created_at.desc()))]
    db.commit()
    return rows


def view(db: Session, user: User, contact_id: uuid.UUID) -> Contact:
    c = _own(db, user, contact_id)
    if c.status == "sent":
        c.status, c.viewed_at = "viewed", now()
        _event(db, c, "viewed", "candidate")
    elif c.status == "offer_v2" and c.viewed_at is None:  # статус остаётся offer_v2, работодатель видит «просмотрено»
        c.viewed_at = now()
        _event(db, c, "viewed", "candidate", version=2)
    db.commit()
    return c


def accept(db: Session, user: User, contact_id: uuid.UUID, data: AcceptIn) -> Contact:
    c = _own(db, user, contact_id)
    _require(c, ("sent", "viewed", "offer_v2"), "принять")
    if c.channel == "group_member" and c.status != "offer_v2":  # контакты раскрываются только после офферов v2 по сроку
        raise AppError(409, "group_conditional_only", "В командном приглашении сначала дайте условное согласие",
                       "Контакты передаются после того, как компания отправит индивидуальный оффер")
    if not data.consent_contact_transfer:
        raise AppError(422, "consent_required", "Без согласия на передачу контактов принять приглашение нельзя")
    record_consent(db, user.id, ConsentType.contact_transfer, target_company_id=c.company_id)
    c.status, c.contacts_revealed_at = "accepted", now()
    _event(db, c, "accepted", "candidate")
    _notify_company(db, c, "invitation_accepted", alias(db.get(CandidateProfile, user.id)))
    db.commit()
    return c


def decline(db: Session, user: User, contact_id: uuid.UUID, data: DeclineIn) -> Contact:
    pre = db.get(Contact, contact_id)
    if pre is not None and pre.group_id is not None:  # порядок блокировок как в группах: сначала группа
        from app.groups.models import GroupInvite

        db.get(GroupInvite, pre.group_id, with_for_update=True)
    c = _own(db, user, contact_id)
    _require(c, ("sent", "viewed", "offer_v2", "conditionally_accepted"), "отклонить")
    if c.status == "conditionally_accepted":
        # выход после срока зависит от набранного минимума
        from app.groups.service import ensure_can_leave

        ensure_can_leave(db, c)
    c.status, c.decline_reason, c.decline_comment = "declined", data.reason, data.comment
    _event(db, c, "declined", "candidate", reason=data.reason)
    if data.reason == "spam":  # жалоба «спам или не соответствует описанию»: штраф к квоте и обращение модератору (4.4)
        penalize(db, db.get(Company, c.company_id, with_for_update=True), c)  # два отказа подряд не теряют штраф
    _notify_company(db, c, "invitation_declined", alias(db.get(CandidateProfile, user.id)))
    db.commit()
    return c


def counter(db: Session, user: User, contact_id: uuid.UUID, data: CounterIn) -> Contact:
    """Встречное условие — один раунд (процесс 2.8). Скрытый порог кандидата не меняется."""
    c = _own(db, user, contact_id)
    _require(c, ("sent", "viewed"), "предложить встречное условие")
    if c.channel == "group_member":
        raise AppError(409, "group_no_counter", "В командном приглашении встречное условие недоступно")
    if c.version > 1:
        raise AppError(409, "counter_used", "Встречное условие можно предложить один раз")
    c.status = "countered"
    c.counter_amount = _convert(data.amount, data.gross_net, c.gross_net)
    c.counter_comment = data.comment
    c.counter_expires_at = now() + timedelta(days=PARAMS.counter_ttl_days)
    _event(db, c, "countered", "candidate", amount=c.counter_amount)
    _notify_company(db, c, "invitation_countered", alias(db.get(CandidateProfile, user.id)))
    db.commit()
    return c


def _convert(amount: int, frm: str, to: str) -> int:
    """Встречная сумма приводится к gross/net оффера, чтобы стороны сравнивали одно и то же."""
    if frm == to:
        return amount
    net = to_net(amount, frm)
    return net if to == "net" else round(net / (1 - NDFL))


def revoke(db: Session, user: User, contact_id: uuid.UUID) -> Contact:
    """«Скрыть контакты на платформе и уведомить компанию»: согласие №4 для этой компании отзывается."""
    c = _own(db, user, contact_id)
    _require(c, ("accepted",), "скрыть контакты")
    t = now()
    # Согласие №4 дано компании, а не потребности: скрываем контакты во всех её принятых приглашениях
    others = db.scalars(select(Contact).where(Contact.user_id == user.id, Contact.company_id == c.company_id,
                                              Contact.status == "accepted", Contact.id != c.id).with_for_update())
    for other in [c, *others]:
        other.status, other.revoked_at = "revoked", t
        _event(db, other, "revoked", "candidate")
    for consent in db.scalars(select(Consent).where(
            Consent.user_id == user.id, Consent.type == ConsentType.contact_transfer.value,
            Consent.target_company_id == c.company_id, Consent.revoked_at.is_(None))):
        consent.revoked_at = t
    _notify_company(db, c, "contacts_revoked", alias(db.get(CandidateProfile, user.id)))
    db.commit()
    return c


def block(db: Session, user: User, company_id: uuid.UUID) -> None:
    if db.get(Company, company_id) is None:
        raise AppError(404, "company_not_found", "Компания не найдена")
    if db.get(CompanyBlock, (user.id, company_id)) is None:
        db.add(CompanyBlock(user_id=user.id, company_id=company_id))
    db.commit()


def unblock(db: Session, user: User, company_id: uuid.UUID) -> None:
    row = db.get(CompanyBlock, (user.id, company_id))
    if row:
        db.delete(row)
    db.commit()


def blocked_companies(db: Session, user: User) -> list[Company]:
    return list(db.scalars(select(Company).join(CompanyBlock, CompanyBlock.company_id == Company.id)
                           .where(CompanyBlock.user_id == user.id).order_by(Company.name)))


# --- работодатель

def _company_contact(db: Session, user: User, contact_id: uuid.UUID) -> Contact:
    company = require_company(db, user)
    c = db.get(Contact, contact_id, with_for_update=True)
    if c is None or c.company_id != company.id:
        raise AppError(404, "contact_not_found", "Приглашение не найдено")
    return refresh(db, c)


def need_invitations(db: Session, user: User, need_id: uuid.UUID) -> list[tuple[Contact, CandidateProfile]]:
    need = get_need(db, user, need_id)
    t = now()
    rows = [(refresh(db, c, t), db.get(CandidateProfile, c.user_id)) for c in db.scalars(
        select(Contact).where(Contact.need_id == need.id).order_by(Contact.created_at.desc()))]
    db.commit()
    return rows


def respond_counter(db: Session, user: User, contact_id: uuid.UUID, data: CounterResponseIn) -> Contact:
    """Исходы встречного условия: оффер v2 (тот же слот квоты, «строго выше» не применяется) или отказ."""
    c = _company_contact(db, user, contact_id)
    _require(c, ("countered",), "ответить на встречное условие")
    company = db.get(Company, c.company_id)
    if data.action == "decline":
        c.status = "company_declined"
        _event(db, c, "company_declined", "employer")
        _notify_candidate(db, c, "counter_declined", company)
    else:
        c.status, c.version, c.viewed_at = "offer_v2", 2, None
        c.salary_from, c.salary_to = data.salary_from, data.salary_to
        c.expires_at = now() + timedelta(days=PARAMS.invite_ttl_days)
        _event(db, c, "offer_v2", "employer", salary_from=c.salary_from, salary_to=c.salary_to)
        _notify_candidate(db, c, "offer_v2", company)
    db.commit()
    return c


def withdraw(db: Session, user: User, contact_id: uuid.UUID) -> Contact:
    c = _company_contact(db, user, contact_id)
    _require(c, ("sent", "viewed", "offer_v2", "countered", "conditionally_accepted"), "отозвать приглашение")
    c.status = "withdrawn"
    _event(db, c, "withdrawn", "employer")
    _notify_candidate(db, c, "invitation_withdrawn", db.get(Company, c.company_id))
    db.commit()
    return c


# --- страница контакта и чат

def _side(db: Session, user: User, contact_id: uuid.UUID) -> tuple[Contact, str]:
    c = db.get(Contact, contact_id, with_for_update=True)
    if c is not None and c.user_id == user.id:
        return refresh(db, c), "candidate"
    if c is not None and db.get(CompanyMember, (c.company_id, user.id)):
        return refresh(db, c), "employer"
    raise AppError(404, "contact_not_found", "Контакт не найден")


def _consent_active(db: Session, c: Contact) -> bool:
    return db.scalar(select(Consent.id).where(
        Consent.user_id == c.user_id, Consent.type == ConsentType.contact_transfer.value,
        Consent.target_company_id == c.company_id, Consent.revoked_at.is_(None)).limit(1)) is not None


def chat_open(db: Session, c: Contact) -> bool:
    """Контакты и чат открыты, пока приглашение принято и согласие №4 этой компании действует (спецификация 5.5)."""
    return c.status in OPEN_CHAT and c.revoked_at is None and _consent_active(db, c)


def contact_page(db: Session, user: User, contact_id: uuid.UUID) -> dict:
    c, role = _side(db, user, contact_id)
    p = db.get(CandidateProfile, c.user_id)
    candidate = None
    open_ = chat_open(db, c)
    if role == "employer" and open_:
        cand_user = db.get(User, c.user_id)
        candidate = {"full_name": p.full_name, "email": cand_user.email, "contacts": p.contacts or {}}
        audit(db, user.id, "contact_view", "contact", str(c.id))  # каждый просмотр контактов — в аудит
    company = db.get(Company, c.company_id)
    out = {"id": str(c.id), "status": c.status, "role": role, "company": company_brief(company),
           "need_title": db.get(Need, c.need_id).title, "alias": alias(p), "candidate": candidate,
           "chat_open": open_, "messages": messages(db, user, c)}
    db.commit()
    return out


def messages(db: Session, user: User, c: Contact) -> list[dict]:
    rows = db.scalars(select(Message).where(Message.contact_id == c.id).order_by(Message.at, Message.id))
    return [{"id": m.id, "mine": m.author_user_id == user.id,
             "author": "candidate" if m.author_user_id == c.user_id else "company", "text": m.text, "at": m.at}
            for m in rows]


def contact_messages(db: Session, user: User, contact_id: uuid.UUID) -> list[dict]:
    """Только сообщения — для опроса чата: без ПДн кандидата и без записи в аудит просмотров."""
    c, _ = _side(db, user, contact_id)
    out = messages(db, user, c)
    db.commit()
    return out


def post_message(db: Session, user: User, contact_id: uuid.UUID, text: str) -> dict:
    c, role = _side(db, user, contact_id)
    if not chat_open(db, c):
        raise AppError(409, "chat_closed", "Чат доступен, когда приглашение принято и контакты не скрыты")
    m = Message(contact_id=c.id, author_user_id=user.id, text=text.strip())
    db.add(m)
    db.flush()
    hour = f"{now():%Y%m%d%H}"
    if role == "employer":
        company = db.get(Company, c.company_id)
        notify(db, c.user_id, "message", {"who": f"компанией «{company.name}»", "link": f"/contacts/{c.id}"},
               f"message:{c.id}:candidate:{hour}")
    else:
        p = db.get(CandidateProfile, c.user_id)
        for uid in _members(db, c.company_id):
            notify(db, uid, "message", {"who": alias(p), "link": f"/contacts/{c.id}"}, f"message:{c.id}:{uid}:{hour}")
    db.commit()
    return {"id": m.id, "mine": True, "author": role if role == "candidate" else "company", "text": m.text, "at": m.at}


def company_brief(company: Company) -> dict:
    return {"id": str(company.id), "name": company.name, "industry": company.industry,
            "description": company.description, "trust_level": company.trust_level}


def decline_title(reason: str | None) -> str | None:
    return DECLINE_TITLES.get(reason) if reason else None
