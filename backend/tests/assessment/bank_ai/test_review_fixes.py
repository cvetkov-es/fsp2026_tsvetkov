"""Замечания финального ревью плана 07a3: спорные ключи, переносимость SQL, подпроцесс проверки данных."""
import json
import subprocess

from app.assessment.bank import verdicts
from app.assessment.bank.verdicts import check_verdict, ideal_response, make_verdict
from app.config.params import PARAMS

from ._helpers import SEEDS


def _flawed(code: str, pick) -> object:
    for s in range(300):
        inst = make_verdict(code, s, True)
        if pick(inst.public()["prompt"]["code"].split("\n")):
            return inst
    raise AssertionError(code)


def test_pages_count_plus_one_is_caught_by_the_exact_multiple():
    inst = _flawed("ai.py.pages_count", lambda lines: lines[1].endswith("+ 1"))
    resp = {"verdict": "defect", "line": 2, "input_class": "boundary", "confidence": "high"}
    assert check_verdict(inst.answer, resp)  # n = k даёт 2 страницы вместо 1 — это граница


def test_password_digits_match_the_requirement():
    for s in SEEDS:
        code = make_verdict("ai.py.password_ok", s, False).public()["prompt"]["code"]
        assert "isdigit" not in code and '"0123456789"' in code  # требование: цифры 0–9


def test_active_last_month_sql_is_portable():
    for s in range(20):
        assert "date(" not in make_verdict("ai.clarify.active_last_month", s, False).public()["prompt"]["code"]


def test_revenue_question_is_genuinely_open():
    inst = make_verdict("ai.clarify.revenue_month", 1, False)
    p = inst.public()["prompt"]
    assert p["clarify"][inst.answer["clarify"]] == "Относить заказ к месяцу по дате создания или по дате оплаты?"
    cols = p["tables"][0]["columns"]
    assert "paid_at" in cols and "status" not in cols


def _sql_defect():
    key = make_verdict("ai.sql.distinct_buyers", 1, True).answer
    return key, ideal_response(key)


def test_sql_subprocess_failure_is_logged(monkeypatch, caplog):
    def timeout(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="sql_isolated", timeout=1)

    monkeypatch.setattr(verdicts.subprocess, "run", timeout)
    key, resp = _sql_defect()
    with caplog.at_level("WARNING"):
        assert check_verdict(key, resp) is False
    assert "sql_isolated" in caplog.text


def test_sql_subprocess_gets_the_param_timeout(monkeypatch):
    seen = {}

    def fake(cmd, **kw):
        seen.update(kw)
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps([[[1]], [[2]]]), stderr="")

    monkeypatch.setattr(verdicts.subprocess, "run", fake)
    key, resp = _sql_defect()
    assert check_verdict(key, resp)
    assert seen["timeout"] == PARAMS.ai_sql_timeout_s >= 10  # запуск интерпретатора входит в бюджет


def test_empty_data_is_compared_without_a_subprocess(monkeypatch):
    def boom(*a, **kw):
        raise AssertionError("пустые данные кандидата — без подпроцесса")

    monkeypatch.setattr(verdicts.subprocess, "run", boom)
    key, _ = _sql_defect()
    assert check_verdict(key, {"verdict": "defect", "line": key["line"], "rows": {}}) is False
