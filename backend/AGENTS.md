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
  bot. The task already takes `channel`, so the seam is there for Task 17,
  where a house chat becomes a place a request can start from.
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
- The forty-five `EventType` members divide with nothing left over: 32 + 1 + 2
  + 10. Thirty-two are recorded **inside** `core/services/`, so a bot handler
  or a route that records one of those again doubles the statistic - pass the
  service the right `source` or `method` and let it write. `BOT_START` is
  recorded in `bot/handlers/commands/start.py`. `MINIAPP_OPEN` and
  `ANNOUNCEMENT_CLICK` are recorded by `POST /me/events`, where the client
  sends the type in the body, so no `EventType.MINIAPP_OPEN` appears at any
  `record` call and grep alone will tell you they are written nowhere; the
  `Literal` in `TrackEventRequest` is the whitelist, and those two are the
  only events a client may send. The remaining ten have no writer yet and
  get one in their own block: `BOT_MUTED`, `BOT_UNMUTED`, `BOT_STOPPED`,
  `CHAT_BOUND`, `CHAT_ADMIN_GRANTED`, `READING_REMINDER_SENT`,
  `APPOINTMENT_REMINDER_SENT`, `REQUEST_EXPORTED`, `LLM_SUGGESTED`,
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
- `grep --include=*.py ...` fails under zsh with `no matches found`, because
  the shell eats the glob. Quote it or drop it.
