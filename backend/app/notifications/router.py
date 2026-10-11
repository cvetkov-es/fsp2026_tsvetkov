from datetime import datetime

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.auth.models import User
from app.db.session import get_db
from app.notifications import service

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    id: int
    kind: str
    title: str
    link: str | None
    created_at: datetime
    read: bool


class NotificationsOut(BaseModel):
    items: list[NotificationOut]
    unread: int


@router.get("", response_model=NotificationsOut)
def list_notifications(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    items, unread = service.latest(db, user.id)
    return {"items": items, "unread": unread}


@router.post("/read", status_code=204)
def read_all(user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    service.mark_read(db, user.id)
    return Response(status_code=204)
