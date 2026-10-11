"""Запускает встроенный PostgreSQL 16 для разработки (Docker не нужен).

Использование: uv run python scripts/devdb.py  → печатает DATABASE_URL.
Данные хранятся в $FSP_DEVDB_DIR (по умолчанию ~/.local/share/fsp-hiring/devdb):
pg_ctl не принимает пути с пробелами, а путь к репозиторию может их содержать.
Сервер продолжает работать после выхода скрипта.
"""
import os
from pathlib import Path

import pgserver

DATA = Path(os.environ.get("FSP_DEVDB_DIR", Path.home() / ".local/share/fsp-hiring/devdb"))


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    srv = pgserver.get_server(str(DATA), cleanup_mode=None)
    uri = srv.get_uri().replace("postgresql://", "postgresql+psycopg://", 1)
    print(f"DATABASE_URL={uri}")


if __name__ == "__main__":
    main()
