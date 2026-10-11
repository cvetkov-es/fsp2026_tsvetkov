from datetime import timedelta

from sqlalchemy import select

from app.assessment.models import ItemFamilyRow
from app.assessment.service import _family_rows
from app.auth.service import create_session
from app.common import clock
from app.config.params import PARAMS
from app.moderation.models import Case
from tests.assessment_api.helpers import answer_current
from tests.hiring.helpers import moderator

START = {"target_grade": "middle", "accept_rules": True, "pledge": True}


def start(client):
    return client.post("/api/v1/candidate/attempts", json=START).json()["id"]


def shown_seq(client, aid):
    return client.post(f"/api/v1/candidate/attempts/{aid}/next").json()["item"]["seq"]


def test_item_report_once_per_item_and_only_for_own_attempts(client, db, candidate_login, toy_bank):
    candidate_login()
    aid = start(client)
    seq = shown_seq(client, aid)
    url = f"/api/v1/candidate/attempts/{aid}/items/{seq}/report"
    r = client.post(url, json={"reason": "wrong_key", "comment": "Ключ неверен"})
    assert r.status_code == 201
    assert client.post(url, json={"reason": "typo"}).json()["code"] == "already_reported"
    assert client.post(f"/api/v1/candidate/attempts/{aid}/items/{seq + 5}/report", json={"reason": "typo"}).status_code == 404
    candidate_login("other@x.ru")
    assert client.post(url, json={"reason": "typo"}).status_code == 404  # чужая попытка


def test_moderator_suspends_the_family_and_it_leaves_the_rotation(client, db, candidate_login, toy_bank):
    u = candidate_login()
    aid = start(client)
    seq = shown_seq(client, aid)
    client.post(f"/api/v1/candidate/attempts/{aid}/items/{seq}/report", json={"reason": "wrong_key", "comment": "Ключ неверен"})
    moderator(client, db)
    case = client.get("/api/v1/moderation/cases").json()[0]
    assert case["type"] == "item_problem" and [a["code"] for a in case["actions"]] == ["suspend", "dismiss"]
    rows = {r["label"]: r["value"] for r in case["summary"]}
    assert "+" in rows["Задание"] and rows["Ключ ответа"] and "Ключ неверен" not in str(case["summary"])  # комментарий — в общей карточке
    assert case["comment"] == "Ключ неверен"
    code = rows["Семейство"]
    assert client.post(f"/api/v1/moderation/cases/{case['id']}/resolve", json={"action": "suspend"}).status_code == 200
    db.expire_all()
    assert db.get(ItemFamilyRow, code).status == "suspended"
    assert code not in {r.code for r in _family_rows(db, "backend")}
    client.cookies.set("fsp_session", create_session(db, u))
    mine = client.get("/api/v1/candidate/cases").json()[0]
    assert mine["status"] == "resolved" and mine["outcome"] == "задание убрано из теста, спасибо"


def test_objection_after_a_decision_only_once_and_reset_lifts_the_cooldown(client, db, candidate_login, toy_bank, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    u = candidate_login()
    aid = start(client)
    url = f"/api/v1/candidate/attempts/{aid}/objection"
    assert client.post(url, json={"comment": "Решение неверное, прошу пересмотреть"}).json()["code"] == "no_decision"
    for _ in range(6):
        answer_current(client, db, aid, False)
    assert client.post(url, json={"comment": "коротко"}).status_code == 422
    assert client.post(url, json={"comment": "Задания были с опечатками, прошу пересмотреть"}).status_code == 201
    assert client.post(url, json={"comment": "Ещё раз то же самое возражение"}).json()["code"] == "already_objected"
    assert client.get("/api/v1/candidate/tests/availability").json()["middle"]["allowed"] is False
    moderator(client, db)
    case = client.get("/api/v1/moderation/cases").json()[0]
    assert case["type"] == "art16" and [a["code"] for a in case["actions"]] == ["uphold", "reset"]
    assert case["due_at"].startswith((t0 + timedelta(days=PARAMS.art16_days)).strftime("%Y-%m-%d"))
    client.post(f"/api/v1/moderation/cases/{case['id']}/resolve", json={"action": "reset", "resolution_text": "Задания проверены"})
    client.cookies.set("fsp_session", create_session(db, u))
    assert client.get("/api/v1/candidate/tests/availability").json()["middle"]["allowed"] is True
    mine = client.get("/api/v1/candidate/cases").json()[0]
    assert mine["outcome"] == "пересдать тест можно уже сейчас" and mine["resolution_text"] == "Задания проверены"


def test_my_cases_lists_only_my_own(client, db, candidate_login, toy_bank):
    candidate_login()
    aid = start(client)
    seq = shown_seq(client, aid)
    client.post(f"/api/v1/candidate/attempts/{aid}/items/{seq}/report", json={"reason": "typo"})
    assert len(client.get("/api/v1/candidate/cases").json()) == 1
    candidate_login("other@x.ru")
    assert client.get("/api/v1/candidate/cases").json() == []
    assert db.scalar(select(Case)) is not None
