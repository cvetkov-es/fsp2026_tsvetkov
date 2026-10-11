"""Alembic: схема — из моделей (Base.metadata), адрес БД — из настроек приложения."""
from alembic import context
from sqlalchemy.engine import Connection

import app.db.all_models  # noqa: F401  — регистрирует все таблицы
from app.db.base import Base
from app.db.session import get_engine

target_metadata = Base.metadata


def run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("offline-режим не используется: миграции применяются к живой БД")
external = context.config.attributes.get("connection")  # тест передаёт своё соединение
if external is not None:
    run(external)
else:
    with get_engine().connect() as conn:
        run(conn)
