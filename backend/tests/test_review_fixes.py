import smtplib

from fastapi.testclient import TestClient

from app.config.params import Params
from app.integrations.mail import Mailer
from app.main import create_app

CAND = {
    "email": "mailfail@example.ru",
    "password": "correct horse 1",
    "role": "candidate",
    "birth_date": "2000-01-15",
    "consents": {"processing": True, "distribution_preset": "standard"},
}


def test_register_survives_mail_failure(client, monkeypatch):
    def boom(self, to, subject, body):
        raise smtplib.SMTPException("mailpit down")

    monkeypatch.setattr(Mailer, "send", boom)
    r = client.post("/api/v1/auth/register", json=CAND)
    assert r.status_code == 201, r.text
    assert r.json()["verify_url"]


def test_unknown_route_is_problem_json():
    r = TestClient(create_app()).get("/api/v1/no-such-route")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == "not_found"


def test_unhandled_exception_is_problem_json():
    app = create_app()

    @app.get("/api/v1/_crash")
    def crash():
        raise RuntimeError("boom")

    r = TestClient(app, raise_server_exceptions=False).get("/api/v1/_crash")
    assert r.status_code == 500
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == "internal_error"


def test_consent_texts_follow_params_and_version_tracks_text():
    from app.auth.consents import ConsentType, build_consent_texts

    base = build_consent_texts(Params())
    custom = build_consent_texts(Params(cooldown_same_days=45, cooldown_up_days=120))
    body = custom[ConsentType.automated_rules].body
    assert "через 45 дней" in body and "через 120 дней" in body
    assert custom[ConsentType.automated_rules].version != base[ConsentType.automated_rules].version
    assert custom[ConsentType.processing].version == base[ConsentType.processing].version


def test_age_and_verify_ttl_are_params():
    p = Params()
    assert p.min_age == 14 and p.verify_ttl_hours == 24
