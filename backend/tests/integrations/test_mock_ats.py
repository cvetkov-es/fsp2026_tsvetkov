import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.common import clock
from app.integrations.outbox import deliver_webhooks
from app.mocks.ats.models import MockAtsEvent
from tests.contacts.helpers import Scene

STACK = ("Python", "PostgreSQL")


def connect(client) -> dict:
    r = client.post("/api/v1/employer/integrations/mock-ats")
    assert r.status_code == 201, r.text
    return r.json()


def test_mock_ats_receives_signed_events_from_the_worker(client, db, make_candidate, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    ep = connect(client)
    assert ep["url"].endswith(f"/mock/ats/{ep['id']}/webhook") and ep["secret"].startswith("whsec_") and ep["page"].endswith(f"/mock/ats/{ep['id']}")
    s.invite(p.public_ref)
    inner = TestClient(client.app)  # серверная доставка идёт в мок того же приложения (как DaData в 07b3)
    out = deliver_webhooks(db, t0, inner)
    assert out["sent"] >= 1
    events = db.scalars(select(MockAtsEvent).where(MockAtsEvent.endpoint_id == uuid.UUID(ep["id"]))).all()
    assert events and all(e.valid for e in events) and "contact.sent" in {e.type for e in events}
    page = inner.get(f"/mock/ats/{ep['id']}")
    assert page.status_code == 200 and "contact.sent" in page.text and "подпись верна" in page.text


def test_mock_ats_rejects_forged_and_replayed_messages(client, db, frozen_now):
    from app.integrations.webhooks import headers, new_secret

    t0 = clock.now()
    frozen_now(t0)
    Scene(client, db)
    ep = connect(client)
    inner = TestClient(client.app)
    url = f"/mock/ats/{ep['id']}/webhook"
    body = '{"type":"contact.sent","timestamp":"2026-10-09T10:00:00+00:00","data":{}}'
    ts = int(t0.timestamp())
    forged = inner.post(url, content=body, headers=headers(new_secret(), "msg_1", ts, body))  # подпись чужим секретом
    assert forged.status_code == 400
    replay = inner.post(url, content=body, headers=headers(ep["secret"], "msg_2", ts - 10 * 60, body))  # слишком старое сообщение
    assert replay.status_code == 400
    genuine = inner.post(url, content=body, headers=headers(ep["secret"], "msg_3", ts, body))
    assert genuine.status_code == 204
    events = db.scalars(select(MockAtsEvent).order_by(MockAtsEvent.id)).all()
    assert [e.valid for e in events] == [True]  # подделка и повтор не сохраняются
    assert "подпись неверна" not in inner.get(f"/mock/ats/{ep['id']}").text
    assert inner.post(f"/mock/ats/{uuid.uuid4()}/webhook", content=body).status_code == 404


def test_connect_mock_ats_needs_mocks_and_is_per_company(client, db):
    s = Scene(client, db)
    first = connect(client)
    other = Scene(client, db, email="hr2@corp.ru", company="Чужая")
    other.as_employer()
    second = connect(client)
    assert first["id"] != second["id"] and first["secret"] != second["secret"]
    s.as_employer()
    assert [e["id"] for e in client.get("/api/v1/employer/integrations").json()["endpoints"]] == [first["id"]]
    assert db.scalar(select(MockAtsEvent)) is None and clock.now() - timedelta(days=1) < clock.now()


def test_mock_ats_refuses_huge_bodies_and_does_not_store_them(client, db):
    Scene(client, db)
    ep = connect(client)
    inner = TestClient(client.app)
    r = inner.post(f"/mock/ats/{ep['id']}/webhook", content="x" * 70_000, headers={"webhook-id": "m", "webhook-timestamp": "1", "webhook-signature": "v1,x"})
    assert r.status_code == 413
    assert db.scalar(select(MockAtsEvent)) is None
