"""Пара SQL-запросов (эталон и показанное решение) на данных кандидата.

Запускается отдельным процессом: `python -m app.assessment.bank.sql_isolated` читает JSON из stdin
(техдизайн 5.2: данные кандидата — только в подпроцессе с таймаутом). Внутри — та же песочница
только для чтения, что и у SQL-заданий; данные вставляются экранированными литералами.
"""
import json
import sqlite3
import sys

from app.assessment.bank.base import Table
from app.assessment.bank.sqlite_sandbox import SandboxError, run_query, setup_sql


def run_payload(payload: dict) -> list:
    """{"schema": [[имя, [колонки]]], "data": {имя: [[ячейки]]}, "queries": [sql, …]} → результат или None."""
    tables = [Table(name, tuple(cols), tuple(tuple(r) for r in payload["data"].get(name, [])))
              for name, cols in payload["schema"]]
    setup = setup_sql(*tables)
    out: list = []
    for q in payload["queries"]:
        try:
            out.append([list(r) for r in run_query(setup, q)])
        except (SandboxError, sqlite3.Error):
            out.append(None)
    return out


if __name__ == "__main__":
    print(json.dumps(run_payload(json.load(sys.stdin)), ensure_ascii=False, default=str))
