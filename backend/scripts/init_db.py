"""Схема — миграциями Alembic (upgrade head), затем банк заданий и пороги."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.assessment.bank_sync import ensure_thresholds, sync_bank
from app.db.session import _session_factory, get_engine

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def migrate() -> None:
    insp = inspect(get_engine())
    if insp.has_table("users") and not insp.has_table("alembic_version"):
        # БД создана через create_all до миграций: «приклеить» ревизию к неизвестной схеме нельзя — колонки могут не совпадать
        raise SystemExit("БД создана до миграций. Пересоздайте dev-БД: make devdb-reset")
    command.upgrade(Config(str(ALEMBIC_INI)), "head")


if __name__ == "__main__":
    migrate()
    with _session_factory()() as db:
        n = sync_bank(db)
        ensure_thresholds(db)
        db.commit()
    print(f"ok: семейств {n}")
