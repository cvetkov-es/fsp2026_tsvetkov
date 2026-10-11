#!/usr/bin/env bash
# Лицензии зависимостей (перечень ТЗ): бэкенд по uv.lock, фронтенд по pnpm-lock.yaml.
# Запуск из корня репозитория: bash tools/licenses.sh > docs/licenses.md
set -euo pipefail
cd "$(dirname "$0")/.."

echo "# Библиотеки и лицензии"
echo
echo "Сгенерировано $(date +%F) скриптом tools/licenses.sh."
echo
echo "## Бэкенд (uv.lock)"
echo
(cd backend && uv run --quiet --with pip-licenses pip-licenses --format=markdown --with-urls --order=license)
echo
echo "## Фронтенд (pnpm-lock.yaml)"
echo
# Корневой пакет фронтенда идёт без ссылки на репозиторий: markdown-ссылка "(undefined)" не нужна
(cd frontend && npx --yes license-checker-rseidelsohn --production --markdown) | sed 's/\](undefined)//'
