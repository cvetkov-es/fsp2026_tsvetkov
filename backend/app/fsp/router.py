import logging
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.audit.service import audit
from app.auth.deps import optional_user, require_roles
from app.auth.models import Role, User
from app.auth.router import set_session_cookie
from app.auth.schemas import MeOut
from app.auth.service import create_session
from app.candidates.models import CandidateProfile
from app.common.errors import AppError
from app.config.params import PARAMS
from app.config.settings import get_settings
from app.db.session import get_db
from app.employers.service import require_company
from app.fsp import accounts, oidc
from app.fsp.http import get_fsp_http
from app.fsp.schemas import FspCompleteIn, FspOut, FspPendingOut, TeamOut
from app.fsp.sync import fsp_view, sync, unlink
from app.fsp.teams import prize_teams

log = logging.getLogger("fsp")
router = APIRouter(tags=["fsp"])
STATE_COOKIE = "fsp_oidc"
STATE_PATH = "/api/v1/auth/fsp"
candidate = require_roles("candidate")
employer = require_roles("employer")


def _go(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=302)


@router.get("/auth/fsp/start")
def fsp_start(purpose: Literal["login", "link"] = "login", user: User | None = Depends(optional_user),
              db: Session = Depends(get_db), http: httpx.Client = Depends(get_fsp_http)) -> RedirectResponse:
    if purpose == "link" and (user is None or user.role != Role.candidate):
        return _go("/login?fsp_error=login_required")
    try:
        url, state = oidc.start(db, http, purpose, user.id if purpose == "link" else None)
    except AppError as e:
        return _go(f"/login?fsp_error={e.code}")
    resp = _go(url)
    resp.set_cookie(STATE_COOKIE, state, httponly=True, samesite="lax", secure=get_settings().cookie_secure,
                    max_age=PARAMS.oidc_ttl_min * 60, path=STATE_PATH)
    return resp


@router.get("/auth/fsp/callback")
def fsp_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None,
                 current: User | None = Depends(optional_user), db: Session = Depends(get_db),
                 http: httpx.Client = Depends(get_fsp_http)) -> RedirectResponse:
    if error or not code or not state:
        return _go(f"/login?fsp_error={'access_denied' if error == 'access_denied' else 'invalid_request'}")
    try:
        st = oidc.consume_state(db, state, request.cookies.get(STATE_COOKIE))
    except AppError as e:
        return _go(f"/login?fsp_error={e.code}")
    if st.purpose == "link" and (current is None or current.id != st.user_id):
        resp = _go("/login?fsp_error=login_required")  # за время входа в браузере сменился пользователь
    else:
        resp = _finish_callback(db, http, code, st)
    resp.delete_cookie(STATE_COOKIE, path=STATE_PATH)
    return resp


def _finish_callback(db: Session, http: httpx.Client, code: str, st) -> RedirectResponse:
    back = "/candidate/profile" if st.purpose == "link" else "/login"
    try:
        ident = oidc.exchange(http, code, st)
        if st.purpose == "link":
            owner = db.get(User, st.user_id)
            accounts.link(db, owner, ident)
            sync(db, http, owner.id, ident.access_token)
            audit(db, owner.id, "fsp.link", "user", str(owner.id))
            db.commit()
            return _go("/candidate/profile?fsp=linked")
        if (linked := accounts.identity_by_subject(db, ident.subject)) is None:
            return _go(f"/fsp/finish?ticket={accounts.create_pending(db, ident)}")
        user = db.get(User, linked.user_id)
        profile = db.get(CandidateProfile, user.id)
        if profile is None or profile.fsp_status != "CONSENT_REVOKED":
            sync(db, http, user.id, ident.access_token)  # после отзыва вход не возвращает удалённые данные
        db.commit()
        resp = _go("/")
        set_session_cookie(resp, create_session(db, user))
        return resp
    except AppError as e:
        db.rollback()
        return _go(f"{back}?fsp_error={e.code}")
    except Exception:  # браузерный переход: вместо JSON 500 — страница с понятной ошибкой
        log.exception("fsp callback failed")
        db.rollback()
        return _go(f"{back}?fsp_error=internal")


@router.get("/auth/fsp/pending/{ticket}", response_model=FspPendingOut)
def fsp_pending(ticket: str, db: Session = Depends(get_db)) -> FspPendingOut:
    p = accounts.pending_for_signup(db, ticket)
    return FspPendingOut(email=p.email, name=p.name)


@router.post("/auth/fsp/complete", response_model=MeOut)
def fsp_complete(data: FspCompleteIn, response: Response, db: Session = Depends(get_db),
                 http: httpx.Client = Depends(get_fsp_http)) -> MeOut:
    user = accounts.complete(db, http, data)
    set_session_cookie(response, create_session(db, user))
    return MeOut(id=user.id, email=user.email, role=user.role, is_demo=user.is_demo)


@router.get("/candidate/fsp", response_model=FspOut)
def my_fsp(user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    return fsp_view(db, user)


@router.delete("/candidate/fsp", status_code=204)
def unlink_fsp(user: User = Depends(candidate), db: Session = Depends(get_db)) -> Response:
    unlink(db, user)
    return Response(status_code=204)


@router.get("/employer/teams", response_model=list[TeamOut])
def teams(specialization: Literal["backend", "frontend", "data"] | None = None, user: User = Depends(employer),
          db: Session = Depends(get_db)) -> list[dict]:
    require_company(db, user)
    return prize_teams(db, specialization)
