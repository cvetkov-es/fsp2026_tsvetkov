from app.auth.models import Role, User
from app.auth.service import create_session
from app.candidates.models import CandidateProfile
from app.common import clock


def login(client, db, role=Role.candidate, email="cand@x.ru"):
    u = User(email=email, role=role, password_hash="x", email_verified_at=clock.now())
    db.add(u)
    db.commit()
    client.cookies.set("fsp_session", create_session(db, u))
    return u


def test_profile_created_lazily_and_survey_saved(client, db):
    login(client, db)
    r = client.get("/api/v1/candidate/profile")
    assert r.status_code == 200 and r.json()["grade_status"] == "not_tested"
    r = client.put("/api/v1/candidate/profile/survey", json={"specialization": "backend", "claimed_grade": "middle"})
    assert r.status_code == 200
    body = r.json()
    assert body["specialization"] == "backend" and body["claimed_grade"] == "middle"


def test_change_specialization_resets_grade(client, db):
    u = login(client, db)
    client.put("/api/v1/candidate/profile/survey", json={"specialization": "backend", "claimed_grade": "middle"})
    p = db.get(CandidateProfile, u.id)
    p.grade_status, p.confirmed_grade = "confirmed", "middle"
    db.commit()
    body = client.put("/api/v1/candidate/profile/survey", json={"specialization": "data", "claimed_grade": "junior"}).json()
    assert body["grade_status"] == "not_tested" and body["confirmed_grade"] is None and body["claimed_grade"] == "junior"


def test_meta_and_validation(client, db):
    login(client, db)
    meta = client.get("/api/v1/candidate/meta").json()
    assert {s["code"] for s in meta["specializations"]} == {"backend", "frontend", "data"}
    assert [g["code"] for g in meta["grades"]] == ["junior", "middle", "senior"]
    r = client.put("/api/v1/candidate/profile/survey", json={"specialization": "cobol", "claimed_grade": "middle"})
    assert r.status_code == 422


def test_employer_forbidden(client, db):
    login(client, db, role=Role.employer, email="hr@x.ru")
    assert client.get("/api/v1/candidate/profile").status_code == 403
