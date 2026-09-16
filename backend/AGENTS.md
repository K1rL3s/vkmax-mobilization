# AGENTS.md - zheka backend

`CLAUDE.md` is a symlink to this file.

## What this is

Backend of "Жэка Коммуналкин", the MAX messenger hackathon entry for the
"Умный город" track. FastAPI on granian serves the mini-app API and, in the
same process, the maxo webhook. Background work runs on taskiq over Redis.
Package `zheka`, Python 3.12, all code async.

## Layout

| Path | Purpose |
|------|---------|
| `zheka/api/` | FastAPI app, routes, schemas, dependencies, error mapping. |
| `zheka/bot/` | maxo dispatcher, webhook engine, handlers, middlewares. |
| `zheka/broker/` | taskiq broker, scheduler, background tasks. |
| `zheka/base.py` | `ZhekaType` / `ZhekaMutableType`, the dataclass metaclass. |
| `zheka/core/models/` | Domain entities on `ZhekaMutableType`, no SQLAlchemy import. |
| `zheka/core/` | Domain models, services, errors, enums, event names. |
| `zheka/di/` | Dishka container and providers. |
| `zheka/infra/database/tables/` | `Table` objects and the `map_imperatively` calls binding them to `core/models/`. |
| `zheka/infra/database/` | Repositories; `models/` re-exports the mapped entities for them. |
| `zheka/infra/max/` | Outgoing MAX calls and the platform rate limits. |
| `zheka/logger/` | Formatters, context columns, `setup_logger`. |
| `migrations/` | Linear Alembic history. |
| `tests/` | Empty for now; mirror the app structure when filling it. |

## Commands

Everything goes through `just` (see `justfile`): `format`, `ruff`, `codespell`,
`slots`, `bandit`, `mypy`, `test`, `lint`, `check`, `all`, `migrate`,
`migration <msg>`, `api`, `worker`, `scheduler`, `bump`.

`just check` is the gate: ruff (no-fix) + ruff format --check + codespell +
slotscheck + bandit + mypy strict. Keep it green.

## Invariants

- Dependency versions are pinned exactly (`==`); `uv.lock` is committed.
  Build backend is `uv_build`, flat layout, package at repo root.
- `maxo` is pinned to `0.9.0`, which caps `redis<9` - hence `redis==8.1.0` and
  `taskiq-redis==1.2.3`. Do not raise `redis` until maxo lifts the ceiling.
- The webhook must answer 200 within 30 seconds. `handle_in_background=True`
  gives that for free, but handlers still must not send messages, run OCR or
  call an LLM inline - they queue a taskiq task instead.
- `MaxSender` is for broadcasts only. It owns the platform ceilings (30 rps
  per bot, 2 messages per second per chat), which earn their bookkeeping when
  one event fans out to many chats. An ordinary handler answers through the
  update facade (`update.send_message(...)`) and does not inject it.
- `notify` is passed explicitly everywhere: the API default is sound on, the
  product default is silent.
- Event names are `EventType` members in `zheka/core/enums/events.py`. Never write
  the string at the call site.
- `EventsService.record` writes its event on a savepoint, so it also flushes
  whatever else is pending on the caller's session at that point. Call it
  after the business action's own flush, not in the middle of building it.
- Any plain data class inherits `ZhekaType` from `zheka/base.py` instead of
  carrying its own `@dataclass` decorator. The metaclass applies
  `dataclass(frozen=True, slots=True, kw_only=True)`; `ZhekaMutableType` is
  the mutable variant, a single class opts out with
  `class Foo(ZhekaType, frozen=False)`, and a class that declares its own
  `__slots__` is left alone. Pydantic stays in `api/schemas/` - that is
  serialization, not domain data. An entity in `core/models/` subclasses
  `ZhekaMutableType` instead of `ZhekaType`, because a class mapped with
  `map_imperatively` cannot be frozen or slotted (SQLAlchemy needs to set
  `_sa_instance_state` and hold a weakref to the instance).
- Domain errors are axes off `ZhekaError` in `zheka/core/errors.py`.
  `api/errors.py` maps them to statuses in the `exception_handlers`
  comprehension; add an axis to that tuple, not a new handler.
  `ZhekaError.__init_subclass__` fills `title` from the class name, so never
  declare `title` in a subclass body. Each axis carries a default message, so
  `raise NotEnoughRights()` still produces a usable `detail`.
- `InvalidRequest` deliberately does not inherit `ValueError`: otherwise the
  `ValueError` handler would answer 409 instead of 400.
- `trace_id_middleware` registers last, making it the outermost middleware, so
  every log line and error body carries a trace id.
- One dispatcher per process. Routers are module-level singletons, so calling
  `make_dispatcher` twice raises `RouterAlreadyIncludedError`. `app_factory`
  owns the only one.
- `zheka/api/asgi.py` builds the app at import time and therefore needs a real
  environment. It is excluded from slotscheck for that reason; import
  `app_factory` from `zheka.api.app` if you need the app without an env.
- `BOT_MODE=polling` runs long polling from the api lifespan, so local work
  needs neither a domain nor a certificate. `BOT_MODE=webhook` is production
  and requires `MAX_WEBHOOK_URL` on 443 with a real certificate.
- Migrations are applied by the `migrations` compose service only. The api
  process does not run alembic, so three containers never race on it.
- Env var names follow the family canon: `POSTGRES_*`, `REDIS_DB`,
  `LOG_LEVEL`, `LOG_FORMAT`, `API_HOST` / `API_PORT` / `API_WORKERS`.
- Alembic revision messages, and therefore revision file names, are English:
  `just migration "initial schema"`. The Russian-only rule covers user-facing
  strings, not the migration history.
- Column order in `infra/database/tables/` is argument order in `Table(...)`.
  Most tables start with `id_column(), created_at_column()[,
  updated_at_column()]` from `tables/_columns.py`; a table whose primary key
  is a natural column instead (`chats.chat_id`, `org_invites`/`flat_invites`
  `.code`, `org_settings.org_id`) starts with that column instead.
- Cross-organization isolation has exactly one tool: `scoped_to_org` in
  `infra/database/repos/scopes.py`. A repo method that takes a `house_id`,
  `flat_id` or `org_id` straight from a path parameter checks no ownership of
  its own, so the caller scopes the query or the route leaks across
  organizations. A foreign id answers `EntityNotFound` (404), never
  `NotEnoughRights` (403) - a 403 confirms the id exists.
