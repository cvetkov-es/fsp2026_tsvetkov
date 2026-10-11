"""Замечания финального ревью плана 05: согласие №4 и контакты, гонки, уведомления, worker, аудит."""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError

from app.audit.models import AuditLog
from app.auth.models import Consent
from app.common import clock
from app.config.params import PARAMS
from app.contacts.models import Contact
from app.notifications.models import Notification
from app.notifications.service import latest
from app.worker import run_once
from tests.contacts.helpers import INVITE, Scene, as_user
from tests.employers.helpers import NEED

STACK = ("Python", "PostgreSQL")


def accept(client, db, user_id, cid):
    as_user(client, db, user_id)
    r = client.post(f"/api/v1/candidate/invitations/{cid}/accept", json={"consent_contact_transfer": True})
    assert r.status_code == 200, r.text


def test_revoke_hides_contacts_in_every_accepted_invitation_of_the_company(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s = Scene(client, db, trust_level="L1")
    first = s.invite(p.public_ref).json()["id"]
    s.as_employer()
    need2 = client.post("/api/v1/employer/needs", json={**NEED, "title": "Вторая команда"}).json()["id"]
    second = client.post(f"/api/v1/employer/needs/{need2}/invitations", json={**INVITE, "ref": p.public_ref}).json()["id"]
    accept(client, db, p.user_id, first)
    accept(client, db, p.user_id, second)
    assert client.post(f"/api/v1/candidate/invitations/{first}/revoke").json()["status"] == "revoked"
    s.as_employer()
    page = client.get(f"/api/v1/contacts/{second}").json()
    assert page["candidate"] is None and page["chat_open"] is False and page["status"] == "revoked"


def test_contacts_need_an_active_consent_not_just_the_status(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    cid = s.invite(p.public_ref).json()["id"]
    accept(client, db, p.user_id, cid)
    for c in db.scalars(select(Consent).where(Consent.user_id == p.user_id, Consent.type == "contact_transfer")):
        c.revoked_at = clock.now()  # согласие отозвано иным путём (например, в настройках приватности)
    db.commit()
    s.as_employer()
    page = client.get(f"/api/v1/contacts/{cid}").json()
    assert page["candidate"] is None and page["chat_open"] is False
    assert client.post(f"/api/v1/contacts/{cid}/messages", json={"text": "Привет"}).json()["code"] == "chat_closed"


def test_concurrent_second_invite_is_409_not_500(client, db, make_candidate, monkeypatch):
    from app.contacts import service

    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    assert s.invite(p.public_ref).status_code == 201
    monkeypatch.setattr(service, "_history", lambda *a: [])  # параллельный запрос не увидел первое приглашение
    r = s.invite(p.public_ref)
    assert r.status_code == 409 and r.json()["code"] == "invite_exists"


def test_active_pair_index_is_the_last_line(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    c = db.get(Contact, uuid.UUID(s.invite(p.public_ref).json()["id"]))
    db.add(Contact(need_id=c.need_id, company_id=c.company_id, user_id=c.user_id, salary_from=1, salary_to=2,
                   gross_net="gross", expires_at=clock.now() + timedelta(days=1)))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def _sql_during(db, fn) -> list[str]:
    seen: list[str] = []

    def grab(conn, cursor, statement, *a):
        seen.append(" ".join(statement.split()))

    conn = db.connection()
    event.listen(conn, "before_cursor_execute", grab)
    try:
        fn()
    finally:
        event.remove(conn, "before_cursor_execute", grab)
    return seen


def test_invite_and_transitions_lock_rows(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    sql = _sql_during(db, lambda: s.invite(p.public_ref))
    assert any("FROM needs" in q and "FOR UPDATE" in q for q in sql)  # квота: приглашения по потребности по одному
    cid = db.scalar(select(Contact.id))
    as_user(client, db, p.user_id)
    sql = _sql_during(db, lambda: client.post(f"/api/v1/candidate/invitations/{cid}/accept",
                                              json={"consent_contact_transfer": True}))
    assert any("FROM contacts" in q and "FOR UPDATE" in q for q in sql)


def test_blank_chat_message_rejected(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    cid = s.invite(p.public_ref).json()["id"]
    accept(client, db, p.user_id, cid)
    assert client.post(f"/api/v1/contacts/{cid}/messages", json={"text": "   "}).status_code == 422


def test_withdraw_and_expiry_notify_the_other_side(client, db, make_candidate, frozen_now):
    start = clock.now()
    frozen_now(start)
    p, q, r = make_candidate(stack=STACK), make_candidate(stack=STACK), make_candidate(stack=STACK)
    s = Scene(client, db)
    withdrawn = s.invite(p.public_ref).json()["id"]
    client.post(f"/api/v1/employer/invitations/{withdrawn}/withdraw")
    kinds = set(db.scalars(select(Notification.kind).where(Notification.user_id == p.user_id)))
    assert "invitation_withdrawn" in kinds
    s.invite(q.public_ref)
    countered = s.invite(r.public_ref).json()["id"]
    as_user(client, db, r.user_id)
    client.post(f"/api/v1/candidate/invitations/{countered}/counter", json={"amount": 400000, "gross_net": "gross"})
    frozen_now(start + timedelta(days=PARAMS.invite_ttl_days, minutes=1))
    s.as_employer()
    client.get(f"/api/v1/employer/needs/{s.need_id}/invitations")  # ленивое истечение при чтении
    employer_kinds = set(db.scalars(select(Notification.kind).where(Notification.user_id == s.employer.id)))
    assert "invitation_expired" in employer_kinds
    candidate_kinds = set(db.scalars(select(Notification.kind).where(Notification.user_id == r.user_id)))
    assert "counter_expired" in candidate_kinds


def test_notification_times_are_moscow_time(client, db, make_candidate, frozen_now):
    start = datetime(2026, 10, 8, 22, 30, tzinfo=UTC)
    frozen_now(start)
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    s.invite(p.public_ref)
    frozen_now(start + timedelta(days=PARAMS.invite_ttl_days) - timedelta(hours=1))
    run_once(db, FakeMailer())
    items, _ = latest(db, p.user_id)
    reminder = next(i for i in items if i["kind"] == "invitation_reminder")
    assert "14.10 01:30" in reminder["title"]  # 13.10 22:30 UTC — это уже 14.10 по Москве


class FakeMailer:
    def __init__(self, fail_on: int | None = None):
        self.sent, self.calls, self.fail_on = [], 0, fail_on

    def send(self, to, subject, body):
        self.calls += 1
        if self.calls == self.fail_on:
            raise ConnectionError("SMTP недоступен")
        self.sent.append((to, subject))


def test_smtp_failure_mid_batch_does_not_resend(client, db, make_candidate):
    p, q = make_candidate(stack=STACK), make_candidate(stack=STACK)
    s = Scene(client, db)
    s.invite(p.public_ref)
    s.invite(q.public_ref)
    mailer = FakeMailer(fail_on=2)
    assert run_once(db, mailer)["emails"] == 1
    assert run_once(db, mailer)["emails"] == 1  # только письмо, которое не ушло
    assert len(mailer.sent) == len(set(mailer.sent)) == 2


def test_chat_polling_does_not_flood_the_audit(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    cid = s.invite(p.public_ref).json()["id"]
    accept(client, db, p.user_id, cid)
    client.post(f"/api/v1/contacts/{cid}/messages", json={"text": "Здравствуйте"})
    s.as_employer()
    for _ in range(3):
        r = client.get(f"/api/v1/contacts/{cid}/messages")
        assert r.status_code == 200 and r.json()[0]["text"] == "Здравствуйте" and "Секретное" not in r.text
    views = db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "contact_view"))
    assert views == 0


def test_employer_sees_that_offer_v2_was_viewed(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    cid = s.invite(p.public_ref).json()["id"]
    as_user(client, db, p.user_id)
    client.post(f"/api/v1/candidate/invitations/{cid}/counter", json={"amount": 320000, "gross_net": "gross"})
    s.as_employer()
    client.post(f"/api/v1/employer/invitations/{cid}/counter-response",
                json={"action": "offer_v2", "salary_from": 250000, "salary_to": 320000})
    assert client.get(f"/api/v1/employer/needs/{s.need_id}/invitations").json()[0]["viewed"] is False
    as_user(client, db, p.user_id)
    assert client.get(f"/api/v1/candidate/invitations/{cid}").json()["status"] == "offer_v2"
    s.as_employer()
    assert client.get(f"/api/v1/employer/needs/{s.need_id}/invitations").json()[0]["viewed"] is True


def test_other_company_gets_404_everywhere(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    cid = s.invite(p.public_ref).json()["id"]
    Scene(client, db, email="hr@other.ru", company="Другая")
    assert client.get(f"/api/v1/contacts/{cid}").status_code == 404
    assert client.get(f"/api/v1/contacts/{cid}/messages").status_code == 404
    assert client.post(f"/api/v1/employer/invitations/{cid}/counter-response", json={"action": "decline"}).status_code == 404
    assert client.get(f"/api/v1/employer/needs/{s.need_id}/invitations").status_code == 404
