import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import require_roles
from app.auth.models import User
from app.config.params import PARAMS
from app.contacts.router import invitation_out
from app.contacts.schemas import InvitationOut
from app.db.session import get_db
from app.groups import service
from app.groups.schemas import GroupIn, GroupListItemOut, GroupOut, LimitsOut

router = APIRouter(tags=["groups"])
employer = require_roles("employer")
candidate = require_roles("candidate")


@router.post("/employer/groups", status_code=201, response_model=GroupOut)
def create(data: GroupIn, user: User = Depends(employer), db: Session = Depends(get_db)) -> dict:
    return service.create_group(db, user, data)


@router.get("/employer/groups/limits", response_model=LimitsOut)
def limits(user: User = Depends(employer)) -> dict:
    """Пределы формы командного приглашения — из PARAMS, чтобы числа не дублировались во фронтенде."""
    return {"ttl_days": PARAMS.group_ttl_days, "min_team": PARAMS.team_min_on_platform}


@router.get("/employer/groups", response_model=list[GroupListItemOut])
def groups(user: User = Depends(employer), db: Session = Depends(get_db)) -> list[dict]:
    return service.employer_groups(db, user)


@router.get("/employer/groups/{group_id}", response_model=GroupOut)
def group(group_id: uuid.UUID, user: User = Depends(employer), db: Session = Depends(get_db)) -> dict:
    return service.employer_group(db, user, group_id)


@router.post("/employer/groups/{group_id}/finalize", response_model=GroupOut)
def finalize(group_id: uuid.UUID, user: User = Depends(employer), db: Session = Depends(get_db)) -> dict:
    return service.finalize(db, user, group_id)


@router.post("/employer/groups/{group_id}/withdraw", response_model=GroupOut)
def withdraw(group_id: uuid.UUID, user: User = Depends(employer), db: Session = Depends(get_db)) -> dict:
    return service.withdraw(db, user, group_id)


@router.post("/candidate/invitations/{contact_id}/conditional-accept", response_model=InvitationOut)
def conditional_accept(contact_id: uuid.UUID, user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    return invitation_out(db, service.conditional_accept(db, user, contact_id))


@router.post("/candidate/invitations/{contact_id}/conditional-withdraw", response_model=InvitationOut)
def conditional_withdraw(contact_id: uuid.UUID, user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    return invitation_out(db, service.conditional_withdraw(db, user, contact_id))
