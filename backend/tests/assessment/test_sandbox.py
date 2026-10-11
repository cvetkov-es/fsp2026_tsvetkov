import pytest

from app.assessment.bank.base import Table
from app.assessment.bank.pysnippet import run_python_snippet
from app.assessment.bank.sqlite_sandbox import SandboxError, run_query, setup_sql

T = Table("t", ("id", "name", "v"), ((1, "O'Brien", 10), (2, "Анна", None)))


def test_setup_and_select_with_quotes_and_nulls():
    rows = run_query(setup_sql(T), "SELECT name, v FROM t ORDER BY id")
    assert rows == [("O'Brien", 10), ("Анна", None)]


@pytest.mark.parametrize("q", [
    "ATTACH DATABASE ':memory:' AS x",
    "PRAGMA table_info(t)",
    "INSERT INTO t VALUES (3, 'x', 1)",
    "DELETE FROM t",
    "CREATE TABLE z (a)",
])
def test_dangerous_statements_denied(q):
    with pytest.raises(SandboxError):
        run_query(setup_sql(T), q)


def test_infinite_recursion_interrupted():
    q = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT count(*) FROM c"
    with pytest.raises(SandboxError):
        run_query(setup_sql(T), q, timeout_s=0.5)


def test_row_limit():
    q = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c LIMIT 500) SELECT x FROM c"
    with pytest.raises(SandboxError):
        run_query(setup_sql(T), q, max_rows=100)


def test_python_snippet_output():
    assert run_python_snippet("a = [1, 2]\nb = a\nb.append(3)\nprint(len(a), a[-1])") == "3 3"
