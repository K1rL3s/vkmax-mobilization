# AGENTS.md - zheka backend

FastAPI on gunicorn serves the mini-app API and the maxo webhook in one
process; taskiq over Redis runs background work. `core/models/` entities know
no SQLAlchemy: `infra/database/tables/` maps them imperatively,
`infra/database/models/` re-exports them for repos.

Keep `just check` and `just test` green (tests need Docker: testcontainers).
Format only via `just format`: bare `ruff format` leaves hugged forms COM812
rejects. `just` reads the root `.env`. slotscheck's class count drifts,
ignore it. zsh: quote globs (`--include='*.py'`).

## Runtime

- Pins `==` + `uv.lock`; `maxo==0.9.0` caps `redis<9`: `redis`, `taskiq-redis`
  stay pinned.
- api runs only as `gunicorn -c gunicorn.conf.py zheka.api.asgi:app` (gunicorn
  26 ASGI worker, no uvicorn, no `--preload`: each worker builds its own
  dispatcher, container, connections). `gunicorn.conf.py` imports nothing
  from `zheka`, owns `bind` (7001: nginx, healthcheck) and `workers` (per
  CPU; 1 under polling, since each lifespan polls).
- Worker and scheduler: one process, `python -m zheka.broker`; the scheduler
  kicks via the container's `ZhekaBroker` (`run_scheduler` would run the
  receiving broker's lifecycle twice).
- `python -m` entry points go through `zheka.runner.run` (uvloop under
  `PYTHONOPTIMIZE=1`); api gets uvloop from `asgi_loop = "auto"`. Image: `fast`
  group, gcc kept (`gunicorn-h1c` has no Linux wheels), `-O` bytecode
  precompiled (under `PYTHONDONTWRITEBYTECODE` each process would compile
  everything on start).
- Prod: `MAX_BOT_MODE=webhook`, `MAX_WEBHOOK_URL` on 443 with a real cert and
  `MAX_SECRET_TOKEN` (config refuses a webhook without it); only
  the `migrations` service runs alembic. `asgi_lifespan = "on"`: failed webhook
  startup kills the worker (ERROR + traceback, healthcheck red); under polling
  a rejected token is one ERROR line and the API runs without the bot.
- Worker retries nothing: a MAX send is not idempotent; `MaxSender` swallows
  MAX errors per recipient.
- `api/asgi.py` builds the app at import (needs a real env): import
  `app_factory` from `zheka.api.app`. Env names: `POSTGRES_*`, `REDIS_DB`,
  `LOG_LEVEL`.
- API change -> `just openapi`, or a test fails on the stale root
  `openapi.yaml`.
- Every entry point closes its APP container (api lifespan; worker and seed in
  `finally`): it owns the db pool, bot session and the process's one
  `aiohttp.ClientSession`. Yandex clients set timeouts per request, never on
  that session.

## Conventions

- Data classes inherit `ZhekaType` (`zheka/base.py`: frozen, slotted, kw-only;
  `frozen=False` opts out); `core/models/` entities `ZhekaMutableType`
  (`map_imperatively` can't map frozen/slotted). Pydantic only in
  `api/schemas/`.
- Domain error = axis off `ZhekaError` (`core/errors.py`), text in the
  `message` ClassVar; a new axis joins the `exception_handlers` tuple in
  `api/errors.py` (class name -> `title`). `InvalidRequest` must not inherit
  `ValueError` (-> 409).
- Events (`EventType`/`EventSource`) are recorded in `core/services/`; handlers
  and routes pass `source`/`method`/`entrance` (recording twice doubles
  counts). Exceptions: bot records `BOT_START` (`commands/start.py`,
  `deeplinks.py`; never the fallback router or a getter), `BOT_STOPPED`,
  `BOT_MUTED`, `BOT_UNMUTED` (`lifecycle.py`); the client posts
  `MINIAPP_OPEN`, `ANNOUNCEMENT_CLICK` to `/api/events` (`TrackEventRequest`).
- Repos: every statement is a named `stmt`, executed on the next line; no
  `session.get(Model, id)`.
- Alembic: English messages and names, a new revision per schema change.
- Fractions are scaled ints with one explicit rounding, never
  `Decimal`/`float`: kopecks; tariff 1/10000 rouble per unit (both
  `BigInteger`); area 1/100 m2; volume, readings 1/1000 m3 or kWh; percent
  1/100 (50% = `5000`). Only coordinates are `Numeric(9, 6)`. The unit goes in
  the Russian `Field(description=...)`, not the name.

## Transactions and access

- A REQUEST container has one decider that commits then flushes
  `TaskPublisher`, or rolls back: http `transaction_middleware` (commits below
  400), taskiq `CommitMiddleware`, bot `TransactionMiddleware`,
  `seed/__main__.py` (never flushes). A new entry point brings its own decider
  or its writes vanish. Providers and routes never commit (dishka hands a
  provider the exception via `agen.asend(exc)`). Services publish tasks by
  `TaskName` via `TaskPublisher.publish`, never `.kiq()`, so a rollback sends
  nothing.
- `API_TEST_TOKEN` (empty = off): `Bearer` with it is one synthetic user,
  `API_CHECKER_MAX_USER_ID` (below every seeded id); else `WebAppData` or 401.
  `/demo/activate` gives it only EMPLOYEE of `API_CHECKER_DEMO_NUMBER`, else
  403: the token is public and the jury sits in org 1. Its own requests stop
  at `ACCEPTED` (`change_request_status`): `DATA-API.yaml` `staff_status`
  moves the test request there and fails 409 once it is further. Demo org
  `API_CHECKER_DEMO_NUMBER` is the token's alone (`DemoService._org` refuses
  anyone else) and the token activates no org invite: nobody can block its
  resident, move its test request or give it a second membership (staff
  checks send no `X-Org-Id`).
- Middleware order lives only in `setup_middlewares` (`api/app.py`),
  `trace_id_middleware` outermost, `RequestStateMiddleware` last (gunicorn 26
  shares one `scope["state"]` per worker; without it concurrent requests share
  a dishka container).
- `EventsService.record` writes on a savepoint and flushes the caller's
  session: call it after the action's own flush.
- Cross-org isolation has one tool, `scoped_to_org` (`repos/scopes.py`): repo
  methods taking a path id check no ownership, callers scope. Foreign id ->
  `EntityNotFound` (404), never 403.
- Route and bot uploads go through `save_download`, which counts
  `max_size_mb` while writing (`Bot.download` streams unchecked for 30 s).
- `HousesService.link` never changes a verified resident's flat or role (УК
  moves them); a blocked resident cannot `unlink` (relinking would shed the
  block). An org invite reopened by a member is free unless it raises the
  role, which consumes an activation. A flat invite works only while its
  issuer is a verified unblocked owner of the flat; a poll's creator manages
  it only while an active chairman. `ResidentsRepo.revoke_verification`
  records `(user, flat)` in `verification_revocations`: that user never
  verifies the flat again by account or invite, only by УК approval.
- MVP decision, not a gap: an unverified resident books reception (no cap per
  person), reads house polls and announcements, votes without area weight and
  files requests. Charges, meters, flat residents and weighted votes need a
  verified flat.
- `UploadQuota` (`infra/quota.py`, like `YandexQuota`) caps `POST /api/files`
  per user per api worker (`UPLOAD_CALLS` an hour, then 429): the host nginx
  hides client IPs, so no per-IP limit. Free text in request bodies is
  `FreeText` (4000 chars).
- A poll ballot's rows carry `choice_index` 0..n-1: unique `(poll, user,
  choice_index)` and `(poll, flat, choice_index) WHERE counted_by_area` make a
  racing second ballot insert nothing (`add_vote` -> `ALREADY_VOTED`).

## Bot

- Webhook answers 200 within 30 s: IO of unknown length (download, OCR, LLM)
  goes to a task.
- Screens are `maxo.dialogs` `Window`s, never hand-built keyboards or stored
  message ids; a flow is a package in `bot/handlers/` included in
  `make_dispatcher`. Dialog state lives in the dialog's `BaseDialogData`
  subclass (`bot/dialog_data.py`), never string keys; start data needed past
  the first window is copied in `on_start`.
- Routers are module singletons: one dispatcher per process (api
  `app_factory`, worker `broker/__main__.py`); a second `make_dispatcher`
  raises; no `include`/filters after startup. The only `BgManagerFactory` on
  the dialog middlewares is `BotSetup`'s; `app_factory` takes a ready
  `BotSetup`, so a test owns the dispatcher.
- Transaction and user middlewares are `inner` on `dp.update`; without
  `setup_maxo_dishka` every update dies on `ctx[CONTAINER_NAME]`, silently.
- `private_router` observers carry `PRIVATE_ONLY`: private routers and dialogs
  sit under it, no handler rechecks; chat, lifecycle, error routers sit
  outside. Never `.filter()` a `Dialog`'s observers (replaces its
  `IntentFilter`).
- Error router: answers every update kind (a message with a reply), resolves
  nothing from dishka (container closed), restarts the menu via
  `ask_in_default_stack` only for a user's own private update (no render
  loop), logs unexpected errors with traceback, never re-raises.
- User middleware upserts `user` only in `ChatType.DIALOG` (house chat members
  gave no consent). `upsert_by_max_id` keeps `max_chat_id` via `coalesce`
  (mini-app passes none) and, given a chat id, clears `bot_stopped_at`.
- `deeplinks_router` precedes `commands_router`; an unparsable payload returns
  `UNHANDLED` (not `None`) to reach `/start`. `BotStarted.payload` is
  `Omittable[str | None]` (`is_not_defined`). Consent precedes every way into
  a house: the payload rides into `Consent.ask` as `start_data`, `on_accept`
  resumes it; `HousesService.link` refusing a user without `consent_at` is the
  backstop.
- `notify` is always explicit, default silent. maxo 0.9.0 hardcodes
  `notify=True` for dialog windows, so `ZhekaMessageManager` reads the
  `dialog_notify` `ContextVar`, raised only by `start_dialog`.
- `MaxSender` serves broadcasts and task windows, not handlers, and owns MAX
  limits: 30 rps per bot (`BOT_RATE_LIMIT`), 2 msg/s per chat keyed on
  `max_user_id`. `send_message` drops private sends to negative ids (seeded
  users, the API checker); group sends go (group chat ids are negative too).
- A task opens a window only via `MaxSender.start_dialog` (`fg()`,
  `RESET_STACK`): `bg().start()` and `NEW_STACK` go through `call_soon` and
  let the task commit first. It skips users without `max_chat_id` or with
  `bot_stopped_at` (log line). Without `stack_id` it replaces the default
  stack; to replace its own window a caller passes its stack id. News windows
  pass `ShowMode.SEND` (else maxo edits the stack's last message, maybe an old
  card); tap re-renders keep the default. Stack ids derive from the entity
  (`review-{request_id}`), never stored.
- maxo 0.9.0 delivers text and photos only to the default stack: input
  windows open there via `ask_in_default_stack` (`bot/cards.py`:
  `bg().start()` + `ShowMode.SEND`; `fg()` in a handler deadlocks on the
  `users` row), replacing whatever was there, drafts included; the service
  rechecks state. `back_to_menu` sends the result as its own message, then
  `Menu.main`; `CANCEL` also returns to `Menu.main` (maxo's `Cancel` empties
  the stack).
- Services validate every bot value: `Select` passes raw callback strings;
  `when=`-hidden buttons still fire from old keyboards. A stale card tap is
  not an error: executor and review handlers catch `ZhekaError`, answer the
  callback with its text and re-render (safe: those services refuse before
  their first write).
- A task that changes a request never renders the window reading it (the
  getter sees pre-commit state): it publishes a follow-up
  (`attach_result_photo` -> `send_executor_card`).
- Texts: formal «вы»; every message and button opens with an emoji and a
  space (four-in-a-row flat numbers go bare); no period ending a message or
  line. A result is its own message (`back_to_menu`), never a line above the
  menu. Both `bot_started` handlers set `ShowMode.SEND` first (AUTO edits the
  last message for anything but `MessageCreated`). The consent tap edits its
  message to «✅ Согласие дано»; the next window is new.
- OpenApp buttons carry `app_payload(path)` (`bot/cards.py`) or no payload
  (home); paths come from `core/deeplinks.py`. Notifications take
  `app_button` + `app_path`; `notify_author` always attaches the request's.
- The menu reads the profile: the last linked house, the staff line and
  cabinet button.
- House search and request draft steps have «🏠 Меню» and, past the first,
  «⬅️ Назад» (`TO_MENU`, `BACK`). A search list also takes text: one match is
  chosen, several narrow, none keeps the list and says so; `on_back` clears it.
- `BOT_COMMANDS` (`commands/start.py`) is set by an `after_startup` hook in
  every api worker (the taskiq worker feeds no signals); failure is logged. A
  new command joins it, `/seed` never. Tests call the hook directly (a second
  `AfterStartup` fails in `DialogRegistry.refresh`).

## Requests and chats

- Executor authority = `executor_user_id` **and** an `OrgRole.EXECUTOR` row in
  the house's org (a removed executor keeps the id and a live card):
  `executor_advance` checks both before writing, `executor_card` returns
  `None`.
- The author's review card is queued only in `AdminRequestsService._move`,
  the one road into `ON_REVIEW`. Every status write first takes
  `RequestsRepo.lock` (`FOR UPDATE`, refreshed), so a concurrent tap sees the
  new status. `_move` to the current status is a no-op (no
  log, event, message, notification): a repeated staff status call answers 200
  with the card; backward is `InvalidState(BACKWARD)`.
- New and repeat requests notify org staff (never executor or author) under
  `REQUESTS`, not mandatory. Deadline: `Request.deadline_at`, printed in the
  house's time.
- A house not `is_connected` takes no request and no flat verification
  (`InvalidState(NOT_CONNECTED)`); the bot's category window says so first.
- A phone request with `resident_id` is wholly that resident's (author, flat,
  notifications, review, rating); without one it has no author.
- LLM hint (`YandexClassifier`) is optional: no call without `YANDEX_API_KEY`
  / `YANDEX_FOLDER_ID`; 401, 403 or a non-header key disables it per process;
  other failures or answers outside `RequestCategory` -> `category: null`.
  Key never logged. The model picks only the category (`CATEGORY_RULES` give
  the zone), the resident's text is its own `user` message. `YandexQuota`
  caps classify and OCR together per user per api worker (`QUOTA_CALLS` an
  hour); past it the route answers as if Yandex were off. The bot does not
  classify. OCR gets the photo's real type and skips types it can't read.
- `RequestChannel.CHAT` is written nowhere (no chat interaction in the spec).
- Chats bind per `BOUND_CHAT` (`repos/chats.py`); fan-out also needs
  `bot_is_admin`. Every `bot_added` is a fresh binding: `upsert_added` clears
  binding, rights, `pins_mid`; `on_bot_added` unpins the old list without
  events. `ChatsService.bind` allows staff of the house's org (`is_staff`, not
  executors) or its active chairman.
- The `bot_added` handler only queues `on_bot_added`, which leaves channels and
  chats whose initiator is unreachable or roleless, then opens the binding
  window (`ChatBinding.code` waits for text: default stack). Binding windows
  read title and chat id from `ChatBindingData`, never the `chats` row.
- MAX sends no rights-change event: `is_chat_admin` runs on the «Готово» tap
  and after each failed chat send. `set_admin` records `CHAT_ADMIN_GRANTED`
  and queues the welcome only on `false -> true`; a failed send without rights
  opens `ChatBinding.rights` for `bound_by` with sound.
- Pins (`/pin`, `/unpin`, `/repin`) work only in bound chats; other groups
  ignore them, a private dialog answers `CHAT_COMMANDS_ONLY`. `ChatsService`
  writes `chat_pins` under `ChatsRepo.lock` and refuses a pin past
  `MESSAGE_TEXT_LIMIT` (raw HTML, UTF-16 units). Only `sync_chat_pins` sends
  the list, rendered from the db. Previews off on send (`BotDefaults`); edits
  take no such flag.
  - `/pin` re-pins the list with sound; a working `/unpin` replies; either on
    the list itself gets a hint.
  - MAX sends no manual pin/unpin event: other in-place edits leave the pin
    alone and, when the list is unpinned, reply to it (`PINS_HERE`) instead of
    fighting whoever pinned over it.
  - A new list message (first list, failed edit, `/repin`) is pinned (silent
    unless `/pin`) and deletes the old one. `/repin` exists because a message
    deleted only for oneself sends no event.
  - `message_removed` of the list (`chats.pins_mid`) unpins all and says so
    (`PINS_ERASED`); of a listed message drops that item. An emptied list is
    deleted, never unpinned.

## Readings, reminders, analytics

- `window_period` (`core/services/readings.py`) alone decides the open
  window's period (a window across month end belongs to the month it opened).
- A reminder selects, stamps and queues in one transaction, never sends:
  `RemindersService` stamps (`*_sent_at` / `*_warned_at` or a
  `READING_REMINDER_SENT` event with `house_id`, `period`, `kind`) and hands
  the text to `NotificationsService` (sends after commit). Date logic takes
  `today` / `now` as arguments.
- `House.timezone` (residents) and `Organization.timezone` (reception,
  appointments, dashboard) are IANA; `Zoned` (`zheka/base.py`) derives every
  local day, bound and printed time, naive input read as local. Schedules are
  UTC: reminders run hourly, act where the local hour reached the target,
  stamps keep one send each.
- `broadcast_access_request` is the one broadcast that opens a window
  (`AccessSlots.pick`, `ShowMode.SEND`).
- `remind_not_submitted` refuses outside the window (`window_open` is only a
  hint), stamps `kind: manual`, skips anyone reminded since the house's local
  midnight.
- Each metric is one SQL expression in `_METRICS` (`repos/analytics.py`),
  shared by dashboard and benchmark; overdue is `overdue_at`
  (`repos/requests.py`), shared with the admin filter. Recent repeats: a count
  per house, not a share.
- The benchmark never exposes one organization: `MIN_ORGS_FOR_CUT = 3`
  (caller included) drops smaller cuts in SQL and nulls `platform_median`,
  `rank`, `total` on a smaller platform; a cut's complement in its parent
  (platform for a region; region and platform for a city) must be 0 or >= 3.
  Peers share the caller's `is_demo`.

## Seed and demo

- Real where public, fictional where it would be a claim. Registry orgs are
  seeded unregistered, without history, linked only to houses their
  reformagkh card names unambiguously; registered orgs are fictional
  «Демо-УК ...» (`is_demo`, checksum-failing INNs). No invented licence or
  cadastral numbers; images are generated. Fictional orgs replace real links
  only in Москва, whose one unmanaged house in the flat range is demo house
  61/1 (`test_a_real_manager_is_replaced_only_in_moscow`; moving a peer's
  second house from Казань to Санкт-Петербург breaks it).
- Seeded users: negative `max_user_id`, no `max_chat_id`.
- The seed is one transaction, offline, takes `today`, seeds `random.Random`
  per entity; after `pg_advisory_xact_lock(SEED_LOCK)` an existing `DEMO_INN`
  org makes it return `False`. History rows are written directly, not via
  services; no request is left `ON_REVIEW` (the scheduler would auto-close
  and message the author). `/seed` (unadvertised, open) only queues
  `seed_demo`, which replies after commit; `seed()` gets no publisher.
- All five demo orgs have history in Москва (region = city), so both benchmark
  cuts survive `MIN_ORGS_FOR_CUT` (`test_seed.py`: five distinct ranks per
  metric). They group requests from `REVIEWERS_GROUP_THRESHOLD` flats, not 3:
  reviewers share an org's first house and file the same category.
- Demo deeplinks are only `demo_{admin,staff,resident}_N`, N 1-4 (5 is the
  API checker's), granting only that role in demo org N: `DemoService.join`
  sets exactly ADMIN or
  EMPLOYEE (lowering too); `settle` gives the verified flat `Д{user_id}` in
  the org's first house, filled by `furnish` (charges from tariffs: every demo
  house has tariffs, every demo org `meter_window_always_open`).
  `POST /demo/activate` (`number`, `admin`) does both, keeping an existing
  role unless `admin` raises it; both idempotent. No seed ->
  `EntityNotFound`; no `consent_at` -> `NotEnoughRights`. A reviewer's flat
  account is random (seeded ones are the zero-padded number), so no other
  reviewer can verify into it.
- Demo orgs are shared by strangers: block and revoke-verification refuse a
  real user (positive `max_user_id`) other than the actor, and a DIRECT
  announcement reaches only its author.
- Reseeding (`docker compose down -v`, `just migrate`, `just seed`) wipes
  reviewers' flats; the dashboard's rolling 30 days start at the seed, so seed
  on the deploy closest to judging. `scripts/fetch_seed_data.py` rewrites
  `seed/data/` (cold run ~20 min, cached in `backend/.cache/seed/`).

## Tests

- Two databases: api tests roll back; bot windows commit for real into
  `zheka_bot`. One dispatcher per session.
- Tasks run through the `task_broker` fixture
  (`task.kicker().with_broker(task_broker).kiq(...)`); published follow-ups
  land in `bot_broker`, the test runs them.
- `make_org_house_flat_user` registers its org unless `registered=False`.
- A new guard gets a test that goes red when that one guard is removed,
  proven by running it, reported per guard. An unkillable guard is an honest
  gap.

## Orientation

- Plans and history: `.superpowers/sdd/` (`progress.md` maps blocks to
  commits).
- maxo's truth is `.venv/lib/python3.12/site-packages/maxo/`, not plans or
  memory: `python -c "import inspect, X; print(inspect.getsource(X.f))"`.
