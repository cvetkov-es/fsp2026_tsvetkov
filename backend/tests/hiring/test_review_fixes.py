"""Замечания ревью 07b1: категория голоса, спор и повторный ответ, необратимый архив, дайджест, напоминания, доска."""
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select

from app.assessment.models import Attempt
from app.candidates.models import CandidateProfile
from app.common import clock
from app.common.clock import MSK
from app.config.params import PARAMS
from app.hiring.jobs import remind_stages, vote_digest
from app.hiring.models import Vote
from app.hiring.votes import holder, unlocks_higher_test, vote_stats
from app.moderation.models import Case
from app.notifications.models import Notification
from app.notifications.service import title_of
from tests.contacts.helpers import as_user

from .helpers import STACK, accepted, moderator, stage

REVIEWS = "/api/v1/candidate/reviews"


def vote_of(db, cid) -> Vote:
    db.expire_all()
    return db.scalar(select(Vote).where(Vote.contact_id == uuid.UUID(cid)))


def test_votes_do_not_cross_specializations(client, db, make_candidate, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    p = make_candidate(stack=STACK)
    for i in range(3):
        _, cid = accepted(client, db, p, email=f"hr{i}@corp.ru", company=f"Корп {i}")
        stage(client, cid, stage="technical", level="above")
    frozen_now(t0 + timedelta(days=PARAMS.vote_dispute_days + 1))
    as_user(client, db, p.user_id)
    client.put("/api/v1/candidate/profile/survey", json={"specialization": "frontend", "claimed_grade": "middle"})
    db.expire_all()
    prof = db.get(CandidateProfile, p.user_id)
    prof.grade_status, prof.confirmed_grade = "confirmed", "middle"  # подтвердил Frontend Middle
    db.commit()
    assert vote_stats(db, {p.user_id: holder(prof)}, clock.now()) == {}
    assert not unlocks_higher_test(db, p.user_id, holder(prof), clock.now())
    assert {r["state"] for r in client.get(REVIEWS).json()} == {"archived"}


def test_archive_is_permanent_after_grade_change_and_back(client, db, make_candidate, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    p = make_candidate(stack=STACK, status="not_confirmed")
    _, cid = accepted(client, db, p)
    stage(client, cid, stage="technical", level="meets")
    as_user(client, db, p.user_id)
    frozen_now(t0 + timedelta(hours=1))
    client.put("/api/v1/candidate/profile/survey", json={"specialization": "backend", "claimed_grade": "senior"})
    frozen_now(t0 + timedelta(hours=2))
    client.put("/api/v1/candidate/profile/survey", json={"specialization": "backend", "claimed_grade": "middle"})
    assert client.get(REVIEWS).json()[0]["state"] == "archived"


def test_same_answer_keeps_an_effective_vote(client, db, make_candidate, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p)
    stage(client, cid, stage="technical", level="meets")
    eff = vote_of(db, cid).effective_at
    frozen_now(t0 + timedelta(days=10))
    stage(client, cid, stage="hired", level="meets")
    v = vote_of(db, cid)
    assert v.effective_at == eff and v.answered_at == t0  # тот же ответ — окно спора не открывается заново


def test_company_answer_during_dispute_applies_on_uphold(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p)
    stage(client, cid, stage="technical", level="below")
    as_user(client, db, p.user_id)
    rv = client.get(REVIEWS).json()[0]
    client.post(f"{REVIEWS}/{rv['id']}/dispute", json={"reason": "wrong_stage", "answered_at": rv["at"]})
    s.as_employer()
    assert stage(client, cid, stage="hired", level="above").json()["vote_note"] == "disputed"
    moderator(client, db)
    case = client.get("/api/v1/moderation/cases").json()[0]
    rows = {r["label"]: r["value"] for r in case["summary"]}
    assert "выше ожиданий" in rows["Ответ во время спора"]  # применится, если оставить оценку в силе
    client.post(f"/api/v1/moderation/cases/{case['id']}/resolve", json={"action": "uphold"})
    v = vote_of(db, cid)
    assert v.value == "above" and v.status == "pending" and v.pending_value is None  # последний ответ, новое окно спора


def test_dispute_is_bound_to_the_version(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p)
    stage(client, cid, stage="technical", level="below")
    as_user(client, db, p.user_id)
    seen = client.get(REVIEWS).json()[0]
    s.as_employer()
    stage(client, cid, stage="technical", level="above")
    as_user(client, db, p.user_id)
    r = client.post(f"{REVIEWS}/{seen['id']}/dispute", json={"reason": "wrong_stage", "answered_at": seen["at"]})
    assert r.status_code == 409 and r.json()["code"] == "vote_changed"


def test_archived_vote_does_not_block_a_vote_on_the_new_grade(client, db, make_candidate, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p)
    stage(client, cid, stage="technical", level="above")
    frozen_now(t0 + timedelta(days=1))
    prof = db.get(CandidateProfile, p.user_id)
    prof.confirmed_grade, prof.claimed_grade, prof.grade_changed_at = "senior", "senior", clock.now()
    db.commit()
    s.need_id = client.post("/api/v1/employer/needs", json={**__import__("tests.employers.helpers", fromlist=["NEED"]).NEED,
                                                             "title": "Сеньор", "grades": ["senior"]}).json()["id"]
    cid2 = s.invite(p.public_ref).json()["id"]
    from .helpers import accept
    accept(client, db, p.user_id, cid2)
    s.as_employer()
    assert stage(client, cid2, stage="technical", level="meets").json()["vote_note"] is None


def test_unlock_needs_l2_trust_not_weight(client, db, make_candidate, frozen_now, monkeypatch):
    from app.hiring import votes as votes_module
    monkeypatch.setattr(votes_module, "PARAMS", PARAMS.model_copy(update={"vote_w_l1": PARAMS.vote_w_l2}))
    t0 = clock.now()
    frozen_now(t0)
    p = make_candidate(stack=STACK)
    for i in range(PARAMS.votes_unlock):
        _, cid = accepted(client, db, p, trust="L1", email=f"hr{i}@corp.ru", company=f"Корп {i}")
        stage(client, cid, stage="technical", level="above")
    frozen_now(t0 + timedelta(days=PARAMS.vote_dispute_days + 1))
    prof = db.get(CandidateProfile, p.user_id)
    assert not unlocks_higher_test(db, p.user_id, holder(prof), clock.now())


def test_moderation_survives_a_deleted_vote(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p)
    stage(client, cid, stage="technical", level="below")
    as_user(client, db, p.user_id)
    rv = client.get(REVIEWS).json()[0]
    client.post(f"{REVIEWS}/{rv['id']}/dispute", json={"reason": "no_interview"})
    db.delete(vote_of(db, cid))
    db.commit()
    moderator(client, db)
    cases = client.get("/api/v1/moderation/cases")
    assert cases.status_code == 200 and "удалена" in {r["label"]: r["value"] for r in cases.json()[0]["summary"]}["Оценка"]
    r = client.post(f"/api/v1/moderation/cases/{cases.json()[0]['id']}/resolve", json={"action": "uphold"})
    assert r.json()["status"] == "resolved"
    assert db.scalar(select(Case)).status == "resolved"


def test_digest_uses_answer_time_and_catches_up(client, db, make_candidate, frozen_now):
    frozen_now(datetime(2026, 10, 8, 12, 0, tzinfo=MSK))  # четверг
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p)
    stage(client, cid, stage="technical", level="below")
    tuesday = datetime(2026, 10, 13, 9, 0, tzinfo=MSK)  # worker простоял понедельник
    assert vote_digest(db, tuesday) == 1
    frozen_now(datetime(2026, 10, 14, 12, 0, tzinfo=MSK))
    as_user(client, db, p.user_id)
    rv = client.get(REVIEWS).json()[0]
    client.post(f"{REVIEWS}/{rv['id']}/dispute", json={"reason": "no_interview"})  # спор меняет запись, не ответ
    assert vote_digest(db, datetime(2026, 10, 19, 10, 5, tzinfo=MSK)) == 0


def test_reminder_text_and_actual_days(client, db, make_candidate, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p)
    remind_stages(db, t0 + timedelta(days=35))
    n = db.scalar(select(Notification).where(Notification.user_id == s.employer.id, Notification.kind == "stage_reminder"))
    assert title_of(n.kind, n.payload).endswith("не менялся 35 дней. Обновите его")
    assert n.payload["days_text"] == "35 дней"


def test_revoked_contact_stays_on_the_board_read_only(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p)
    stage(client, cid, stage="first")
    as_user(client, db, p.user_id)
    client.post(f"/api/v1/candidate/invitations/{cid}/revoke")
    s.as_employer()
    cards = client.get(f"/api/v1/employer/needs/{s.need_id}/board").json()["cards"]
    assert cards[0]["contact_id"] == cid and cards[0]["revoked"] and not cards[0]["chat_open"]
    assert stage(client, cid, stage="technical", level="meets").json()["code"] == "contact_not_open"


def test_attempt_decision_changing_grade_archives_votes(db, make_candidate):
    from app.assessment.service import _apply_to_profile
    p = make_candidate(stack=STACK)
    a = Attempt(user_id=p.user_id, kind="grade", specialization="backend", target_grade="senior", item_cap=15,
                thresholds_version="expert", decision="confirmed")
    _apply_to_profile(db, a, p)
    assert p.grade_changed_at is not None and p.confirmed_grade == "senior"
