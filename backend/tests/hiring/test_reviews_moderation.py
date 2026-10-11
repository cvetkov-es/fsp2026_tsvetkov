from datetime import timedelta

from sqlalchemy import select

from app.common import clock
from app.config.params import PARAMS
from app.hiring.votes import Holder, vote_stats
from app.moderation.models import Case
from app.notifications.models import Notification
from tests.contacts.helpers import as_user

from .helpers import STACK, accepted, moderator, stage

REVIEWS = "/api/v1/candidate/reviews"


def disputed(client, db, make_candidate, level="meets"):
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p)
    stage(client, cid, stage="technical", level=level)
    as_user(client, db, p.user_id)
    vote_id = client.get(REVIEWS).json()[0]["id"]
    r = client.post(f"{REVIEWS}/{vote_id}/dispute", json={"reason": "no_interview", "comment": "Созвона не было"})
    assert r.status_code == 200, r.text
    return p, s, vote_id, r.json()


def test_candidate_sees_private_reviews_and_disputes_only_by_facts(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p)
    stage(client, cid, stage="technical", level="below")
    as_user(client, db, p.user_id)
    rv = client.get(REVIEWS).json()
    assert (rv[0]["company"], rv[0]["value"], rv[0]["state"], rv[0]["can_dispute"]) == ("Корп", "below", "pending", True)
    assert client.post(f"{REVIEWS}/{rv[0]['id']}/dispute", json={"reason": "unfair"}).status_code == 422
    s.as_employer()
    assert client.get(REVIEWS).status_code == 403


def test_disputed_vote_does_not_count_and_opens_a_case(client, db, make_candidate, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    p, s, vote_id, rv = disputed(client, db, make_candidate)
    assert rv[0]["state"] == "disputed" and not rv[0]["can_dispute"]
    case = db.scalar(select(Case))
    assert case.type == "vote_dispute" and case.status == "open" and case.comment == "Созвона не было"
    frozen_now(t0 + timedelta(days=PARAMS.vote_dispute_days + 1))
    assert vote_stats(db, {p.user_id: Holder("backend", "middle")}, clock.now()) == {}


def test_dispute_window_closes(client, db, make_candidate, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p)
    stage(client, cid, stage="technical", level="below")
    frozen_now(t0 + timedelta(days=PARAMS.vote_dispute_days, minutes=1))
    as_user(client, db, p.user_id)
    rv = client.get(REVIEWS).json()
    assert rv[0]["state"] == "active" and not rv[0]["can_dispute"]
    r = client.post(f"{REVIEWS}/{rv[0]['id']}/dispute", json={"reason": "no_interview"})
    assert r.status_code == 409 and r.json()["code"] == "dispute_closed"


def test_moderator_annuls_a_disputed_vote(client, db, make_candidate):
    mod = moderator(client, db)
    p, s, vote_id, _ = disputed(client, db, make_candidate)
    assert db.scalar(select(Notification).where(Notification.user_id == mod.id, Notification.kind == "case_opened"))
    as_user(client, db, mod.id)
    cases = client.get("/api/v1/moderation/cases").json()
    d = {r["label"]: r["value"] for r in cases[0]["summary"]}
    assert cases[0]["type_title"] == "Спор об оценке" and d["Компания"] == "Корп" and d["Причина спора"] == "собеседования не было"
    assert "соответствует ожиданиям" in d["Оценка"] and d["Этапы"].startswith("Техническое интервью")
    assert [a["code"] for a in cases[0]["actions"]] == ["annul", "uphold"]
    url = f"/api/v1/moderation/cases/{cases[0]['id']}/resolve"
    assert client.post(url, json={"action": "annul", "resolution_text": "Компания подтвердила ошибку"}).json()["status"] == "resolved"
    assert client.post(url, json={"action": "uphold"}).json()["code"] == "case_closed"
    assert client.get("/api/v1/moderation/cases").json() == []
    as_user(client, db, p.user_id)
    assert client.get(REVIEWS).json()[0]["state"] == "annulled"
    assert db.scalar(select(Notification).where(Notification.user_id == p.user_id,
                                                Notification.kind == "vote_dispute_resolved"))
    s.as_employer()
    assert client.post(url, json={"action": "annul"}).status_code == 403  # только модератор


def test_upheld_vote_acts_at_once(client, db, make_candidate):
    p, s, vote_id, _ = disputed(client, db, make_candidate)
    mod = moderator(client, db, email="mod2@x.ru")
    as_user(client, db, mod.id)
    case_id = client.get("/api/v1/moderation/cases").json()[0]["id"]
    client.post(f"/api/v1/moderation/cases/{case_id}/resolve", json={"action": "uphold"})
    assert vote_stats(db, {p.user_id: Holder("backend", "middle")}, clock.now())[p.user_id].positive == 1
