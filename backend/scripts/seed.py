"""Засев демо-базы (идемпотентно). Только в демо-режиме: в боевой базе синтетики быть не должно."""
import app.db.all_models  # noqa: F401
from app.config.settings import get_settings
from app.db.session import _session_factory
from app.demo.seed import seed_all

if __name__ == "__main__":
    if not get_settings().demo_mode:
        print("skip: DEMO_MODE выключен")
    else:
        with _session_factory()() as db:
            print(seed_all(db))
