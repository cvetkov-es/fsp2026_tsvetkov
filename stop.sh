#!/usr/bin/env sh
# Остановка стенда на Linux и macOS. В Windows то же делает stop.cmd.
set -e
cd "$(dirname "$0")"

echo "Останавливаю стенд ФСП · Обратный найм..."
docker compose down
echo
echo "Готово. Данные остались в томе: следующий запуск через ./start.sh поднимет стенд как был."
