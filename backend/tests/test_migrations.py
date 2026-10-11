"""Миграции и модели не расходятся: upgrade head на пустой БД даёт ровно Base.metadata, downgrade base всё убирает."""
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from app.db.base import Base

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def test_migrations_match_models(engine):
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
        c.execute(text("DROP DATABASE IF EXISTS fsp_migrations"))
        c.execute(text("CREATE DATABASE fsp_migrations"))
    eng = create_engine(engine.url.set(database="fsp_migrations"))
    cfg = Config(str(ALEMBIC_INI))
    try:
        with eng.begin() as conn:
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "head")
        with eng.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
        # непустой diff: модель изменили без миграции — make migration m="…"
        assert diff == [], diff
        with eng.begin() as conn:
            cfg.attributes["connection"] = conn
            command.downgrade(cfg, "base")
        assert set(inspect(eng).get_table_names()) <= {"alembic_version"}
    finally:
        eng.dispose()
