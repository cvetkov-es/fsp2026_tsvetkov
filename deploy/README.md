# Стенд на VPS

**Сервер:** Ubuntu 22.04 или 24.04, от 2 vCPU и 4 ГБ RAM, 20 ГБ диска, в России (на стенде будут персональные данные, 152-ФЗ). Порты 80 и 443 открыты у провайдера.

**Домен:** A-запись домена (или поддомена) указывает на IP сервера. Сертификат HTTPS Caddy выпустит сам.

## 1. Клонировать репозиторий

```bash
git clone https://github.com/cvetkov-es/fsp2026_tsvetkov.git
cd fsp2026_tsvetkov
```

## 2. Поднять стенд

```bash
sudo bash deploy/bootstrap.sh
```

Скрипт ставит Docker, спрашивает домен и ключ LLM (можно пропустить — продукт работает и без LLM), генерирует пароль БД и секрет сессий в `.env`, собирает и запускает стенд, загружает отчёт лаборатории и проверяет стенд смоук-тестом изнутри и снаружи по HTTPS. Первый запуск — 5–10 минут.

## Обновить

```bash
git pull && sudo bash deploy/bootstrap.sh
```

`.env` и данные сохраняются; схема БД обновляется миграциями при старте.

## Если что-то пошло не так

Пришлите вывод скрипта и журналы:

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml logs --tail=200
```

Ключ LLM в `.env` никому не пересылайте: в журналах его нет.

## Если на сервере уже работают другие приложения

`bootstrap.sh` поднимает свой Caddy на портах 80 и 443. Если они заняты, разверните стек за существующим прокси хоста.

1. В `.env` задайте `APP_PORT` (по умолчанию 8080). `PUBLIC_BASE_URL` оставьте с публичным адресом сайта.
2. Запустите стек с оверлеем для общего сервера:

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.shared.yml up -d --build --wait
```

3. Направьте в прокси хоста запросы на `http://127.0.0.1:APP_PORT`. Пример для nginx:

```nginx
# Открытие по http:// уводит на https://
server {
  listen 80;
  server_name fsp.example.ru;
  return 301 https://$host$request_uri;
}

server {
  listen 443 ssl;
  server_name fsp.example.ru;
  # сертификаты хоста

  location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    client_max_body_size 6m;      # резюме до 5 МБ и разбор с запасом
    proxy_read_timeout 150s;
  }

  add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
  add_header X-Content-Type-Options "nosniff" always;
  add_header X-Frame-Options "DENY" always;
  add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
```

В этом режиме наружу открыт только `127.0.0.1:APP_PORT`; порты 80 и 443, как и раньше, за прокси хоста. Проверить: `ss -ltnp | grep 8080` показывает адрес 127.0.0.1, а не 0.0.0.0. Разбор безопасности и чек-лист — в `../docs/security.md`.
