import json

from app.employers.need_parse import rules_draft
from app.llm.deps import get_llm
from tests.employers.helpers import employer
from tests.llm_fakes import fake_llm

VACANCY = """Вакансия: Python-разработчик в платёжную платформу
Ищем middle+ бэкенд-разработчика. Формат — удалёнка или гибрид, Москва.
Требования:
- Python, FastAPI, PostgreSQL, Docker
- опыт от 3 до 5 лет
Будет плюсом:
- Kafka, Redis
Условия:
- от 250 000 до 350 000 ₽ до вычета НДФЛ
- связь: hr@corp.example, +7 495 000-00-00
"""


def test_rules_draft_from_vacancy():
    d = rules_draft(VACANCY)
    assert d.title == "Python-разработчик в платёжную платформу" and d.specialization == "backend"
    assert d.grades == ["middle", "senior"] and d.formats == ["remote", "hybrid"] and d.city == "Москва"
    assert d.must == ["Python", "FastAPI", "PostgreSQL", "Docker"] and d.nice == ["Kafka", "Redis"]
    assert (d.salary_from, d.salary_to, d.gross_net) == (250_000, 350_000, "gross")


def test_parse_endpoint_without_llm_reports_missing(client, db):
    employer(client, db)
    assert client.post("/api/v1/employer/needs/parse", json={"text": VACANCY}).status_code == 409  # нет компании
    client.put("/api/v1/employer/company", json={"name": "Корп"})
    d = client.post("/api/v1/employer/needs/parse", json={"text": VACANCY}).json()
    assert d["source"] == "rules" and d["missing"] == []
    d = client.post("/api/v1/employer/needs/parse", json={"text": "Нужен человек в команду, пишите нам"}).json()
    assert set(d["missing"]) >= {"специализация", "целевые грейды", "вилка от"}


def test_parse_endpoint_with_llm_masks_contacts_and_normalizes(client, db):
    employer(client, db)
    client.put("/api/v1/employer/company", json={"name": "Корп"})
    llm, t = fake_llm(json.dumps({"title": "Бэкенд", "specialization": "backend", "grades": ["middle", "senior"],
                                  "must": ["python", "postgres", "Docker"], "nice": ["kafka", "очень редкая БД"],
                                  "formats": ["remote"], "salary_from": 250000, "salary_to": 350000,
                                  "gross_net": "gross"}))
    client.app.dependency_overrides[get_llm] = lambda: llm
    d = client.post("/api/v1/employer/needs/parse", json={"text": VACANCY}).json()
    assert d["source"] == "llm" and d["must"] == ["Python", "PostgreSQL", "Docker"] and d["nice"] == ["Kafka"]
    assert d["unknown_terms"] == ["очень редкая БД"] and d["city"] == "Москва"  # город дополнен правилами
    assert "hr@corp.example" not in t.sent_text() and "000-00-00" not in t.sent_text()


def test_llm_title_stuffed_with_fields_falls_back_to_rules(client, db):
    employer(client, db)
    client.put("/api/v1/employer/company", json={"name": "Корп"})
    stuffed = "Python-разработчик в платёжную платформу, специализация: backend, grades: middle, senior, salary: "
    llm, _ = fake_llm(json.dumps({"title": stuffed, "specialization": "backend", "must": ["python", "x" * 61]}))
    client.app.dependency_overrides[get_llm] = lambda: llm
    d = client.post("/api/v1/employer/needs/parse", json={"text": VACANCY}).json()
    assert d["source"] == "llm" and d["title"] == "Python-разработчик в платёжную платформу"
    assert d["must"] == ["Python"] and all(len(x) <= 60 for x in d["unknown_terms"])


def test_recruiter_name_masked_before_llm(client, db):
    employer(client, db)
    client.put("/api/v1/employer/company", json={"name": "Корп"})
    llm, t = fake_llm(json.dumps({"title": "Бэкенд"}))
    client.app.dependency_overrides[get_llm] = lambda: llm
    client.post("/api/v1/employer/needs/parse", json={"text": VACANCY + "Контакты: Мария Иванова, telegram @maria_hr\n"})
    assert "Мария" not in t.sent_text() and "Иванова" not in t.sent_text() and "@maria_hr" not in t.sent_text()
