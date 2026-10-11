import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.auth.models import User
from app.config.params import PARAMS
from app.db.session import get_db
from app.lab import service

router = APIRouter(prefix="/lab", tags=["lab"])


class RunIn(BaseModel):
    population: int = Field(default=500, ge=100, le=PARAMS.lab_max_pop)


def run_brief(run) -> dict | None:
    if run is None:
        return None
    return {"id": str(run.id), "kind": run.kind, "population": run.population, "status": run.status,
            "error": run.error, "created_at": run.created_at, "finished_at": run.finished_at}


@router.get("/latest")
def latest(db: Session = Depends(get_db)) -> dict:
    """Публично: страница лаборатории из README открывается без входа. Только синтетика."""
    done, active, failed = service.latest(db)
    return {"run": run_brief(done), "results": done.results if done else None, "active": run_brief(active),
            "failed": run_brief(failed), "max_population": PARAMS.lab_max_pop}


@router.post("/runs", status_code=202)
def start(data: RunIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return run_brief(service.enqueue(db, user, data.population))


@router.get("/runs/{run_id}")
def status(run_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return run_brief(service.get_run(db, run_id))
