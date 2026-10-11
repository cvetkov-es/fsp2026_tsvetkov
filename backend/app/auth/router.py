from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.consents import CONSENT_TEXTS, DISTRIBUTION_PRESETS, ConsentType
from app.auth.deps import SESSION_COOKIE, current_user
from app.auth.models import User
from app.auth.schemas import LoginIn, MeOut, RegisterIn, RegisterOut, TokenIn
from app.config.params import PARAMS
from app.config.settings import get_settings
from app.db.session import get_db

router = APIRouter(tags=["auth"])


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE, token, httponly=True, samesite="lax",
        secure=get_settings().cookie_secure, max_age=PARAMS.session_ttl_days * 86400, path="/",
    )


def me_out(user: User, request: Request) -> MeOut:
    session = getattr(request.state, "session", None)
    return MeOut(id=user.id, email=user.email, role=user.role, is_demo=user.is_demo,
                 impersonated_by=session.impersonated_by if session else None)


@router.post("/auth/register", status_code=201, response_model=RegisterOut)
def register(data: RegisterIn, db: Session = Depends(get_db)) -> RegisterOut:
    user, url = service.register(db, data)
    return RegisterOut(user_id=user.id, email=user.email,
                       verify_url=url if get_settings().demo_mode else None)


@router.post("/auth/verify", status_code=204)
def verify(data: TokenIn, db: Session = Depends(get_db)) -> Response:
    service.verify_email(db, data.token)
    return Response(status_code=204)


@router.post("/auth/login", response_model=MeOut)
def login(data: LoginIn, response: Response, db: Session = Depends(get_db)) -> MeOut:
    user = service.authenticate(db, data.email, data.password)
    set_session_cookie(response, service.create_session(db, user))
    return MeOut(id=user.id, email=user.email, role=user.role, is_demo=user.is_demo)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        service.revoke_session(db, token)
    resp = Response(status_code=204)
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


@router.get("/auth/me", response_model=MeOut)
def me(request: Request, user: User = Depends(current_user)) -> MeOut:
    return me_out(user, request)


@router.get("/consents/texts", tags=["consents"])
def consent_texts() -> dict:
    return {
        "texts": [{"type": t.value, "version": c.version, "title": c.title, "body": c.body}
                  for t, c in CONSENT_TEXTS.items() if t != ConsentType.guardian],  # текст представителя — на странице /guardian/{token}
        "presets": DISTRIBUTION_PRESETS,
    }
