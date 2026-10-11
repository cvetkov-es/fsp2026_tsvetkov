SHELL := /bin/bash
DEVDB = $(shell cd backend && uv run python scripts/devdb.py | sed 's/^DATABASE_URL=//')

.PHONY: devdb initdb seed api web worker test lint openapi docs bank-check llm-smoke validate migration devdb-reset up down logs smoke
devdb:      ## запустить встроенный PostgreSQL и напечатать DATABASE_URL
	cd backend && uv run python scripts/devdb.py
initdb:     ## создать таблицы в dev-БД
	cd backend && DATABASE_URL="$(DEVDB)" uv run python -m scripts.init_db
seed:        ## засеять демо-базу (≈450 синтетических кандидатов, демо-компания)
	cd backend && DEMO_MODE=true DATABASE_URL="$(DEVDB)" uv run python -m scripts.seed
api:        ## бэкенд на :8000 поверх dev-БД
	cd backend && DEMO_MODE=true DATABASE_URL="$(DEVDB)" FSP_SERVER_BASE=http://localhost:8000 uv run uvicorn app.main:app --reload --port 8000
worker:      ## worker: истечение приглашений, напоминания, письма (раз в минуту)
	cd backend && DEMO_MODE=true DATABASE_URL="$(DEVDB)" uv run python -m app.worker
web:        ## фронтенд на :5173 (прокси /api → :8000)
	cd frontend && pnpm dev
test:       ## все тесты
	cd backend && uv run pytest
	cd frontend && pnpm test
lint:
	cd backend && uv run ruff check .
openapi:    ## экспорт openapi.json в docs/api
	mkdir -p docs/api
	cd backend && DEMO_MODE=true uv run python -c "import json; from app.main import app; print(json.dumps(app.openapi(), ensure_ascii=False, indent=2))" > ../docs/api/openapi.json
bank-check:  ## проверить все семейства банка
	cd backend && uv run python -m tools.bank_check
docs:        ## собрать документы и генерируемые части (ER, валидация, согласия, лицензии)
	cd backend && uv run python -m tools.er_diagram > ../docs/er.mmd
	cd backend && uv run python -m tools.validation_md
	cd backend && uv run python -m tools.consents_md
	bash tools/licenses.sh > docs/licenses.md
llm-smoke:   ## живая проверка LLM на синтетике (нужен ключ в .env; ключ не печатается)
	cd backend && NER_ENABLED=true uv run python -m scripts.llm_smoke
validate:    ## лаборатория: полный прогон → reports/validation.json (LLM — если есть ключ); флаги: ARGS="--no-llm --n 500"
	cd backend && DEMO_MODE=true DATABASE_URL="$(DEVDB)" uv run python -m scripts.validate $(ARGS)
migration:   ## новая миграция по изменённым моделям: make migration m="что изменилось"
	cd backend && DATABASE_URL="$(DEVDB)" uv run alembic revision --autogenerate -m "$(m)"
devdb-reset: ## dev-БД с нуля: схема, миграции, банк, засев
	cd backend && DATABASE_URL="$(DEVDB)" uv run python -m scripts.reset_db
	$(MAKE) initdb seed
COMPOSE = docker compose -f docker-compose.yml $(if $(PROD),-f deploy/docker-compose.prod.yml)
up:      ## стенд: make up (локально) / make up PROD=1 (VPS, HTTPS)
	$(COMPOSE) up -d --build --wait
down:    ## остановить стенд (данные в томе сохраняются)
	$(COMPOSE) down
logs:    ## журналы стенда
	$(COMPOSE) logs -f --tail=200
smoke:   ## смоук-тест: make smoke URL=https://<домен>
	python deploy/smoke.py $(or $(URL),http://localhost:8080)
