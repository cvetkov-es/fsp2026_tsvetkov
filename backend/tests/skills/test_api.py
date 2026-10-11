from datetime import timedelta

from sqlalchemy import select

from app.assessment.models import Attempt
from app.auth.service import create_session
from app.candidates.models import CandidateProfile, CandidateStack, SkillResult
from app.candidates.service import stack_states
from app.common import clock
from app.config.params import PARAMS
from tests.assessment_api.helpers import answer_current
from tests.candidates.test_profile import login

START = {"accept_rules": True, "pledge": True}
URL = "/api/v1/candidate/skills"


def finish_skill(client, db, correct: bool) -> dict:
    a = client.post(f"{URL}/sql/attempts", json=START)
    assert a.status_code == 201, a.text
    state = a.json()
    for _ in range(PARAMS.skill_len):
        state = answer_current(client, db, state["id"], correct)
    return state


def test_overview_lists_skills_with_recommendation(client, db, toy_skill_bank):
    u = login(client, db)
    db.add(CandidateStack(user_id=u.id, tech="PostgreSQL"))
    db.commit()
    skills = {s["code"]: s for s in client.get(URL).json()}
    assert set(skills) == {"sql", "devops", "frontend_basics", "backend_basics", "ml_basics", "ai"}
    assert skills["sql"]["status"] == "not_taken" and skills["sql"]["recommended"] and skills["sql"]["bank_ready"]
    assert not skills["devops"]["recommended"] and not skills["devops"]["bank_ready"]
    assert "PostgreSQL" in skills["sql"]["techs"]


def test_rules_and_bank_are_required(client, db, toy_skill_bank):
    login(client, db)
    assert client.post(f"{URL}/sql/attempts", json={"accept_rules": True}).json()["code"] == "rules_required"
    assert client.post(f"{URL}/devops/attempts", json=START).json()["code"] == "bank_unavailable"
    assert client.post(f"{URL}/nope/attempts", json=START).status_code == 404


def test_six_items_then_passed_and_stack_confirmed(client, db, toy_skill_bank):
    u = login(client, db)
    db.add(CandidateStack(user_id=u.id, tech="PostgreSQL"))
    db.commit()
    state = finish_skill(client, db, correct=True)
    assert state["stage"] == "finished" and state["target_grade"] == "skill" and state["phase2_total"] == 0
    assert state["result"]["phrase"] == "Навык «SQL» подтверждён · решено 6 из 6"
    row = db.scalar(select(SkillResult).where(SkillResult.user_id == u.id))
    assert row.passed and row.skill_code == "sql" and row.metrics["n"] == 6
    p = db.get(CandidateProfile, u.id)
    assert stack_states(db, p)["PostgreSQL"] == "confirmed"  # навык SQL подтверждает PostgreSQL


def test_implied_tech_recommends_skill(client, db, toy_skill_bank):
    u = login(client, db)
    db.add(CandidateStack(user_id=u.id, tech="TypeScript"))  # TypeScript подразумевает JavaScript
    db.commit()
    skills = {s["code"]: s for s in client.get(URL).json()}
    assert skills["frontend_basics"]["recommended"] and not skills["sql"]["recommended"]


def test_cooldown_and_confirmed_skill_block_restart(client, db, toy_skill_bank, frozen_now):
    start = clock.now()
    frozen_now(start)
    u = login(client, db)
    finish_skill(client, db, correct=False)
    s = {x["code"]: x for x in client.get(URL).json()}["sql"]
    assert s["status"] == "failed" and not s["available"]
    r = client.post(f"{URL}/sql/attempts", json=START)
    assert r.status_code == 409 and r.json()["code"] == "cooldown"
    frozen_now(start + timedelta(days=PARAMS.cooldown_skill_days, minutes=1))
    client.cookies.set("fsp_session", create_session(db, u))  # сессия живёт SESSION_TTL — меньше кулдауна
    finish_skill(client, db, correct=True)
    assert client.post(f"{URL}/sql/attempts", json=START).json()["code"] == "skill_already_confirmed"


def test_reset_cooldowns_demo_unlocks_skill(client, db, toy_skill_bank):
    login(client, db)
    finish_skill(client, db, correct=False)
    assert client.post("/api/v1/demo/reset-cooldowns").status_code == 204
    assert client.post(f"{URL}/sql/attempts", json=START).status_code == 201


def test_skill_attempt_does_not_touch_grade(client, db, toy_skill_bank):
    u = login(client, db)
    client.put("/api/v1/candidate/profile/survey", json={"specialization": "backend", "claimed_grade": "middle"})
    finish_skill(client, db, correct=True)
    p = db.get(CandidateProfile, u.id)
    assert p.grade_status == "not_tested" and p.s_cache is None
    assert client.get("/api/v1/candidate/attempts").json() == []  # история основного теста — без навыков


def test_abandoned_skill_attempt_closes_without_result(client, db, toy_skill_bank, frozen_now):
    start = clock.now()
    frozen_now(start)
    u = login(client, db)
    aid = client.post(f"{URL}/sql/attempts", json=START).json()["id"]
    answer_current(client, db, aid, True)
    frozen_now(start + timedelta(hours=PARAMS.attempt_autoclose_hours, minutes=1))
    assert client.get(f"/api/v1/candidate/attempts/{aid}").json()["stage"] == "incomplete"
    assert db.scalar(select(SkillResult).where(SkillResult.user_id == u.id)) is None
    assert client.post(f"{URL}/sql/attempts", json=START).status_code == 201  # без кулдауна


def test_extend_is_rejected_for_skill(client, db, toy_skill_bank):
    login(client, db)
    aid = client.post(f"{URL}/sql/attempts", json=START).json()["id"]
    r = client.post(f"/api/v1/candidate/attempts/{aid}/extend")
    assert r.status_code == 409 and r.json()["code"] == "not_extendable"


def test_one_active_skill_attempt(client, db, toy_skill_bank):
    login(client, db)
    first = client.post(f"{URL}/sql/attempts", json=START).json()["id"]
    assert client.post(f"{URL}/sql/attempts", json=START).json()["id"] == first  # продолжение той же попытки
    assert db.scalar(select(Attempt.kind).where(Attempt.id == first)) == "skill"
