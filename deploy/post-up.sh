#!/usr/bin/env bash
# После запуска стенда: отчёт лаборатории в БД (если прогонов ещё нет) и смоук-тест приложения изнутри.
# Вызывают deploy/bootstrap.sh на VPS и CI (workflow compose). Файлы compose — в COMPOSE_FILES через пробел.
set -euo pipefail
cd "$(dirname "$0")/.."
read -ra FILES <<< "${COMPOSE_FILES:-docker-compose.yml}"
COMPOSE=(docker compose)
for f in "${FILES[@]}"; do COMPOSE+=(-f "$f"); done

# Полный отчёт из репозитория (3000 синтетических кандидатов, с разделами LLM) — чтобы страница лаборатории сразу показывала числа.
# Свой прогон жюри может запустить на самой странице.
"${COMPOSE[@]}" exec -T api python -c '
import json, sys
from sqlalchemy import func, select
from app.db.session import _session_factory
from app.lab.models import LabRun
from app.lab.service import record
with _session_factory()() as db:
    if db.scalar(select(func.count()).select_from(LabRun)):
        print("лаборатория: прогоны уже есть — отчёт не загружаю")
    else:
        record(db, json.load(sys.stdin))
        print("лаборатория: отчёт reports/validation.json загружен")
' < reports/validation.json

echo "смоук-тест приложения изнутри (http://web:8080):"
"${COMPOSE[@]}" exec -T api python - http://web:8080 < deploy/smoke.py
