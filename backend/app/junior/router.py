from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.auth.deps import require_roles
from app.auth.models import User
from app.common.errors import AppError
from app.config.settings import get_settings
from app.db.session import get_db
from app.junior import service

router = APIRouter(tags=["junior"])
candidate = require_roles("candidate")


class GuardianIn(BaseModel):
    email: EmailStr


class GuardianRequestOut(BaseModel):
    status: str
    guardian_url: str | None = None  # только в демо-режиме, как verify_url при регистрации


class JuniorOut(BaseModel):
    minor: bool
    age: int | None
    status: str  # adult | draft | active
    guardian_email: str | None
    hours_limit_vacation: int | None
    hours_limit_school: int | None


class GuardianPageOut(BaseModel):
    title: str
    body: str
    candidate_email: str
    guardian_email: str | None


class GuardianAcceptIn(BaseModel):
    accept: bool
    guardian_name: str = Field(min_length=3, max_length=200)


@router.get("/candidate/junior", response_model=JuniorOut)
def junior_state(user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    out = service.state(db, user)
    db.commit()
    return out


@router.post("/candidate/junior/guardian", status_code=201, response_model=GuardianRequestOut)
def request_guardian(data: GuardianIn, user: User = Depends(candidate), db: Session = Depends(get_db)) -> GuardianRequestOut:
    url = service.request_guardian(db, user, str(data.email))
    return GuardianRequestOut(status="sent", guardian_url=url if get_settings().demo_mode else None)


@router.get("/guardian/{token}", response_model=GuardianPageOut)
def guardian_page(token: str, db: Session = Depends(get_db)) -> dict:
    return service.guardian_page(db, token)


@router.post("/guardian/{token}", response_model=GuardianRequestOut)
def guardian_accept(token: str, data: GuardianAcceptIn, db: Session = Depends(get_db)) -> GuardianRequestOut:
    if not data.accept:
        raise AppError(422, "consent_required", "Без согласия законного представителя профиль остаётся черновиком")
    service.accept_guardian(db, token, data.guardian_name.strip())
    return GuardianRequestOut(status="accepted")
