"""Юниорский трек 14–17 лет (процесс 2.10): согласие законного представителя, состояние кабинета.

Правила возраста и часов — в `rules.py` (чистые функции); здесь только то, что ходит в БД и в почту.
"""
import logging
from datetime import date, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.audit.service import audit
from app.auth.consents import CONSENT_TEXTS, ConsentType, record_consent
from app.auth.models import EmailToken, User
from app.candidates.models import CandidateProfile
from app.candidates.service import get_or_create_profile
from app.common.clock import now
from app.common.errors import AppError
from app.common.security import hash_token, new_token
from app.config.params import PARAMS
from app.config.settings import get_settings
from app.integrations.mail import get_mailer
from app.junior.rules import age_of, hours_limit, is_minor_age

log = logging.getLogger(__name__)
__all__ = ["age", "hours_limit", "is_minor", "request_guardian", "guardian_page", "accept_guardian", "state"]


def age(user: User, today: date) -> int | None:
    return age_of(user.birth_date, user.birth_year, today)


def is_minor(user: User, today: date) -> bool:
    return is_minor_age(age(user, today))


def _mask(email: str) -> str:
    name, _, domain = email.partition("@")
    return f"{name[:2]}***@{domain}"


def request_guardian(db: Session, user: User, email: str) -> str:
    """Записывает почту представителя и выдаёт одноразовую ссылку на согласие (действует GUARDIAN_TOKEN_TTL)."""
    p = get_or_create_profile(db, user)
    if not is_minor(user, now().date()):
        raise AppError(409, "not_minor", "Согласие представителя нужно только кандидатам младше 18 лет")
    t = now()
    # токен живёт TTL: если до конца срока осталось больше TTL минус пауза, ссылка выдана совсем недавно
    recent = db.scalar(select(EmailToken.id).where(
        EmailToken.user_id == user.id, EmailToken.purpose == "guardian", EmailToken.used_at.is_(None),
        EmailToken.expires_at > t + timedelta(days=PARAMS.guardian_token_ttl_days) - timedelta(minutes=PARAMS.guardian_resend_minutes)))
    if recent is not None:
        raise AppError(429, "guardian_link_recent", "Ссылка представителю уже отправлена",
                       f"Новую можно запросить через {PARAMS.guardian_resend_minutes} мин")
    p.guardian_email = email.lower()
    # прежние неиспользованные ссылки гасим: действует только последняя
    db.execute(update(EmailToken).where(EmailToken.user_id == user.id, EmailToken.purpose == "guardian",
                                        EmailToken.used_at.is_(None)).values(used_at=t))
    token = new_token()
    db.add(EmailToken(user_id=user.id, purpose="guardian", token_hash=hash_token(token),
                      expires_at=t + timedelta(days=PARAMS.guardian_token_ttl_days)))
    audit(db, user.id, "junior.guardian_requested", "user", str(user.id))
    db.commit()
    url = f"{get_settings().public_base_url}/guardian/{token}"
    try:  # письмо — по возможности: сбой почты не должен ломать запрос
        get_mailer().send(p.guardian_email, "Согласие законного представителя", f"Ссылка для согласия: {url}")
    except Exception:
        log.exception("guardian mail failed for user %s", user.id)
    return url


def _open_token(db: Session, token: str) -> EmailToken:
    row = db.scalar(select(EmailToken).where(EmailToken.token_hash == hash_token(token), EmailToken.purpose == "guardian",
                                             EmailToken.used_at.is_(None), EmailToken.expires_at >= now()))
    if row is None:
        raise AppError(400, "token_invalid", "Ссылка недействительна, устарела или уже использована")
    return row


def guardian_page(db: Session, token: str) -> dict:
    row = _open_token(db, token)
    text = CONSENT_TEXTS[ConsentType.guardian]
    return {"title": text.title, "body": text.body, "candidate_email": _mask(db.get(User, row.user_id).email),
            "guardian_email": db.get(CandidateProfile, row.user_id).guardian_email}


def accept_guardian(db: Session, token: str, guardian_name: str) -> None:
    ts = now()
    # одно условное UPDATE: из двух одновременных запросов с одной ссылкой пройдёт только первый
    user_id = db.scalar(update(EmailToken).where(
        EmailToken.token_hash == hash_token(token), EmailToken.purpose == "guardian", EmailToken.used_at.is_(None),
        EmailToken.expires_at >= ts).values(used_at=ts).returning(EmailToken.user_id))
    if user_id is None:
        raise AppError(400, "token_invalid", "Ссылка недействительна, устарела или уже использована")
    p = db.get(CandidateProfile, user_id)
    record_consent(db, user_id, ConsentType.guardian, scope={"guardian_email": p.guardian_email, "guardian_name": guardian_name})
    p.guardian_consent_at = ts
    audit(db, user_id, "junior.guardian_consent", "user", str(user_id))
    db.commit()


def state(db: Session, user: User) -> dict:
    p = get_or_create_profile(db, user)
    a = age(user, now().date())
    minor = is_minor_age(a)
    out = {"minor": minor, "age": a, "status": "adult", "guardian_email": p.guardian_email if minor else None,
           "hours_limit_vacation": None, "hours_limit_school": None}
    if minor:
        out |= {"status": "active" if p.guardian_consent_at else "draft",
                "hours_limit_vacation": hours_limit(a, "vacation"), "hours_limit_school": hours_limit(a, "internship")}
    return out
