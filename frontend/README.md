# Фронтенд платформы обратного найма ФСП

React + TypeScript + Vite, стили — Tailwind v4 с палитрой ФСП (`src/index.css`), шрифт Montserrat раздаётся локально (`@fontsource-variable/montserrat`).

## Команды

```bash
pnpm install
pnpm dev     # http://localhost:5173, /api проксируется на бэкенд :8000 (make api)
pnpm test    # Vitest + Testing Library
pnpm build   # проверка типов и сборка в dist/
pnpm lint    # oxlint
```

## Устройство

- `src/api/client.ts` — `api()` с CSRF-заголовком `X-Requested-With: fsp` и cookie-сессией; ошибки `problem+json` превращаются в `ApiError`.
- `src/auth/AuthContext.tsx` — текущий пользователь (`/auth/me`), вход и выход.
- `src/pages/` — регистрация (с текстами согласий), вход, подтверждение почты, главная.
- `src/components/` — шапка с демо-переключателем ролей и базовые UI-компоненты.
