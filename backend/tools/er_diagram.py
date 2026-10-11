"""ER-диаграмма Mermaid из моделей SQLAlchemy.

Запуск (из каталога backend): uv run python -m tools.er_diagram > ../docs/er.mmd
Отфильтровать таблицы: uv run python -m tools.er_diagram --tables users,attempts,candidate_profiles
"""
import argparse

import app.db.all_models  # noqa: F401  — регистрирует таблицы
from app.db.base import Base

SKIP_COLS = {"created_at", "updated_at"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", default="", help="список имён таблиц через запятую")
    args = ap.parse_args()
    wanted = {t.strip() for t in args.tables.split(",") if t.strip()}
    tables = [t for t in Base.metadata.sorted_tables if not wanted or t.name in wanted]
    print("erDiagram")
    for t in tables:
        print(f"  {t.name} {{")
        for c in t.columns:
            if c.name in SKIP_COLS:
                continue
            key = " PK" if c.primary_key else (" FK" if c.foreign_keys else "")
            print(f"    {type(c.type).__name__.lower()} {c.name}{key}")
        print("  }")
    names = {t.name for t in tables}
    for t in tables:
        for fk in t.foreign_keys:
            parent = fk.column.table.name
            if parent in names:
                print(f'  {parent} ||--o{{ {t.name} : "{fk.parent.name}"')


if __name__ == "__main__":
    main()
