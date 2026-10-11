import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import require_roles
from app.auth.models import User
from app.db.session import get_db
from app.hiring import helper, service
from app.hiring.schemas import BoardCardOut, BoardOut, DisputeIn, HelperOut, ReviewOut, StageIn

router = APIRouter(tags=["hiring"])
employer = require_roles("employer")
candidate = require_roles("candidate")


@router.get("/employer/needs/{need_id}/board", response_model=BoardOut)
def board(need_id: uuid.UUID, user: User = Depends(employer), db: Session = Depends(get_db)) -> dict:
    return service.board(db, user, need_id)


@router.post("/employer/contacts/{contact_id}/stage", response_model=BoardCardOut)
def move_stage(contact_id: uuid.UUID, data: StageIn, user: User = Depends(employer),
               db: Session = Depends(get_db)) -> dict:
    return service.move_stage(db, user, contact_id, data)


@router.get("/employer/contacts/{contact_id}/interview-helper", response_model=HelperOut)
def interview_helper(contact_id: uuid.UUID, user: User = Depends(employer), db: Session = Depends(get_db)) -> dict:
    return helper.interview_helper(db, user, contact_id)


@router.get("/candidate/reviews", response_model=list[ReviewOut])
def reviews(user: User = Depends(candidate), db: Session = Depends(get_db)) -> list[dict]:
    return service.my_reviews(db, user)


@router.post("/candidate/reviews/{vote_id}/dispute", response_model=list[ReviewOut])
def dispute(vote_id: uuid.UUID, data: DisputeIn, user: User = Depends(candidate),
            db: Session = Depends(get_db)) -> list[dict]:
    return service.dispute(db, user, vote_id, data)
