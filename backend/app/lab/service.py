"""Прогоны лаборатории: очередь из интерфейса выполняет worker, `make validate` пишет результат напрямую."""
import logging
import uuid
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.clock import now
from app.common.errors import AppError
from app.config.params import PARAMS
from app.lab.models import LabRun
from app.lab.report import run_all, sanitize

log = logging.getLogger("lab")
ACTIVE = ("queued", "running")


def _fail(db: Session, status: str, older_than, error: str) -> int:
    column = LabRun.started_at if status == "running" else LabRun.created_at
    stmt = update(LabRun).where(LabRun.status == status)
    if older_than is not None:
        stmt = stmt.where(column < older_than)
    n = db.execute(stmt.values(status="failed", error=error, finished_at=now())).rowcount
    db.commit()
    return n


def reap_stale(db: Session) -> int:
    """Прогон, который висит дольше LAB_RUN_STALE_MIN, прерван (worker упал или не запущен): он не должен
    навсегда держать лабораторию в «Идёт прогон…»."""
    edge = now() - timedelta(minutes=PARAMS.lab_run_stale_min)
    return _fail(db, "running", edge, "stale") + _fail(db, "queued", edge, "worker_unavailable")


def reset_interrupted(db: Session) -> int:
    """При старте worker: прогоны в работе принадлежали прошлому процессу и уже не завершатся."""
    return _fail(db, "running", None, "worker_restarted")


def _has_active(db: Session) -> bool:
    return db.scalar(select(LabRun.id).where(LabRun.status.in_(ACTIVE)).limit(1)) is not None


def enqueue(db: Session, user: User, population: int) -> LabRun:
    reap_stale(db)
    busy = AppError(409, "lab_busy", "Прогон уже идёт. Дождитесь результата")
    if _has_active(db):
        raise busy
    run = LabRun(kind="ui", population=population)
    db.add(run)
    try:
        db.commit()
    except IntegrityError:  # параллельный запрос успел поставить свой прогон (uq_lab_runs_one_active)
        db.rollback()
        raise busy from None
    log.info("lab: прогон %s поставлен в очередь пользователем %s", run.id, user.id)
    return run


def latest(db: Session) -> tuple[LabRun | None, LabRun | None, LabRun | None]:
    """Последний завершённый прогон, текущий (если идёт) и упавший, если он новее завершённого."""
    reap_stale(db)
    done = db.scalar(select(LabRun).where(LabRun.status == "done").order_by(LabRun.finished_at.desc()).limit(1))
    active = db.scalar(select(LabRun).where(LabRun.status.in_(ACTIVE)).order_by(LabRun.created_at).limit(1))
    failed_q = select(LabRun).where(LabRun.status == "failed")
    if done is not None:
        failed_q = failed_q.where(LabRun.finished_at > done.finished_at)
    failed = db.scalar(failed_q.order_by(LabRun.finished_at.desc()).limit(1))
    return done, active, failed


def get_run(db: Session, run_id: uuid.UUID) -> LabRun:
    run = db.get(LabRun, run_id)
    if run is None:
        raise AppError(404, "lab_run_not_found", "Прогон не найден")
    return run


def run_pending(db: Session, runner=run_all) -> LabRun | None:
    """Шаг worker: берёт самый старый прогон из очереди. Прогоны из интерфейса — без платных вызовов LLM
    и с облегчённой фиксированной частью (кривая решений, «утечка»), чтобы демо не ждало минут."""
    run = db.scalar(select(LabRun).where(LabRun.status == "queued").order_by(LabRun.created_at).limit(1)
                    .with_for_update(skip_locked=True))
    if run is None:
        return None
    run.status, run.started_at = "running", now()
    db.commit()
    run_id = run.id  # после сбоя записи объект истёк: id нужен для журнала до rollback
    try:
        run.results = sanitize(runner(run.population, with_llm=False, light=True))
        run.status = "done"
        run.finished_at = now()
        db.commit()
    except Exception as e:  # сбой прогона или записи результата виден на странице, worker продолжает работу
        log.exception("lab: прогон %s упал", run_id)
        db.rollback()
        run.status, run.error, run.results, run.finished_at = "failed", type(e).__name__, None, now()
        db.commit()
    return run


def record(db: Session, results: dict) -> LabRun:
    run = LabRun(kind="validate", population=results["population"], status="done", results=sanitize(results),
                 started_at=now(), finished_at=now())
    db.add(run)
    db.commit()
    return run
