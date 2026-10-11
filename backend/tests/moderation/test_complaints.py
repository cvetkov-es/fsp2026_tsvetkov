from datetime import timedelta

from sqlalchemy import select

from app.assessment.bank_sync import sync_bank
from app.assessment.models import ItemFamilyRow
from app.common import clock
from app.config.params import PARAMS
from app.contacts.service import quota
from app.employers.models import Need
from tests.contacts.helpers import Scene, as_user
from tests.hiring.helpers import moderator

STACK = ("Python", "PostgreSQL")
START = {"target_grade": "middle", "accept_rules": True, "pledge": True}


def decline_spam(client, db, p, s):
    cid = s.invite(p.public_ref).json()["id"]
    as_user(client, db, p.user_id)
    client.post(f"/api/v1/candidate/invitations/{cid}/decline", json={"reason": "spam", "comment": "Это рассылка"})


def test_spam_decline_penalizes_quota_and_opens_case(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s = Scene(client, db, trust_level="L1")
    need = db.get(Need, s.need_id)
    _, before = quota(db, need, s.company)
    decline_spam(client, db, p, s)
    db.refresh(s.company)
    assert quota(db, need, s.company)[1] == before - PARAMS.complaint_quota_penalty
    moderator(client, db)
    case = client.get("/api/v1/moderation/cases").json()[0]
    assert case["type"] == "employer_complaint" and [a["code"] for a in case["actions"]] == ["uphold", "annul"]
    client.post(f"/api/v1/moderation/cases/{case['id']}/resolve", json={"action": "annul"})
    db.refresh(s.company)
    assert quota(db, need, s.company)[1] == before and s.company.quota_penalty_slots == 0


def test_penalties_accumulate_and_annul_removes_only_its_own(client, db, make_candidate):
    p1, p2 = make_candidate(stack=STACK), make_candidate(stack=STACK)
    s = Scene(client, db, trust_level="L2")
    need = db.get(Need, s.need_id)
    _, before = quota(db, need, s.company)
    decline_spam(client, db, p1, s)
    decline_spam(client, db, p2, s)
    db.refresh(s.company)
    assert quota(db, need, s.company)[1] == before - 2 * PARAMS.complaint_quota_penalty
    moderator(client, db)
    first = client.get("/api/v1/moderation/cases").json()[0]
    client.post(f"/api/v1/moderation/cases/{first['id']}/resolve", json={"action": "annul"})
    db.refresh(s.company)
    assert quota(db, need, s.company)[1] == before - PARAMS.complaint_quota_penalty  # второй штраф остался


def test_annul_after_the_penalty_expired_does_not_go_below_zero(client, db, make_candidate, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    p = make_candidate(stack=STACK)
    s = Scene(client, db, trust_level="L1")
    decline_spam(client, db, p, s)
    frozen_now(t0 + timedelta(days=PARAMS.complaint_penalty_days + 1))
    moderator(client, db)
    case = client.get("/api/v1/moderation/cases").json()[0]
    assert client.post(f"/api/v1/moderation/cases/{case['id']}/resolve", json={"action": "annul"}).status_code == 200
    db.refresh(s.company)
    assert s.company.quota_penalty_slots >= 0
    assert quota(db, db.get(Need, s.need_id), s.company)[1] == PARAMS.quota_l1


def test_annulling_an_expired_complaint_keeps_a_newer_penalty(client, db, make_candidate, frozen_now):
    t0 = clock.now()
    frozen_now(t0)
    p1, p2 = make_candidate(stack=STACK), make_candidate(stack=STACK)
    s = Scene(client, db, trust_level="L2")
    need = db.get(Need, s.need_id)
    decline_spam(client, db, p1, s)  # штраф A
    frozen_now(t0 + timedelta(days=PARAMS.complaint_penalty_days + 1))
    decline_spam(client, db, p2, s)  # штраф B: старый уже истёк
    db.refresh(s.company)
    assert quota(db, need, s.company)[1] == PARAMS.quota_l2 - PARAMS.complaint_quota_penalty
    frozen_now(t0 + timedelta(days=PARAMS.complaint_penalty_days + 2))
    moderator(client, db)
    cases = client.get("/api/v1/moderation/cases").json()
    older = min(cases, key=lambda c: c["created_at"])  # обращение A — первое по времени
    client.post(f"/api/v1/moderation/cases/{older['id']}/resolve", json={"action": "annul"})
    db.refresh(s.company)
    assert quota(db, need, s.company)[1] == PARAMS.quota_l2 - PARAMS.complaint_quota_penalty  # штраф B на месте


def test_suspended_family_that_left_the_registry_stays_suspended(db):
    sync_bank(db)
    db.add(ItemFamilyRow(code="ghost.family", specialization="backend", area="lang", level=1, fmt="toy", b=0.0,
                         median_time_s=30, status="suspended"))
    db.commit()
    sync_bank(db)  # семейства нет в реестре: обычно оно становится retired, но решение модератора важнее
    db.refresh(db.get(ItemFamilyRow, "ghost.family"))
    assert db.get(ItemFamilyRow, "ghost.family").status == "suspended"


def test_suspended_family_survives_sync(db):
    sync_bank(db)
    row = db.scalars(select(ItemFamilyRow)).first()
    row.status = "suspended"
    db.commit()
    sync_bank(db)
    db.refresh(row)
    assert row.status == "suspended"


def test_every_complaint_type_is_registered():
    from app.moderation.types import TYPES

    assert {"employer_complaint", "item_problem", "art16"} <= set(TYPES)
    assert TYPES["art16"].due_days == PARAMS.art16_days
