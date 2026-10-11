import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.assessment import service
from app.assessment.schemas import (
    AnswerIn,
    AttemptOut,
    AttemptSummary,
    AvailabilityOut,
    SkillOut,
    SkillStartIn,
    StartIn,
)
from app.auth.deps import require_roles
from app.auth.models import User
from app.db.session import get_db
from app.moderation import complaints
from app.moderation.schemas import ObjectionIn, ObjectionOut, ReportIn

router = APIRouter(prefix="/candidate", tags=["assessment"])
candidate = require_roles("candidate")


@router.post("/attempts", status_code=201, response_model=AttemptOut)
def start(data: StartIn, user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    a = service.start_attempt(db, user, data)
    return service.attempt_state(db, a)


@router.get("/attempts/{attempt_id}", response_model=AttemptOut)
def get_attempt(attempt_id: uuid.UUID, user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    return service.get_attempt_state(db, user, attempt_id)


@router.get("/tests/availability", response_model=dict[str, AvailabilityOut])
def availability(user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    return {g: {"allowed": av.allowed, "available_at": av.available_at, "reasons": list(av.reasons)}
            for g, av in service.availability_all(db, user).items()}


@router.post("/attempts/{attempt_id}/next", response_model=AttemptOut)
def next_item(attempt_id: uuid.UUID, user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    return service.attempt_state(db, service.present_next(db, user, attempt_id))


@router.post("/attempts/{attempt_id}/answer", response_model=AttemptOut)
def answer(attempt_id: uuid.UUID, data: AnswerIn, user: User = Depends(candidate),
           db: Session = Depends(get_db)) -> dict:
    return service.attempt_state(db, service.submit_answer(db, user, attempt_id, data))


@router.post("/attempts/{attempt_id}/extend", response_model=AttemptOut)
def extend(attempt_id: uuid.UUID, user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    return service.attempt_state(db, service.extend_express(db, user, attempt_id))


@router.get("/attempts", response_model=list[AttemptSummary])
def history(user: User = Depends(candidate), db: Session = Depends(get_db)) -> list[dict]:
    return service.list_attempts(db, user)


@router.get("/skills", response_model=list[SkillOut])
def skills(user: User = Depends(candidate), db: Session = Depends(get_db)) -> list[dict]:
    return service.skills_overview(db, user)


@router.post("/skills/{code}/attempts", status_code=201, response_model=AttemptOut)
def start_skill(code: str, data: SkillStartIn, user: User = Depends(candidate), db: Session = Depends(get_db)) -> dict:
    return service.attempt_state(db, service.start_skill_attempt(db, user, code, data))


@router.post("/attempts/{attempt_id}/items/{seq}/report", status_code=201)
def report_item(attempt_id: uuid.UUID, seq: int, data: ReportIn, user: User = Depends(candidate),
                db: Session = Depends(get_db)) -> dict:
    """Проблема в показанном задании: обращение модератору, таймер попытки не трогаем."""
    complaints.report_item(db, user.id, attempt_id, seq, data)
    return {"ok": True}


@router.post("/attempts/{attempt_id}/objection", status_code=201, response_model=ObjectionOut)
def objection(attempt_id: uuid.UUID, data: ObjectionIn, user: User = Depends(candidate),
              db: Session = Depends(get_db)) -> dict:
    """Возражение против решения, принятого автоматически (ст. 16 152-ФЗ): ответ — в течение ART16_DAYS."""
    return complaints.object_to_decision(db, user.id, attempt_id, data)
