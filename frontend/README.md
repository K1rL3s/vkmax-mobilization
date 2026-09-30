# Фронтенд Жэки Коммуналкина

Мини-приложение MAX: React, TypeScript, Vite, `@maxhub/max-ui`, TanStack Query, MapLibre GL. Типы API генерируются из `../openapi.yaml`. Правила кода - в [AGENTS.md](AGENTS.md)

## Запуск

Нужны Node 24.21.0 и pnpm

```sh
cp .env.local.example .env.local
pnpm i
pnpm dev
```

Vite проксирует `/api` на `DEV_API_TARGET` (по умолчанию `http://localhost`, бэкенд за nginx из `docker compose`), а `/tiles/ofm` и `/tiles/osm` - на OpenFreeMap и OpenStreetMap. Без бэкенда можно поднять мок-сервер `pnpm mock` на порту 31299 и указать `DEV_API_TARGET=http://localhost:31299`

API пускает только с подписанной `initData` из MAX, поэтому приложение целиком работает, только когда его открывает MAX по HTTPS. Чтобы открыть локальный dev-сервер в MAX, `pnpm tunnel` пробрасывает его на удаленный хост через reverse SSH tunnel (переменные `DEV_TUNNEL_*` в `.env.local`, справка - `pnpm tunnel --help`)

## Переменные

| Переменная | Назначение |
|---|---|
| `VITE_API_URL` | Адрес API при сборке, пусто - тот же домен |
| `DEV_API_TARGET` | Куда dev-сервер проксирует `/api` |
| `DEV_TUNNEL_SSH_HOST`, `DEV_TUNNEL_SSH_USER`, `DEV_TUNNEL_SSH_KEY` | SSH-хост, пользователь и ключ для `pnpm tunnel` |
| `DEV_TUNNEL_REMOTE_PORT`, `DEV_TUNNEL_REMOTE_BIND`, `DEV_TUNNEL_LOCAL_PORT` | Порты туннеля, по умолчанию 5022, 127.0.0.1 и 5173 |

## Скрипты

| Команда | Что делает |
|---|---|
| `pnpm dev` | Dev-сервер Vite |
| `pnpm build` | Проверка типов и сборка в `dist/` |
| `pnpm preview` | Раздача собранного `dist/` |
| `pnpm lint`, `pnpm format` | ESLint и Prettier по `src/` |
| `pnpm test` | Тесты `node --test` из `tests/` |
| `pnpm api` | Перегенерировать `src/shared/api/schema/generated.ts` из `../openapi.yaml` |
| `pnpm mock` | Мок-сервер API на порту 31299 |
| `pnpm tunnel` | Reverse SSH tunnel к dev-серверу |
| `pnpm pre-commit` | lint, format и `tsc -b` |

В Docker образ `web` собирает статику командой `pnpm build` и отдает ее через nginx, см. `Dockerfile`
