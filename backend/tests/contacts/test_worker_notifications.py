import uuid
from datetime import timedelta

from sqlalchemy import select

from app.common import clock
from app.config.params import PARAMS
from app.contacts.models import Contact
from app.notifications.models import Notification
from app.worker import run_once
from tests.contacts.helpers import Scene, as_user


class FakeMailer:
    def __init__(self):
        self.sent = []

    def send(self, to, subject, body):
        self.sent.append((to, subject, body))


def test_worker_expires_reminds_and_mails_idempotently(client, db, make_candidate, frozen_now):
    start = clock.now()
    frozen_now(start)
    p = make_candidate(stack=("Python", "PostgreSQL"))
    s = Scene(client, db)
    cid = s.invite(p.public_ref).json()["id"]
    mailer = FakeMailer()
    assert run_once(db, mailer) == {"expired": 0, "reminders": 0, "fsp_purged": 0, "stage_reminders": 0, "vote_digests": 0, "webhooks": {"queued": 0, "sent": 0}, "emails": 1}  # письмо о приглашении
    assert "Новое приглашение от компании «Корп»" in mailer.sent[0][1]
    frozen_now(start + timedelta(days=PARAMS.invite_ttl_days) - timedelta(hours=PARAMS.invite_remind_hours - 1))
    assert run_once(db, mailer)["reminders"] == 1
    run_once(db, mailer)
    reminders = db.scalars(select(Notification).where(Notification.kind == "invitation_reminder")).all()
    assert len(reminders) == 1  # dedupe_key: одно напоминание на версию приглашения
    frozen_now(start + timedelta(days=PARAMS.invite_ttl_days, minutes=1))
    assert run_once(db, mailer)["expired"] == 1
    assert db.get(Contact, uuid.UUID(cid)).status == "expired"
    assert run_once(db, mailer) == {"expired": 0, "reminders": 0, "fsp_purged": 0, "stage_reminders": 0, "vote_digests": 0, "webhooks": {"queued": 0, "sent": 0}, "emails": 0}


def test_notifications_api(client, db, make_candidate):
    p = make_candidate(stack=("Python", "PostgreSQL"))
    s = Scene(client, db)
    s.invite(p.public_ref)
    as_user(client, db, p.user_id)
    data = client.get("/api/v1/notifications").json()
    assert data["unread"] == 1 and data["items"][0]["link"] == "/candidate/invitations"
    assert data["items"][0]["title"] == "Новое приглашение от компании «Корп»"
    assert client.post("/api/v1/notifications/read").status_code == 204
    assert client.get("/api/v1/notifications").json()["unread"] == 0
