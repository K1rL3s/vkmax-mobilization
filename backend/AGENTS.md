# AGENTS.md - zheka backend

`CLAUDE.md` is a symlink to this file.

## What this is

Backend of "Жэка Коммуналкин", the MAX messenger hackathon entry for the
"Умный город" track. FastAPI on gunicorn serves the mini-app API and, in the
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
`slotscheck`'s scanned-class count varies between runs on an unchanged tree,
so it is not evidence of anything and does not belong in a report or a
review finding.

## Invariants

- Dependency versions are pinned exactly (`==`); `uv.lock` is committed.
  Build backend is `uv_build`, flat layout, package at repo root.
- `maxo` is pinned to `0.9.0`, which caps `redis<9` - hence `redis==8.1.0` and
  `taskiq-redis==1.2.3`. Do not raise `redis` until maxo lifts the ceiling.
- The webhook must answer 200 within 30 seconds. `handle_in_background=True`
  gives that for free, but a handler still must not do IO of unknown length -
  no file download, no OCR, no LLM call - and queues a taskiq task instead.
  Rendering its own window is the handler's answer, not such IO.
- The bot's screens are `maxo.dialogs`: a screen with buttons is a `Window` in
  a `Dialog`, never a hand-built keyboard with its own callback data and never
  a stored message id. A handler answers through its dialog manager, and a new
  flow is a package under `zheka/bot/handlers/` added to the include list in
  `make_dispatcher`.
- `MaxSender` is for broadcasts and for opening a window from a task. It owns
  the platform ceilings (30 rps per bot, 2 messages per second per chat),
  which earn their bookkeeping when one event fans out to many chats. One
  destination is one bucket: both `send_message` and `start_dialog` key the
  per-chat limiter on `max_user_id`, because a private dialog's chat id and
  user id are different integers and keying them apart would hand the same
  resident two buckets and double the ceiling. An ordinary handler answers
  through its dialog and does not inject it.
- A task opens or replaces a window only through `MaxSender.start_dialog`,
  which wraps `BgManager.fg()`. Not `bg().start()`: that one hands the update
  to `call_soon` and returns at once, so the task would commit before the
  message is sent and a failed send would surface as an unretrieved task
  exception. For the same reason its default mode is `RESET_STACK` and not
  `StartMode.NEW_STACK`: `DialogManager._start_new_stack` re-enters
  `BgManager.start()` and goes through `call_soon` again, which voids the
  guarantee `fg()` was chosen for. A window that needs a stack of its own
  passes `stack_id` and stays synchronous. A user with no `users.max_chat_id`
  or with a `bot_stopped_at` is skipped with a log line - a background manager
  addresses a chat, `NULL` there means the user never started the bot, and a
  stopped bot earns a 403 from MAX, exactly as the broadcast query already
  filters out.
- Every router and dialog of the private flow sits under one parent router
  (`private_router` in `make_dispatcher`) whose `message_created`,
  `message_callback` and `bot_started` observers carry `PRIVATE_ONLY`. A
  router whose own observer filter fails returns `UNHANDLED` without touching
  its children, so that one filter closes the whole subtree and no handler
  repeats the condition. Never call `.filter()` on a `Dialog`'s observers:
  `Dialog._setup_filter` already put an `IntentFilter` there and `filter()`
  assigns rather than appends, so yours would silently break the dialog's
  routing. Filters are set before startup - maxo refuses them afterwards, and
  refuses `include` afterwards too.
- The error router answers a `MessageCallback` with a callback notification and
  a `MessageCreated` with a message: a handler that returns `None` counts as
  handled for maxo's `ErrorMiddleware`, so an unanswered branch loses the error
  entirely. It lives outside `private_router` and resolves nothing from
  dishka: maxo registers `ErrorMiddleware` as the first outer middleware of
  `dp.update`, so by the time an exception reaches the router the session is
  rolled back and the request container is closed. It follows that the menu
  window renders without a single service - the error router restarts it.
- `zheka/bot/middlewares/user.py` upserts the `users` row from every update
  and puts the `User` into the middleware data under `user`, so no handler or
  getter repeats it. It is `inner` on `dp.update` and after
  `TransactionMiddleware`. Two rules it must keep: the chat id is written only
  when the update comes from `ChatType.DIALOG`, and `upsert_by_max_id` keeps
  the old one with `coalesce` - a message from a house chat would otherwise
  wipe it and every task would silently stop opening windows for that user.
  On a `DialogUpdateEvent` the user is a `FakeUser` built from ids with an
  empty name, so there the middleware only reads the row.
- `BOT_START` is recorded once, in the `/start` and `bot_started` handler. Not
  in the fallback router - an update with no state is not a start - and not in
  a window getter, which re-runs on every re-render.
- `notify` is passed explicitly everywhere: the API default is sound on, the
  product default is silent. A dialog window is the one place the flag travels
  in a `ContextVar` (`dialog_notify` in `zheka/infra/max/sender.py`), because
  maxo 0.9.0 hardcodes `notify=True` inside `MessageManager.send_message`;
  `ZhekaMessageManager` reads the var there. Only `start_dialog` raises it.
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
- `trace_id_middleware` registers last among the http middlewares, so it wraps
  logging and the transaction and every log line and error body carries a trace
  id. Middleware order lives in one place, `setup_middlewares` in
  `zheka/api/app.py`, and registration order is the stack inside out: the last
  registered is the outermost.
- A dishka REQUEST container always belongs to exactly one decider, and there
  are exactly three: `transaction_middleware` for an http request (commits only
  on a response below 400), `CommitMiddleware` for a taskiq task (commits on a
  result without an error), and `TransactionMiddleware` in `zheka/bot/` for a
  bot update (commits when the handler returns). Each of them commits the
  session and then flushes the `TaskPublisher`; each rolls back on an
  exception. No provider and no route commits - the session provider keeps a
  rollback as a backstop only. A new entry point that opens a REQUEST container
  brings its own decider, otherwise its writes are silently dropped.
- The provider cannot decide the transaction itself: domain errors are turned
  into responses by `ExceptionMiddleware`, which sits inside the dishka
  container, and dishka finalizes a provider generator with `agen.asend(exc)`,
  so an exception arrives as a value and never as a raise.
- The bot's `TransactionMiddleware` registers `inner` on `dp.update`, because
  `DishkaMiddleware` is registered later, by `setup_dishka`, and an outer
  middleware from `make_dispatcher` would sit outside the container. It follows
  that a dispatcher from `make_dispatcher` is only usable once
  `setup_maxo_dishka` has wired it: without that, every update raises
  `KeyError` on `ctx[CONTAINER_NAME]`, and maxo's error middleware logs and
  swallows it, so the bot goes quiet instead of failing loudly.
- One dispatcher per process, in two processes of three: the api builds it in
  `app_factory`, the worker in `zheka/broker/broker.py` (a background manager
  feeds its update into a dispatcher in the same process), and the scheduler
  only enqueues and builds none. Routers and dialogs are module-level
  singletons, so calling `make_dispatcher` twice raises
  `RouterAlreadyIncludedError`, and maxo forbids `include` after startup.
- `make_dispatcher` returns a `BotSetup`: the dispatcher and the
  `BgManagerFactory` that `setup_dialogs` returned. That factory is the only
  way to get the one the dialog middlewares were registered with, so both go
  into the container context and nothing rebuilds `BgManagerFactoryImpl(dp)`.
  `app_factory` takes a ready `BotSetup` - that argument exists so a test can
  own the process's single real dispatcher.
- `zheka/api/asgi.py` builds the app at import time and therefore needs a real
  environment. It is excluded from slotscheck for that reason; import
  `app_factory` from `zheka.api.app` if you need the app without an env.
- The api process is started by the `gunicorn` CLI and never from Python:
  `gunicorn -c gunicorn.conf.py zheka.api.asgi:app`. The worker is gunicorn's
  own ASGI worker (gunicorn 26), so uvicorn is not in the tree at all; it picks
  uvloop up by itself when the `fast` group is installed.
- `gunicorn.conf.py` is the server's own config, read by the master before the
  application is importable, so it imports nothing from `zheka` and repeats the
  one value it needs (`polling`) as a literal. It owns `bind` (`API_HOST` /
  `API_PORT`, defaulting to the `0.0.0.0:7001` that nginx and the healthcheck
  expect) and `workers`, so `ApiConfig` carries `cors` and nothing else.
- The worker count is not configurable and there is no `API_WORKERS`: an async
  worker saturates one CPU, so `gunicorn.conf.py` takes one worker per logical
  CPU - `sched_getaffinity`, falling back to `cpu_count`, both of which count
  hardware threads rather than physical cores, and neither of which sees a
  cgroup cpu quota. `MAX_BOT_MODE=polling` overrides that to exactly one.
- `--preload` stays off. Every worker imports `zheka.api.asgi` in its own
  process and builds its own dispatcher, container and connections; preloading
  would fork them out of the master and break both.
- `BOT_MODE=polling` runs long polling from the api lifespan, so local work
  needs neither a domain nor a certificate. The lifespan runs per worker, which
  is why polling pins the worker count to one - two workers mean two pollers on
  one bot. `BOT_MODE=webhook` is production and requires `MAX_WEBHOOK_URL` on
  443 with a real certificate.
- Migrations are applied by the `migrations` compose service only. The api
  process does not run alembic, so three containers never race on it.
- Env var names follow the family canon: `POSTGRES_*`, `REDIS_DB`,
  `LOG_LEVEL`, `LOG_FORMAT`, `API_HOST` / `API_PORT`.
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
- Every fractional quantity is a scaled integer. No `Decimal` and no `float`
  in charge, consumption or quorum math - the scale is part of the unit, the
  arithmetic is integer, and rounding happens exactly once, explicitly:

  | Quantity | Python | Column | Unit |
  |---|---|---|---|
  | money | `int` | `BigInteger` | kopeck, 1/100 rouble |
  | tariff rate | `int` | `BigInteger` | 1/10000 rouble per unit |
  | area | `int` | `Integer` | 1/100 square metre |
  | volume, meter reading | `int` | JSON number | 1/1000 cubic metre, kWh on the same scale |
  | percent | `int` | - | 1/100 of a percent, so 50% is `5000` |

  Latitude and longitude are the one exception and stay `Numeric(9, 6)`: they
  feed a distance formula, where a scaled integer only gets in the way.
  A scaled field never carries a unit suffix in its name. The unit lives in the
  Russian `Field(description=...)` in `api/schemas/`, which puts it in OpenAPI,
  and in a short comment on the entity field.
- There is no production database yet, so a correction to the existing schema
  regenerates the initial migration instead of stacking a corrective revision
  on top of it. The history stays one file until the first deploy, and a
  developer picks the change up by recreating the local database. This covers
  corrections only - all 32 tables already exist, so it should be rare. Once
  something is deployed, this rule dies and every change is a new revision.
- A repository builds a statement into a named `stmt` and executes it on the
  next line - never inline, and never modified again at the call site
  (`stmt = stmt.order_by(...)` first, then `execute(stmt)`). This holds for
  `select`, `update`, `delete`, `insert` and for `.scalar()` / `.scalars()`
  alike, and it keeps a repo method readable top to bottom instead of buried
  inside a call's parentheses. `self._session.get(Model, id)` is not used
  either, for the same reason: the query stays visible as a `stmt`, at the
  cost of skipping the identity-map short circuit `get()` gives for free.
