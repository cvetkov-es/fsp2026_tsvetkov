import uuid

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import audit
from app.auth.deps import optional_user, require_roles
from app.auth.models import User
from app.auth.router import set_session_cookie
from app.auth.schemas import MeOut
from app.auth.service import create_session
from app.candidates.service import get_or_create_profile
from app.common.clock import now
from app.common.errors import AppError
from app.config.settings import get_settings
from app.db.session import get_db


def require_demo_mode() -> None:
    if not get_settings().demo_mode:
        raise AppError(404, "not_found", "Не найдено")


router = APIRouter(prefix="/demo", tags=["demo"], dependencies=[Depends(require_demo_mode)])


class LoginAsIn(BaseModel):
    user_id: uuid.UUID


@router.get("/personas")
def personas(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(User).where(User.is_demo.is_(True)).order_by(User.email))
    return [{"id": str(u.id), "email": u.email, "role": u.role} for u in rows]


@router.post("/login-as", response_model=MeOut)
def login_as(data: LoginAsIn, response: Response, request: Request,
             db: Session = Depends(get_db), actor: User | None = Depends(optional_user)) -> MeOut:
    target = db.get(User, data.user_id)
    if target is None or not target.is_demo:
        raise AppError(403, "not_demo_persona", "Это не демо-персона. Выберите другую из списка")
    token = create_session(db, target, impersonated_by=actor.id if actor else None)
    audit(db, actor.id if actor else None, "demo.login_as", "user", str(target.id))
    db.commit()
    set_session_cookie(response, token)
    return MeOut(id=target.id, email=target.email, role=target.role, is_demo=True,
                 impersonated_by=actor.id if actor else None)


candidate = require_roles("candidate")


@router.post("/reset-cooldowns", status_code=204)
def reset_cooldowns(user: User = Depends(candidate), db: Session = Depends(get_db)) -> Response:
    p = get_or_create_profile(db, user)
    p.cooldown_reset_at = now()
    audit(db, user.id, "demo.reset_cooldowns", "user", str(user.id))
    db.commit()
    return Response(status_code=204)
