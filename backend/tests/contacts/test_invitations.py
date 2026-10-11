from datetime import timedelta

from sqlalchemy import select

from app.audit.models import AuditLog
from app.auth.models import Consent
from app.common import clock
from app.config.params import PARAMS
from app.notifications.models import Notification
from tests.contacts.helpers import Scene, as_user

STACK = ("Python", "PostgreSQL")


def test_draft_prefill_and_send(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    d = client.get(f"/api/v1/employer/needs/{s.need_id}/invitations/draft", params={"ref": p.public_ref}).json()
    assert (d["salary_from"], d["salary_to"], d["gross_net"]) == (200000, 300000, "gross")
    assert d["why_you"].startswith("Middle подтверждён тестом") and (d["quota_used"], d["quota_limit"]) == (0, 3)
    r = s.invite(p.public_ref)
    assert r.status_code == 201 and r.json()["status"] == "sent" and r.json()["alias"].startswith("B-M-")
    as_user(client, db, p.user_id)
    inv = client.get("/api/v1/candidate/invitations").json()
    assert inv[0]["company"]["name"] == "Корп" and inv[0]["salary_to_net"] == 261000
    assert client.get(f"/api/v1/candidate/invitations/{inv[0]['id']}").json()["status"] == "viewed"
    kinds = set(db.scalars(select(Notification.kind).where(Notification.user_id == p.user_id)))
    assert kinds == {"invitation"}


def test_one_active_per_pair_and_reinvite_rules(client, db, make_candidate, frozen_now):
    start = clock.now()
    frozen_now(start)
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    cid = s.invite(p.public_ref).json()["id"]
    assert s.invite(p.public_ref).json()["code"] == "invite_exists"
    as_user(client, db, p.user_id)
    client.post(f"/api/v1/candidate/invitations/{cid}/decline", json={"reason": "salary"})
    assert s.invite(p.public_ref).json()["code"] == "reinvite_too_early"  # та же вилка раньше срока
    cid2 = s.invite(p.public_ref, salary_to=320000).json()["id"]  # строго выше — можно, один раз
    as_user(client, db, p.user_id)
    client.post(f"/api/v1/candidate/invitations/{cid2}/decline", json={"reason": "salary"})
    assert s.invite(p.public_ref, salary_to=400000).json()["code"] == "reinvite_too_early"
    frozen_now(start + timedelta(days=PARAMS.reinvite_days + 1))
    assert s.invite(p.public_ref).status_code == 201


def test_quota_l0_penalty_and_slot_release(client, db, make_candidate):
    cands = [make_candidate(stack=STACK) for _ in range(4)]
    s = Scene(client, db)
    ids = [s.invite(c.public_ref).json()["id"] for c in cands[:3]]
    r = s.invite(cands[3].public_ref)
    assert r.status_code == 409 and r.json()["code"] == "quota_exceeded"
    as_user(client, db, cands[0].user_id)
    client.post(f"/api/v1/candidate/invitations/{ids[0]}/decline", json={"reason": "not_looking"})
    assert s.invite(cands[3].public_ref).status_code == 201
    s.company.quota_penalty_slots, s.company.quota_penalty_until = 1, clock.now() + timedelta(days=1)
    db.commit()
    assert client.get(f"/api/v1/employer/needs/{s.need_id}/quota").json() == {"used": 3, "limit": 2}


def test_lazy_expiry_without_worker(client, db, make_candidate, frozen_now):
    start = clock.now()
    frozen_now(start)
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    cid = s.invite(p.public_ref).json()["id"]
    frozen_now(start + timedelta(days=PARAMS.invite_ttl_days, minutes=1))
    assert client.get(f"/api/v1/employer/needs/{s.need_id}/quota").json()["used"] == 0
    as_user(client, db, p.user_id)
    assert client.get("/api/v1/candidate/invitations").json()[0]["status"] == "expired"
    r = client.post(f"/api/v1/candidate/invitations/{cid}/accept", json={"consent_contact_transfer": True})
    assert r.status_code == 409 and r.json()["code"] == "invalid_transition"


def test_counter_one_round_offer_v2_same_slot(client, db, make_candidate, frozen_now):
    start = clock.now()
    frozen_now(start)
    p, q = make_candidate(stack=STACK), make_candidate(stack=STACK)
    s = Scene(client, db)
    cid = s.invite(p.public_ref).json()["id"]
    as_user(client, db, p.user_id)
    r = client.post(f"/api/v1/candidate/invitations/{cid}/counter", json={"amount": 300000, "gross_net": "net"})
    assert r.json()["status"] == "countered" and r.json()["counter_amount"] == 344828  # 300 000 на руки в gross
    s.as_employer()
    r = client.post(f"/api/v1/employer/invitations/{cid}/counter-response",
                    json={"action": "offer_v2", "salary_from": 250000, "salary_to": 345000})
    assert r.json()["status"] == "offer_v2" and r.json()["version"] == 2
    assert client.get(f"/api/v1/employer/needs/{s.need_id}/quota").json()["used"] == 1  # тот же слот
    as_user(client, db, p.user_id)
    again = client.post(f"/api/v1/candidate/invitations/{cid}/counter", json={"amount": 400000, "gross_net": "gross"})
    assert again.status_code == 409
    assert client.post(f"/api/v1/candidate/invitations/{cid}/accept",
                       json={"consent_contact_transfer": True}).json()["status"] == "accepted"
    cid_q = s.invite(q.public_ref).json()["id"]
    as_user(client, db, q.user_id)
    client.post(f"/api/v1/candidate/invitations/{cid_q}/counter", json={"amount": 400000, "gross_net": "gross"})
    frozen_now(start + timedelta(days=PARAMS.counter_ttl_days, minutes=1))
    assert client.get(f"/api/v1/candidate/invitations/{cid_q}").json()["status"] == "expired"


def test_company_declines_counter(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    cid = s.invite(p.public_ref).json()["id"]
    as_user(client, db, p.user_id)
    client.post(f"/api/v1/candidate/invitations/{cid}/counter", json={"amount": 500000, "gross_net": "gross"})
    s.as_employer()
    r = client.post(f"/api/v1/employer/invitations/{cid}/counter-response", json={"action": "decline"})
    assert r.json()["status"] == "company_declined"
    kinds = set(db.scalars(select(Notification.kind).where(Notification.user_id == p.user_id)))
    assert "counter_declined" in kinds


def test_accept_needs_consent_reveals_contacts_with_audit_and_chat(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    cid = s.invite(p.public_ref).json()["id"]
    page = client.get(f"/api/v1/contacts/{cid}").json()
    assert page["candidate"] is None and not page["chat_open"] and "Секретное" not in str(page)
    assert client.post(f"/api/v1/contacts/{cid}/messages", json={"text": "Привет"}).json()["code"] == "chat_closed"
    as_user(client, db, p.user_id)
    r = client.post(f"/api/v1/candidate/invitations/{cid}/accept", json={"consent_contact_transfer": False})
    assert r.status_code == 422 and r.json()["code"] == "consent_required"
    assert client.post(f"/api/v1/candidate/invitations/{cid}/accept",
                       json={"consent_contact_transfer": True}).json()["chat_open"] is True
    consent = db.scalar(select(Consent).where(Consent.user_id == p.user_id, Consent.type == "contact_transfer"))
    assert consent.target_company_id == s.company.id
    assert client.post(f"/api/v1/contacts/{cid}/messages", json={"text": "Здравствуйте!"}).status_code == 201
    s.as_employer()
    page = client.get(f"/api/v1/contacts/{cid}").json()
    assert page["candidate"]["full_name"].startswith("Секретное Имя") and page["candidate"]["contacts"]["phone"]
    assert [(m["author"], m["mine"]) for m in page["messages"]] == [("candidate", False)]
    client.post(f"/api/v1/contacts/{cid}/messages", json={"text": "Добрый день, созвонимся?"})
    views = db.scalars(select(AuditLog).where(AuditLog.action == "contact_view", AuditLog.object_id == cid)).all()
    assert len(views) == 1 and views[0].actor_id == s.employer.id
    kinds = set(db.scalars(select(Notification.kind).where(Notification.user_id == s.employer.id)))
    assert {"invitation_accepted", "message"} <= kinds


def test_revoke_hides_contacts_and_closes_chat(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    cid = s.invite(p.public_ref).json()["id"]
    as_user(client, db, p.user_id)
    client.post(f"/api/v1/candidate/invitations/{cid}/accept", json={"consent_contact_transfer": True})
    assert client.post(f"/api/v1/candidate/invitations/{cid}/revoke").json()["status"] == "revoked"
    consent = db.scalar(select(Consent).where(Consent.user_id == p.user_id, Consent.type == "contact_transfer"))
    assert consent.revoked_at is not None
    s.as_employer()
    page = client.get(f"/api/v1/contacts/{cid}").json()
    assert page["candidate"] is None and page["chat_open"] is False
    assert s.invite(p.public_ref).json()["code"] == "reinvite_too_early"


def test_blocked_company_gets_candidate_unavailable(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    as_user(client, db, p.user_id)
    assert client.put(f"/api/v1/candidate/blocks/{s.company.id}").status_code == 204
    assert client.get("/api/v1/candidate/blocks").json()[0]["name"] == "Корп"
    r = s.invite(p.public_ref)
    assert r.status_code == 409 and r.json()["code"] == "candidate_unavailable"
    as_user(client, db, p.user_id)
    client.delete(f"/api/v1/candidate/blocks/{s.company.id}")
    assert s.invite(p.public_ref).status_code == 201


def test_foreign_access_is_404(client, db, make_candidate):
    p, other = make_candidate(stack=STACK), make_candidate(stack=STACK)
    s = Scene(client, db)
    cid = s.invite(p.public_ref).json()["id"]
    as_user(client, db, other.user_id)
    assert client.get(f"/api/v1/candidate/invitations/{cid}").status_code == 404
    assert client.get(f"/api/v1/contacts/{cid}").status_code == 404
    Scene(client, db, email="hr@other.ru", company="Другая")
    assert client.post(f"/api/v1/employer/invitations/{cid}/withdraw").status_code == 404
