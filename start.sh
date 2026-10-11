#!/usr/bin/env sh
# Запуск стенда на Linux и macOS. В Windows то же делает start.cmd.
# Общая суть — одна команда docker compose; различия только в обёртке под клик.
set -e
cd "$(dirname "$0")"

echo "================================================"
echo "  ФСП · Обратный найм — локальный стенд"
echo "================================================"
echo

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker не найден. Установите Docker Desktop: https://www.docker.com/products/docker-desktop/"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker установлен, но не запущен. Запустите Docker Desktop или демон docker и повторите."
  exit 1
fi

if [ ! -f .env ]; then
  echo "[1/2] Файла .env нет — создаю из .env.example и генерирую секрет..."
  cp .env.example .env
  secret=""
  if command -v openssl >/dev/null 2>&1; then
    secret=$(openssl rand -hex 32)
  elif command -v python3 >/dev/null 2>&1; then
    secret=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  fi
  if [ -n "$secret" ]; then
    # sed -i.bak переносим между GNU и BSD
    sed -i.bak "s/^SECRET_KEY=.*/SECRET_KEY=${secret}/" .env
    rm -f .env.bak
  fi
fi

echo "[2/2] Собираю и запускаю стенд."
echo "      Первый запуск занимает несколько минут: образы, миграции, банк заданий, засев."
echo
docker compose up -d --build --wait

echo
echo "Готово. Стенд открывается на http://localhost:8080"
echo "В шапке — переключатель демо-персон: кандидат, работодатель, модератор."
echo "Остановить стенд: ./stop.sh"
echo

if command -v xdg-open >/dev/null 2>&1; then
  xdg-open http://localhost:8080 >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then
  open http://localhost:8080 >/dev/null 2>&1 || true
fi
