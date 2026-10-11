from app.config.settings import get_settings
from app.demo.service import ensure_demo_personas


def test_personas_and_login_as_with_audit(client, db):
    personas = ensure_demo_personas(db)
    r = client.get("/api/v1/demo/personas")
    assert r.status_code == 200 and {p["role"] for p in r.json()} >= {"candidate", "employer"}
    emp = next(p for p in personas if p.role == "employer")
    r = client.post("/api/v1/demo/login-as", json={"user_id": str(emp.id)})
    assert r.status_code == 200 and r.json()["role"] == "employer"
    assert client.get("/api/v1/auth/me").json()["email"] == emp.email


def test_login_as_non_demo_user_forbidden(client, db):
    from app.auth.models import Role, User

    u = User(email="real@x.ru", role=Role.candidate, password_hash="x")
    db.add(u)
    db.commit()
    r = client.post("/api/v1/demo/login-as", json={"user_id": str(u.id)})
    assert r.status_code == 403 and r.json()["code"] == "not_demo_persona"


def test_demo_disabled_returns_404(client, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    assert client.get("/api/v1/demo/personas").status_code == 404
