import logging
from datetime import date, timedelta
from functools import lru_cache

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.audit.service import audit
from app.auth.consents import DISTRIBUTION_PRESETS, ConsentType, record_consent
from app.auth.models import EmailToken, Role, User, UserSession
from app.auth.schemas import RegisterConsents, RegisterIn
from app.common.clock import now
from app.common.errors import AppError
from app.common.security import hash_password, hash_token, new_token, verify_password
from app.config.params import PARAMS
from app.config.settings import get_settings
from app.integrations.mail import get_mailer

log = logging.getLogger("auth")


def _age(birth: date, today: date) -> int:
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


@lru_cache
def _dummy_hash() -> str:
    """Хэш-заглушка: вход с несуществующим email тратит столько же времени, сколько с настоящим."""
    return hash_password("timing-equalizer")


def validate_candidate_signup(consents: RegisterConsents, birth_date: date | None) -> None:
    if not consents.processing or not consents.distribution_preset:
        raise AppError(422, "consent_required", "Нужны обязательные согласия")
    if birth_date is None:
        raise AppError(422, "birth_date_required", "Укажите дату рождения")
    if _age(birth_date, now().date()) < PARAMS.min_age:
        raise AppError(422, "age_restricted", f"Регистрация доступна с {PARAMS.min_age} лет")


def record_signup_consents(db: Session, user_id, role: str, consents: RegisterConsents) -> None:
    record_consent(db, user_id, ConsentType.processing)
    if role == Role.candidate:
        preset = consents.distribution_preset
        record_consent(db, user_id, ConsentType.distribution,
                       scope={"preset": preset, "fields": DISTRIBUTION_PRESETS[preset]})


def register(db: Session, data: RegisterIn) -> tuple[User, str]:
    email = data.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise AppError(409, "email_taken", "Этот email уже зарегистрирован")
    c = data.consents
    if data.role == Role.candidate:
        validate_candidate_signup(c, data.birth_date)
    elif not c.processing:
        raise AppError(422, "consent_required", "Нужны обязательные согласия")

    user = User(email=email, role=data.role, password_hash=hash_password(data.password),
                birth_year=data.birth_date.year if data.birth_date else None, birth_date=data.birth_date)
    db.add(user)
    db.flush()
    record_signup_consents(db, user.id, data.role, c)
    token = new_token()
    db.add(EmailToken(user_id=user.id, purpose="verify", token_hash=hash_token(token),
                      expires_at=now() + timedelta(hours=PARAMS.verify_ttl_hours)))
    audit(db, user.id, "user.register", "user", str(user.id), {"role": data.role})
    db.commit()

    url = f"{get_settings().public_base_url}/verify?token={token}"
    # Письмо — по возможности: сбой почты не должен оставлять аккаунт без ответа клиенту
    try:
        get_mailer().send(email, "Подтвердите адрес почты", f"Ссылка для подтверждения: {url}")
    except Exception:
        log.exception("verification mail failed for user %s", user.id)
    return user, url


def verify_email(db: Session, token: str) -> None:
    # Одно условное UPDATE: из двух одновременных запросов с одним токеном пройдёт только первый
    ts = now()
    user_id = db.scalar(
        update(EmailToken)
        .where(EmailToken.token_hash == hash_token(token), EmailToken.purpose == "verify",
               EmailToken.used_at.is_(None), EmailToken.expires_at >= ts)
        .values(used_at=ts)
        .returning(EmailToken.user_id)
    )
    if user_id is None:
        raise AppError(400, "token_invalid", "Ссылка недействительна или уже использована")
    db.execute(update(User).where(User.id == user_id).values(email_verified_at=ts))
    db.commit()


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not user.password_hash:
        verify_password(_dummy_hash(), password)
        raise AppError(401, "bad_credentials", "Неверный email или пароль")
    if not verify_password(user.password_hash, password):
        raise AppError(401, "bad_credentials", "Неверный email или пароль")
    if user.email_verified_at is None:
        raise AppError(403, "email_not_verified", "Подтвердите адрес почты")
    return user


def create_session(db: Session, user: User, impersonated_by=None) -> str:
    token = new_token()
    db.add(UserSession(user_id=user.id, token_hash=hash_token(token),
                       expires_at=now() + timedelta(days=PARAMS.session_ttl_days),
                       impersonated_by=impersonated_by))
    db.commit()
    return token


def revoke_session(db: Session, token: str) -> None:
    s = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    if s and s.revoked_at is None:
        s.revoked_at = now()
        db.commit()
