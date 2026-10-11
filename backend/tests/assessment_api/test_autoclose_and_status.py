from datetime import UTC, datetime, timedelta

from app.candidates.models import CandidateProfile
from app.config.params import PARAMS
from tests.assessment_api.helpers import answer_current

START = {"target_grade": "middle", "accept_rules": True, "pledge": True}
T0 = datetime(2026, 10, 9, 10, 0, tzinfo=UTC)


def start(client, **kw):
    return client.post("/api/v1/candidate/attempts", json={**START, **kw}).json()["id"]


def later(frozen_now):
    frozen_now(T0 + timedelta(hours=PARAMS.attempt_autoclose_hours, minutes=1))


def test_abandoned_early_is_incomplete_and_does_not_block(client, db, candidate_login, toy_bank, frozen_now):
    frozen_now(T0)
    candidate_login()
    aid = start(client)
    answer_current(client, db, aid, True)
    answer_current(client, db, aid, True)
    later(frozen_now)
    st = client.get(f"/api/v1/candidate/attempts/{aid}").json()
    assert st["stage"] == "incomplete" and st["result"] is None
    assert client.post("/api/v1/candidate/attempts", json=START).status_code == 201


def test_abandoned_after_decision_keeps_status(client, db, candidate_login, toy_bank, frozen_now):
    frozen_now(T0)
    u = candidate_login()
    aid = start(client)
    for _ in range(6):
        answer_current(client, db, aid, True)
    later(frozen_now)
    st = client.get(f"/api/v1/candidate/attempts/{aid}").json()
    assert st["stage"] == "finished" and st["result"]["decision"] == "confirmed"
    p = db.get(CandidateProfile, u.id)
    db.refresh(p)
    assert p.grade_status == "confirmed"


def test_failed_upgrade_keeps_confirmed_grade(client, db, candidate_login, toy_bank):
    u = candidate_login(grade="junior")
    aid = start(client, target_grade="junior")
    for _ in range(6):
        answer_current(client, db, aid, True)
    for _ in range(10):
        st = answer_current(client, db, aid, True)
        if st["stage"] == "finished":
            break
    client.post("/api/v1/demo/reset-cooldowns")
    aid2 = start(client, target_grade="middle")
    for _ in range(6):
        answer_current(client, db, aid2, False)
    p = db.get(CandidateProfile, u.id)
    db.refresh(p)
    assert p.confirmed_grade == "junior" and p.grade_status == "confirmed" and p.claimed_grade == "junior"


def test_voluntary_retest_of_confirmed_grade_replaces_status(client, db, candidate_login, toy_bank):
    u = candidate_login()
    aid = start(client)
    for _ in range(6):
        answer_current(client, db, aid, True)
    for _ in range(10):
        if answer_current(client, db, aid, True)["stage"] == "finished":
            break
    client.post("/api/v1/demo/reset-cooldowns")
    aid2 = start(client)
    for _ in range(6):
        answer_current(client, db, aid2, False)
    p = db.get(CandidateProfile, u.id)
    db.refresh(p)
    assert p.grade_status == "not_confirmed" and p.confirmed_grade is None
