import uuid
from datetime import timedelta

from sqlalchemy import func, select

from app.common import clock
from app.config.params import PARAMS
from app.hiring import service as hiring_service
from app.hiring.models import Vote
from tests.contacts.helpers import Scene, as_user
from tests.employers.helpers import NEED

from .helpers import STACK, accept, accepted, stage

BOARD = "/api/v1/employer/needs/{}/board"


def test_board_lists_accepted_contacts_and_moves_forward(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p)
    b = client.get(BOARD.format(s.need_id)).json()
    assert (b["trust_level"], b["vote_weight"], b["votes_used"], b["votes_limit"]) == ("L2", 1.0, 0, PARAMS.vote_monthly)
    card = b["cards"][0]
    assert card["contact_id"] == cid and card["stage"] is None and card["chat_open"] and card["grade"] == "middle"
    assert {o["code"] for o in card["area_options"]} == {"lang", "http", "db", "arch", "debug"}
    assert stage(client, cid, stage="first").json()["stage"] == "first"
    r = stage(client, cid, stage="technical")
    assert r.status_code == 422 and r.json()["code"] == "level_required"
    card = stage(client, cid, stage="technical", level="meets").json()
    assert card["vote"]["state"] == "pending" and card["vote"]["value"] == "meets" and card["vote_note"] is None
    assert stage(client, cid, stage="first").json()["code"] == "stage_not_allowed"  # только вперёд
    assert client.get(BOARD.format(s.need_id)).json()["votes_used"] == 1


def test_last_answer_overwrites_and_unknown_keeps_the_vote(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p)
    stage(client, cid, stage="technical", level="below")
    stage(client, cid, stage="technical", level="unknown")  # «пока не могу сказать» — голос прежний
    v = db.scalar(select(Vote).where(Vote.contact_id == uuid.UUID(cid)))
    assert v.value == "below"
    card = stage(client, cid, stage="rejected", level="above", reason="candidate_declined", weak_areas=["db"]).json()
    db.refresh(v)
    assert v.value == "above" and card["reason"] == "candidate_declined" and card["weak_areas"] == ["db"]
    assert db.scalar(select(func.count()).select_from(Vote)) == 1  # один голос на контакт


def test_final_needs_reason_and_areas_of_the_specialization(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p)
    assert stage(client, cid, stage="rejected", level="below").json()["code"] == "reason_required"
    assert stage(client, cid, stage="hired", level="meets", weak_areas=["js"]).json()["code"] == "bad_weak_areas"
    assert stage(client, cid, stage="hired", level="meets").json()["stage"] == "hired"
    assert stage(client, cid, stage="rejected", level="below", reason="other").json()["code"] == "stage_not_allowed"


def test_l0_company_answers_without_a_vote(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p, trust="L0")
    card = stage(client, cid, stage="technical", level="meets").json()
    assert card["vote"] is None and card["vote_note"] == "trust" and card["level"] == "meets"


def test_one_vote_per_company_per_candidate(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p)
    stage(client, cid, stage="technical", level="meets")
    s.need_id = client.post("/api/v1/employer/needs", json={**NEED, "title": "Ещё одна"}).json()["id"]
    cid2 = s.invite(p.public_ref).json()["id"]
    accept(client, db, p.user_id, cid2)
    s.as_employer()
    assert stage(client, cid2, stage="technical", level="above").json()["vote_note"] == "duplicate"


def test_monthly_vote_limit(client, db, make_candidate, monkeypatch):
    monkeypatch.setattr(hiring_service, "PARAMS", PARAMS.model_copy(update={"vote_monthly": 1}))
    p1, p2 = make_candidate(stack=STACK), make_candidate(stack=STACK)
    s, cid1 = accepted(client, db, p1)
    cid2 = s.invite(p2.public_ref).json()["id"]
    accept(client, db, p2.user_id, cid2)
    s.as_employer()
    assert stage(client, cid1, stage="technical", level="meets").json()["vote_note"] is None
    assert stage(client, cid2, stage="technical", level="meets").json()["vote_note"] == "limit"


def test_board_is_private_and_needs_open_contacts(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s, cid = accepted(client, db, p)
    Scene(client, db, email="hr2@corp.ru", company="Чужая")
    assert client.get(BOARD.format(s.need_id)).status_code == 404
    assert stage(client, cid, stage="first").status_code == 404
    as_user(client, db, p.user_id)
    client.post(f"/api/v1/candidate/invitations/{cid}/revoke")
    s.as_employer()
    assert stage(client, cid, stage="first").json()["code"] == "contact_not_open"
    cards = client.get(BOARD.format(s.need_id)).json()["cards"]
    assert [c["revoked"] for c in cards] == [True]  # карточка остаётся только для чтения


def test_three_positive_votes_raise_the_candidate_after_the_dispute_window(client, db, make_candidate, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    p = make_candidate(stack=STACK)
    scenes = []
    for i in range(3):
        s, cid = accepted(client, db, p, email=f"hr{i}@corp.ru", company=f"Корп {i}")
        stage(client, cid, stage="technical", level="meets")
        scenes.append(s)

    def my_card():
        scenes[0].as_employer()
        blocks = client.get(f"/api/v1/employer/needs/{scenes[0].need_id}/selection").json()["blocks"]
        return next(c for b in blocks for c in b["items"] if c["ref"] == p.public_ref)

    assert my_card()["interview_badge"] is None  # до конца окна спора голоса не действуют
    frozen_now(t0 + timedelta(days=PARAMS.vote_dispute_days, minutes=1))
    card = my_card()
    assert card["interview_badge"] == "Подтверждено на собеседованиях (3)"
    assert card["explanation"]["lines"][0].endswith("подтверждено на собеседованиях (3) → выше в выдаче")
