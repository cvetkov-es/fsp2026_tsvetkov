from app.candidates.models import CandidateProfile
from tests.candidates.test_profile import login
from tests.pdf_factory import pdf_text


def test_own_pdf_has_name_contacts_and_threshold(client, db):
    u = login(client, db)
    client.put("/api/v1/candidate/profile/survey", json={"specialization": "backend", "claimed_grade": "middle"})
    client.put("/api/v1/candidate/profile/details", json={
        "full_name": "Иван Петров", "contacts": {"telegram": "@ivan"}, "formats": ["remote"], "city": "Казань",
        "salary_threshold": 250000, "salary_gross_net": "net"})
    client.put("/api/v1/candidate/profile/stack", json={"techs": ["Python", "Docker"]})
    p = db.get(CandidateProfile, u.id)
    p.grade_status, p.confirmed_grade = "confirmed", "middle"
    db.commit()
    r = client.get("/api/v1/candidate/profile/pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    text = pdf_text(r.content)
    for s in ("Иван Петров", "@ivan", "Backend · Middle · подтверждён тестом", "Python", "Казань", "250 000",
              "Истории ФСП нет"):
        assert s in text, s


def test_pdf_shows_skill_titles_and_moscow_dates(client, db, frozen_now):
    from datetime import UTC, datetime

    from app.candidates.models import SkillResult

    frozen_now(datetime(2026, 10, 8, 22, 30, tzinfo=UTC))  # в Москве уже 9 октября
    u = login(client, db)
    client.put("/api/v1/candidate/profile/survey", json={"specialization": "backend", "claimed_grade": "middle"})
    db.add(SkillResult(user_id=u.id, skill_code="ai", passed=True))
    db.commit()
    text = pdf_text(client.get("/api/v1/candidate/profile/pdf").content)
    assert "Работа с ИИ" in text and "09.10.2026" in text
