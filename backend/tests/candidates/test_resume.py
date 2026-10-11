import json
from datetime import date

from app.candidates.resume.rules import draft_fields, experience_years
from app.llm.deps import get_llm
from tests.candidates.test_profile import login
from tests.llm.samples import NAMES, PII, SAMPLES
from tests.llm_fakes import fake_llm
from tests.pdf_factory import make_pdf

URL = "/api/v1/candidate/profile/resume"


def upload(client, data: bytes, name="cv.pdf"):
    return client.post(URL, files={"file": (name, data, "application/pdf")})


def test_experience_from_total_and_intervals():
    today = date(2026, 10, 8)
    assert experience_years(SAMPLES["hh"], today) == 4.2  # строка «Опыт работы — 4 года 2 месяца»
    # 2019–2021 (36 мес.) и 01.2022–09.2026 (57 мес.) идут встык: 93 мес. = 7.75 года
    assert experience_years(SAMPLES["front"], today) == 7.8
    # пересекающиеся интервалы не суммируются дважды: март 2020 — июнь 2021 = 16 мес.
    assert experience_years("Март 2020 — Февраль 2021, Январь 2021 — Июнь 2021", today) == 1.3
    assert experience_years("без дат", today) is None


def test_rules_draft_fields():
    f = draft_fields(SAMPLES["hh"])
    assert f["specialization"] == "backend" and f["recommended_grade"] == "middle"
    assert {"Python", "FastAPI", "PostgreSQL", "Docker", "Kafka", "GitLab CI"} <= set(f["stack"])
    assert f["formats"] == ["remote"] and f["city"] == "Казань"
    front = draft_fields(SAMPLES["front"])
    assert front["specialization"] == "frontend" and front["recommended_grade"] == "senior"
    assert front["city"] == "Санкт-Петербург" and set(front["formats"]) == {"hybrid", "office"}


def test_upload_without_llm_builds_rules_draft(client, db):
    login(client, db)
    r = upload(client, make_pdf(SAMPLES["hh"]))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["source"] == "rules" and d["specialization"] == "backend" and "PostgreSQL" in d["stack"]
    assert d["full_name"] == "Петров Иван Сергеевич"
    assert d["contacts"]["email"] == "ivan.petrov@example.ru" and d["contacts"]["telegram"] == "@ivan_petrov_dev"


def test_upload_with_llm_sends_only_masked_text(client, db, monkeypatch):
    from types import SimpleNamespace

    from app.llm import names

    # NER включён: в тестах он выключен (conftest), а LLM-разбор требует полного маскирования
    monkeypatch.setattr(names, "get_settings", lambda: SimpleNamespace(ner_enabled=True))
    monkeypatch.setattr(names, "natasha_names", lambda text: [])
    login(client, db)
    llm, t = fake_llm(json.dumps({"specialization": "backend", "recommended_grade": "middle", "experience_years": 4,
                                  "stack": ["Python", "Kubernetes", "квантовый блокчейн"], "domains": ["финтех"],
                                  "formats": ["remote"], "city": "Казань"}))
    client.app.dependency_overrides[get_llm] = lambda: llm
    d = upload(client, make_pdf(SAMPLES["hh"])).json()
    assert d["source"] == "llm" and d["domains"] == ["финтех"] and d["unknown_terms"] == ["квантовый блокчейн"]
    assert "Kubernetes" in d["stack"] and d["experience_years"] == 4.2  # стаж по датам надёжнее
    sent = t.sent_text()
    for value in PII["hh"]:
        assert value not in sent, f"в LLM ушло «{value}»"
    assert "[ИМЯ]" in sent and NAMES["hh"][0] not in sent


def test_upload_errors(client, db):
    login(client, db)
    assert upload(client, b"not a pdf").json()["code"] == "resume_not_pdf"
    assert upload(client, make_pdf("стр", pages=6)).json()["code"] == "resume_pages"
    assert upload(client, make_pdf("секрет", password="x")).json()["code"] == "resume_encrypted"
    big = b"%PDF" + b"0" * (5 * 1024 * 1024 + 10)
    r = upload(client, big)
    assert r.status_code == 413 and r.json()["code"] == "resume_too_large"


def test_scan_like_pdf_warns(client, db):
    login(client, db)
    d = upload(client, make_pdf("Скан", pages=2)).json()
    assert d["warnings"] and "скан" in d["warnings"][0]


def test_ner_failure_keeps_resume_away_from_llm(client, db, monkeypatch):
    from types import SimpleNamespace

    from app.llm import names

    monkeypatch.setattr(names, "get_settings", lambda: SimpleNamespace(ner_enabled=True))
    monkeypatch.setattr(names, "natasha_names", lambda text: None)
    login(client, db)
    llm, t = fake_llm(json.dumps({"stack": ["Python"]}))
    client.app.dependency_overrides[get_llm] = lambda: llm
    d = upload(client, make_pdf(SAMPLES["data"])).json()
    assert d["source"] == "rules" and t.calls == []  # маскирование неполное — в LLM не отправляем


def test_ner_disabled_keeps_resume_away_from_llm(client, db, monkeypatch):
    from types import SimpleNamespace

    from app.llm import names

    monkeypatch.setattr(names, "get_settings", lambda: SimpleNamespace(ner_enabled=False))
    login(client, db)
    llm, t = fake_llm(json.dumps({"stack": ["Python"]}))
    client.app.dependency_overrides[get_llm] = lambda: llm
    d = upload(client, make_pdf(SAMPLES["hh"])).json()
    assert d["source"] == "rules" and t.calls == []  # без NER гарантий по ФИО из тела резюме нет


def test_pdf_worker_crash_is_a_server_error(monkeypatch, caplog):
    import subprocess

    import pytest

    from app.candidates.resume import extract
    from app.common.errors import AppError

    monkeypatch.setattr(extract.subprocess, "run",
                        lambda *a, **kw: subprocess.CompletedProcess(a, -9, stdout=b"", stderr=b"Killed"))
    with pytest.raises(AppError) as e:
        extract.extract_text(make_pdf("текст"))
    assert e.value.status == 503 and e.value.code == "resume_unavailable" and "Killed" in caplog.text


def test_pdf_worker_runs_with_memory_limit(monkeypatch):
    import subprocess

    from app.candidates.resume import extract

    seen = {}

    def run(*a, **kw):
        seen["preexec"] = kw.get("preexec_fn")
        return subprocess.CompletedProcess(a, 0, stdout=b'{"text": "x", "pages": 1}', stderr=b"")

    monkeypatch.setattr(extract.subprocess, "run", run)
    assert extract.extract_text(make_pdf("x")) == ("x", 1) and seen["preexec"] is not None


def test_overlong_llm_list_items_are_dropped(client, db, monkeypatch):
    from types import SimpleNamespace

    from app.llm import names

    monkeypatch.setattr(names, "get_settings", lambda: SimpleNamespace(ner_enabled=True))
    monkeypatch.setattr(names, "natasha_names", lambda text: [])
    login(client, db)
    llm, _ = fake_llm(json.dumps({"stack": ["Python", "я" * 61], "domains": ["финтех", "д" * 41]}))
    client.app.dependency_overrides[get_llm] = lambda: llm
    d = upload(client, make_pdf(SAMPLES["hh"])).json()
    assert d["source"] == "llm" and d["domains"] == ["финтех"] and all(len(x) <= 60 for x in d["unknown_terms"])
