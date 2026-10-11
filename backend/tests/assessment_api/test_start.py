from sqlalchemy import select

from app.auth.models import Consent

START = {"target_grade": "middle", "accept_rules": True, "pledge": True}


def test_requires_survey(client, db, candidate_login, toy_bank):
    from app.auth.models import Role, User
    from app.auth.service import create_session
    from app.common import clock

    u = User(email="nosurvey@x.ru", role=Role.candidate, password_hash="x", email_verified_at=clock.now())
    db.add(u)
    db.commit()
    client.cookies.set("fsp_session", create_session(db, u))
    r = client.post("/api/v1/candidate/attempts", json=START)
    assert r.status_code == 409 and r.json()["code"] == "survey_required"


def test_requires_rules_and_pledge(client, db, candidate_login, toy_bank):
    candidate_login()
    for body in ({**START, "accept_rules": False}, {**START, "pledge": False}):
        r = client.post("/api/v1/candidate/attempts", json=body)
        assert r.status_code == 422 and r.json()["code"] == "rules_required"


def test_start_records_consent_once_and_resumes(client, db, candidate_login, toy_bank):
    u = candidate_login()
    r1 = client.post("/api/v1/candidate/attempts", json=START)
    assert r1.status_code == 201
    a = r1.json()
    assert a["stage"] == "phase1" and a["item"] is None and a["target_grade"] == "middle"
    r2 = client.post("/api/v1/candidate/attempts", json=START)
    assert r2.status_code == 201 and r2.json()["id"] == a["id"]
    consents = db.scalars(select(Consent).where(Consent.user_id == u.id, Consent.type == "automated_rules")).all()
    assert len(consents) == 1
    r3 = client.post("/api/v1/candidate/attempts", json={**START, "target_grade": "senior"})
    assert r3.status_code == 409 and r3.json()["code"] == "attempt_in_progress"


def test_availability_initially_all_open(client, db, candidate_login, toy_bank):
    candidate_login()
    av = client.get("/api/v1/candidate/tests/availability").json()
    assert all(av[g]["allowed"] for g in ("junior", "middle", "senior"))
