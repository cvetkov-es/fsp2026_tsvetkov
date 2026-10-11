from app.config.settings import Settings
from app.lab.ai_policies import ai_policies, render_verdict, sample_attempts
from app.lab.report import _ai_section
from tests.llm_fakes import FakeTransport

DEFECT = '{"verdict": "defect", "line": 1, "input_class": "empty"}'


def test_trusting_everything_never_passes_and_needs_no_llm(toy_ai_bank):
    r = ai_policies(None, Settings(_env_file=None), attempts=4)
    assert r["llm"] == "skipped" and [p["key"] for p in r["policies"]] == ["trust_all"]
    p = r["policies"][0]
    assert p["pass_rate"] == 0 and p["miss_weighted"] == 1 and 5 / 12 <= p["accuracy"] <= 7 / 12


def test_llm_policies_share_answers_and_differ_only_in_confidence(toy_ai_bank):
    t = FakeTransport(*['{"verdict": "ok"}', DEFECT] * 12)
    r = ai_policies(t, Settings(_env_file=None), attempts=2)
    rows = {p["key"]: p for p in r["policies"]}
    assert set(rows) == {"trust_all", "llm_only", "llm_verified"} and len(t.calls) == 24  # одна модель на обе политики
    assert {c["model"] for c in t.calls} == {Settings(_env_file=None).llm_model_ai_policy}
    assert rows["llm_only"]["accuracy"] == rows["llm_verified"]["accuracy"]
    assert rows["llm_verified"]["miss_weighted"] <= rows["llm_only"]["miss_weighted"]  # неуверенный пропуск весит меньше


def test_render_numbers_lines_and_lists_closed_options(toy_ai_bank):
    insts = sample_attempts(1, 1)[0]
    text = render_verdict(next(i for i in insts if i.public()["prompt"]["language"] == "python"))
    assert "  1  def solve(xs):" in text and "empty — Пустой ввод" in text and "4) " in text


def test_report_section_without_llm(toy_ai_bank):
    section = _ai_section(7, with_llm=False)
    assert section["llm"] == "skipped" and section["policies"][0]["title"] == "Принимает всё"


def test_llm_rows_are_checked_in_a_subprocess(toy_ai_bank, monkeypatch):
    import subprocess

    from app.assessment.bank import verdicts

    calls, real = [], subprocess.run

    def spy(*a, **kw):
        calls.append(1)
        return real(*a, **kw)

    monkeypatch.setattr(verdicts.subprocess, "run", spy)
    t = FakeTransport(*['{"verdict": "defect", "line": 3, "rows": {"t": [[5]]}}'] * 24)
    ai_policies(t, Settings(_env_file=None), attempts=1)
    assert calls  # данные от модели — как данные кандидата: вне процесса
