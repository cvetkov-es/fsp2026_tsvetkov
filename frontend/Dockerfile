# Контекст сборки — корень репозитория (см. docker-compose.yml), чтобы взять deploy/nginx.conf
FROM node:26-alpine AS build
WORKDIR /app
# corepack в Node 25+ не поставляется — ставим ту же версию pnpm, что в package.json
RUN npm install -g pnpm@11.13.1
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ .
RUN pnpm build

FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
