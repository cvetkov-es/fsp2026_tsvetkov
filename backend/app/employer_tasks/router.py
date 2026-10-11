import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import require_roles
from app.auth.models import User
from app.config.params import PARAMS
from app.db.session import get_db
from app.employer_tasks import service
from app.employer_tasks.schemas import (
    CompanyTaskOut,
    ComplaintIn,
    ContactCreatedOut,
    CreatedOut,
    EvaluateIn,
    FeedItemOut,
    LimitsOut,
    MySubmissionOut,
    OkOut,
    SubmissionIn,
    SubmissionOut,
    TaskIn,
    TaskInviteIn,
    TaskSubmissionsOut,
)
from app.llm.client import LLM
from app.llm.deps import get_llm

router = APIRouter(tags=["employer-tasks"])
employer = require_roles("employer")
candidate = require_roles("candidate")


@router.post("/employer/tasks", status_code=201, response_model=CreatedOut)
def create(data: TaskIn, user: User = Depends(employer), db: Session = Depends(get_db)) -> dict:
    return {"id": str(service.create_task(db, user, data).id)}


@router.get("/employer/tasks", response_model=list[CompanyTaskOut])
def company_tasks(user: User = Depends(employer), db: Session = Depends(get_db)) -> list[dict]:
    return service.company_tasks(db, user)


@router.get("/employer/tasks/limits", response_model=LimitsOut)
def limits(user: User = Depends(employer)) -> dict:
    """Пределы формы публикации — из PARAMS, чтобы числа не дублировались во фронтенде."""
    return {"text_max": PARAMS.task_text_max, "ttl_days": PARAMS.task_ttl_days}


@router.get("/employer/tasks/{task_id}/submissions", response_model=TaskSubmissionsOut)
def submissions(task_id: uuid.UUID, user: User = Depends(employer), db: Session = Depends(get_db)) -> dict:
    return service.task_submissions(db, user, task_id)


@router.post("/employer/task-submissions/{submission_id}/evaluate", response_model=SubmissionOut)
def evaluate(submission_id: uuid.UUID, data: EvaluateIn, user: User = Depends(employer),
             db: Session = Depends(get_db)) -> dict:
    return service.evaluate(db, user, submission_id, data)


@router.post("/employer/task-submissions/{submission_id}/hint", response_model=SubmissionOut)
def hint(submission_id: uuid.UUID, user: User = Depends(employer), db: Session = Depends(get_db),
         llm: LLM = Depends(get_llm)) -> dict:
    return service.hint(db, user, submission_id, llm)


@router.post("/employer/task-submissions/{submission_id}/invite", status_code=201, response_model=ContactCreatedOut)
def invite_author(submission_id: uuid.UUID, data: TaskInviteIn, user: User = Depends(employer),
                  db: Session = Depends(get_db)) -> dict:
    return service.invite_author(db, user, submission_id, data)


@router.get("/candidate/tasks", response_model=list[FeedItemOut])
def feed(specialization: str | None = None, user: User = Depends(candidate), db: Session = Depends(get_db)) -> list[dict]:
    return service.feed(db, user, specialization)


@router.post("/candidate/tasks/{task_id}/submission", response_model=MySubmissionOut)
def submit(task_id: uuid.UUID, data: SubmissionIn, user: User = Depends(candidate),
           db: Session = Depends(get_db)) -> dict:
    return service.submit(db, user, task_id, data)


@router.post("/candidate/tasks/{task_id}/complaint", status_code=201, response_model=OkOut)
def complaint(task_id: uuid.UUID, data: ComplaintIn, user: User = Depends(candidate),
              db: Session = Depends(get_db)) -> dict:
    service.complain(db, user, task_id, data.comment)
    return {"ok": True}
