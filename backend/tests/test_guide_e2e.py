"""Гид для жюри из 6 шагов на уровне API (процесс 10, спецификация 5.6) — без ключа LLM.

Шаг 1 — вход по email (FSP ID появится в плане 07a), экспресс-тест — на учебном банке из тестов плана 03.
"""
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select

from app.auth.models import User
from app.candidates.models import CandidateProfile
from app.demo.seed import STRONG, WEAK, seed_all
from tests.assessment_api.conftest import toy_bank  # noqa: F401 — фикстура плана 03
from tests.assessment_api.helpers import answer_current

EMAIL, PASSWORD = "jury@example.ru", "jury-password-1"
VACANCY = """Бэкенд-разработчик в платёжную платформу
Ищем middle или senior. Требования: Python, PostgreSQL, Docker. Будет плюсом: Kafka.
Формат — удалёнка. Вилка от 250 000 до 350 000 ₽ до вычета НДФЛ."""


def login_candidate(client):
    assert client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 200


@pytest.mark.usefixtures("toy_bank")
def test_six_step_guide_without_llm(client, db):
    # 1. Регистрация с согласиями, подтверждение почты, вход
    r = client.post("/api/v1/auth/register", json={
        "email": EMAIL, "password": PASSWORD, "role": "candidate", "birth_date": "2000-05-01",
        "consents": {"processing": True, "distribution_preset": "standard"}})
    token = parse_qs(urlparse(r.json()["verify_url"]).query)["token"][0]
    assert client.post("/api/v1/auth/verify", json={"token": token}).status_code == 204
    login_candidate(client)
    # 2. Опрос и заявленный грейд; стек и условия профиля
    client.put("/api/v1/candidate/profile/survey", json={"specialization": "backend", "claimed_grade": "middle"})
    client.put("/api/v1/candidate/profile/stack", json={"techs": ["Python", "PostgreSQL", "Docker"]})
    client.put("/api/v1/candidate/profile/details", json={
        "full_name": "Юрий Жюри", "contacts": {"telegram": "@jury"}, "formats": ["remote"],
        "salary_threshold": 220000, "salary_gross_net": "net"})
    client.post("/api/v1/candidate/profile/open-window")
    # 3. Экспресс-тест → категория
    aid = client.post("/api/v1/candidate/attempts", json={"target_grade": "middle", "express": True,
                                                          "accept_rules": True, "pledge": True}).json()["id"]
    state = {"stage": "phase1"}
    for _ in range(20):
        state = answer_current(client, db, aid, True)
        if state["stage"] == "finished":
            break
    assert state["stage"] == "finished" and state["result"]["decision"] == "confirmed"
    me = db.scalar(select(User).where(User.email == EMAIL))
    profile = db.get(CandidateProfile, me.id)
    db.refresh(profile)
    assert profile.grade_status == "confirmed" and profile.confirmed_grade == "middle"
    # 4. Демо-работодатель → потребность из текста вакансии (без LLM — правила)
    seed_all(db, n_per_cell=2)
    personas = client.get("/api/v1/demo/personas").json()
    emp_id = next(p["id"] for p in personas if p["role"] == "employer")
    assert client.post("/api/v1/demo/login-as", json={"user_id": emp_id}).status_code == 200
    draft = client.post("/api/v1/employer/needs/parse", json={"text": VACANCY}).json()
    assert draft["source"] == "rules" and draft["missing"] == []
    body = {k: draft[k] for k in ("title", "specialization", "grades", "must", "nice", "formats", "city",
                                  "salary_from", "salary_to", "gross_net")}
    need_id = client.post("/api/v1/employer/needs", json={**body, "contact_method": "chat"}).json()["id"]
    # 5. Карта → подборка: сильный тест без ФСП выше слабого теста с ФСП
    cells = client.get("/api/v1/employer/map").json()["cells"]
    assert any(c["specialization"] == "backend" and c["confirmed"] > 0 for c in cells)
    sel = client.get(f"/api/v1/employer/needs/{need_id}/selection").json()
    order = [i["ref"] for b in sel["blocks"] for i in b["items"]]
    refs = {p.full_name: p.public_ref for p in db.scalars(
        select(CandidateProfile).where(CandidateProfile.full_name.in_((STRONG, WEAK, "Юрий Жюри"))))}
    assert order.index(refs[STRONG]) < order.index(refs[WEAK]) and refs["Юрий Жюри"] in order
    # 6. Приглашение → кандидат принимает → контакты и чат
    ref = refs["Юрий Жюри"]
    inv = client.get(f"/api/v1/employer/needs/{need_id}/invitations/draft", params={"ref": ref}).json()
    payload = {k: inv[k] for k in ("salary_from", "salary_to", "gross_net", "description", "why_you", "next_step",
                                   "contact_method")}
    cid = client.post(f"/api/v1/employer/needs/{need_id}/invitations", json={**payload, "ref": ref}).json()["id"]
    login_candidate(client)
    assert client.get("/api/v1/notifications").json()["unread"] >= 1
    assert client.post(f"/api/v1/candidate/invitations/{cid}/accept",
                       json={"consent_contact_transfer": True}).json()["status"] == "accepted"
    client.post(f"/api/v1/contacts/{cid}/messages", json={"text": "Здравствуйте! Готов созвониться."})
    client.post("/api/v1/demo/login-as", json={"user_id": emp_id})
    page = client.get(f"/api/v1/contacts/{cid}").json()
    assert page["candidate"]["full_name"] == "Юрий Жюри" and page["candidate"]["email"] == EMAIL
    assert page["messages"][0]["text"].startswith("Здравствуйте")
