import pytest

from app.llm.masking import contacts_from, inn_ok, mask, snils_ok
from app.llm.names import heuristic_names, natasha_names
from tests.llm.samples import NAMES, PII, SAMPLES


def test_checksums():
    assert inn_ok("500100732259") and inn_ok("7707083893") and not inn_ok("500100732250")
    assert snils_ok("11223344595") and not snils_ok("11223344500")


@pytest.mark.parametrize("key", SAMPLES)
def test_no_pii_left_and_tech_kept(key):
    m = mask(SAMPLES[key], NAMES[key])
    for value in PII[key]:
        assert value not in m.text, f"{key}: осталось «{value}»"
    assert "[EMAIL]" in m.text and "[ТЕЛЕФОН]" in m.text and "[ИМЯ]" in m.text
    assert "Python" in m.text or "React" in m.text


def test_salary_and_years_not_masked():
    m = mask("Ожидания от 250 000 руб., опыт 2019–2024, 4 года")
    assert m.text == "Ожидания от 250 000 руб., опыт 2019–2024, 4 года" and m.found == {}


def test_long_number_without_checksum_is_masked():
    # Паспорт под контрольную сумму ИНН/СНИЛС не подходит, но это такой же идентификатор
    m = mask("Паспорт 45 10 123456, выдан отделом")
    assert "45 10 123456" not in m.text and "[НОМЕР]" in m.text


def test_contacts_from_found():
    c = contacts_from(mask(SAMPLES["hh"]).found)
    assert c["email"] == "ivan.petrov@example.ru" and c["phone"].startswith("+7 (999)")
    assert c["telegram"] == "@ivan_petrov_dev" and c["github"].endswith("ivanpetrov")
    assert contacts_from(mask(SAMPLES["front"]).found)["telegram"] == "@anna_front"


def test_heuristic_names_first_lines():
    assert heuristic_names(SAMPLES["hh"]) == ["Петров Иван Сергеевич"]
    assert heuristic_names(SAMPLES["front"]) == ["Анна Смирнова"]
    assert heuristic_names(SAMPLES["data"]) == []  # «Резюме», «Аналитик данных» — не имена


@pytest.mark.slow
def test_natasha_finds_name_in_text_body():
    names = natasha_names(SAMPLES["data"])
    assert names is not None and any("Кузнецов" in n for n in names)


def test_scoped_packages_are_not_handles():
    m = mask("Стек: @angular/core, @tanstack/react-query; мой ник @ivan_dev")
    assert "@angular/core" in m.text and "@tanstack/react-query" in m.text and "@ivan_dev" not in m.text


def test_ner_failures_are_logged_and_reported(monkeypatch, caplog):
    import subprocess

    from app.llm import names

    def timeout(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="ner", timeout=1)

    monkeypatch.setattr(names.subprocess, "run", timeout)
    assert names.natasha_names("текст") is None and "timeout" in caplog.text
    caplog.clear()

    def crash(*a, **kw):
        raise subprocess.CalledProcessError(1, "ner", stderr=b"MemoryError: boom")

    monkeypatch.setattr(names.subprocess, "run", crash)
    assert names.natasha_names("текст") is None and "boom" in caplog.text


def test_ner_subprocess_limited_and_serialized(monkeypatch):
    import fcntl
    import subprocess

    from app.llm import names

    seen = {}

    def run(*a, **kw):
        seen["preexec"] = kw.get("preexec_fn")
        seen["locked"] = names.NER_LOCK.locked()
        with open(names.NER_LOCK_FILE, "a") as other:  # другой воркер того же контейнера ждёт своей очереди
            try:
                fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
                seen["shared"] = False
            except BlockingIOError:
                seen["shared"] = True
        return subprocess.CompletedProcess(a, 0, stdout='["Олег Кузнецов"]'.encode(), stderr=b"")

    monkeypatch.setattr(names.subprocess, "run", run)
    assert names.natasha_names("Олег Кузнецов") == ["Олег Кузнецов"]
    assert seen["preexec"] is not None and seen["locked"] and seen["shared"]


def test_full_name_only_from_first_lines(monkeypatch):
    from types import SimpleNamespace

    from app.llm import names

    monkeypatch.setattr(names, "get_settings", lambda: SimpleNamespace(ner_enabled=True))
    monkeypatch.setattr(names, "natasha_names", lambda text: ["Олег Кузнецов", "Сергей Иванов"])
    scan = names.scan_names(SAMPLES["data"] + "\n" * 3 + "Руководитель проекта — Сергей Иванов\n")
    assert scan.full_name == "Олег Кузнецов" and "Сергей Иванов" in scan.names and scan.complete
    body_only = "Резюме\nАналитик данных\nОпыт 2 года\nSQL, Python\nУдалёнка\nПроекты\nРуководитель — Сергей Иванов"
    monkeypatch.setattr(names, "natasha_names", lambda text: ["Сергей Иванов"])
    assert names.scan_names(body_only).full_name is None
    monkeypatch.setattr(names, "natasha_names", lambda text: None)
    assert names.scan_names(body_only).complete is False
