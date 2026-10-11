"""Очередь прогонов лаборатории переживает сбои: застрявший прогон, перезапуск worker, несохраняемый результат."""
import math
from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.common import clock
from app.common.errors import AppError
from app.config.params import PARAMS
from app.lab import service
from app.lab.models import LabRun
from app.lab.report import sanitize
from app.lab.service import record, reset_interrupted, run_pending
from tests.candidates.test_profile import login


def _old(minutes: int):
    return clock.now() - timedelta(minutes=minutes)


def test_stale_runs_do_not_block_the_lab_forever(client, db):
    stuck = LabRun(kind="ui", population=100, status="running", created_at=_old(PARAMS.lab_run_stale_min + 5),
                   started_at=_old(PARAMS.lab_run_stale_min + 5))
    db.add(stuck)
    db.commit()
    login(client, db)
    r = client.post("/api/v1/lab/runs", json={"population": 500})
    assert r.status_code == 202 and r.json()["status"] == "queued"
    db.refresh(stuck)
    assert stuck.status == "failed" and stuck.error == "stale"


def test_queued_run_without_worker_expires(client, db):
    waiting = LabRun(kind="ui", population=100, created_at=_old(PARAMS.lab_run_stale_min + 5))
    db.add(waiting)
    db.commit()
    assert client.get("/api/v1/lab/latest").json()["active"] is None
    db.refresh(waiting)
    assert waiting.status == "failed" and waiting.error == "worker_unavailable"


def test_worker_restart_marks_interrupted_runs_failed(db):
    running = LabRun(kind="ui", population=100, status="running", started_at=clock.now())
    db.add(running)
    db.commit()
    assert reset_interrupted(db) == 1
    db.refresh(running)
    assert running.status == "failed" and running.error == "worker_restarted"


def test_unsaveable_results_fail_the_run_instead_of_leaving_it_running(db):
    db.add(LabRun(kind="ui", population=100))
    db.commit()
    run = run_pending(db, runner=lambda n, with_llm, light: {"x": object()})
    assert run.status == "failed" and run.error == "TypeError"
    db.expire_all()
    assert db.get(LabRun, run.id).status == "failed"


def test_nan_and_inf_are_stored_as_null():
    assert sanitize({"a": [float("nan"), 1.5, {"b": float("inf")}], "c": (float("-inf"),)}) == {"a": [None, 1.5, {"b": None}], "c": [None]}


def test_run_with_nan_results_is_saved(db):
    db.add(LabRun(kind="ui", population=100))
    db.commit()
    run = run_pending(db, runner=lambda n, with_llm, light: {"population": n, "rate": math.nan})
    assert run.status == "done" and run.results == {"population": 100, "rate": None}


def test_latest_reports_failed_run_newer_than_last_success(client, db):
    db.add(LabRun(kind="validate", population=100, status="done", results={"population": 100}, finished_at=_old(10)))
    db.add(LabRun(kind="ui", population=200, status="failed", error="RuntimeError", finished_at=_old(5)))
    db.commit()
    body = client.get("/api/v1/lab/latest").json()
    assert body["failed"]["status"] == "failed" and body["failed"]["error"] == "RuntimeError"
    assert body["run"]["population"] == 100 and body["max_population"] == PARAMS.lab_max_pop
    record(db, {"population": 300, "headline": []})
    assert client.get("/api/v1/lab/latest").json()["failed"] is None


def test_only_one_active_run_even_under_a_race(client, db, monkeypatch):
    db.add(LabRun(kind="ui", population=100))
    db.commit()
    db.add(LabRun(kind="ui", population=100))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    user = login(client, db)
    monkeypatch.setattr(service, "_has_active", lambda db: False)  # два POST одновременно прошли проверку
    with pytest.raises(AppError) as e:
        service.enqueue(db, user, 500)
    assert e.value.code == "lab_busy"


def test_lab_tick_skips_quietly_while_a_run_is_in_progress(monkeypatch):
    from app import worker

    called = []
    monkeypatch.setattr(service, "run_pending", lambda db: called.append(db))
    with worker._lab_lock:
        worker._lab_tick()
    assert called == []


def test_worker_start_resets_interrupted_runs_and_schedules_lab_separately(db, monkeypatch):
    import contextlib

    import apscheduler.schedulers.blocking as blocking

    from app import worker

    jobs = []

    class FakeScheduler:
        def __init__(self, **kw):
            pass

        def add_job(self, fn, *args, **kw):
            jobs.append((fn, kw))

        def start(self):
            pass

    monkeypatch.setattr(blocking, "BlockingScheduler", FakeScheduler)
    monkeypatch.setattr("app.db.session._session_factory", lambda: lambda: contextlib.nullcontext(db))
    running = LabRun(kind="ui", population=100, status="running", started_at=clock.now())
    db.add(running)
    db.commit()
    worker.main()
    db.refresh(running)
    assert running.status == "failed" and running.error == "worker_restarted"
    assert [fn for fn, _ in jobs] == [worker._tick, worker._lab_tick]
