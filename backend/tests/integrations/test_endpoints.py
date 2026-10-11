import uuid

from sqlalchemy import select

from app.integrations.models import Outbox, WebhookEndpoint
from tests.contacts.helpers import Scene, as_user


def test_secret_is_shown_once_and_private_urls_are_refused(client, db, monkeypatch):
    Scene(client, db)
    r = client.post("/api/v1/employer/integrations/webhooks", json={"url": "https://127.0.0.1/hook"})
    assert r.status_code == 422 and r.json()["code"] == "webhook_url_private"
    assert client.post("/api/v1/employer/integrations/webhooks", json={"url": "http://example.com/hook"}).json()["code"] == "webhook_url_https"
    # настоящий публичный адрес в песочнице может не резолвиться — подменяем только проверку DNS
    import app.integrations.router as router

    monkeypatch.setattr(router, "check_url", lambda url: None)
    r = client.post("/api/v1/employer/integrations/webhooks", json={"url": "https://ats.example.com/hook"})
    assert r.status_code == 201 and r.json()["secret"].startswith("whsec_")
    listing = client.get("/api/v1/employer/integrations").json()
    assert [e["url"] for e in listing["endpoints"]] == ["https://ats.example.com/hook"]
    assert "secret" not in str(listing)  # повторно секрет не показывается


def test_only_the_owner_manages_an_endpoint_and_ping_goes_to_the_outbox(client, db, monkeypatch):
    import app.integrations.router as router

    monkeypatch.setattr(router, "check_url", lambda url: None)
    s = Scene(client, db)
    ep = client.post("/api/v1/employer/integrations/webhooks", json={"url": "https://ats.example.com/hook"}).json()
    assert client.post(f"/api/v1/employer/integrations/webhooks/{ep['id']}/test").status_code == 202
    assert db.scalar(select(Outbox).where(Outbox.event_type == "ping", Outbox.company_id == s.company.id)) is not None
    other = Scene(client, db, email="hr2@corp.ru", company="Чужая")
    other.as_employer()
    assert client.delete(f"/api/v1/employer/integrations/webhooks/{ep['id']}").status_code == 404
    assert client.post(f"/api/v1/employer/integrations/webhooks/{ep['id']}/test").status_code == 404
    s.as_employer()
    assert client.delete(f"/api/v1/employer/integrations/webhooks/{ep['id']}").status_code == 204
    assert client.get("/api/v1/employer/integrations").json()["endpoints"] == []
    assert db.get(WebhookEndpoint, uuid.UUID(ep["id"])).active is False  # журнал доставок сохраняется


def test_the_number_of_endpoints_is_limited(client, db, monkeypatch):
    import app.integrations.router as router
    from app.config.params import PARAMS

    monkeypatch.setattr(router, "check_url", lambda url: None)
    Scene(client, db)
    for i in range(PARAMS.webhook_endpoints_max):
        assert client.post("/api/v1/employer/integrations/webhooks", json={"url": f"https://ats{i}.example.com/h"}).status_code == 201
    r = client.post("/api/v1/employer/integrations/webhooks", json={"url": "https://more.example.com/h"})
    assert r.status_code == 409 and r.json()["code"] == "webhook_limit"


def test_integrations_are_for_employers_only(client, db, make_candidate):
    p = make_candidate()
    as_user(client, db, p.user_id)
    assert client.get("/api/v1/employer/integrations").status_code == 403
