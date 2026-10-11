from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.assessment.models import Attempt
from app.common import clock
from app.common.clock import MSK
from app.config.params import PARAMS
from app.hiring.jobs import remind_stages, vote_digest
from app.notifications.models import Notification
from tests.contacts.helpers import as_user

from .helpers import STACK, accepted, stage


def _count(db, user_id, kind) -> int:
    return db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user_id,
                                                                          Notification.kind == kind))


def test_two_above_votes_from_l2_lift_cooldown_up(client, db, make_candidate, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    p = make_candidate(stack=STACK)
    db.add(Attempt(user_id=p.user_id, kind="grade", specialization="backend", target_grade="middle", item_cap=15,
                   thresholds_version="expert", status="completed", decision="confirmed", decided_at=t0,
                   finished_at=t0))
    db.commit()
    as_user(client, db, p.user_id)
    assert not client.get("/api/v1/candidate/tests/availability").json()["senior"]["allowed"]  # COOLDOWN_UP
    for i in range(PARAMS.votes_unlock):
        _, cid = accepted(client, db, p, email=f"hr{i}@corp.ru", company=f"Корп {i}")
        stage(client, cid, stage="technical", level="above")
    frozen_now(t0 + timedelta(days=PARAMS.vote_dispute_days, minutes=1))
    as_user(client, db, p.user_id)
    av = client.get("/api/v1/candidate/tests/availability").json()
    assert av["senior"]["allowed"] and not av["middle"]["allowed"]  # COOLDOWN_SAME исключения не снимают


def test_stage_reminders_after_reminder_days(client, db, make_candidate, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p)
    first, second = PARAMS.reminder_days
    remind_stages(db, t0 + timedelta(days=first) - timedelta(minutes=1))
    assert _count(db, s.employer.id, "stage_reminder") == 0
    remind_stages(db, t0 + timedelta(days=first, minutes=1))
    remind_stages(db, t0 + timedelta(days=first, minutes=2))
    assert _count(db, s.employer.id, "stage_reminder") == 1  # идемпотентно
    remind_stages(db, t0 + timedelta(days=second, minutes=1))
    assert _count(db, s.employer.id, "stage_reminder") == 2
    frozen_now(t0 + timedelta(days=second, minutes=2))
    s.as_employer()
    stage(client, cid, stage="hired", level="meets")
    remind_stages(db, t0 + timedelta(days=second * 3))
    assert _count(db, s.employer.id, "stage_reminder") == 2  # финал — напоминаний нет


def test_weekly_digest_is_neutral_and_once_a_week(client, db, make_candidate, frozen_now):
    wednesday = datetime(2026, 10, 7, 12, 0, tzinfo=MSK)
    frozen_now(wednesday)
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p)
    stage(client, cid, stage="technical", level="below")
    assert vote_digest(db, datetime(2026, 10, 8, 12, 0, tzinfo=MSK)) == 0  # не понедельник
    monday = datetime(2026, 10, 12, 10, 5, tzinfo=MSK)
    assert vote_digest(db, monday) == 1
    vote_digest(db, monday + timedelta(hours=3))
    n = db.scalars(select(Notification).where(Notification.user_id == p.user_id,
                                              Notification.kind == "vote_digest")).all()
    assert len(n) == 1 and n[0].payload["companies"] == "Корп" and "below" not in str(n[0].payload)
