from sqlalchemy import select

from app.auth.models import Consent, Role, User
from app.common import clock
from tests.contacts.helpers import Scene, as_user
from tests.hiring.helpers import accept as accept_invitation

STACK = ("Python", "PostgreSQL")
APPLY = {"consent_contact_transfer": True, "message": "Интересна платёжная платформа"}


def published(client, db, **scene):
    s = Scene(client, db, **scene)
    r = client.post(f"/api/v1/employer/needs/{s.need_id}/vacancy", json={"description": "Платёжная платформа"})
    assert r.status_code == 201, r.text
    return s, r.json()["id"]


def test_publish_once_with_salary_from_need(client, db):
    s, vid = published(client, db)
    assert client.post(f"/api/v1/employer/needs/{s.need_id}/vacancy", json={"description": "Ещё одно описание"}).json()["code"] == "vacancy_exists"
    v = client.get("/api/v1/employer/vacancies").json()[0]
    assert v["id"] == vid and v["salary_from"] > 0 and v["gross_net"] in ("gross", "net")


def test_apply_requires_consent_and_once(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s, vid = published(client, db)
    as_user(client, db, p.user_id)
    lst = client.get("/api/v1/candidate/vacancies").json()
    assert lst[0]["id"] == vid and lst[0]["company"]["name"] == "Корп" and lst[0]["my_application"] is None
    r = client.post(f"/api/v1/candidate/vacancies/{vid}/apply", json={**APPLY, "consent_contact_transfer": False})
    assert r.status_code == 422 and r.json()["code"] == "consent_required"
    assert client.post(f"/api/v1/candidate/vacancies/{vid}/apply", json=APPLY).status_code == 201
    assert client.post(f"/api/v1/candidate/vacancies/{vid}/apply", json=APPLY).json()["code"] == "already_applied"
    consent = db.scalar(select(Consent).where(Consent.user_id == p.user_id, Consent.type == "contact_transfer"))
    assert consent.target_company_id == s.company.id
    assert client.get("/api/v1/candidate/applications").json()[0]["status"] == "sent"


def test_accepted_application_opens_chat_and_board(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s, vid = published(client, db, trust_level="L2")
    as_user(client, db, p.user_id)
    client.post(f"/api/v1/candidate/vacancies/{vid}/apply", json=APPLY)
    s.as_employer()
    apps = client.get(f"/api/v1/employer/vacancies/{vid}/applications").json()
    assert apps[0]["alias"].startswith("B-M-") and "Секретное Имя" not in str(apps)
    as_user(client, db, p.user_id)
    assert client.get("/api/v1/candidate/applications").json()[0]["status"] == "viewed"
    s.as_employer()
    cid = client.post(f"/api/v1/employer/applications/{apps[0]['id']}/accept").json()["contact_id"]
    page = client.get(f"/api/v1/contacts/{cid}").json()
    assert page["chat_open"] and page["candidate"]["full_name"].startswith("Секретное Имя")
    board = client.get(f"/api/v1/employer/needs/{s.need_id}/board").json()
    assert [c["contact_id"] for c in board["cards"]] == [cid]


def test_decline_and_revoked_consent(client, db, make_candidate):
    p1, p2 = make_candidate(stack=STACK), make_candidate(stack=STACK)
    s, vid = published(client, db)
    for p in (p1, p2):
        as_user(client, db, p.user_id)
        client.post(f"/api/v1/candidate/vacancies/{vid}/apply", json=APPLY)
    s.as_employer()
    apps = {a["ref"]: a["id"] for a in client.get(f"/api/v1/employer/vacancies/{vid}/applications").json()}
    assert client.post(f"/api/v1/employer/applications/{apps[p1.public_ref]}/decline", json={"reason": "stack"}).json()["status"] == "declined"
    # API отзыва согласия №4 до принятия контакта нет — отзыв ставим в БД, как это сделал бы кандидат
    consent = db.scalar(select(Consent).where(Consent.user_id == p2.user_id, Consent.type == "contact_transfer"))
    consent.revoked_at = clock.now()
    db.commit()
    assert client.post(f"/api/v1/employer/applications/{apps[p2.public_ref]}/accept").json()["code"] == "consent_revoked"


def test_apply_refuses_a_pair_that_already_has_an_invitation(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s, vid = published(client, db, trust_level="L2")
    cid = s.invite(p.public_ref).json()["id"]
    as_user(client, db, p.user_id)
    assert client.post(f"/api/v1/candidate/vacancies/{vid}/apply", json=APPLY).json()["code"] == "invite_exists"
    accept_invitation(client, db, p.user_id, cid)
    assert client.post(f"/api/v1/candidate/vacancies/{vid}/apply", json=APPLY).json()["code"] == "already_in_contact"


def test_accept_does_not_duplicate_a_contact_created_meanwhile(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s, vid = published(client, db, trust_level="L2")
    as_user(client, db, p.user_id)
    client.post(f"/api/v1/candidate/vacancies/{vid}/apply", json=APPLY)
    s.as_employer()
    aid = client.get(f"/api/v1/employer/vacancies/{vid}/applications").json()[0]["id"]
    cid = s.invite(p.public_ref).json()["id"]  # компания пригласила, пока отклик ждал
    assert client.post(f"/api/v1/employer/applications/{aid}/accept").json()["code"] == "invite_exists"
    accept_invitation(client, db, p.user_id, cid)
    s.as_employer()
    assert client.post(f"/api/v1/employer/applications/{aid}/accept").json()["code"] == "already_in_contact"
    board = client.get(f"/api/v1/employer/needs/{s.need_id}/board").json()
    assert [c["contact_id"] for c in board["cards"]] == [cid]  # кандидат на доске один раз


def test_accept_refused_after_the_candidate_hid_the_company(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s, vid = published(client, db)
    as_user(client, db, p.user_id)
    client.post(f"/api/v1/candidate/vacancies/{vid}/apply", json=APPLY)
    client.put(f"/api/v1/candidate/blocks/{s.company.id}")  # «Не показывать эту компанию» после отклика
    s.as_employer()
    aid = client.get(f"/api/v1/employer/vacancies/{vid}/applications").json()[0]["id"]
    assert client.post(f"/api/v1/employer/applications/{aid}/accept").json()["code"] == "candidate_unavailable"


def test_candidate_without_a_profile_can_apply(client, db):
    u = User(email="noprofile@x.ru", role=Role.candidate, password_hash="x", email_verified_at=clock.now())
    db.add(u)
    db.commit()
    s, vid = published(client, db)
    as_user(client, db, u.id)
    assert client.post(f"/api/v1/candidate/vacancies/{vid}/apply", json=APPLY).status_code == 201
    s.as_employer()
    assert client.get(f"/api/v1/employer/vacancies/{vid}/applications").status_code == 200
