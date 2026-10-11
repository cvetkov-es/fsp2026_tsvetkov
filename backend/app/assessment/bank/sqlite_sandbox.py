"""SQLite в памяти для SQL-заданий: только чтение, лимит шагов, времени и строк (техдизайн 5.2)."""
import sqlite3
import time
from typing import Any

from app.assessment.bank.base import Table
from app.config.params import PARAMS


class SandboxError(Exception):
    pass


_ALLOWED = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION,
            sqlite3.SQLITE_RECURSIVE}


def _authorizer(action, *_args):
    return sqlite3.SQLITE_OK if action in _ALLOWED else sqlite3.SQLITE_DENY


def _literal(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int | float):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def setup_sql(*tables: Table) -> str:
    parts = []
    for t in tables:
        parts.append(f"CREATE TABLE {t.name} ({', '.join(t.columns)});")
        for row in t.rows:
            parts.append(f"INSERT INTO {t.name} VALUES ({', '.join(_literal(v) for v in row)});")
    return "\n".join(parts)


def run_query(setup: str, query: str, *, max_rows: int = PARAMS.sandbox_max_rows,
              max_steps: int = PARAMS.sandbox_max_steps,
              timeout_s: float = PARAMS.sandbox_timeout_s) -> list[tuple]:
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(setup)  # наши данные, до включения ограничений
        conn.set_authorizer(_authorizer)
        # Одно значение не может быть огромным: zeroblob(200 МБ) прогресс-хендлер не прервёт
        conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, PARAMS.sandbox_max_value_bytes)
        deadline = time.monotonic() + timeout_s
        steps = {"n": 0}

        def progress() -> int:
            steps["n"] += 1000
            return int(steps["n"] > max_steps or time.monotonic() > deadline)

        conn.set_progress_handler(progress, 1000)
        try:
            cur = conn.execute(query)
            rows = cur.fetchmany(max_rows + 1)
        except sqlite3.Error as e:
            raise SandboxError(str(e)) from e
        if len(rows) > max_rows:
            raise SandboxError("слишком много строк")
        return [tuple(r) for r in rows]
    finally:
        conn.close()
