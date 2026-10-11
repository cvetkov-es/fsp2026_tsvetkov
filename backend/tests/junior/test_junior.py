from datetime import date

from sqlalchemy import select

from app.auth.models import Consent, EmailToken, User
from app.common import clock
from app.employers.models import Need
from app.junior.service import age, hours_limit, is_minor
from tests.contacts.helpers import Scene, as_user
from tests.junior.helpers import give_consent, guardian_token, in_selection, minor

STACK = ("Python", "PostgreSQL")
TODAY = date(2026, 10, 9)


def test_age_is_exact_with_a_birth_date_and_conservative_with_a_year_only():
    u = User(email="a@x.ru", role="candidate", birth_date=date(2011, 10, 10))
    assert age(u, TODAY) == 14 and is_minor(u, TODAY)  # день рождения ещё не наступил
    assert age(User(email="b@x.ru", role="candidate", birth_date=date(2008, 10, 9)), TODAY) == 18
    assert not is_minor(User(email="b@x.ru", role="candidate", birth_date=date(2008, 10, 9)), TODAY)
    assert age(User(email="c@x.ru", role="candidate", birth_year=2010), TODAY) == 15  # младший из возможных
    assert age(User(email="d@x.ru", role="candidate"), TODAY) is None and not is_minor(User(email="d@x.ru", role="candidate"), TODAY)


def test_hours_limits():
    assert (hours_limit(15, "vacation"), hours_limit(15, "internship")) == (24, 12)
    assert (hours_limit(17, "vacation"), hours_limit(17, "internship")) == (35, 17)


def test_registration_keeps_the_exact_birth_date(client, db):
    body = {"email": "kid@example.ru", "password": "correct horse 1", "role": "candidate", "birth_date": "2011-03-05",
            "consents": {"processing": True, "distribution_preset": "standard"}}
    assert client.post("/api/v1/auth/register", json=body).status_code == 201
    u = db.scalar(select(User).where(User.email == "kid@example.ru"))
    assert u.birth_date == date(2011, 3, 5) and u.birth_year == 2011


def test_minor_hidden_until_guardian_consent(client, db, make_candidate):
    p = minor(db, make_candidate)
    s = Scene(client, db)
    db.get(Need, s.need_id).employment = "internship"
    db.commit()
    assert not in_selection(client, s.need_id, p.public_ref)
    give_consent(client, db, p)
    s.as_employer()
    assert in_selection(client, s.need_id, p.public_ref)


def test_minor_hidden_on_the_map_until_guardian_consent_then_marked(client, db, make_candidate):
    p = minor(db, make_candidate)
    s = Scene(client, db)
    assert client.get("/api/v1/employer/map/backend/middle").json()["items"] == []
    give_consent(client, db, p)
    s.as_employer()
    items = client.get("/api/v1/employer/map/backend/middle").json()["items"]
    assert [i["minor"] for i in items] == [True]


def test_minor_only_in_internship_and_vacation(client, db, make_candidate):
    p = minor(db, make_candidate)
    give_consent(client, db, p)
    s = Scene(client, db)  # потребность по умолчанию — полная занятость
    assert not in_selection(client, s.need_id, p.public_ref)
    adult = make_candidate(stack=STACK)
    s.as_employer()
    assert in_selection(client, s.need_id, adult.public_ref)  # взрослых правило не касается


def test_minor_invite_needs_hours_within_limit(client, db, make_candidate):
    p = minor(db, make_candidate, years=15)
    give_consent(client, db, p)
    s = Scene(client, db)
    db.get(Need, s.need_id).employment = "vacation"
    db.commit()
    s.as_employer()
    draft = client.get(f"/api/v1/employer/needs/{s.need_id}/invitations/draft?ref={p.public_ref}").json()
    assert draft["minor_hours_limit"] == 24
    assert s.invite(p.public_ref).json()["code"] == "hours_required"
    assert s.invite(p.public_ref, hours_per_week=30).json()["code"] == "hours_over_limit"
    r = s.invite(p.public_ref, hours_per_week=20)
    assert r.status_code == 201
    as_user(client, db, p.user_id)
    assert client.get("/api/v1/candidate/invitations").json()[0]["hours_per_week"] == 20
    s.as_employer()
    assert client.get(f"/api/v1/employer/needs/{s.need_id}/invitations").json()[0]["hours_per_week"] == 20


def test_an_adult_invite_does_not_ask_for_hours(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    s = Scene(client, db)
    draft = client.get(f"/api/v1/employer/needs/{s.need_id}/invitations/draft?ref={p.public_ref}").json()
    assert draft["minor_hours_limit"] is None
    assert s.invite(p.public_ref).status_code == 201


def test_need_employment_is_validated_and_returned(client, db):
    s = Scene(client, db, trust_level="L2")  # у L0 лимит потребностей уже выбран сценой
    from tests.employers.helpers import NEED

    ok = client.post("/api/v1/employer/needs", json={**NEED, "employment": "internship"})
    assert ok.status_code == 201 and ok.json()["employment"] == "internship"
    assert client.post("/api/v1/employer/needs", json={**NEED, "employment": "moon"}).status_code == 422
    assert client.get(f"/api/v1/employer/needs/{s.need_id}").json()["employment"] == "full"


def test_guardian_flow_text_token_and_single_use(client, db, make_candidate):
    p = minor(db, make_candidate)
    token = guardian_token(client, db, p)
    page = client.get(f"/api/v1/guardian/{token}").json()
    assert page["title"].startswith("Согласие законного представителя") and "@" in page["candidate_email"]
    assert page["candidate_email"] != db.get(User, p.user_id).email  # почта кандидата маскирована
    assert client.post(f"/api/v1/guardian/{token}", json={"accept": False, "guardian_name": "Анна Иванова"}).status_code == 422
    assert client.post(f"/api/v1/guardian/{token}", json={"accept": True, "guardian_name": "Анна Иванова"}).status_code == 200
    consent = db.scalar(select(Consent).where(Consent.user_id == p.user_id, Consent.type == "guardian"))
    assert consent.scope == {"guardian_email": "mama@example.ru", "guardian_name": "Анна Иванова"}
    again = client.post(f"/api/v1/guardian/{token}", json={"accept": True, "guardian_name": "Анна Иванова"})
    assert again.status_code == 400 and again.json()["code"] == "token_invalid"
    assert client.get(f"/api/v1/guardian/{token}").json()["code"] == "token_invalid"
    assert client.get("/api/v1/guardian/not-a-token").status_code == 400


def test_guardian_token_expires(client, db, make_candidate, frozen_now):
    from datetime import timedelta

    t0 = clock.now()
    frozen_now(t0)
    p = minor(db, make_candidate)
    token = guardian_token(client, db, p)
    frozen_now(t0 + timedelta(days=8))
    assert client.post(f"/api/v1/guardian/{token}", json={"accept": True, "guardian_name": "Анна Иванова"}).json()["code"] == "token_invalid"
    assert db.scalar(select(EmailToken).where(EmailToken.purpose == "guardian")).used_at is None


def test_a_new_guardian_link_is_not_issued_more_often_than_every_few_minutes(client, db, make_candidate, frozen_now):
    from datetime import timedelta

    from app.config.params import PARAMS

    t0 = clock.now()
    frozen_now(t0)
    p = minor(db, make_candidate)
    as_user(client, db, p.user_id)
    assert client.post("/api/v1/candidate/junior/guardian", json={"email": "mama@example.ru"}).status_code == 201
    r = client.post("/api/v1/candidate/junior/guardian", json={"email": "spam@example.ru"})
    assert r.status_code == 429 and r.json()["code"] == "guardian_link_recent"
    frozen_now(t0 + timedelta(minutes=PARAMS.guardian_resend_minutes, seconds=1))
    as_user(client, db, p.user_id)
    assert client.post("/api/v1/candidate/junior/guardian", json={"email": "mama@example.ru"}).status_code == 201


def test_adult_cannot_ask_for_a_guardian(client, db, make_candidate):
    p = make_candidate(stack=STACK)
    as_user(client, db, p.user_id)
    r = client.post("/api/v1/candidate/junior/guardian", json={"email": "mama@example.ru"})
    assert r.status_code == 409 and r.json()["code"] == "not_minor"


def test_junior_state_for_the_cabinet(client, db, make_candidate):
    adult = make_candidate(stack=STACK)
    as_user(client, db, adult.user_id)
    assert client.get("/api/v1/candidate/junior").json() == {
        "minor": False, "age": None, "status": "adult", "guardian_email": None, "hours_limit_vacation": None, "hours_limit_school": None}
    p = minor(db, make_candidate, years=15)
    as_user(client, db, p.user_id)
    st = client.get("/api/v1/candidate/junior").json()
    assert st["minor"] and st["age"] == 15 and st["status"] == "draft" and st["hours_limit_vacation"] == 24 and st["hours_limit_school"] == 12
    give_consent(client, db, p)
    as_user(client, db, p.user_id)
    st = client.get("/api/v1/candidate/junior").json()
    assert st["status"] == "active" and st["guardian_email"] == "mama@example.ru"
