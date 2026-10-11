"""Связь аккаунта с FSP ID по iss + sub. Никакой автоматической привязки по email (исследование 04, §4)."""
import secrets
from datetime import timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit.service import audit
from app.auth.models import ExternalIdentity, Role, User
from app.auth.service import record_signup_consents, validate_candidate_signup
from app.candidates.service import get_or_create_profile
from app.common.clock import now
from app.common.errors import AppError
from app.config.params import PARAMS
from app.config.settings import get_settings
from app.fsp.models import OidcPending
from app.fsp.oidc import Identity
from app.fsp.schemas import FspCompleteIn
from app.fsp.sync import FSP_PROVIDER, sync


def identity_by_subject(db: Session, subject: str) -> ExternalIdentity | None:
    return db.scalar(select(ExternalIdentity).where(ExternalIdentity.issuer == get_settings().fsp_issuer,
                                                    ExternalIdentity.subject == subject))


def link(db: Session, user: User, ident: Identity) -> None:
    existing = identity_by_subject(db, ident.subject)
    if existing is not None and existing.user_id != user.id:
        raise AppError(409, "fsp_already_linked", "Этот FSP ID уже привязан к другому аккаунту")
    other = db.scalar(select(ExternalIdentity).where(ExternalIdentity.user_id == user.id,
                                                     ExternalIdentity.provider == FSP_PROVIDER))
    if other is not None and other.subject != ident.subject:
        raise AppError(409, "fsp_other_linked", "К аккаунту уже привязан другой FSP ID. Сначала отвяжите его")
    if existing is None:
        _add_identity(db, user.id, ident.subject)


def _add_identity(db: Session, user_id, subject: str) -> None:
    """Две одновременные привязки одного FSP ID: UNIQUE(issuer, subject) решает гонку, ответ — тот же 409."""
    try:
        with db.begin_nested():
            db.add(ExternalIdentity(user_id=user_id, provider=FSP_PROVIDER, issuer=get_settings().fsp_issuer,
                                    subject=subject))
    except IntegrityError as e:
        raise AppError(409, "fsp_already_linked", "Этот FSP ID уже привязан к другому аккаунту") from e


def create_pending(db: Session, ident: Identity) -> str:
    ticket = secrets.token_urlsafe(32)
    db.add(OidcPending(ticket=ticket, subject=ident.subject, email=(ident.email or "").lower() or None,
                       email_verified=ident.email_verified, name=ident.name, access_token=ident.access_token))
    db.commit()
    return ticket


def pending(db: Session, ticket: str) -> OidcPending:
    p = db.get(OidcPending, ticket)
    if p is None or p.used_at is not None or p.created_at < now() - timedelta(minutes=PARAMS.oidc_ttl_min):
        raise AppError(400, "fsp_ticket_invalid", "Ссылка устарела. Начните вход через FSP ID заново")
    return p


def pending_for_signup(db: Session, ticket: str) -> OidcPending:
    """Билет годен для нового аккаунта, только если FSP ID подтвердил почту — это видно сразу, до согласий."""
    p = pending(db, ticket)
    if not p.email or not p.email_verified:
        raise AppError(422, "fsp_email_unverified", "FSP ID не подтвердил почту. Зарегистрируйтесь по почте")
    return p


def complete(db: Session, http: httpx.Client, data: FspCompleteIn) -> User:
    p = pending_for_signup(db, data.ticket)
    if db.scalar(select(User.id).where(User.email == p.email)):
        raise AppError(409, "email_taken_link",
                       "Этот email уже зарегистрирован: войдите по почте и привяжите FSP ID в профиле")
    if identity_by_subject(db, p.subject):
        raise AppError(409, "fsp_already_linked", "Этот FSP ID уже привязан к другому аккаунту")
    validate_candidate_signup(data.consents, data.birth_date)
    user = User(email=p.email, role=Role.candidate, password_hash=None, birth_year=data.birth_date.year, birth_date=data.birth_date,
                email_verified_at=now())  # почту подтвердил FSP ID
    db.add(user)
    db.flush()
    record_signup_consents(db, user.id, Role.candidate, data.consents)
    _add_identity(db, user.id, p.subject)
    get_or_create_profile(db, user).full_name = p.name
    p.used_at = now()
    sync(db, http, user.id, p.access_token)
    p.access_token = None  # токен нужен был один раз — для первой синхронизации
    audit(db, user.id, "user.register_fsp", "user", str(user.id))
    db.commit()
    return user
