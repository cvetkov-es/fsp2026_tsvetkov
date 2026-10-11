import json
import random

import pytest

from app.assessment.bank.base import REGISTRY
from app.assessment.bank.canon import is_correct
from app.assessment.bank.checks import check_family
from app.assessment.bank.verdicts import (
    Mutation,
    check_verdict,
    ideal_response,
    make_verdict,
    python_verdict,
    roundtrip,
    run_cases,
)
from app.config.params import PARAMS
from app.config.settings import Settings
from app.lab.llm_checks import solver_check
from tests.llm_fakes import FakeTransport

PY, SQL, CLAR = "toy.ai.python.0", "toy.ai.sql.0", "toy.ai.clarify.0"


def test_python_key_is_computed_by_execution(toy_verdicts):
    ok, bad = make_verdict(PY, 1, False), make_verdict(PY, 1, True)
    assert ok.answer == {"truth": "ok", "line": None, "breaks": [], "sql": None, "clarify": None}
    assert bad.answer["truth"] == "defect" and bad.answer["line"] == 2 and bad.answer["breaks"] in (["boundary"], ["dup"])
    prompt = bad.public()["prompt"]
    assert prompt["input_classes"] == ("empty", "dup", "boundary") and len(prompt["clarify"]) == 4
    assert not {"truth", "breaks", "witness"} & set(json.dumps(bad.public(), ensure_ascii=False).split('"'))


def test_defect_needs_line_and_breaking_class(toy_verdicts):
    key = make_verdict(PY, 2, True).answer
    good = {"verdict": "defect", "line": 2, "input_class": key["breaks"][0], "confidence": "low"}
    assert check_verdict(key, good)
    assert not check_verdict(key, good | {"line": 1})
    assert not check_verdict(key, good | {"input_class": "empty"})  # пустой список не ломает решение
    assert not check_verdict(key, {"verdict": "ok"})
    assert not check_verdict(key, {"verdict": "clarify", "clarify": 0})


def test_ok_and_ambiguous_keys(toy_verdicts):
    ok = make_verdict(PY, 3, False).answer
    assert check_verdict(ok, {"verdict": "ok", "confidence": "high"})
    assert not check_verdict(ok, {"verdict": "defect", "line": 2, "input_class": "boundary"})
    amb = make_verdict(CLAR, 3, False)
    assert amb.answer["truth"] == "ambiguous"
    assert amb.public()["prompt"]["clarify"][amb.answer["clarify"]] == "Как быть с повторами?"
    assert check_verdict(amb.answer, ideal_response(amb.answer))
    assert not check_verdict(amb.answer, {"verdict": "ok"})
    assert not check_verdict(amb.answer, {"verdict": "clarify", "clarify": (amb.answer["clarify"] + 1) % 4})


def test_sql_breaking_data_is_checked_in_a_subprocess(toy_verdicts):
    key = make_verdict(SQL, 4, True).answer
    n = key["sql"]["witness"][0][2][0][0]
    assert check_verdict(key, ideal_response(key))  # данные-свидетель — через отдельный процесс
    resp = {"verdict": "defect", "line": 3}
    assert check_verdict(key, resp | {"rows": {"t": [[str(n)]]}})  # из формы приходят строки: "123" → 123
    assert not check_verdict(key, resp | {"rows": {"t": [[n + 5]]}})  # на этих данных решения совпадают
    assert not check_verdict(key, resp | {"rows": {"t": [["x'); DROP TABLE t; --"]]}})
    assert not check_verdict(key, resp | {"rows": {"t": [[n]] * (PARAMS.sql_input_max_rows + 1)}})
    assert not check_verdict(key, resp | {"rows": {"nope": [[n]]}})
    assert not check_verdict(key, resp | {"rows": {"t": [[n, 1]]}})  # лишняя колонка
    assert not check_verdict(key, resp | {"rows": {"t": [["x" * 41]]}})


def test_candidate_garbage_never_raises(toy_verdicts):
    inst = make_verdict(SQL, 5, True)
    for raw in (None, "defect", 1, [], {"verdict": "maybe"}, {"verdict": "defect", "line": "two"},
                {"verdict": "defect", "line": 3, "rows": "x"}, {"verdict": "defect", "line": 3, "rows": {"t": [[1e400]]}}):
        assert check_verdict(inst.answer, raw) is False
        assert is_correct(inst, raw) is False


def test_generation_rejects_a_harmless_mutation():
    with pytest.raises(ValueError, match="не ломает"):
        python_verdict(random.Random(1), True, text="t", reference="def solve(xs):\n    return len(xs)",
                       mutations=(Mutation(2, "    return len(list(xs))", cls="dup"),), cases={"dup": [1, 1]},
                       clarify=("a", "b", "c", "d"))


def test_generation_rejects_a_mutation_that_misses_its_class():
    # дефект объявлен как «отрицательные», но представитель этого класса его не ловит
    with pytest.raises(ValueError, match="negative"):
        python_verdict(random.Random(1), True, text="t", reference="def solve(xs):\n    return sum(xs)",
                       mutations=(Mutation(2, "    return sum(set(xs))", cls="negative"),),
                       cases={"negative": [-1, 2], "dup": [3, 3]}, clarify=("a", "b", "c", "d"))


def test_run_cases_reports_a_crash_as_output():
    out = run_cases("def solve(xs):\n    return xs[0]", {"empty": [], "dup": [2, 2]})
    assert out == {"empty": "<ошибка IndexError>", "dup": "2"}


def test_bank_pipeline_checks_verdict_families(toy_verdicts):
    for code in (PY, SQL, CLAR):
        r = check_family(REGISTRY[code], subprocess_probe=False)
        assert r.ok, (code, r.errors)
        assert all(roundtrip(make_verdict(code, s, fl)) for s in range(20) for fl in (False, True))


def test_lab_solver_does_not_sample_verdicts(toy_verdicts):
    r = solver_check(FakeTransport(*['{"answer": "1"}'] * 50), Settings(_env_file=None), per_spec=5)
    assert not any(row["family"].startswith("toy.ai.") for row in r["rows"])
