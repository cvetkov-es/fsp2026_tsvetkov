#!/usr/bin/env bash
# Стенд на VPS одной командой. Из корня клонированного репозитория:  sudo bash deploy/bootstrap.sh
# Повторный запуск безопасен: .env не перезаписывается, стенд пересобирается из текущего коммита (так и обновляют: git pull и снова этот скрипт).
set -euo pipefail
cd "$(dirname "$0")/.."

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
die() { printf '\n\033[31mОшибка: %s\033[0m\n' "$*" >&2; exit 1; }
COMPOSE=(docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml)

[ "$(id -u)" -eq 0 ] || die "запустите через sudo: sudo bash deploy/bootstrap.sh"

say "1/6 Docker"
if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
docker compose version

say "2/6 Настройки стенда (.env)"
if [ -f .env ]; then
  echo ".env уже есть — оставляю как есть (чтобы задать заново: удалите .env и запустите скрипт ещё раз)"
else
  read -rp "Домен стенда, например fsp.example.ru (A-запись должна указывать на этот сервер): " DOMAIN
  [ -n "$DOMAIN" ] || die "домен обязателен"
  read -rsp "Ключ LLM (Enter — без LLM: продукт работает и без него): " LLM_API_KEY; echo
  PG_PASS=$(openssl rand -hex 16)
  umask 077
  cat > .env <<EOF
DOMAIN=$DOMAIN
POSTGRES_PASSWORD=$PG_PASS
DATABASE_URL=postgresql+psycopg://fsp:$PG_PASS@db:5432/fsp
SECRET_KEY=$(openssl rand -hex 32)
DEMO_MODE=true
PUBLIC_BASE_URL=https://$DOMAIN
COOKIE_SECURE=true
LLM_PROFILE=prod
LLM_BASE_URL=https://polza.ai/api/v1
LLM_API_KEY=$LLM_API_KEY
NER_ENABLED=true
MAIL_HOST=mailpit
MAIL_PORT=1025
EOF
  umask 022
  echo ".env создан, права 600; пароль БД и секрет сессий сгенерированы"
fi
DOMAIN=$(grep -E '^DOMAIN=' .env | cut -d= -f2-)
[ -n "$DOMAIN" ] || die "в .env нет DOMAIN"

say "3/6 DNS и порты"
SERVER_IP=$(curl -fsS --max-time 10 https://api.ipify.org || true)
DOMAIN_IP=$(getent ahostsv4 "$DOMAIN" | awk 'NR==1 {print $1}' || true)
if [ -n "$SERVER_IP" ] && [ "$DOMAIN_IP" != "$SERVER_IP" ]; then
  echo "ВНИМАНИЕ: $DOMAIN указывает на ${DOMAIN_IP:-ничего}, а IP сервера — $SERVER_IP."
  echo "Без верной A-записи сертификат HTTPS не выпустится. Исправьте DNS или продолжите, если знаете, что делаете."
  read -rp "Продолжить? [y/N] " answer
  [ "$answer" = "y" ] || exit 1
else
  echo "$DOMAIN → $DOMAIN_IP — совпадает с IP сервера"
fi
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  ufw allow 80/tcp && ufw allow 443/tcp
fi

say "4/6 Сборка и запуск (в первый раз — 5–10 минут)"
"${COMPOSE[@]}" up -d --build --wait --wait-timeout 900

say "5/6 Лаборатория и смоук-тест изнутри"
COMPOSE_FILES="docker-compose.yml deploy/docker-compose.prod.yml" bash deploy/post-up.sh \
  || die "приложение не прошло смоук-тест: ${COMPOSE[*]} logs --tail=200"

say "6/6 Смоук-тест снаружи"
echo "https://$DOMAIN (сертификат может выпускаться до минуты):"
ok=0
for _ in $(seq 1 12); do
  if "${COMPOSE[@]}" exec -T api python - "https://$DOMAIN" < deploy/smoke.py; then ok=1; break; fi
  sleep 10
done
[ "$ok" = 1 ] || die "по HTTPS стенд не отвечает. Журнал Caddy: ${COMPOSE[*]} logs caddy --tail=100"

say "Готово: https://$DOMAIN"
cat <<EOF
Жюри: на главной — вход, в шапке — «Демо: Кандидат / Работодатель», модератор — в списке «Ещё…».
Обновить стенд:   git pull && sudo bash deploy/bootstrap.sh
Журналы:          ${COMPOSE[*]} logs -f --tail=200
Резервная копия:  ${COMPOSE[*]} exec -T db pg_dump -U fsp fsp | gzip > backup-\$(date +%F).sql.gz
EOF
