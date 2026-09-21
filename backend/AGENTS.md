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
| `zheka/seed/` | `just seed`: the directory, the demo organizations and their history; `data/` holds the committed CSVs and images. |
| `scripts/` | `fetch_seed_data.py`, the one-off download that wrote `zheka/seed/data/`. |
| `migrations/` | Linear Alembic history. |
| `tests/` | Empty for now; mirror the app structure when filling it. |

## Commands

Everything goes through `just` (see `justfile`): `format`, `ruff`, `codespell`,
`slots`, `bandit`, `mypy`, `test`, `lint`, `check`, `all`, `migrate`,
`migration <msg>`, `api`, `worker`, `scheduler`, `seed`, `bump`.

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
- Dialog state goes through a `BaseDialogData` subclass from
  `zheka/bot/dialog_data.py`, one per dialog, serving both `start_data` and
  `dialog_data`, and is never read or written by string key. A start site
  passes `SomeData(...).to_data()`, a reader calls `load` or `load_start`, a
  writer goes through `proxy`. `dump` merges with `update` so foreign keys
  survive, and `proxy` has no `try/finally` so a body that raised persists no
  half-mutation. A dialog whose start data must outlive the first window
  copies it into `dialog_data` once, in its `on_start`, as onboarding does.
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
  passes `stack_id` and stays synchronous. Without one it lands on the default
  stack and throws away whatever the resident was doing there, so a caller that
  replaces its own window passes the stack id it started from and a caller that
  interrupts out of nowhere is deciding to interrupt. A window that announces
  something new passes `show_mode=ShowMode.SEND`: in its own stack maxo edits
  the stack's last message in place, which may sit far up the history, so a
  reassignment back to the same executor would change an old card silently. A
  re-render after the user's own action keeps the default and edits the card
  they just tapped. A user with no `users.max_chat_id`
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
- The error router answers a `MessageCallback` with a callback notification, a
  `MessageCreated` by replying and a `BotStarted` by writing into the chat: a
  handler that returns `None` counts as handled for maxo's `ErrorMiddleware`,
  so an unanswered branch loses the error entirely - a dead invite link would
  be silence. It lives outside `private_router` and resolves nothing from
  dishka: maxo registers `ErrorMiddleware` as the first outer middleware of
  `dp.update`, so by the time an exception reaches the router the session is
  rolled back and the request container is closed. It follows that the menu
  window renders without a single service - the error router restarts it.
- `zheka/bot/middlewares/user.py` upserts the `users` row from every private
  update and puts the `User` into the middleware data under `user`, so no
  handler or getter repeats it. It is `inner` on `dp.update` and after
  `TransactionMiddleware`. It upserts only on `ChatType.DIALOG`: an admin bot
  receives every message of a house chat, and an upsert there would create a
  row, name and username, for every member who writes - none of whom gave
  consent. On any other chat type it only reads the row, and the same goes for
  a `DialogUpdateEvent`, whose user is a `FakeUser` built from ids with an
  empty name. `upsert_by_max_id` keeps the old chat id with `coalesce`, and
  that is load-bearing: the mini-app upsert in `api/dependencies/current_account.py`
  passes no chat id on every request and would otherwise wipe `max_chat_id`,
  cutting the resident off from every window a task opens. It clears
  `bot_stopped_at` whenever it is given a chat id: a private update proves the
  dialog is alive, and without that a resident who stopped the bot once would
  never get a window or a broadcast again. A mini-app request is no such proof
  and keeps the mark.
  `BotStopped` is itself a private update, so the middleware clears the mark
  and the `bot_stopped` handler sets it again in the same transaction.
- `BOT_START` is recorded once, in the `/start` and `bot_started` handler. Not
  in the fallback router - an update with no state is not a start - and not in
  a window getter, which re-runs on every re-render.
- `deeplinks_router` sits ahead of `commands_router` under `private_router`,
  because a deeplink and a bare `/start` arrive as the same `BotStarted` and
  maxo stops at the first handler that returns anything but `UNHANDLED`. A
  payload it cannot parse returns `UNHANDLED` explicitly, so the start falls
  through to `/start` and is recorded exactly once; returning `None` would
  consume the update and leave a typo'd link with a mute bot.
  `BotStarted.payload` is `Omittable[str | None]` - three states, so it is read
  through `is_not_defined` and never through a magic filter on truthiness.
  Consent comes before every way into a house: the payload rides into
  `Consent.ask` as `start_data`, `on_accept` resumes it instead of falling back
  to the menu, and `HousesService.link` refusing a user without `consent_at` is
  the backstop under the routing.
- `notify` is passed explicitly everywhere: the API default is sound on, the
  product default is silent. A dialog window is the one place the flag travels
  in a `ContextVar` (`dialog_notify` in `zheka/infra/max/sender.py`), because
  maxo 0.9.0 hardcodes `notify=True` inside `MessageManager.send_message`;
  `ZhekaMessageManager` reads the var there. Only `start_dialog` raises it.
- Event names are `EventType` members in `zheka/core/enums/events.py`, and the
  `source` of a start, an open or a link is an `EventSource` member beside
  them. Never write either string at the call site.
- `RequestChannel.CHAT` is written nowhere yet: nothing but the mini-app and
  the bot dialog can open a request, and the dialog knows only that it is the
  bot. The task already takes `channel`, so the seam is there for when the
  product gives a chat a way to start a request. The spec has none: a house
  chat gets announcements and one link button, and no interaction.
- `HousesService` records `HOUSE_SEARCH` and `HOUSE_LINKED` itself, in `search`,
  `nearest` and `link`. A bot handler's whole job for those two is to pass the
  right `source: EventSource` and `entrance` into `link()`; recording them a
  second time double-counts every onboarding.
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
  are exactly four: `transaction_middleware` for an http request (commits only
  on a response below 400), `CommitMiddleware` for a taskiq task (commits on a
  result without an error), `TransactionMiddleware` in `zheka/bot/` for a
  bot update (commits when the handler returns), and `zheka/seed/__main__.py`
  (commits once, when `seed` reports it wrote something). The first three
  commit the session and then flush the `TaskPublisher`; the seed never
  flushes it, because nothing it creates may notify anyone. Each rolls back on
  an exception. No provider and no route commits - the session provider keeps a
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
- `FilesService` owns the size and mime ceiling on both paths into the file
  directory. `save(UploadFile)` is the route's; `save_download(content_type,
  download)` is the bot's, and it repeats the same mime whitelist, the same
  `max_size_mb` and the same `unlink(missing_ok=True)` cleanup. Both count
  bytes as they write them and raise mid-stream: `Bot.download` checks nothing
  and streams for its whole 30-second timeout, so a ceiling applied to the
  finished file would bound the disk by link throughput rather than by
  `max_size_mb`. Hence `save_download` hands the downloader a counting writer
  around the open file instead of a path.
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
- An executor's authority over a request is the assignment **and** the
  membership: `executor_user_id` equal to the user and an `OrgRole.EXECUTOR`
  row in the house's org. An executor removed from the org keeps
  `executor_user_id` and a live card, so the assignment alone is never enough.
  `AdminRequestsService.executor_advance` checks both before its first write,
  because `attach_result_photo` catches the refusal and renders the card anyway;
  `executor_card` asks the same question as a bool and returns `None`, since a
  getter that raised would drop the old card into the error router.
- The author's review card is queued in `AdminRequestsService._move`, the one
  road into `ON_REVIEW` for the executor, the cabinet and a group move alike.
  It replaces the plain status text rather than joining it, and a request
  without an author gets neither.
- A card's stack id is derived from its request, never stored:
  `executor-{request_id}` and `review-{request_id}`. A resent card replaces the
  one already in that stack instead of opening a second live copy, and an
  explicit `stack_id` keeps `MaxSender.start_dialog` synchronous.
- A value the bot hands a service is checked in the service. `Select` passes
  `on_click` the raw callback string without matching it against the rendered
  items, and a button hidden by `when=` still fires from an old keyboard, so
  `when=` is presentation only: the rating range lives in `RequestsService.rate`
  (the API schema imports `MIN_RATING` / `MAX_RATING` from there) and the
  executor's transitions in `executor_advance`.
- maxo 0.9.0 delivers a text or a photo only to the default stack
  (`IntentMiddleware.process_message` loads `DEFAULT_STACK_ID`), so a window
  that waits for input cannot live in a card's own stack. `ask_in_default_stack`
  in `zheka/bot/cards.py` opens it there on the user's own tap, through
  `bg().start()`: `fg()` from inside a handler deadlocks, because
  `_get_fake_user` hands the nested update the real `User`, its
  `UserMiddleware` upserts the `users` row the tap's uncommitted transaction
  already holds, and the tap waits for the nested update. It starts with
  `ShowMode.SEND`, because for a dialog event in a private chat maxo picks
  `EDIT` and would rewrite whatever message the default stack showed last. The
  prompt replaces what the user had there, a half-filled request draft
  included. Once the input is taken, `back_to_menu` leaves the default stack on
  `Menu.main` with a notice rather than on a buttonless window that swallows
  every message. The service behind the prompt checks the state again
  (`RequestsService.reject` refuses anything but `ON_REVIEW`), since the prompt
  outlives the card it came from.
- A tap on a stale card is not an error. The executor and review handlers catch
  `ZhekaError`, answer the callback with its text and return, so the getter
  re-renders the truth ("передали другому", a closed request with no buttons).
  That is safe only because those services refuse before their first write.
- A task that changes a request and then renders a window reading it does not
  render it itself: the window's getter runs in another session and would see
  the status from before the task's commit. `attach_result_photo` publishes
  `send_executor_card` instead, which the publisher flushes after the commit,
  and passes its own `user_id`: the card is re-rendered for the one who sent
  the photo, who may no longer be the assignee.
- A task body is tested through the `task_broker` fixture: an `InMemoryBroker`
  with `ContainerMiddleware` and `CommitMiddleware`, run by
  `task.kicker().with_broker(task_broker).kiq(...)`. It commits and flushes
  like the worker, and whatever the task publishes lands in `bot_broker`
  instead of running, so a test runs the follow-up itself.
- A chat is bound when `house_id IS NOT NULL`, `bound_at IS NOT NULL` and
  `status == ACTIVE` - `BOUND_CHAT` in `infra/database/repos/chats.py`, the one
  expression the house card and the announcement fan-out share. A bot removed
  from a chat keeps `bound_at`, so `bound_at` alone would call a chat nobody can
  reach bound. The fan-out also needs `bot_is_admin`: a non-admin bot cannot
  write into a MAX chat.
- Every `bot_added` is a fresh binding: `ChatsRepo.upsert_added` clears
  `house_id`, `bound_by`, `bound_at` and `bot_is_admin`, because whoever re-adds
  the bot may not be the one who bound it, and an inherited binding would skip
  the check of their rights. That check lives in `ChatsService.bind`: staff of
  the house's org (`is_staff`, so not an executor) or its active chairman,
  otherwise `NotEnoughRights`; the house arrives as the raw `Select` string.
- The chat handlers (`bot/handlers/chats/router.py`) and the lifecycle
  handlers (`bot/handlers/lifecycle.py`) sit outside `private_router`. The
  `bot_added` handler only queues `on_bot_added`; the task reads the title,
  leaves a channel or a chat whose initiator the bot cannot reach privately or
  who is neither staff, chairman nor an active resident, and opens the binding
  window. `ChatBinding.house` and `rights` live in the derived stack
  `chat-{chat_id}`; `ChatBinding.code` waits for text and therefore opens on
  the default stack. No binding window reads the `chats` row: the title and the
  chat id ride in `ChatBindingData`, because the window is rendered in another
  session than the task that wrote the row.
- MAX sends no event when the bot's rights change, so they are asked for:
  `is_chat_admin` in `infra/max/sender.py`, on the "Готово" tap and after every
  failed send in `broadcast_to_chats`. `ChatsService.set_admin` records
  `CHAT_ADMIN_GRANTED` and queues the welcome only on the `false -> true` edge.
  A failed chat send whose re-check finds no rights opens `ChatBinding.rights`
  for `bound_by` with sound, since a bot without rights silences the house.
  `is_chat_admin` goes through `BOT_RATE_LIMIT`, because the broadcast calls it
  once per failed chat; `get_chat` and `leave_chat` in `on_bot_added` bypass it
  on purpose - one call per add, the same weight as a handler's own answer.
- One reading window is one period, the month it opened in. A window that
  wraps the month end (`day_from > day_to`, Moscow's 15th to the 3rd) takes on
  its tail days the readings for the month it opened in, not for the calendar
  month of the day. `window_period` in `core/services/readings.py` is the one
  function that answers "which period does the open window accept":
  `ReadingsService.submit`, `ReadingsService.periods` and the reading reminder
  all call it, and none of them computes the period on its own, since two
  answers would split one window into two periods and remind residents who
  already submitted. The out-of-window choice of past periods is separate.
- A reminder selects its recipients, stamps them and queues the sends in one
  transaction, and never sends from its own body: `RemindersService` writes
  the stamp (`polls.reminder_sent_at`, `appointments.reminder_sent_at`,
  `meters.verification_warned_at`, or a `READING_REMINDER_SENT` event whose
  payload carries `house_id`, `period` and `kind`, since each house has its own
  window; a resident of two houses reminded the same day gets one text and a
  stamp in each) and hands the text to
  `NotificationsService`, whose publisher flushes only after the commit. A run
  that dies before its commit sent nothing and stamped nothing; a rerun after
  it sees the stamps. The reminder date logic takes `today` or `now` as an
  argument and the task passes `datetime.now(UTC)`, which is what lets a test
  pin the day. The reading reminder checks `window_period`, the very function
  `ReadingsService.submit` writes by: another period would remind those who
  already submitted, and a window across the month end is one period, the
  month it opened in. The access window is the one broadcast that opens a
  window instead of sending text: `AccessService.create` queues
  `broadcast_access_request`, which opens `AccessSlots.pick` in the derived
  stack `access-{access_request_id}` with `ShowMode.SEND`.
- An analytics number is computed once, in SQL. Each metric is one
  expression in `_METRICS` in `infra/database/repos/analytics.py`, shared by
  the dashboard tile and the benchmark, so an organization sees the same value
  on both screens. Overdue is `overdue_at` from `repos/requests.py`, built from
  `CATEGORY_RULES` and shared with the admin list filter - never a second
  table of hours. A share is `share()` there: true division (SQLAlchemy 2's
  `/` casts the divisor to numeric, `//` would floor), 1/100 of a percent, one
  rounding. A rating goes out in `MetricUnit.POINTS`, hundredths of a point,
  because `count` means unscaled. A median is `percentile_cont` cast to numeric before
  its one rounding, so a half rounds away from zero like a share does.
- The benchmark names nobody, and a name is not the only leak. A region or
  city row with one organization is that organization's number, and a
  platform of two hands the caller its own value, the median and "1 из 2",
  from which the other value follows by subtraction. Hence `MIN_ORGS_FOR_CUT
  = 3` in `core/services/analytics.py`, one constant for both: a cut with
  fewer organizations having data is dropped in SQL, and a platform metric
  with fewer keeps the caller's value with `platform_median`, `rank` and
  `total` set to `None`. The caller counts toward the three. The threshold
  covers a cut's complement too: a row stays only if the organizations of its
  parent left outside it number 0 or at least three, since the parent's
  median against the cut's gives the value of a lone one outside, and `total`
  against `orgs_count` tells which region it sits in. A region's parent is
  the platform; a city is checked against its region and against the
  platform, because its region row may be hidden while the platform median is
  not. Peers are
  registered organizations of the caller's own `is_demo`: the seeded demo
  history is invented, and a real organization ranked against it, or a demo
  one against a real one, would be compared with fiction.
- The manual reading reminder (`remind_not_submitted`) refuses outside the
  window with `InvalidState` - `window_open` in the season payload is only a
  hint for the button - and reminds the period `window_period` gives, the
  same one `submit` writes. It reuses the scheduled reminder's selection and
  stamps `kind: manual`, but skips anyone who got any reading reminder since
  the start of the day, so ten presses are one message and a press yesterday
  does not silence today.
- Real where it is public, fictional where it would be a claim. Every
  organization from the registry (`zheka/seed/data/organizations.csv`) is
  seeded unregistered and without staff or history, so "УК не подключена" is
  true about it, and it is linked only to a house whose reformagkh card names
  it, matched by name within the region and dropped when the name is
  ambiguous. Every registered organization is fictional, named «Демо-УК ...»,
  `is_demo = True`, and its INN fails the INN checksum (`DEMO_INN` and the
  four peers in `PROFILES`), so it collides with no real registration. Nothing
  real-world is invented: no licence number, no cadastral number
  (`houses.cadastral_no` is nullable because the open data has none), no
  photo - the seed's images are generated and live in `zheka/seed/data/files/`.
  A fictional organization takes a house whose card names no manager wherever
  its city has one, and replaces a real link only where the street has too
  few: Москва has one such house (61/1, the demo house) and needs five. The
  replaced links, exactly: Ленинский проспект 7 (ГБУ «Жилищник района
  Якиманка»), 13 (ГБУ ЭВАЖД), 16 and 20 (ООО «Жилищник»). The replacement
  says nothing about the real organization, but those four buildings read
  "connected" with invented history. `test_a_real_manager_is_replaced_only_in_moscow`
  holds the rule; a peer's second house moving from Казань to
  Санкт-Петербург (one unmanaged house there) breaks it.
- Seeded people can never be reached or impersonated: every seeded user has a
  negative `max_user_id` and `max_chat_id NULL`. A real MAX id is positive and
  arrives only signed in `initData`, and a `NULL` chat is what `MaxSender` and
  the broadcast queries already skip, so a reminder, card or announcement that
  lands on seeded data sends nothing.
- The seed is one transaction with one guard: the organization with
  `DEMO_INN` exists, so the seed ran, logs that and returns `False`. There are
  no per-row upserts; changing seeded data means recreating the database. It
  never touches the network, takes `today` as an argument (history is the six
  months before it, strictly before its midnight UTC), and draws randomness
  from `random.Random` seeded with a string per entity (its address, a flat's
  house and number), never from the global generator. The history rows it
  writes (`REQUEST_ASSIGNED` events, status log, readings) are data with past
  timestamps, not records of actions, so they are written as rows and not
  through the services that record the live ones. It leaves no request
  `ON_REVIEW`: the scheduler would auto-close it and write to the author.
- The benchmark's cut rules decide the seed's layout: all five fictional
  organizations have request history in Москва, a federal city where region
  and city coincide, so the region's complement is 0 and both the region and
  the city rows survive `MIN_ORGS_FOR_CUT`. Their profiles differ on every
  metric, and `test_seed.py` asserts five distinct ranks per metric; moving a
  peer out of Москва hides the cut rows. Repeats of the last 30 days are a
  count per house (`recent_repeats`), older ones a share: a percent of the
  dozen requests a month holds rounds every organization to the same number.
- `DemoService.activate(user_id)` takes no kind: both demo deeplinks and
  `POST /demo/activate` grant `EMPLOYEE` in the demo organization and a
  verified owner's own flat `Д{user_id}` in the demo house, the one house that
  organization owns. The flat number is derived from the user, so parallel
  activations never race for a number, and every insert goes through
  `ON CONFLICT DO NOTHING`, so ten taps are one membership, one residency and
  one flat. The flat is furnished by `DemoService.furnish`, the same code the
  seed uses for the demo house's flats: meters, seven monthly readings (the
  first is the baseline), six charges built with `ChargeLine` and
  `to_kopecks`, and the current period left open. No seed is
  `EntityNotFound`; a user without `consent_at` is `NotEnoughRights`, the
  backstop under the route's and the bot's consent gates, as in
  `HousesService.link`. The reviewer's account number ends with the flat
  number `Д{user_id}`, so it never equals a seeded flat's. The kind changes only the bot's notice.

## Orientation

Facts that each cost one block half an hour to rediscover. They are here so
the next agent does not pay for them again.

- The plan and the block history live in `.superpowers/sdd/` at the repository
  root, not under `backend/`: `backend-mvp-plan.md` holds blocks 1 to 22,
  `progress.md` is the ledger of closed blocks with their commit ranges,
  `task-N-brief.md` the controller decisions for a block and
  `task-N-review.md` its review findings. The ledger answers "which commit
  belongs to which block" more reliably than `git log` does.
- One refactor is decided and waiting: `refactor-startapp-routing.md` (base64
  json in `startParam` so a deeplink can land on a mini-app screen). It waits
  for its frontend half and blocks no backend block; block 16 has no mini-app
  screen to route to.
- The forty-five `EventType` members divide with nothing left over: 36 + 4
  + 2 + 3. Thirty-six are recorded **inside** `core/services/`, so a bot
  handler or a route that records one of those again doubles the statistic -
  pass the service the right `source` or `method` and let it write; `CHAT_BOUND`
  and `CHAT_ADMIN_GRANTED` are among them, in `ChatsService`, and so are
  `READING_REMINDER_SENT` and `APPOINTMENT_REMINDER_SENT`, in
  `RemindersService`. Four are recorded
  in bot handlers: `BOT_START` in `bot/handlers/commands/start.py`,
  `BOT_STOPPED`, `BOT_MUTED` and `BOT_UNMUTED` in `bot/handlers/lifecycle.py`.
  `MINIAPP_OPEN` and `ANNOUNCEMENT_CLICK` are recorded by `POST /me/events`,
  where the client sends the type in the body, so no `EventType.MINIAPP_OPEN`
  appears at any `record` call and grep alone will tell you they are written
  nowhere; the `Literal` in `TrackEventRequest` is the whitelist, and those two
  are the only events a client may send. The remaining three have no writer yet
  and get one in their own block: `REQUEST_EXPORTED`, `LLM_SUGGESTED`,
  `LLM_ACCEPTED`.
- The truth about maxo is in the installed sources,
  `.venv/lib/python3.12/site-packages/maxo/`, never in the plan and never from
  memory - the plan was wrong four times in block 15 and reading the source
  found every one. `python -c "import inspect, X; print(inspect.getsource(X.f))"`
  is cheaper than opening the file.
- Tests use two databases, the main one and `zheka_bot`. An api test runs
  inside a transaction that is rolled back, while a bot window commits for
  real through `TransactionMiddleware`, so its rows landed in other tests'
  assertions over the whole `events` table. That is isolation, not
  concealment. The dispatcher is built once per session by the real
  `make_dispatcher`; a second call raises `RouterAlreadyIncludedError`.
- A new guard is closed by a test that goes red when **that one** guard is
  removed, proved by running it rather than by reasoning about it, and
  reported per guard - never as an aggregate row covering several. A guard
  that cannot be killed is an honest gap, not a reason to invent a test.
- The seed runs once into an empty database: to reseed, recreate the local
  database (`docker compose down -v` drops the volume), `just migrate`, then
  `just seed`. The history ends at the seed date, and the dashboard and the
  benchmark read a rolling 30 days, so `just seed` runs on the deploy closest
  to judging: after about three weeks the benchmark thins out, after 30 days
  it is empty. A reseed wipes every reviewer's flat and membership. `uv run python scripts/fetch_seed_data.py` rewrites the CSVs in
  `zheka/seed/data/` from reformagkh.ru and Nominatim; its downloads are
  cached in `backend/.cache/seed/` (gitignored), so a rerun with a warm cache
  touches no network. A cold run makes about 330 requests 1.1 s apart and
  took twenty minutes, most of it reformagkh answering slowly.
- `grep --include=*.py ...` fails under zsh with `no matches found`, because
  the shell eats the glob. Quote it or drop it.
