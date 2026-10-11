from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User, UserSession
from app.common.clock import now
from app.common.errors import AppError
from app.common.security import hash_token
from app.db.session import get_db

SESSION_COOKIE = "fsp_session"


def _session_from_request(request: Request, db: Session) -> UserSession | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    s = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    if s is None or s.revoked_at is not None or s.expires_at < now():
        return None
    return s


def optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    s = _session_from_request(request, db)
    if s is None:
        return None
    request.state.session = s
    return db.get(User, s.user_id)


def current_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise AppError(401, "unauthenticated", "Требуется вход")
    return user


def require_roles(*roles: str) -> Callable[..., User]:
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise AppError(403, "forbidden", "Недостаточно прав")
        return user

    return dep
