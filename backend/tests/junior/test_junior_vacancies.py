"""Вакансии и отклики (07b2) и юниорский трек (07b3): отклик — не обход правил для несовершеннолетних."""
from sqlalchemy import select

from app.contacts.models import Contact
from app.employers.models import Need
from tests.contacts.helpers import Scene, as_user
from tests.junior.helpers import give_consent, minor

APPLY = {"consent_contact_transfer": True, "message": "Хочу на стажировку"}


def vacancy_of(client, db, employment="full", **scene):
    s = Scene(client, db, **scene)
    db.get(Need, s.need_id).employment = employment
    db.commit()
    r = client.post(f"/api/v1/employer/needs/{s.need_id}/vacancy", json={"description": "Описание вакансии для проверки"})
    assert r.status_code == 201, r.text
    return s, r.json()["id"]


def test_minor_without_guardian_consent_cannot_apply_and_sees_no_vacancies(client, db, make_candidate):
    p = minor(db, make_candidate)
    s, vid = vacancy_of(client, db, employment="internship")
    as_user(client, db, p.user_id)
    assert client.get("/api/v1/candidate/vacancies").json() == []  # профиль — черновик
    r = client.post(f"/api/v1/candidate/vacancies/{vid}/apply", json=APPLY)
    assert r.status_code == 409 and r.json()["code"] == "guardian_consent_required"


def test_minor_sees_only_internship_and_vacation_vacancies_and_cannot_apply_to_full(client, db, make_candidate):
    p = minor(db, make_candidate)
    full_s, full_vid = vacancy_of(client, db, employment="full", email="hr1@corp.ru", company="Полная")
    intern_s, intern_vid = vacancy_of(client, db, employment="internship", email="hr2@corp.ru", company="Стажировки")
    give_consent(client, db, p)
    as_user(client, db, p.user_id)
    assert [v["id"] for v in client.get("/api/v1/candidate/vacancies").json()] == [intern_vid]
    r = client.post(f"/api/v1/candidate/vacancies/{full_vid}/apply", json=APPLY)
    assert r.status_code == 409 and r.json()["code"] == "minor_full_employment"
    assert client.post(f"/api/v1/candidate/vacancies/{intern_vid}/apply", json=APPLY).status_code == 201


def test_adult_sees_every_vacancy(client, db, make_candidate):
    p = make_candidate(stack=("Python",))
    vacancy_of(client, db, employment="full", email="hr1@corp.ru", company="Полная")
    vacancy_of(client, db, employment="internship", email="hr2@corp.ru", company="Стажировки")
    as_user(client, db, p.user_id)
    assert len(client.get("/api/v1/candidate/vacancies").json()) == 2


def test_accepting_a_minors_application_needs_hours_within_the_limit(client, db, make_candidate):
    p = minor(db, make_candidate, years=15)
    s, vid = vacancy_of(client, db, employment="vacation", trust_level="L2")
    give_consent(client, db, p)
    as_user(client, db, p.user_id)
    client.post(f"/api/v1/candidate/vacancies/{vid}/apply", json=APPLY)
    s.as_employer()
    app = client.get(f"/api/v1/employer/vacancies/{vid}/applications").json()[0]
    assert app["minor_hours_limit"] == 24
    url = f"/api/v1/employer/applications/{app['id']}/accept"
    assert client.post(url).json()["code"] == "hours_required"
    assert client.post(url, json={"hours_per_week": 30}).json()["code"] == "hours_over_limit"
    cid = client.post(url, json={"hours_per_week": 20}).json()["contact_id"]
    assert db.scalar(select(Contact.hours_per_week).where(Contact.id == cid)) == 20


def test_accept_is_refused_if_the_guardian_consent_disappeared(client, db, make_candidate):
    p = minor(db, make_candidate)
    s, vid = vacancy_of(client, db, employment="internship")
    give_consent(client, db, p)
    as_user(client, db, p.user_id)
    client.post(f"/api/v1/candidate/vacancies/{vid}/apply", json=APPLY)
    db.refresh(p)
    p.guardian_consent_at = None  # согласие снято: профиль снова черновик
    db.commit()
    s.as_employer()
    aid = client.get(f"/api/v1/employer/vacancies/{vid}/applications").json()[0]["id"]
    assert client.post(f"/api/v1/employer/applications/{aid}/accept").json()["code"] == "guardian_consent_required"


def test_an_adult_application_is_accepted_without_hours(client, db, make_candidate):
    p = make_candidate(stack=("Python",))
    s, vid = vacancy_of(client, db, employment="full")
    as_user(client, db, p.user_id)
    client.post(f"/api/v1/candidate/vacancies/{vid}/apply", json=APPLY)
    s.as_employer()
    app = client.get(f"/api/v1/employer/vacancies/{vid}/applications").json()[0]
    assert app["minor_hours_limit"] is None
    assert client.post(f"/api/v1/employer/applications/{app['id']}/accept").status_code == 200
