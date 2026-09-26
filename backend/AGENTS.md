# AGENTS.md - zheka backend

Backend of "Жэка Коммуналкин" (MAX messenger hackathon): FastAPI on gunicorn
serves the mini-app API and the maxo webhook in one process, taskiq over Redis
runs background work, all code is async. Entities in `zheka/core/models/` know
nothing of SQLAlchemy: `zheka/infra/database/tables/` maps them imperatively
and `zheka/infra/database/models/` re-exports them for the repos.

`just check` and `just test` stay green. Format only with `just format`: a bare
`ruff format` leaves the hugged form that COM812 in `just check` rejects.
slotscheck's class count drifts on an unchanged tree and proves nothing.

## Invariants

### Build and runtime

- Dependencies are pinned `==` with `uv.lock` committed; `maxo==0.9.0` caps
  `redis<9`, so `redis` and `taskiq-redis` stay at their pins.
- The api runs only as `gunicorn -c gunicorn.conf.py zheka.api.asgi:app`
  (gunicorn 26's ASGI worker, no uvicorn). `gunicorn.conf.py` imports nothing
  from `zheka` and alone owns `bind` (port 7001, which nginx and the
  healthcheck expect) and `workers`: one per CPU, one under
  `MAX_BOT_MODE=polling`, since each worker's lifespan polls. `--preload` stays
  off: each worker builds its own dispatcher, container and connections.
- The taskiq worker and scheduler share one process, `python -m zheka.broker`,
  to spare memory on the server. The scheduler kicks through the container's
  `ZhekaBroker`: `run_scheduler` starts and shuts down its broker, which would
  run the receiving broker's lifecycle twice.
- A `python -m` entry point starts through `zheka.runner.run`, which picks
  uvloop under `PYTHONOPTIMIZE=1` (the Dockerfile) and asyncio otherwise; the
  api gets uvloop from gunicorn's `asgi_loop = "auto"`.
- Production is `MAX_BOT_MODE=webhook` with `MAX_WEBHOOK_URL` on 443 and a real
  certificate. Only the `migrations` compose service runs alembic.
- `zheka/api/asgi.py` builds the app at import and needs a real env; import
  `app_factory` from `zheka.api.app` instead. Env names follow the family canon
  (`POSTGRES_*`, `REDIS_DB`, `LOG_LEVEL`).
- An API change reruns `just openapi`, or a test fails on the stale root
  `openapi.yaml`.
- Every entry point with an APP container closes it (api lifespan, worker and
  seed in `finally`), which owns the database pool, the bot session and the
  process's one `aiohttp.ClientSession`. The Yandex clients pass their timeout
  per request, never on that shared session.

### Code conventions

- A plain data class inherits `ZhekaType` (`zheka/base.py`: frozen, slotted,
  kw-only; `class Foo(ZhekaType, frozen=False)` opts out). Entities in
  `core/models/` use `ZhekaMutableType`, since `map_imperatively` cannot map a
  frozen or slotted class. Pydantic lives only in `api/schemas/`.
- A domain error is an axis off `ZhekaError` (`zheka/core/errors.py`) with its
  default text in the `message` ClassVar; a new axis joins the tuple of the
  `exception_handlers` comprehension in `api/errors.py`, which answers the class
  name as `title`.
  `InvalidRequest` must not inherit `ValueError`, or it answers 409, not 400.
- Events are `EventType` / `EventSource` members recorded in `core/services/`:
  a handler or route passes the service `source`, `method` or `entrance`, since
  recording the event itself doubles the count. The exceptions: bot handlers
  record `BOT_START` (`commands/start.py`, `deeplinks.py`, never the fallback
  router or a getter), `BOT_STOPPED`, `BOT_MUTED`, `BOT_UNMUTED`
  (`lifecycle.py`); the client sends `MINIAPP_OPEN` and `ANNOUNCEMENT_CLICK` to
  `POST /api/events` (whitelist: `TrackEventRequest`).
- A repo builds every statement into a named `stmt` and executes it on the next
  line; no `self._session.get(Model, id)`.
- Alembic messages and file names are English; every schema change is a new
  revision.
- A fractional quantity is a scaled integer with one explicit rounding, never
  `Decimal` or `float`: money in kopecks, tariff rate in 1/10000 rouble per
  unit (both `BigInteger`), area in 1/100 m2, volume and readings in 1/1000 m3
  or kWh, percent in 1/100 (50% = `5000`); only coordinates are
  `Numeric(9, 6)`. The unit goes in the Russian `Field(description=...)`, not
  in the name.

### Transactions and isolation

- A dishka REQUEST container has exactly one decider that commits, then
  flushes the `TaskPublisher`, or rolls back on an exception: http
  `transaction_middleware` (commits below 400), taskiq `CommitMiddleware`, bot
  `TransactionMiddleware`, and `zheka/seed/__main__.py`, which never flushes.
  Providers and routes never commit: dishka hands a provider the exception as
  `agen.asend(exc)`, so it cannot decide. A new entry point with a REQUEST
  container brings its own decider, or its writes are silently dropped.
- Http middleware order lives only in `setup_middlewares` (`zheka/api/app.py`),
  `trace_id_middleware` outermost. `RequestStateMiddleware` registers last:
  gunicorn 26 hands every request the worker's one `scope["state"]`, and
  without it concurrent requests share one dishka container.
- `EventsService.record` writes on a savepoint and flushes the caller's pending
  session: call it after the business action's own flush.
- Cross-org isolation has one tool, `scoped_to_org`
  (`infra/database/repos/scopes.py`): a repo method taking an id from a path
  checks no ownership, the caller scopes. A foreign id is `EntityNotFound`
  (404), never 403.
- Uploads from the route and the bot go through `save_download`, which counts
  `max_size_mb` during the write, since `Bot.download` streams unchecked for 30
  seconds.

### Bot

- The webhook answers 200 within 30 seconds, so IO of unknown length
  (download, OCR, LLM) goes to a taskiq task.
- Screens are `maxo.dialogs` `Window`s, never hand-built keyboards or stored
  message ids; a new flow is a package under `zheka/bot/handlers/` included in
  `make_dispatcher`.
- Dialog state goes through the dialog's `BaseDialogData` subclass
  (`zheka/bot/dialog_data.py`), never a string key. Start data that must
  outlive the first window is copied into `dialog_data` in `on_start`.
- Routers are module-level singletons, so a process builds one dispatcher (api
  `app_factory`, worker `zheka/broker/__main__.py`) and a second
  `make_dispatcher` raises; maxo refuses `include` and filters after startup.
  The only `BgManagerFactory` wired to the dialog middlewares is the one in
  `BotSetup`, and `app_factory` takes a ready `BotSetup`, so a test owns the
  dispatcher.
- The transaction and user middlewares are `inner` on `dp.update`: without
  `setup_maxo_dishka` every update dies on `ctx[CONTAINER_NAME]` and maxo
  swallows it silently.
- `private_router`'s observers carry `PRIVATE_ONLY`, so every private router and
  dialog sits under it and no handler repeats the check; chat, lifecycle and
  error routers sit outside. `.filter()` on a `Dialog`'s observers replaces its
  `IntentFilter`: leave them alone.
- The error router answers every update kind (a `None` return loses the
  error), a message with a reply, and resolves nothing from dishka (the
  container is closed), so the menu window it restarts renders without
  services.
- The user middleware upserts `user` only in `ChatType.DIALOG` (house chat
  members gave no consent) and only reads elsewhere. `upsert_by_max_id` keeps
  `max_chat_id` with `coalesce` (the mini-app passes none) and, given a chat
  id, clears `bot_stopped_at`.
- `deeplinks_router` precedes `commands_router`; an unparsable payload returns
  `UNHANDLED`, not `None`, to fall through to `/start`. `BotStarted.payload` is
  `Omittable[str | None]`, read with `is_not_defined`. Consent precedes every
  way into a house: the payload rides into `Consent.ask` as `start_data` and
  `on_accept` resumes it; `HousesService.link` refusing a user without
  `consent_at` is the backstop.
- `notify` is always explicit, the product default silent. maxo 0.9.0
  hardcodes `notify=True` for dialog windows, so `ZhekaMessageManager` reads
  the `dialog_notify` `ContextVar`, raised only by `start_dialog`.
- `MaxSender` serves broadcasts and task windows, not ordinary handlers, and
  owns the MAX limits: 30 rps per bot (`BOT_RATE_LIMIT`) and 2 msg/s per chat,
  keyed on `max_user_id` for private sends and windows alike.
- A task opens a window only via `MaxSender.start_dialog` (`fg()`,
  `RESET_STACK`): `bg().start()` and `NEW_STACK` go through `call_soon` and let
  the task commit before the send. Without `stack_id` the window replaces the
  default stack, so a caller replacing its own window passes its stack id. A
  window announcing news passes `ShowMode.SEND`, or maxo edits the stack's
  last message, maybe an old card; a re-render after a tap keeps the default.
  Users without `max_chat_id` or with `bot_stopped_at` are skipped with a log
  line. Stack ids are derived from the entity (`review-{request_id}`), never
  stored.
- maxo 0.9.0 delivers text and photos only to the default stack, so an input
  window opens there via `ask_in_default_stack` (`zheka/bot/cards.py`:
  `bg().start()` with `ShowMode.SEND`, since `fg()` in a handler deadlocks on
  the `users` row), replacing whatever was there, a request draft included;
  the service rechecks state. `back_to_menu` sends the result as its own
  message, then `Menu.main`; «❌ Отмена» (`CANCEL`) returns to `Menu.main` too,
  since maxo's `Cancel` leaves the stack empty.
- The service validates every value the bot hands it: `Select` passes raw
  callback strings and `when=`-hidden buttons still fire from old keyboards.
- A stale card tap is not an error: executor and review handlers catch
  `ZhekaError`, answer the callback with its text and let the getter
  re-render, safe only because those services refuse before their first write.
- A task that changes a request never renders the window reading it, whose
  getter would see the pre-commit state: it publishes a follow-up task
  (`attach_result_photo` -> `send_executor_card`).
- Bot texts: formal «вы», an emoji and a space opening every message and
  button, no period ending a message or line. A result is its own message
  (`back_to_menu`), never a line above the menu. Both `bot_started` handlers
  set `ShowMode.SEND` first: maxo's AUTO edits the last message for anything
  but `MessageCreated`.
- The consent tap edits its message to «✅ Согласие дано», the next window comes
  as a new one. The policy button opens the mini-app with `startParam`
  `{"path":"/privacy"}`, which the frontend does not route yet.
- Every step of the house search and the request draft has «🏠 Меню» and, past
  the first, «⬅️ Назад» (`TO_MENU`, `BACK`). A search list step also takes
  typed text: one match is chosen, several narrow the list, none keeps it and
  says so; `on_back` clears that state.
- `BOT_COMMANDS` (`bot/handlers/commands/start.py`) is the command menu, set by
  an `after_startup` hook in every api worker (the taskiq worker feeds no
  signals); a failure is logged, not raised. A new command joins it, `/seed`
  never. Tests call the hook directly: a second `AfterStartup` fails in
  `DialogRegistry.refresh`.

### Requests and chats

- Executor authority is `executor_user_id` **and** an `OrgRole.EXECUTOR` row in
  the house's org, since a removed executor keeps the id and a live card:
  `executor_advance` checks both before its first write, `executor_card`
  returns `None`.
- The author's review card is queued only in `AdminRequestsService._move`, the
  one road into `ON_REVIEW`.
- A house not `is_connected` takes no request and no flat verification request
  (`InvalidState(NOT_CONNECTED)`); the bot's category window says so first.
- A phone request with `resident_id` is wholly that resident's (author, flat,
  notifications, review, rating); without one it has no author.
- The LLM category hint (`YandexClassifier`) is optional: without
  `YANDEX_API_KEY` / `YANDEX_FOLDER_ID` it makes no call; 401, 403 or a key that
  cannot be a header disables it for the process; any other failure or an
  answer outside `RequestCategory` is `category: null`. The key is never
  logged. The model picks only the category (`CATEGORY_RULES` give the zone),
  the resident's text is its own `user` message, and there is no per-user
  limit yet. The bot does not classify.
- `RequestChannel.CHAT` is written nowhere: the spec has no chat interaction.
- A chat is bound per `BOUND_CHAT` (`infra/database/repos/chats.py`); the
  fan-out also needs `bot_is_admin`.
- Every `bot_added` is a fresh binding: `ChatsRepo.upsert_added` clears the
  binding, rights and `pins_mid`, and `on_bot_added` unpins the old list
  without events. `ChatsService.bind` allows staff of the house's org
  (`is_staff`, not an executor) or its active chairman.
- The `bot_added` handler only queues `on_bot_added`, which leaves channels and
  chats whose initiator is unreachable or has no role, then opens the binding
  window (`ChatBinding.code` waits for text, so on the default stack). Binding
  windows read title and chat id from `ChatBindingData`, never the `chats` row.
- MAX sends no rights-change event: `is_chat_admin` runs on the «Готово» tap
  and after each failed chat send. `ChatsService.set_admin` records
  `CHAT_ADMIN_GRANTED` and queues the welcome only on `false -> true`; a failed
  send without rights opens `ChatBinding.rights` for `bound_by` with sound.
- Pins (`/pin`, `/unpin`, `/repin`) work in bound chats only; another group
  chat ignores them, a private dialog answers `CHAT_COMMANDS_ONLY`.
  `ChatsService` writes `chat_pins` under the chat row lock (`ChatsRepo.lock`)
  and refuses a pin once the list would pass `MESSAGE_TEXT_LIMIT` (raw HTML in
  UTF-16 units). Only `sync_chat_pins` sends the list, rendered from the
  database. Link previews are off on send (`BotDefaults`); an edit takes no
  such flag.
  - `/pin` answers by pinning the list again with sound, a working `/unpin`
    with a reply; either on the list itself gets a hint.
  - MAX sends no event for a manual pin or unpin, so every other in-place edit
    leaves the pin alone and, when the list is not pinned, replies to it
    (`PINS_HERE`) instead of fighting whoever pinned over it.
  - A new list message (first list, failed edit, `/repin`) is pinned, silently
    unless for `/pin`, and deletes the old one. `/repin` exists because a
    message deleted only for oneself sends no event.
  - `message_removed` of the list (`chats.pins_mid`) unpins everything and says
    so (`PINS_ERASED`), of a listed message drops that item. An emptied list is
    deleted, never unpinned.

### Readings, reminders, analytics

- `window_period` (`core/services/readings.py`) is the only answer to which
  period the open window accepts (a window across the month end belongs to the
  month it opened in).
- A reminder selects, stamps and queues in one transaction and never sends
  itself: `RemindersService` stamps (a `*_sent_at` / `*_warned_at` column or a
  `READING_REMINDER_SENT` event with `house_id`, `period`, `kind`) and hands
  the text to `NotificationsService`, which sends after the commit. Date logic
  takes `today` / `now` as an argument.
- `House.timezone` (what residents see) and `Organization.timezone` (reception,
  appointments, dashboard) are IANA names; `Zoned` (`zheka/base.py`) derives
  every local day, bound and printed time and reads a naive input as local.
  Schedules are UTC: reminders run hourly and act where the local hour reached
  the target, and their stamps keep each to one send.
- `broadcast_access_request` is the one broadcast that opens a window
  (`AccessSlots.pick`, `ShowMode.SEND`).
- `remind_not_submitted` refuses outside the window (`window_open` is only a
  button hint), stamps `kind: manual` and skips anyone reminded since the
  house's local midnight.
- Each analytics metric is one SQL expression in `_METRICS`
  (`infra/database/repos/analytics.py`), shared by the dashboard and the
  benchmark; overdue is `overdue_at` (`repos/requests.py`), shared with the
  admin filter. Recent repeats are a count per house, not a share.
- The benchmark never exposes a single organization: `MIN_ORGS_FOR_CUT = 3`
  (caller included) drops a smaller cut in SQL and nulls `platform_median`,
  `rank` and `total` on a smaller platform, and a cut's complement within its
  parent (platform for a region; region and platform for a city) must also be
  0 or at least 3. Peers share the caller's `is_demo`.

### Seed and demo

- Real where public, fictional where it would be a claim. Registry
  organizations are seeded unregistered and without history, linked only to
  houses whose reformagkh card names them unambiguously; registered ones are
  fictional «Демо-УК ...» (`is_demo`, checksum-failing INNs). No invented
  licence or cadastral numbers; images are generated. Fictional organizations
  replace real links only in Москва, whose one unmanaged house in the flat
  range is the demo house 61/1 (`test_a_real_manager_is_replaced_only_in_moscow`;
  moving a peer's second house from Казань to Санкт-Петербург breaks it).
- Seeded users have negative `max_user_id` and no `max_chat_id`: unreachable.
- The seed is one transaction, never touches the network, takes `today` and
  seeds `random.Random` per entity; after `pg_advisory_xact_lock(SEED_LOCK)`
  an existing `DEMO_INN` organization makes it return `False`. History rows
  are written directly, not through the services, and no request is left
  `ON_REVIEW` (the scheduler would auto-close it and message the author).
- `/seed` (unadvertised, open to anyone) only queues `seed_demo`, which replies
  after the commit; `seed()` itself gets no publisher.
- All five fictional organizations have history in Москва (region = city), so
  both benchmark cuts survive `MIN_ORGS_FOR_CUT` (`test_seed.py` asserts five
  distinct ranks per metric).
- Demo deeplinks are only `demo_{admin,staff,resident}_N`, N 1-5, and grant
  only their role in demo organization N: `DemoService.join` sets exactly
  ADMIN or EMPLOYEE, lowering included; `settle` gives the verified flat
  `Д{user_id}` in the org's first house, filled by `furnish`.
  `POST /demo/activate` does both for org 1 and keeps an existing role; both
  are idempotent. `furnish` charges from tariffs, so every demo house has
  tariffs and every demo org `meter_window_always_open`. No seed is
  `EntityNotFound`, no `consent_at` is `NotEnoughRights`.
- Reseeding (`docker compose down -v`, `just migrate`, `just seed`) wipes
  reviewers' flats; the dashboard's rolling 30 days start at the first
  `/seed`, so seed on the deploy closest to judging.
  `scripts/fetch_seed_data.py` rewrites `zheka/seed/data/` (a cold run takes
  about 20 minutes; `backend/.cache/seed/` caches it).

## Tests

- Two databases: api tests roll back, bot windows commit for real into
  `zheka_bot`. The dispatcher is built once per session.
- Tasks run through the `task_broker` fixture
  (`task.kicker().with_broker(task_broker).kiq(...)`); published follow-ups
  land in `bot_broker` and the test runs them itself.
- `make_org_house_flat_user` registers its org unless `registered=False`.
- A new guard gets a test that goes red when that one guard is removed, proven
  by running it and reported per guard. An unkillable guard is an honest gap.

## Orientation

- Plans and block history live in `.superpowers/sdd/` at the repo root
  (`progress.md` maps blocks to commits); `refactor-startapp-routing.md` waits
  for its frontend half.
- maxo's truth is `.venv/lib/python3.12/site-packages/maxo/`, not the plan or
  memory: `python -c "import inspect, X; print(inspect.getsource(X.f))"`.
- `grep --include=*.py` fails under zsh (`no matches found`): quote the glob.
