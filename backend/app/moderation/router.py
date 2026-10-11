import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import require_roles
from app.auth.models import User
from app.db.session import get_db
from app.moderation import service
from app.moderation.schemas import CaseOut, ResolveIn

router = APIRouter(prefix="/moderation", tags=["moderation"])
moderator = require_roles("moderator", "admin")


@router.get("/cases", response_model=list[CaseOut])
def cases(status: Literal["open", "resolved"] = "open", user: User = Depends(moderator),
          db: Session = Depends(get_db)) -> list[dict]:
    return service.list_cases(db, status)


@router.post("/cases/{case_id}/resolve", response_model=CaseOut)
def resolve(case_id: uuid.UUID, data: ResolveIn, user: User = Depends(moderator), db: Session = Depends(get_db)) -> dict:
    return service.resolve(db, user, case_id, data)
