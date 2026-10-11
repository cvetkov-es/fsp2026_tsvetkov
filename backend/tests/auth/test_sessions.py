from datetime import UTC, datetime, timedelta

from app.auth.models import Role, User
from app.auth.service import create_session
from app.common import clock
from app.config.params import PARAMS


def _verified_user(db):
    u = User(email="s@x.ru", role=Role.candidate, password_hash="x",
             email_verified_at=clock.now())
    db.add(u)
    db.commit()
    return u


def test_expired_session_is_401_not_500(client, db, frozen_now):
    t0 = datetime(2026, 10, 9, 10, 0, tzinfo=UTC)
    frozen_now(t0)
    token = create_session(db, _verified_user(db))
    client.cookies.set("fsp_session", token)
    assert client.get("/api/v1/auth/me").status_code == 200
    frozen_now(t0 + timedelta(days=PARAMS.session_ttl_days, seconds=1))
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401 and r.json()["code"] == "unauthenticated"


def test_garbage_cookie_is_401(client):
    client.cookies.set("fsp_session", "garbage")
    assert client.get("/api/v1/auth/me").status_code == 401
