import random
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.assessment.bank.base import REGISTRY, Family, Generated, Prompt
from app.assessment.bank.canon import CanonError, canonical, is_correct
from app.assessment.bank.checks import check_family
from app.assessment.bank.families import load_all
from app.assessment.bank.pysnippet import run_python_snippet
from app.assessment.bank.sqlite_sandbox import SandboxError, run_query

load_all()


def test_snippets_are_thread_safe_and_leave_stdout_alone():
    f = REGISTRY["be.lang.list_alias_copy"]
    expected = {s: f.make(s).answer for s in range(300)}
    stdout_before = sys.stdout
    with ThreadPoolExecutor(8) as pool:
        got = dict(zip(expected, pool.map(lambda s: f.make(s).answer, expected), strict=True))
    assert got == expected
    assert sys.stdout is stdout_before


def test_snippet_output_isolated_from_process_stdout(capsys):
    assert run_python_snippet("print(1)") == "1"
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("kind,raw", [
    ("line", "inf"), ("line", "nan"), ("choice", "1e400"), ("order", "9" * 400),
    ("order", ["inf"]), ("number", 10**400), ("number", "nan"),
])
def test_non_finite_and_huge_inputs_are_canon_errors(kind, raw):
    with pytest.raises(CanonError):
        canonical(kind, raw)


def test_is_correct_never_raises_on_candidate_garbage():
    inst = REGISTRY["be.debug.window_sums_bug"].make(1)
    for raw in ("inf", "nan", "1e400", "9" * 400, None, [], {"a": 1}):
        assert is_correct(inst, raw) is False


def test_public_hides_family_code_but_key_keeps_it():
    inst = REGISTRY["be.db.avg_ignores_null"].make(3)
    assert "family_code" not in inst.public()
    assert inst.key()["family_code"] == "be.db.avg_ignores_null"


def test_rows_tolerate_case_and_inner_spaces():
    assert canonical("rows", [["анна  иванова", "x"]]) == canonical("rows", [["Анна Иванова", "X"]])


def test_order_digits_without_separators():
    assert canonical("order", "312645") == (3, 1, 2, 6, 4, 5)


def test_sandbox_rejects_huge_values():
    with pytest.raises(SandboxError):
        run_query("CREATE TABLE t (a);", "SELECT length(zeroblob(200000000))")


def test_probe_failure_is_reported_not_raised():
    def gen(rng: random.Random) -> Generated:
        a = rng.randint(1, 10**6)
        return Generated("number", Prompt(text=f"{a}?"), a, ("x",))

    r = check_family(Family("not.registered", "backend", "lang", 1, "output", 10**6, 20, gen))
    assert not r.ok and any("подпроцесс" in e for e in r.errors)
