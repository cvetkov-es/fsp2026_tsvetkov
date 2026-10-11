import logging
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth import service
from app.auth.models import Role, User
from app.auth.service import create_session, revoke_session
from app.config.settings import Settings, get_settings
from app.integrations.mail import Mailer
from app.main import create_app

CAND = {
    "email": "teen@example.ru",
    "password": "correct horse 1",
    "role": "candidate",
    "consents": {"processing": True, "distribution_preset": "standard"},
}


def test_age_checked_by_full_birth_date(client, db, frozen_now):
    frozen_now(datetime(2026, 10, 7, 12, 0, tzinfo=UTC))
    r = client.post("/api/v1/auth/register", json={**CAND, "birth_date": "2012-10-08"})
    assert r.status_code == 422 and r.json()["code"] == "age_restricted"
    r = client.post("/api/v1/auth/register", json={**CAND, "birth_date": "2012-10-07"})
    assert r.status_code == 201, r.text
    user = db.scalars(select(User).where(User.email == "teen@example.ru")).one()
    assert user.birth_year == 2012


def test_revoked_session_still_presented_is_401(client, db):
    u = User(email="rev@x.ru", role=Role.candidate, password_hash="x")
    db.add(u)
    db.commit()
    token = create_session(db, u)
    revoke_session(db, token)
    client.cookies.set("fsp_session", token)
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401 and r.json()["code"] == "unauthenticated"


def test_login_without_csrf_header_is_403():
    r = TestClient(create_app()).post("/api/v1/auth/login", json={"email": "a@b.ru", "password": "x"})
    assert r.status_code == 403 and r.json()["code"] == "csrf"


def test_demo_mode_is_off_by_default(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    assert Settings(_env_file=None).demo_mode is False


def test_demo_routes_hidden_from_openapi_when_off(monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    paths = create_app().openapi()["paths"]
    assert not any(p.startswith("/api/v1/demo") for p in paths)


def test_llm_key_is_secret(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k-123")
    s = Settings(_env_file=None)
    assert "k-123" not in repr(s)
    assert s.llm_api_key.get_secret_value() == "k-123"


def test_mail_log_has_no_recipient(caplog, monkeypatch):
    monkeypatch.setattr(get_settings(), "mail_host", None)
    with caplog.at_level(logging.INFO, logger="mail"):
        Mailer().send("secret.person@x.ru", "Тема", "Тело")
    assert "secret.person@x.ru" not in caplog.text


def test_unknown_email_login_still_runs_password_hash(client, monkeypatch):
    calls = []
    real = service.verify_password

    def counting(h, p):
        calls.append(1)
        return real(h, p)

    monkeypatch.setattr(service, "verify_password", counting)
    r = client.post("/api/v1/auth/login", json={"email": "nobody@x.ru", "password": "whatever1"})
    assert r.status_code == 401 and r.json()["code"] == "bad_credentials"
    assert calls == [1]
