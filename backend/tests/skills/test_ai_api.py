import json
import uuid
from collections import Counter
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy import select

from app.assessment.bank.verdicts import ideal_response
from app.assessment.models import Attempt, AttemptItem
from app.assessment.service import GRACE_S
from app.candidates.models import CandidateProfile, CandidateStack, SkillResult
from app.candidates.service import stack_states
from app.common import clock
from app.config.params import PARAMS
from tests.assessment_api.helpers import assert_no_leak
from tests.candidates.test_profile import login

URL = "/api/v1/candidate/skills"
ATT = "/api/v1/candidate/attempts"
START = {"accept_rules": True, "pledge": True}


def start_ai(client) -> str:
    r = client.post(f"{URL}/ai/attempts", json=START)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def answer_ai(client, db, aid: str, choose: Callable[[dict], dict] = ideal_response, confidence: str = "high") -> dict:
    """Открыть текущий вердикт и ответить: по умолчанию — эталонным ответом по ключу из БД."""
    state = client.post(f"{ATT}/{aid}/next").json()
    assert_no_leak(state)
    item = state["item"]
    db.expire_all()
    row = db.scalar(select(AttemptItem).where(AttemptItem.attempt_id == aid, AttemptItem.seq == item["seq"]))
    response = choose(row.instance["answer"]) | {"confidence": confidence}
    return client.post(f"{ATT}/{aid}/answer", json={"seq": item["seq"], "response": response, "events": []}).json()


def accept_all(key: dict) -> dict:
    return {"verdict": "ok"}


def test_overview_shows_the_ai_format(client, db, toy_ai_bank):
    login(client, db)
    ai = {s["code"]: s for s in client.get(URL).json()}["ai"]
    assert (ai["format"], ai["items"], ai["minutes"], ai["bank_ready"]) == ("ai", 12, 10, True)
    assert ai["title"] == "Работа с ИИ" and "Copilot" in ai["techs"]


def test_bank_must_cover_every_area(client, db, toy_ai_bank_short):
    login(client, db)
    assert not {s["code"]: s for s in client.get(URL).json()}["ai"]["bank_ready"]
    assert client.post(f"{URL}/ai/attempts", json=START).json()["code"] == "bank_unavailable"


def test_full_attempt_passes_and_confirms_ai_tools(client, db, toy_ai_bank):
    u = login(client, db)
    db.add(CandidateStack(user_id=u.id, tech="Copilot"))
    db.commit()
    aid = start_ai(client)
    first = client.post(f"{ATT}/{aid}/next").json()
    assert first["skill_code"] == "ai" and first["ai"]["total"] == 12 and first["ai"]["time_left_s"] == 600
    assert first["item"]["kind"] == "verdict" and first["item"]["time_limit_s"] == 600
    for _ in range(PARAMS.ai_verdicts):
        state = answer_ai(client, db, aid)
    assert state["stage"] == "finished" and state["result"]["decision"] == "confirmed"
    assert state["result"]["phrase"].startswith("Работа с ИИ: подтверждено · верных ответов 12 из 12")
    assert state["result"]["ai"]["accuracy"] == 1.0 and state["ai"]["time_left_s"] is None
    row = db.scalar(select(SkillResult).where(SkillResult.user_id == u.id))
    assert row.skill_code == "ai" and row.passed and row.metrics["in_time"]
    assert stack_states(db, db.get(CandidateProfile, u.id))["Copilot"] == "confirmed"


def test_plan_mixes_areas_and_hides_the_defect_share(client, db, toy_ai_bank):
    login(client, db)
    aid = start_ai(client)
    for _ in range(PARAMS.ai_verdicts):
        answer_ai(client, db, aid)
    items = list(db.scalars(select(AttemptItem).where(AttemptItem.attempt_id == aid)))
    assert Counter(i.area for i in items) == {"python": 6, "sql": 4, "clarify": 2}
    assert len({i.family_code for i in items}) == 12
    assert 5 <= sum(i.instance["answer"]["truth"] != "ok" for i in items) <= 7


def test_trusting_everything_fails_and_starts_the_cooldown(client, db, toy_ai_bank):
    login(client, db)
    aid = start_ai(client)
    for _ in range(PARAMS.ai_verdicts):
        state = answer_ai(client, db, aid, choose=accept_all)
    assert state["result"]["decision"] == "not_confirmed" and state["result"]["ai"]["miss_weighted"] == 1.0
    r = client.post(f"{URL}/ai/attempts", json=START)
    assert r.status_code == 409 and r.json()["code"] == "cooldown"


def test_one_unsure_miss_is_forgiven_a_sure_one_is_not(client, db, toy_ai_bank):
    def first_flaw_accepted(confidence: str) -> dict:
        login(client, db, email=f"{confidence}@x.ru")
        aid, missed = start_ai(client), []

        def choose(key: dict) -> dict:
            if key["truth"] != "ok" and not missed:
                missed.append(key)
                return {"verdict": "ok", "confidence": confidence}
            return ideal_response(key)
        for _ in range(PARAMS.ai_verdicts):
            state = client.post(f"{ATT}/{aid}/next").json()
            db.expire_all()
            row = db.scalar(select(AttemptItem).where(AttemptItem.attempt_id == aid,
                                                      AttemptItem.seq == state["item"]["seq"]))
            body = {"seq": row.seq, "response": choose(row.instance["answer"]), "events": []}
            state = client.post(f"{ATT}/{aid}/answer", json=body).json()
        return state["result"]

    assert first_flaw_accepted("low")["decision"] == "confirmed"
    assert first_flaw_accepted("high")["decision"] == "not_confirmed"


def test_timer_is_shared_and_runs_out(client, db, toy_ai_bank, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    login(client, db)
    aid = start_ai(client)
    answer_ai(client, db, aid)
    frozen_now(t0 + timedelta(seconds=90))
    second = client.post(f"{ATT}/{aid}/next").json()
    assert second["item"]["time_limit_s"] == 510 and second["ai"]["time_left_s"] == 510
    frozen_now(t0 + timedelta(minutes=PARAMS.ai_minutes, seconds=GRACE_S + 1))
    state = client.get(f"{ATT}/{aid}").json()
    assert state["stage"] == "finished" and state["result"]["decision"] == "not_confirmed"
    assert state["result"]["phrase"].endswith("время вышло")
    db.expire_all()
    assert db.get(Attempt, uuid.UUID(aid)).finished_at == t0 + timedelta(minutes=PARAMS.ai_minutes)  # как при мгновенном закрытии


def test_no_answer_means_no_result_and_no_cooldown(client, db, toy_ai_bank, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    u = login(client, db)
    aid = start_ai(client)
    client.post(f"{ATT}/{aid}/next")
    frozen_now(t0 + timedelta(minutes=PARAMS.ai_minutes + 1))
    assert client.get(f"{ATT}/{aid}").json()["stage"] == "incomplete"
    assert db.scalar(select(SkillResult).where(SkillResult.user_id == u.id)) is None
    assert client.post(f"{URL}/ai/attempts", json=START).status_code == 201


def test_verdict_item_never_leaks_the_key(client, db, toy_ai_bank):
    login(client, db)
    state = client.post(f"{ATT}/{start_ai(client)}/next").json()
    text = json.dumps(state, ensure_ascii=False)
    assert not any(f'"{k}"' in text for k in ("truth", "breaks", "witness", "reference", "shown"))
    assert len(state["item"]["prompt"]["clarify"]) == 4


def test_ai_attempt_does_not_touch_grade_or_history(client, db, toy_ai_bank):
    u = login(client, db)
    client.put("/api/v1/candidate/profile/survey", json={"specialization": "backend", "claimed_grade": "middle"})
    aid = start_ai(client)
    for _ in range(PARAMS.ai_verdicts):
        answer_ai(client, db, aid)
    p = db.get(CandidateProfile, u.id)
    assert p.grade_status == "not_tested" and p.s_cache is None
    assert client.get(ATT).json() == []


def test_finish_follows_the_attempt_cap(client, db, toy_ai_bank):
    login(client, db)
    aid = start_ai(client)
    db.get(Attempt, uuid.UUID(aid)).item_cap = 3  # число вердиктов попытки — её собственное, а не текущий PARAMS
    db.commit()
    for _ in range(3):
        state = answer_ai(client, db, aid)
    assert state["stage"] == "finished"


def test_progress_reports_the_cooldown(client, db, toy_ai_bank):
    login(client, db)
    state = client.post(f"{ATT}/{start_ai(client)}/next").json()
    assert state["ai"]["cooldown_days"] == PARAMS.cooldown_skill_days
