# AGENTS.md - zheka backend

`CLAUDE.md` is a symlink to this file.

Backend of "Жэка Коммуналкин" (MAX messenger hackathon, "Умный город" track).
FastAPI on gunicorn serves the mini-app API and, in the same process, the maxo
webhook; background work runs on taskiq over Redis. Package `zheka`, Python
3.12, all code async. `zheka/core/models/` holds entities without SQLAlchemy;
`zheka/infra/database/tables/` holds the `Table` objects and the
`map_imperatively` calls; `zheka/infra/database/models/` re-exports the mapped
entities for the repos.

Commands live in `justfile`. `just check` is the gate (ruff, ruff format,
codespell, slotscheck, bandit, mypy strict) and `just test` runs pytest; keep
both green. slotscheck's scanned-class count varies on an unchanged tree and is
no evidence in a report or review. Format with `just format`, not bare
`ruff format`: COM812 puts every construct that does not fit on one line one
element per line with a trailing comma, and `just check` rejects the hugged form.

## Invariants

### Build and runtime

- Dependencies pinned `==`, `uv.lock` committed. `maxo==0.9.0` caps `redis<9`:
  keep `redis==8.1.0` and `taskiq-redis==1.2.3` until maxo lifts it.
- The api starts only as `gunicorn -c gunicorn.conf.py zheka.api.asgi:app`
  (gunicorn 26's ASGI worker, no uvicorn; uvloop comes with the `fast` group).
  `gunicorn.conf.py` imports nothing from `zheka` and owns `bind` (`API_HOST` /
  `API_PORT`, default `0.0.0.0:7001` that nginx and the healthcheck expect) and
  `workers`, so `ApiConfig` carries only `cors`. No `API_WORKERS`: one worker
  per logical CPU (blind to a cgroup quota), and `MAX_BOT_MODE=polling` forces
  one, since the lifespan polls per worker. `--preload` stays off: each worker
  builds its own dispatcher, container and connections.
- `MAX_BOT_MODE=webhook` (production) requires `MAX_WEBHOOK_URL` on 443 with a
  real certificate. Only the `migrations` compose service runs alembic.
- `zheka/api/asgi.py` builds the app at import and needs a real env (excluded
  from slotscheck); import `app_factory` from `zheka.api.app` instead. Env var
  names follow the family canon (`POSTGRES_*`, `REDIS_DB`, `LOG_LEVEL`).
- An API change regenerates the root `openapi.yaml` with `just openapi`;
  `test_committed_openapi_yaml_matches_the_app` fails on a stale one.
- Every entry point closes its APP container (api lifespan, worker
  `WORKER_SHUTDOWN`, scheduler and seed in `finally`): it owns the database
  pool, the bot session and the one `aiohttp.ClientSession` of the process
  (`YandexProvider.http_session`). Both Yandex clients share it and pass their
  own timeout on each request, never on the session.

### Code conventions

- A plain data class inherits `ZhekaType` (`zheka/base.py`), never
  `@dataclass`: the metaclass applies `frozen=True, slots=True, kw_only=True`.
  `ZhekaMutableType` is the mutable variant, `class Foo(ZhekaType,
  frozen=False)` opts one class out, own `__slots__` is left alone. Entities in
  `core/models/` use `ZhekaMutableType`, since `map_imperatively` cannot map a
  frozen or slotted class. Pydantic only in `api/schemas/`.
- Domain errors are axes off `ZhekaError` (`zheka/core/errors.py`), mapped in
  the `exception_handlers` comprehension in `api/errors.py`: add an axis to
  that tuple, not a handler. Never declare `title` (`__init_subclass__` fills
  it); each axis has a default message. `InvalidRequest` must not inherit
  `ValueError`, or it answers 409 instead of 400.
- Event names and sources are `EventType` / `EventSource` members
  (`zheka/core/enums/events.py`), never strings at the call site.
- A repo builds every statement into a named `stmt` and executes it on the next
  line; no `self._session.get(Model, id)`.
- Alembic messages and file names are English. Until the first deploy a schema
  correction regenerates the single initial migration (developers recreate the
  local database); after it, every change is a new revision.
- Every fractional quantity is a scaled integer, no `Decimal` or `float`, one
  explicit rounding: money in kopecks, tariff rate in 1/10000 rouble per unit
  (both `BigInteger`), area in 1/100 m2, volume and readings in 1/1000 m3 or
  kWh, percent in 1/100 (50% = `5000`). Only latitude and longitude are
  `Numeric(9, 6)`. No unit suffix in a name: the unit goes in the Russian
  `Field(description=...)` in `api/schemas/` and a comment on the entity.

### Transactions and isolation

- A dishka REQUEST container belongs to exactly one of four deciders:
  `transaction_middleware` (http, commits below 400), `CommitMiddleware`
  (taskiq, commits without error), `TransactionMiddleware` in `zheka/bot/`
  (commits when the handler returns) and `zheka/seed/__main__.py` (commits when
  `seed` wrote something). The first three commit, then flush the
  `TaskPublisher`; the seed never flushes it. All roll back on an exception. No
  provider or route commits: dishka hands a provider the exception as
  `agen.asend(exc)`, so it cannot decide. A new entry point with a REQUEST
  container brings its own decider or its writes are silently dropped.
- Http middleware order lives only in `setup_middlewares` (`zheka/api/app.py`);
  `trace_id_middleware` is the outermost `app.middleware("http")`.
  `RequestStateMiddleware` registers last: gunicorn 26 hands every request the
  one worker `scope["state"]` instead of a copy, so without it concurrent
  requests share the dishka container of the last one to arrive.
- `EventsService.record` writes on a savepoint and flushes the caller's
  pending session: call it after the business action's own flush.
- Cross-org isolation has one tool, `scoped_to_org`
  (`infra/database/repos/scopes.py`). A repo method taking `house_id`,
  `flat_id` or `org_id` from a path checks no ownership, so the caller scopes.
  A foreign id is `EntityNotFound` (404), never 403.
- `FilesService.save` (route) delegates to `save_download` (bot): mime
  whitelist, `max_size_mb` counted during the write and cleanup exist once.
  Never check size on the finished file: `Bot.download` streams unchecked for
  30 seconds.

### Bot

- The webhook answers 200 within 30 seconds: a handler does no IO of unknown
  length (download, OCR, LLM) and queues a taskiq task (its own window is fine).
- Screens are `maxo.dialogs` `Window`s, never hand-built keyboards or stored
  message ids; a new flow is a package under `zheka/bot/handlers/` included in
  `make_dispatcher`.
- Dialog state goes through one `BaseDialogData` subclass per dialog
  (`zheka/bot/dialog_data.py`) for `start_data` and `dialog_data`, never by
  string key: `SomeData(...).to_data()` to start, `load` / `load_start` to
  read, `proxy` to write. Start data that must outlive the first window is
  copied into `dialog_data` in `on_start`, as onboarding does.
- One dispatcher per process: api (`app_factory`) and worker
  (`zheka/broker/broker.py`); the scheduler builds none. Routers are
  module-level singletons, so a second `make_dispatcher` raises
  `RouterAlreadyIncludedError`; maxo refuses `include` and filters after
  startup. `make_dispatcher` returns `BotSetup` (dispatcher plus the
  `BgManagerFactory` from `setup_dialogs`, the only one wired to the dialog
  middlewares; never rebuild `BgManagerFactoryImpl(dp)`). `app_factory` takes a
  ready `BotSetup` so a test owns the one dispatcher.
- `TransactionMiddleware` and the user middleware are `inner` on `dp.update`:
  a dispatcher works only after `setup_maxo_dishka`, otherwise every update
  dies on `ctx[CONTAINER_NAME]` and maxo swallows it silently.
- Every private router and dialog sits under `private_router`, whose
  `message_created`, `message_callback` and `bot_started` observers carry
  `PRIVATE_ONLY`; no handler repeats the check. Never `.filter()` a `Dialog`'s
  observers: it replaces its `IntentFilter`. Chat and lifecycle handlers
  (`bot/handlers/chats/router.py`, `bot/handlers/lifecycle.py`) and the error
  router sit outside it.
- The error router answers every update kind (a `None` return loses the
  error), a message with a reply to it, and resolves nothing from dishka (the
  container is closed by then), so the menu window it restarts renders without
  services.
- `zheka/bot/middlewares/user.py` puts `user` into middleware data; it upserts
  only on `ChatType.DIALOG` (house chat members gave no consent) and only reads
  for other chats and `DialogUpdateEvent`. `upsert_by_max_id` keeps
  `max_chat_id` with `coalesce` (the mini-app upsert in
  `api/dependencies/current_account.py` passes none) and clears
  `bot_stopped_at` when given a chat id (the `bot_stopped` handler resets it).
- `deeplinks_router` sits ahead of `commands_router`; an unparsable payload
  returns `UNHANDLED` (not `None`) to fall through to `/start`.
  `BotStarted.payload` is `Omittable[str | None]`, read with `is_not_defined`.
  Consent precedes every way into a house: the payload rides into `Consent.ask`
  as `start_data`, `on_accept` resumes it, and `HousesService.link` refusing a
  user without `consent_at` is the backstop.
- `notify` is always passed explicitly (product default silent). A dialog
  window gets it through the `dialog_notify` `ContextVar`
  (`zheka/infra/max/sender.py`), read by `ZhekaMessageManager` and raised only
  by `start_dialog`, because maxo 0.9.0 hardcodes `notify=True`.
- `MaxSender` is for broadcasts and task windows, not ordinary handlers. It
  owns the MAX limits: 30 rps per bot (`BOT_RATE_LIMIT`), 2 msg/s per chat,
  keyed on `max_user_id` for private sends and `start_dialog` alike so one
  resident is one bucket.
- A task opens a window only via `MaxSender.start_dialog` (`fg()`, always
  `RESET_STACK`): `bg().start()` and `NEW_STACK` go through `call_soon` and let
  the task commit before the send. Without `stack_id` the window replaces the
  resident's default stack, so a caller replacing its own window passes its
  stack id. A window announcing news passes `show_mode=ShowMode.SEND`, or maxo
  edits the stack's last message, possibly an old card; a re-render after the
  user's tap keeps the default. Users without `max_chat_id` or with
  `bot_stopped_at` are skipped with a log line. Stack ids are derived, never
  stored: `executor-{request_id}`, `review-{request_id}`, `chat-{chat_id}`,
  `access-{access_request_id}`.
- maxo 0.9.0 delivers text and photos only to the default stack, so an input
  window opens there: `ask_in_default_stack` (`zheka/bot/cards.py`) via
  `bg().start()` with `ShowMode.SEND` (`fg()` in a handler deadlocks on the
  `users` row), replacing whatever the user had there, a request draft
  included. `back_to_menu` sends the result as its own message, then
  `Menu.main` as a new one; «❌ Отмена» (`CANCEL`) returns to `Menu.main` too,
  since maxo's `Cancel` would leave the stack empty. The service rechecks state
  (`RequestsService.reject` accepts only `ON_REVIEW`).
- The service validates every value the bot hands it: `Select` passes raw
  callback strings and `when=`-hidden buttons still fire from old keyboards.
  The rating range lives in `RequestsService.rate` (`MIN_RATING` /
  `MAX_RATING`, imported by the API schema), transitions in
  `executor_advance`.
- A stale card tap is not an error: executor and review handlers catch
  `ZhekaError`, answer the callback with its text and let the getter re-render.
  Safe only because those services refuse before their first write.
- A task that changes a request never renders the window reading it (the
  getter's session would see the pre-commit state): `attach_result_photo`
  publishes `send_executor_card` with its own `user_id`.
- Tasks are tested through the `task_broker` fixture (`InMemoryBroker` with
  `ContainerMiddleware` and `CommitMiddleware`,
  `task.kicker().with_broker(task_broker).kiq(...)`); published follow-ups land
  in `bot_broker` and the test runs them itself.
- Bot texts: formal «вы», an emoji and a space before every button text and
  at the start of a message, no period at the end of a message or a line. A
  result is its own message (`back_to_menu`), never a line above the menu.
  Both `bot_started` handlers set `ShowMode.SEND` first: maxo's AUTO edits the
  last message for anything but `MessageCreated`.
- The consent tap edits its message to «✅ Согласие дано» and the next window
  comes as a new message. `CONSENT_GIVEN` carries the entry source
  (`Deeplink.source`, `DIRECT` without a payload, `MINIAPP` from the API). The
  policy button opens the mini-app with `startParam`
  `encode_payload('{"path":"/privacy"}')`; the frontend half that decodes and
  routes it is pending, so today the button opens the start screen.
- Every step of the house search and the request draft carries «🏠 Меню»
  and, past the first, «⬅️ Назад» (`TO_MENU`, `BACK` in `zheka/bot/cards.py`).
  A list step of the search also takes typed text: one match is chosen,
  several narrow the list, none leaves the list and says so; `on_back` clears
  that state.

### Requests and chats

- Executor authority is `executor_user_id` **and** an `OrgRole.EXECUTOR` row in
  the house's org: a removed executor keeps both the id and a live card.
  `AdminRequestsService.executor_advance` checks both before its first write;
  `executor_card` returns `None` instead of raising.
- The author's review card is queued only in `AdminRequestsService._move`, the
  one road into `ON_REVIEW`; it replaces the status text.
- A house not `is_connected` takes no request and no flat verification request
  (`InvalidState(NOT_CONNECTED)`, 409); the bot's category window says so
  first. `make_org_house_flat_user` registers its org unless `registered=False`.
- A phone request with `resident_id` is that resident's own request (author,
  flat, notifications, review, rating); without one it has no author.
- The LLM category hint (`YandexClassifier`, `zheka/infra/yandex/classifier.py`)
  is optional: no call without `YANDEX_API_KEY` / `YANDEX_FOLDER_ID`; 401, 403
  or a key that cannot be a header (non-ASCII or a control character) disables
  it for the process; any other failure or an answer outside `RequestCategory`
  is `None` for that call. `POST /requests/classify` then answers 200 with
  `category: null`. The key is never logged. The model picks only the category,
  the zone comes from `CATEGORY_RULES`; the resident's text is its own `user`
  message. The bot does not classify (`NewRequest` asks the category first).
  `RequestChannel.CHAT` is written nowhere yet (no chat interaction in the
  spec). The missing per-user limit is a `ponytail:` marker at
  `RequestsService.classify`.
- A chat is bound when `house_id` and `bound_at` are set and `status ==
  ACTIVE`: `BOUND_CHAT` (`infra/database/repos/chats.py`), shared by the house
  card and the fan-out, which also needs `bot_is_admin`.
- Every `bot_added` is a fresh binding (`ChatsRepo.upsert_added` clears
  `house_id`, `bound_by`, `bound_at`, `bot_is_admin`, `pins_mid`, and
  `on_bot_added` unpins the old list without events). `ChatsService.bind`
  allows staff of the house's org (`is_staff`, not an executor) or its active
  chairman.
- The `bot_added` handler only queues `on_bot_added`, which leaves channels and
  chats whose initiator is unreachable or has no role, and opens the binding
  window. `ChatBinding.code` waits for text, so it opens on the default stack.
  Binding windows take title and chat id from `ChatBindingData`, never from the
  `chats` row.
- MAX sends no rights-change event: `is_chat_admin` (`infra/max/sender.py`,
  via `BOT_RATE_LIMIT`, which `on_bot_added`'s `get_chat` / `leave_chat`
  bypass) runs on the "Готово" tap and after each failed chat send.
  `ChatsService.set_admin` records `CHAT_ADMIN_GRANTED` and queues the welcome
  only on `false -> true`. A failed send without rights opens
  `ChatBinding.rights` for `bound_by` with sound.
- Pins (`/pin`, `/unpin`, bound chats only, any other chat is ignored
  silently) live in `chat_pins`; a command that worked gets a reply, so the
  chat sees the bot reacted. The bot sends with link previews off
  (`BotDefaults` in `zheka/di/max_bot.py`), but MAX takes no such flag on an
  edit. `ChatsService` writes pins under the chat row lock (`ChatsRepo.lock`);
  only `sync_chat_pins` renders the list, from the database, always with the
  house link button. `message_removed` of `chats.pins_mid` unpins everything
  and tells the chat (`PINS_ERASED`), of a listed message drops that item. Only
  `/pin` pins the list again, with sound (`sync_chat_pins(notify=True)`), so
  the chat learns of the new item. MAX sends no event for a manual pin or
  unpin, so any other sync leaves the pin alone: when the list is not the
  chat's pinned message, the bot replies to it (`PINS_HERE`) instead of
  fighting whoever pinned over it. `/pin` and `/unpin` on the list itself get
  a friendly hint. An emptied list is deleted, never unpinned.

### Readings, reminders, analytics

- `window_period` (`core/services/readings.py`) is the only answer to "which
  period does the open window accept" (a window across the month end is the
  month it opened in). `ReadingsService.submit`, `ReadingsService.periods` and
  both reading reminders call it.
- A reminder selects, stamps and queues in one transaction and never sends
  itself: `RemindersService` stamps (`polls.reminder_sent_at`,
  `appointments.reminder_sent_at`, `meters.verification_warned_at`, or a
  `READING_REMINDER_SENT` event with `house_id`, `period`, `kind`) and hands
  the text to `NotificationsService`, which sends after the commit. Date logic
  takes `today` / `now` as an argument.
- `House.timezone` (what residents see) and `Organization.timezone` (reception,
  appointments, dashboard) are IANA names; `Zoned` (`zheka/base.py`) derives
  every local "today", day bound and printed time and reads a naive input as
  local. Schedules are UTC, no `cron_offset`: reminders run hourly and act
  where the local hour reached the target; their stamps keep each reminder to
  one send.
- `broadcast_access_request` (from `AccessService.create`) is the one
  broadcast that opens a window (`AccessSlots.pick`, `ShowMode.SEND`).
- `remind_not_submitted` refuses outside the window with `InvalidState`
  (`window_open` is only a button hint), stamps `kind: manual` and skips anyone
  reminded since the start of the house's local day.
- Each analytics metric is one SQL expression in `_METRICS`
  (`infra/database/repos/analytics.py`), shared by the dashboard and the
  benchmark. Overdue is `overdue_at` (`repos/requests.py`, from
  `CATEGORY_RULES`), shared with the admin filter. Shares use `share()`, a
  rating is `MetricUnit.POINTS` (hundredths), a median is cast to numeric.
- The benchmark must not leak a single organization: `MIN_ORGS_FOR_CUT = 3`
  (`core/services/analytics.py`, caller included) drops a smaller cut in SQL
  and nulls `platform_median`, `rank` and `total` for a smaller platform. A
  cut's complement within its parent (platform for a region; region and
  platform for a city) must be 0 or at least 3 too. Peers share the caller's
  `is_demo`.

### Seed and demo

- Real where public, fictional where it would be a claim. Registry
  organizations (`zheka/seed/data/organizations.csv`) are seeded unregistered
  and without history, linked only to houses whose reformagkh card names them
  unambiguously. Registered organizations are fictional «Демо-УК ...»,
  `is_demo = True`, with checksum-failing INNs (`DEMO_INNS`, numbered 1-5 in
  `PROFILES` order). No invented licence or cadastral numbers
  (`houses.cadastral_no` is nullable), images are generated
  (`zheka/seed/data/files/`). In Москва, where 61/1 (the demo house) is the
  only unmanaged house within `MIN_FLATS`..`MAX_FLATS` (74 has 273 flats),
  fictional organizations replace real
  links on Ленинский проспект 7 (ГБУ «Жилищник района Якиманка»), 11 с.1
  and 13 (ГБУ ЭВАЖД), 12 (ООО «Жилищник»);
  `test_a_real_manager_is_replaced_only_in_moscow` holds that; moving a peer's
  second house from Казань to Санкт-Петербург breaks it.
- Seeded users have negative `max_user_id` and `max_chat_id NULL`: unreachable.
- The seed is one transaction, never touches the network, takes `today` and
  seeds `random.Random` per entity. Its guard: the `DEMO_INN` organization
  exists, then it returns `False`; `pg_advisory_xact_lock(SEED_LOCK)` precedes
  the guard. History rows are written directly, not through the services. No
  request is left `ON_REVIEW` (the scheduler would auto-close it and message
  the author).
- `/seed` (`bot/handlers/commands/start.py`, unadvertised, anyone may send it)
  only queues `seed_demo`, which replies via `NotificationsService.notify_user`
  after the commit. `seed()` itself gets no publisher.
- All five fictional organizations have history in Москва (region = city),
  so both benchmark cuts survive `MIN_ORGS_FOR_CUT`; `test_seed.py` asserts five
  distinct ranks per metric. Recent repeats are a count per house
  (`recent_repeats`), not a share.
- Demo deeplinks are only `demo_{admin,staff,resident}_N`, N 1-5 (anything
  else is `UNHANDLED`), and grant only their role in demo organization N:
  `DemoService.join` sets exactly ADMIN or EMPLOYEE, lowering included;
  `DemoService.settle` gives the verified flat `Д{user_id}` in the first house
  of `list_for_org` (street, then building: org 2's is in Санкт-Петербург),
  filled by `DemoService.furnish`. `POST /demo/activate` does both for org 1
  and keeps an existing role. Inserts are `ON CONFLICT DO NOTHING`. `furnish`
  charges from tariffs, so the seed gives every demo house tariffs and every
  demo org `meter_window_always_open`. No seed is `EntityNotFound`, no
  `consent_at` is `NotEnoughRights`.

## Orientation

- Plans and block history: `.superpowers/sdd/` at the repo root
  (`progress.md` maps blocks to commits); `refactor-startapp-routing.md` waits
  for its frontend half.
- `EventType`'s 48 members split 42 + 4 + 2. 42 are recorded inside
  `core/services/` (e.g. `HOUSE_SEARCH` / `HOUSE_LINKED` in `HousesService`,
  `CHAT_BOUND`, `LLM_SUGGESTED`, `CONSENT_GIVEN` in `ProfileService`), so a
  handler or route recording them doubles the count: pass the service
  `source`, `method` or `entrance`. 4 in bot
  handlers: `BOT_START` (`bot/handlers/commands/start.py`, `deeplinks.py`), `BOT_STOPPED`,
  `BOT_MUTED`, `BOT_UNMUTED` (`bot/handlers/lifecycle.py`); `BOT_START` never
  in the fallback router or a getter. `MINIAPP_OPEN` / `ANNOUNCEMENT_CLICK` come
  from the client via `POST /api/events` (whitelist:
  the `Literal` in `TrackEventRequest`), so no `record` call names them.
- maxo's truth is `.venv/lib/python3.12/site-packages/maxo/`, not the plan or
  memory; `python -c "import inspect, X; print(inspect.getsource(X.f))"`.
- Tests use two databases: api tests roll back, bot windows commit for real
  into `zheka_bot`. The dispatcher is built once per session.
- A new guard gets a test that goes red when that one guard is removed, proven
  by running it and reported per guard. An unkillable guard is an honest gap.
- Reseed: `docker compose down -v`, `just migrate`, `just seed`; it wipes
  reviewers' flats. Dashboard and benchmark read a rolling 30 days, so seed on
  the deploy closest to judging; the first `/seed` on a fresh deploy starts
  that clock. `uv run python scripts/fetch_seed_data.py` rewrites
  `zheka/seed/data/`, cached in `backend/.cache/seed/` (a cold run is ~20
  minutes).
- `grep --include=*.py` fails under zsh (`no matches found`): quote the glob.
