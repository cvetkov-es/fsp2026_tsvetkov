import pytest

from app.assessment.bank.base import Instance, Prompt
from app.config.settings import Settings
from app.lab.llm_checks import judge_check, render, solver_check, to_response
from tests.llm_fakes import FakeTransport


def test_render_and_response_mapping():
    inst = Instance("x", "choice", Prompt(text="Код ответа?", options=("200", "404")), 1)
    text = render(inst)
    assert "1) 200" in text and "2) 404" in text
    assert to_response(inst, "2") == 1  # модель нумерует с 1, проверка кандидата — с 0


def test_solver_check_structure_with_fake_models():
    t = FakeTransport(*['{"answer": "1"}'] * 100)
    r = solver_check(t, Settings(_env_file=None), per_spec=3)
    assert r["n"] == len(r["rows"]) > 0 and 0 <= r["agree_a"] <= 1
    assert {c["model"] for c in t.calls} == {"deepseek/deepseek-v4.1-flash", "google/gemini-3.8-flash"}


def test_judge_must_differ_from_rephrase_model_and_reports_agreement():
    with pytest.raises(ValueError, match="другой моделью"):
        judge_check(FakeTransport(), Settings(_env_file=None, llm_model_judge="deepseek/deepseek-v4.1-flash"))
    t = FakeTransport(*['{"better": "A"}'] * 50)
    r = judge_check(t, Settings(_env_file=None), pairs=10)
    assert r["pairs"] == 10 and 0 <= r["ours_agrees_with_truth"] <= 1
    assert all(c["model"] == "google/gemini-3.8-flash" for c in t.calls)


def test_solver_samples_skill_banks_too():
    t = FakeTransport(*['{"answer": "1"}'] * 100)
    r = solver_check(t, Settings(_env_file=None), per_spec=3)
    assert any(row["family"].startswith("sk.") for row in r["rows"])  # 245 семейств, а не только 195
