import json

from app.llm.deps import get_llm
from app.matching.summary import fact_check
from tests.employers.helpers import NEED, employer
from tests.llm_fakes import fake_llm

FACTS = {"грейд": "Middle подтверждён тестом · сильнее 82% категории", "стек": "Стек: Python ✓, PostgreSQL (заявлено)",
         "ФСП": "Истории ФСП нет, навыки оценены по тесту", "чего не хватает": ["PostgreSQL: заявлено, не подтверждено"],
         "готовность": "вилка покрывает ожидания · окно поиска открыто до 20.10"}


def test_fact_check():
    assert fact_check("Кандидат с подтверждённым Middle сильнее 82% категории, Python подтверждён.", FACTS)
    assert not fact_check("Кандидат с опытом 5 лет на Python.", FACTS)  # числа 5 нет в фактах
    assert not fact_check("Кандидат знает Python и Kafka.", FACTS)  # Kafka нет в фактах
    assert not fact_check("Кандидат [ИМЯ] подходит.", FACTS)


def setup(client, db, make_candidate) -> tuple[str, str]:
    """URL сводки для двух кандидатов одной потребности."""
    a, b = make_candidate(stack=("Python", "PostgreSQL")), make_candidate(stack=("Python",))
    employer(client, db)
    client.put("/api/v1/employer/company", json={"name": "Корп"})
    nid = client.post("/api/v1/employer/needs", json=NEED).json()["id"]
    return tuple(f"/api/v1/employer/needs/{nid}/candidates/{p.public_ref}/summary" for p in (a, b))


def test_summary_template_without_llm(client, db, make_candidate):
    url, _ = setup(client, db, make_candidate)
    r = client.get(url).json()
    assert r["source"] == "template" and r["text"].startswith("Middle подтверждён тестом")


def test_summary_llm_cached_and_rejected_when_inventing(client, db, make_candidate):
    url, url2 = setup(client, db, make_candidate)
    llm, t = fake_llm(json.dumps({"text": "Кандидат с подтверждённым Middle, Python подтверждён тестом."}))
    client.app.dependency_overrides[get_llm] = lambda: llm
    first, second = client.get(url).json(), client.get(url).json()
    assert first == second == {"text": "Кандидат с подтверждённым Middle, Python подтверждён тестом.", "source": "llm"}
    assert len(t.calls) == 1  # второй раз — из кэша
    llm2, _ = fake_llm(json.dumps({"text": "Кандидат с 7 годами опыта в Kafka."}))
    client.app.dependency_overrides[get_llm] = lambda: llm2
    assert client.get(url2).json()["source"] == "template"


def test_summary_unknown_candidate_404(client, db, make_candidate):
    url, _ = setup(client, db, make_candidate)
    assert client.get(url.rsplit("/", 2)[0] + "/nope/summary").status_code == 404


def test_fact_check_rejects_a_different_grade():
    assert not fact_check("Кандидат уровня Senior, Python подтверждён.", FACTS)
    assert not fact_check("Кандидат — сеньор, Python подтверждён.", FACTS)


def test_summary_cache_survives_race_and_keeps_one_row(client, db, make_candidate, monkeypatch):
    from sqlalchemy import func, select

    from app.matching import summary as summary_mod
    from app.matching.models import ExplanationCache

    url, _ = setup(client, db, make_candidate)
    text = "Кандидат с подтверждённым Middle, Python подтверждён тестом."
    llm, _ = fake_llm(json.dumps({"text": text}), json.dumps({"text": text}))
    client.app.dependency_overrides[get_llm] = lambda: llm
    assert client.get(url).json()["source"] == "llm"
    row = db.scalar(select(ExplanationCache))
    db.add(ExplanationCache(need_id=row.need_id, user_id=row.user_id, facts_hash="устаревшие факты",
                            template_text="t", llm_text="старый текст", model="m"))
    db.commit()
    # параллельный запрос не увидел запись в кэше и тоже вызывает LLM
    monkeypatch.setattr(summary_mod, "_cached", lambda *a: None)
    assert client.get(url).json() == {"text": text, "source": "llm"}
    assert db.scalar(select(func.count()).select_from(ExplanationCache)) == 1  # устаревшая запись удалена
