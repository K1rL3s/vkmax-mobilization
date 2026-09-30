# Архитектура в диаграммах

Системный дизайн «Жэки Коммуналкина» в картинках: из чего состоит решение,
как части связаны между собой и со всеми внешними системами - реальными и
подменными (моки, заглушки, демо-режимы, фолбэки). Текстовое описание
архитектуры - в [`docs/architecture.md`](../architecture.md), этот раздел его
иллюстрирует и не заменяет.

Каждая диаграмма есть в двух видах:

- **Mermaid** - прямо в этом файле, GitHub и большинство IDE рисуют ее сами;
- **PlantUML** - исходники в [`plantuml/`](plantuml/), схемы архитектуры в
  нотации C4. Рендер из корня репозитория:
  `docker run --rm -v "$PWD/docs/architecture/plantuml:/data" plantuml/plantuml -tsvg '/data/*.puml'`.

| # | Диаграмма | Mermaid | PlantUML |
|---|-----------|---------|----------|
| 1 | Системный контекст | [раздел 1](#1-системный-контекст) | [`01-context.puml`](plantuml/01-context.puml) |
| 2 | Контейнеры | [раздел 2](#2-контейнеры) | [`02-containers.puml`](plantuml/02-containers.puml) |
| 3 | Компоненты бэкенда | [раздел 3](#3-компоненты-бэкенда) | [`03-backend-components.puml`](plantuml/03-backend-components.puml) |
| 4 | Компоненты фронтенда | [раздел 4](#4-компоненты-фронтенда) | [`04-frontend-components.puml`](plantuml/04-frontend-components.puml) |
| 5 | Развертывание и доставка | [раздел 5](#5-развертывание-и-доставка) | [`05-deployment.puml`](plantuml/05-deployment.puml) |
| 6 | Внешние системы: реальные и моки | [раздел 6](#6-внешние-системы-реальные-и-моки) | [`06-integrations.puml`](plantuml/06-integrations.puml) |
| 7 | Режимы окружения | [раздел 7](#7-режимы-окружения) | [`07-environments.puml`](plantuml/07-environments.puml) |
| 8 | Запуск мини-приложения и авторизация | [раздел 8.1](#81-запуск-мини-приложения-и-авторизация) | [`08-seq-miniapp-auth.puml`](plantuml/08-seq-miniapp-auth.puml) |
| 9 | Апдейты бота: вебхук и опрос | [раздел 8.2](#82-апдейты-бота-вебхук-и-опрос) | [`09-seq-bot-updates.puml`](plantuml/09-seq-bot-updates.puml) |
| 10 | Транзакция, задачи и уведомления | [раздел 8.3](#83-транзакция-задачи-и-уведомления) | [`10-seq-tasks-notifications.puml`](plantuml/10-seq-tasks-notifications.puml) |
| 11 | Подсказка категории заявки (LLM) | [раздел 8.4](#84-подсказка-категории-заявки-llm) | [`11-seq-classify.puml`](plantuml/11-seq-classify.puml) |
| 12 | Показание счетчика по фото (OCR) | [раздел 8.5](#85-показание-счетчика-по-фото-ocr) | [`12-seq-ocr.puml`](plantuml/12-seq-ocr.puml) |
| 13 | Голосовое в боте (SpeechKit) | [раздел 8.6](#86-голосовое-в-боте-speechkit) | [`13-seq-voice.puml`](plantuml/13-seq-voice.puml) |
| 14 | Загрузка и отдача файлов | [раздел 8.7](#87-загрузка-и-отдача-файлов) | [`14-seq-files.puml`](plantuml/14-seq-files.puml) |
| 15 | Карта: подложки и геокодер | [раздел 8.8](#88-карта-подложки-и-геокодер) | [`15-seq-map.puml`](plantuml/15-seq-map.puml) |
| 16 | Демо-оплата квитанции | [раздел 8.9](#89-демо-оплата-квитанции) | [`16-seq-demo-payment.puml`](plantuml/16-seq-demo-payment.puml) |
| 17 | Деплой и мониторинг стенда | [раздел 8.10](#810-деплой-и-мониторинг-стенда) | [`17-seq-deploy-uptime.puml`](plantuml/17-seq-deploy-uptime.puml) |

Условные обозначения на всех диаграммах:

- сплошная линия - основной путь, работает в коде;
- пунктир - необязательная связь, фолбэк, подмена или разовая операция;
- синим - наша система, серым - внешняя реальная система, оранжевым - мок,
  заглушка, демо-режим или фолбэк вместо внешней системы.

## 1. Системный контекст

Решение живет внутри MAX: житель и сотрудник УК открывают мини-приложение из
клиента MAX, исполнитель работает только в боте, бот пишет в личные сообщения
и домовые чаты. Обязателен только MAX. Сервисы Yandex, подложки карты и
геокодер необязательны: без каждого есть фолбэк. ГИС ЖКХ и Реформа ЖКХ в
рантайме не вызываются - их данные собраны в сид заранее.

```mermaid
flowchart LR
    resident(["Житель<br/>собственник или арендатор"])
    staff(["Сотрудник УК<br/>creator / admin / employee"])
    executor(["Исполнитель<br/>только в боте"])
    checker(["Проверяющий API<br/>DATA-API, тестовый токен"])

    subgraph MAX["Платформа MAX"]
        client["Клиент MAX<br/>iOS / Android / desktop / web"]
        bridge["MAX Bridge<br/>st.max.ru/js/max-web-app.js"]
        botapi["MAX Bot API<br/>platform-api2.max.ru"]
    end

    zheka["Жэка Коммуналкин<br/>мини-приложение, бот, API, фоновые задачи"]

    subgraph YC["Yandex Cloud, необязательно"]
        llm["AI Studio<br/>yandexgpt-5-lite"]
        ocr["Vision OCR"]
        stt["SpeechKit"]
    end

    subgraph OSM["Карта, необязательно"]
        tiles["OpenFreeMap, OpenStreetMap<br/>подложки"]
        nominatim["Nominatim<br/>обратный геокодер"]
    end

    subgraph OPEN["Открытые данные, офлайн"]
        reforma["Реформа ЖКХ<br/>дома и УК"]
        gis["ГИС ЖКХ<br/>кадастр, износ, класс"]
    end

    gh["GitHub Actions<br/>деплой и мониторинг"]
    gzhi["ГЖИ<br/>жилищная инспекция, без API"]
    pay["Демо-оплата<br/>вместо эквайринга"]

    resident --> client
    staff --> client
    executor --> client
    client -- "открывает мини-приложение" --> bridge
    bridge -- "HTTPS /api, WebAppData" --> zheka
    checker -- "HTTPS /api, Bearer API_TEST_TOKEN" --> zheka
    botapi -- "апдейты: вебхук или опрос" --> zheka
    zheka -- "сообщения, карточки, закрепы, файлы" --> botapi
    botapi --> client
    zheka -. "категория и риск аварии" .-> llm
    zheka -. "показание по фото" .-> ocr
    zheka -. "расшифровка голосового" .-> stt
    zheka -. "прокси /tiles/ с кэшем" .-> tiles
    zheka -. "адрес по точке" .-> nominatim
    reforma -. "выгрузка в сид" .-> zheka
    gis -. "выгрузка в сид" .-> zheka
    gh -- "деплой по SSH, проверки" --> zheka
    resident -. "PDF жалобы от бота, подает сам" .-> gzhi
    zheka --- pay

    classDef ours fill:#dbeafe,stroke:#1d4ed8,color:#0f172a
    classDef ext fill:#e5e7eb,stroke:#4b5563,color:#111827
    classDef mock fill:#ffedd5,stroke:#c2410c,color:#431407
    class zheka ours
    class client,bridge,botapi,llm,ocr,stt,tiles,nominatim,reforma,gis,gh,gzhi ext
    class pay mock
```

## 2. Контейнеры

Все локальные компоненты поднимает `docker compose up`. Наружу опубликован
только порт nginx. `migrations` собирает образ `zheka:local`, а `api` и
`worker` берут его же (`pull_policy: never`) и отличаются только командой.
TLS в репозитории не настроен: на проде его снимает nginx хоста перед compose.

```mermaid
flowchart TB
    user(["Клиент MAX"])
    botapi["MAX Bot API"]
    yandex["Yandex Cloud<br/>AI Studio, Vision, SpeechKit"]
    tilesup["OpenFreeMap, OSM"]
    nominatim["Nominatim"]
    hosttls["nginx хоста<br/>TLS :443"]

    subgraph compose["docker compose"]
        nginx["nginx 1.27<br/>:80 на хосте, NGINX_PORT"]
        web["web<br/>nginx со статикой SPA<br/>React 19 + Vite, :80"]
        api["api<br/>gunicorn ASGI: FastAPI + maxo<br/>:7001"]
        worker["worker<br/>python -m zheka.broker<br/>прием задач + шедулер"]
        migrations["migrations<br/>alembic upgrade head<br/>собирает образ, разовый"]
        db[("database<br/>PostgreSQL 16.9")]
        redis[("redis 7.4")]
        files[/"bind mount<br/>backend/content -> /data/files"/]
        tilecache[("том zheka-tiles<br/>кэш подложек")]
    end

    user -- "HTTPS" --> hosttls
    botapi -- "POST /webhook" --> hosttls
    hosttls -- "HTTP" --> nginx
    nginx -- "/" --> web
    nginx -- "/api/, /files/, = /webhook" --> api
    nginx -- "/tiles/ofm/, /tiles/osm/" --> tilecache
    tilecache -. "промах кэша" .-> tilesup
    api -- "SQL" --> db
    worker -- "SQL" --> db
    migrations -- "DDL" --> db
    api -- "FSM бота, задачи, кэш геокодера" --> redis
    worker -- "стрим задач, FSM бота" --> redis
    api --- files
    worker --- files
    api -- "ответы бота, опрос" --> botapi
    worker -- "рассылки, карточки, диалоги" --> botapi
    api -. "LLM, OCR" .-> yandex
    worker -. "OCR, SpeechKit" .-> yandex
    api -. "reverse, 1 rps" .-> nominatim

    classDef ours fill:#dbeafe,stroke:#1d4ed8,color:#0f172a
    classDef store fill:#ede9fe,stroke:#6d28d9,color:#1e1b4b
    classDef ext fill:#e5e7eb,stroke:#4b5563,color:#111827
    class nginx,web,api,worker,migrations ours
    class db,redis,files,tilecache store
    class user,botapi,yandex,tilesup,nominatim,hosttls ext
```

Порядок старта задают `depends_on`: `database` и `redis` проходят healthcheck,
один раз отрабатывает `migrations`, затем стартуют `api` и `worker`, nginx
ждет здорового `api`.

| Контейнер | Что делает | Порт | Хранилища |
|-----------|-----------|------|-----------|
| `nginx` | Единая точка входа, разводит пути, кэширует подложки карты | 80 на хосте | том `zheka-tiles` |
| `web` | Собранный SPA, SPA-фолбэк, кэш `/assets/` | 80 в сети compose | - |
| `api` | REST мини-приложения и кабинета УК, бот на maxo в том же процессе | 7001 в сети compose | Postgres, Redis, файлы |
| `worker` | Прием задач taskiq и шедулер в одном процессе | - | Postgres, Redis, файлы |
| `migrations` | Собирает образ бэкенда, применяет alembic и завершается | - | Postgres |
| `database` | Данные домена, события аналитики, ключи идемпотентности | 5432 в сети compose | том `zheka-postgres` |
| `redis` | FSM и диалоги бота, очередь и расписание taskiq, кэш и слот Nominatim | 6379 в сети compose | том `zheka-redis` |

## 3. Компоненты бэкенда

Пакет `zheka`, Python 3.12, все асинхронно. Транспорт (`api`, `bot`,
`broker`) берет сервисы из контейнера dishka, сервисы работают с
репозиториями и публикуют задачи через `TaskPublisher`. Все, что ходит
наружу, лежит в `infra/`. Транзакцию закрывает одна точка на входе: HTTP -
`transaction_middleware`, задачи - `CommitMiddleware`, апдейты бота -
`TransactionMiddleware`.

```mermaid
flowchart TB
    subgraph transport["Транспорт"]
        direction LR
        httptx["api/middlewares<br/>trace id, транзакция:<br/>commit ниже 400, flush задач"]
        routes["api/routes + dependencies<br/>initData или тестовый токен,<br/>X-Org-Id, idempotency, квоты"]
        bot["bot<br/>maxo.dialogs, сценарии,<br/>user, transaction, throttling"]
        broker["broker<br/>worker: прием задач + шедулер,<br/>notifications, chats, bot_requests,<br/>meters, reminders, webhook, ..."]
    end

    subgraph core["core"]
        direction LR
        services["services<br/>заявки, счетчики, начисления,<br/>опросы, объявления, прием и доступ,<br/>УК, дом и карта, demo"]
        domain["models, enums, errors, ids,<br/>mask_pii, правила danger,<br/>pp290.json, workdays"]
        publisher["TaskPublisher<br/>задачи после коммита"]
    end

    subgraph infra["infra"]
        direction LR
        repos["database<br/>41 таблица, scoped_to_org"]
        sender["max/MaxSender<br/>30 rps бот, 2 rps чат,<br/>повтор после 429"]
        yandexc["yandex<br/>Classifier 3 с, Vision 3 с,<br/>Speech 10 с, квота 60 в час"]
        geo["nominatim<br/>слот 1 rps, кэш Redis"]
        pdf["pdf, fpdf2<br/>ГЖИ, реестр"]
    end

    subgraph ext["Хранилища и внешние системы"]
        direction LR
        pg[("PostgreSQL")]
        rds[("Redis")]
        fs[/"/data/files"/]
        maxapi["MAX Bot API"]
        yc["Yandex Cloud"]
        osm["Nominatim"]
    end

    di["di: dishka<br/>STRICT_VALIDATION"]
    seed["seed<br/>справочник и 17 демо-УК"]

    httptx --> routes
    routes --> services
    bot --> services
    broker --> services
    routes -- "OCR синхронно" --> yandexc
    broker -- "OCR и голос из бота" --> yandexc
    broker --> sender
    bot -- "ответ через фасад апдейта" --> maxapi
    bot -- "FSM, диалоги" --> rds
    services --> domain
    services --> publisher
    services --> repos
    services -- "classify" --> yandexc
    services --> geo
    services --> pdf
    services --> fs
    publisher -- "kiq" --> rds
    rds -. "задачи" .-> broker
    repos --> pg
    sender --> maxapi
    yandexc --> yc
    geo --> osm
    geo --> rds
    di -. "внедряет" .-> transport
    seed --> services

    classDef ours fill:#dbeafe,stroke:#1d4ed8,color:#0f172a
    classDef store fill:#ede9fe,stroke:#6d28d9,color:#1e1b4b
    classDef extc fill:#e5e7eb,stroke:#4b5563,color:#111827
    class httptx,routes,bot,broker,services,domain,publisher,repos,sender,yandexc,geo,pdf,di,seed ours
    class pg,rds,fs store
    class maxapi,yc,osm extc
```

Правила, которые видны на схеме:

- Сервис не отправляет сообщений сам: он публикует задачу, а `TaskPublisher`
  ставит ее в Redis только после коммита. Откат не отправляет ничего.
- Обработчик вебхука не качает файлы, не зовет OCR и SpeechKit - это задачи
  `bot_requests` и `meters`, чтобы уложиться в 30 секунд на ответ MAX.
- Подсказка категории и OCR из мини-приложения - синхронные вызовы с
  таймаутом 3 секунды, SpeechKit работает только из задачи.
- Изоляция УК - зависимость `current_org` и фильтр `scoped_to_org` в
  репозиториях: чужая УК - 403, чужой объект внутри своей - 404.

## 4. Компоненты фронтенда

Мини-приложение на React 19 + Vite, UI-кит `@maxhub/max-ui`, данные через
TanStack Query поверх `openapi-fetch`. Типы генерируются из `openapi.yaml` в
корне репозитория (`pnpm api`). Импорты идут только вниз: `app` -> `features`
-> `shared`, это проверяет eslint.

```mermaid
flowchart LR
    subgraph app["src/app"]
        router["router.tsx<br/>react-router 7"]
        loaders["session-loader, protected-loader,<br/>deeplink-loader"]
        transition["screen-transition"]
    end

    subgraph features["src/features"]
        resident["житель: onboarding, house, house-map,<br/>new-request, request, meters, charges,<br/>flat-confirmation, meetings, appointments, profile"]
        admin["кабинет УК: admin-requests, admin-houses,<br/>admin-analytics, admin-announcements,<br/>admin-polls, admin-reception, admin-org"]
        outside["outside-max<br/>заглушка вне MAX"]
    end

    subgraph shared["src/shared"]
        apiinst["api/instance<br/>openapi-fetch + openapi-react-query,<br/>authParams: WebAppData"]
        gen["api/schema/generated.ts<br/>из openapi.yaml"]
        mocks["api/mocks<br/>mock-config-server, около 25 файлов"]
        maxlib["lib/max<br/>launch, back-button, closing-confirmation,<br/>haptic, scan-code"]
        idem["lib/idempotency<br/>Idempotency-Key"]
        track["lib/analytics<br/>useTrack -> POST /api/events"]
        map["ui/map<br/>MapLibre GL, basemaps, tiles"]
        ui["ui<br/>card, status-pill, state, icon, ..."]
    end

    bridge["window.WebApp<br/>MAX Bridge"]
    backend["Бэкенд /api"]
    tiles["/tiles/ofm, /tiles/osm"]
    mockserver["mock-config-server<br/>:31299"]

    router --> loaders
    loaders --> apiinst
    router --> features
    features --> apiinst
    features --> ui
    features --> maxlib
    features --> track
    features --> idem
    resident --> map
    admin --> map
    track --> apiinst
    apiinst --> gen
    apiinst -- "initData" --> maxlib
    maxlib -- "initData, BackButton, HapticFeedback,<br/>openCodeReader, requestContact,<br/>closing confirmation" --> bridge
    apiinst -- "HTTP /api" --> backend
    map -- "подложки" --> tiles
    apiinst -. "dev: прокси Vite" .-> mockserver
    mocks --> mockserver
    gen -- "типы ответов" --> mocks

    classDef ours fill:#dbeafe,stroke:#1d4ed8,color:#0f172a
    classDef ext fill:#e5e7eb,stroke:#4b5563,color:#111827
    classDef mock fill:#ffedd5,stroke:#c2410c,color:#431407
    class router,loaders,transition,resident,admin,apiinst,gen,maxlib,idem,track,map,ui ours
    class bridge,backend,tiles ext
    class outside,mocks,mockserver mock
```

## 5. Развертывание и доставка

Прод - один VPS с Docker. MAX принимает вебхук и открывает мини-приложение
только по HTTPS на 443 с настоящим сертификатом, поэтому перед compose стоит
nginx хоста с TLS. Push в `master` деплоит GitHub Actions по SSH, отдельный
workflow каждые 15 минут проверяет стенд и при сбое пишет капитану через Bot
API.

```mermaid
flowchart TB
    subgraph github["GitHub"]
        repo["репозиторий, ветка master"]
        deploy["Actions: deploy.yml<br/>заморозка после 30.09 12:00 МСК"]
        uptime["Actions: uptime.yml<br/>каждые 15 минут, затем раз в час"]
    end

    subgraph internet["Интернет"]
        maxcloud["MAX<br/>клиенты и Bot API"]
        yandex["Yandex Cloud"]
        osm["OpenFreeMap, OSM, Nominatim"]
    end

    subgraph vps["VPS"]
        hostnginx["nginx хоста<br/>TLS :443"]
        script["deploy.sh, reseed.sh"]
        subgraph net["docker compose"]
            nginx["nginx :80"]
            web["web"]
            api["api<br/>воркер gunicorn на логический CPU,<br/>MAX_BOT_MODE=webhook"]
            worker["worker"]
            db[("database")]
            redis[("redis")]
        end
        vols[("тома zheka-postgres,<br/>zheka-redis, zheka-tiles")]
        content[/"backend/content"/]
    end

    repo -- "push" --> deploy
    deploy -- "SSH" --> script
    script -- "git merge --ff-only,<br/>compose up --build" --> net
    uptime -- "healthcheck и коммит, главная,<br/>вебхук без секрета = 403" --> hostnginx
    uptime -. "при сбое POST /messages" .-> maxcloud
    maxcloud -- "443" --> hostnginx
    hostnginx --> nginx
    nginx --> web
    nginx --> api
    api --> db
    api --> redis
    worker --> db
    worker --> redis
    db --- vols
    redis --- vols
    api --- content
    worker --- content
    api -- "исходящий HTTPS" --> maxcloud
    worker -- "исходящий HTTPS" --> maxcloud
    api -. "исходящий HTTPS" .-> yandex
    worker -. "исходящий HTTPS" .-> yandex
    nginx -. "подложки" .-> osm
    api -. "геокодер" .-> osm
```

Маршруты nginx в compose:

| Путь | Куда | Особенности |
|------|------|-------------|
| `/` | `web:80` | статика SPA, фолбэк на `index.html` |
| `= /api/files` | `api:7001` | `client_max_body_size 60m`: видео до 50 МБ |
| `/api/` | `api:7001` | `client_max_body_size 15m`, `/api` и `/api/` уводят на `/api/docs` |
| `/files/` | `api:7001` | файлы по подписанной ссылке, `X-Content-Type-Options: nosniff` |
| `/tiles/ofm/`, `/tiles/osm/` | OpenFreeMap, OSM | кэш в томе `zheka-tiles` до 2 ГБ, stale при ошибках источника |
| `= /webhook` | `api:7001` | таймауты 35 с, MAX ждет ответа 30 с |

## 6. Внешние системы: реальные и моки

Каждая строка - одна точка интеграции: наш компонент, реальная система и то,
что работает вместо нее, когда ее нет. «Мок» здесь - любая подмена: мок-сервер,
заглушка, фолбэк, демо-реализация, тестовый токен или данные-сиды.

```mermaid
flowchart LR
    subgraph i8["Доставка и мониторинг"]
        direction LR
        gh8["GitHub Actions"] -- "push в master" --> vps8["VPS: deploy.sh"]
        gh8 -- "uptime.yml" --> stand8["стенд: healthcheck,<br/>главная, вебхук"]
        gh8 -. "при сбое" .-> botapi8["MAX Bot API:<br/>сообщение капитану"]
    end

    subgraph i7["Данные домов и демо"]
        direction LR
        seed7["seed"] -. "выгрузка заранее" .-> reforma["Реформа ЖКХ<br/>дома, УК"]
        seed7 -. "выгрузка заранее" .-> gis["ГИС ЖКХ<br/>кадастр, износ"]
        seed7 --> demo7["17 демо-УК, модельные<br/>жители и начисления за полгода"]
        bot7["бот /start"] --> links7["demo_resident_N, demo_staff_N,<br/>demo_admin_N, demo_executor_N"]
    end

    subgraph i6["Деньги и документы"]
        direction LR
        charges["ChargesService"] -. "не делаем" .-> acq["Эквайринг"]
        charges --> pay["Демо-оплата: paid_at = now"]
        charges -. "точка интеграции" .-> bill["Биллинг УК"]
        charges --> modelbill["Модельные начисления"]
        pdf6["pdf/gji"] -. "житель подает сам" .-> gzhi["ГЖИ"]
    end

    subgraph i5["Карта"]
        direction LR
        map5["MapLibre + nginx /tiles/"] -- "промах кэша" --> tiles["OpenFreeMap, OSM"]
        map5 -. "нет WebGL или ошибка" .-> list5["выбор дома списком"]
        geo5["NominatimClient"] -- "1 rps, кэш 30 дней" --> nom["Nominatim"]
        geo5 -. "ожидание слота дольше 1,5 с" .-> nogeo["ошибка геокодера,<br/>дом только из справочника"]
    end

    subgraph i4["ИИ: Yandex Cloud"]
        direction LR
        cls["YandexClassifier"] -- "ключ задан" --> llm["AI Studio<br/>yandexgpt-5-lite"]
        cls -. "нет ключа, отказ, таймаут,<br/>60 в час исчерпаны" .-> rules["кнопки категорий<br/>и правила danger"]
        vis["VisionClient"] -- "ключ задан" --> ocr["Vision OCR"]
        vis -. "нет ключа или сбой" .-> manual["житель вводит число"]
        stt4["SpeechClient"] -- "MAX не расшифровал" --> stt["SpeechKit"]
        stt4 -. "нет ключа или сбой" .-> text4["просьба написать текстом"]
    end

    subgraph i3["Бот"]
        direction LR
        api3["api: maxo"] -- "MAX_BOT_MODE=webhook" --> botapi["MAX Bot API"]
        api3 -. "MAX_BOT_MODE=polling, локально" .-> polling["опрос GET /updates<br/>без домена и сертификата"]
        worker3["worker: MaxSender, keep_webhook"] --> botapi
    end

    subgraph i2["Бэкенд для фронтенда"]
        direction LR
        fe2["Мини-приложение"] -- "prod и compose" --> back["api за nginx"]
        fe2 -. "pnpm mock, DEV_API_TARGET" .-> mcs["mock-config-server :31299<br/>почти весь openapi.yaml"]
    end

    subgraph i1["Запуск и авторизация"]
        direction LR
        fe1["Мини-приложение"] -- "внутри MAX" --> bridge["MAX Bridge: initData"]
        fe1 -. "dev-сборка вне MAX" .-> devinit["WebAppData = dev"]
        fe1 -. "прод-сборка вне MAX" .-> outside["экран outside-max"]
        checker["DATA-API, curl"] -. "без MAX" .-> token["Bearer API_TEST_TOKEN:<br/>учетка «Проверяющий API»,<br/>демо-УК №5"]
    end

    classDef ours fill:#dbeafe,stroke:#1d4ed8,color:#0f172a
    classDef ext fill:#e5e7eb,stroke:#4b5563,color:#111827
    classDef mock fill:#ffedd5,stroke:#c2410c,color:#431407
    class fe1,fe2,back,api3,worker3,cls,vis,stt4,map5,geo5,charges,pdf6,seed7,bot7,gh8,vps8,stand8,checker ours
    class bridge,botapi,botapi8,llm,ocr,stt,tiles,nom,acq,bill,gzhi,reforma,gis ext
    class devinit,outside,token,mcs,polling,rules,manual,text4,list5,nogeo,pay,modelbill,demo7,links7 mock
```

| Внешняя система | Кто и как ходит | Настройка | Без нее или вместо нее |
|-----------------|-----------------|-----------|------------------------|
| MAX Bot API `platform-api2.max.ru` | `api` отвечает на апдейты, `worker` шлет уведомления, карточки в чатах, закрепы, диалоги, качает файлы из сообщений | `MAX_TOKEN` | не работает ничего, в Docker не воспроизвести |
| MAX вебхук (входящий) | MAX шлет апдейты на `/webhook`, секрет в `X-Max-Bot-Api-Secret`; `keep_webhook` каждые 10 минут перерегистрирует потерянный | `MAX_BOT_MODE`, `MAX_WEBHOOK_URL`, `MAX_SECRET_TOKEN` | локально `polling`, домен и сертификат не нужны |
| MAX Bridge | фронт читает `window.WebApp`: `initData`, `BackButton`, `HapticFeedback`, `openCodeReader` (QR квитанции), `requestContact` (телефон), подтверждение закрытия | - | dev-сборка вне MAX шлет `WebAppData: dev`, прод-сборка показывает `outside-max` |
| Подпись `initData` | `current_user` проверяет HMAC заголовка `WebAppData` на токене бота | `MAX_TOKEN` | тестовый токен `API_TEST_TOKEN` в `Authorization: Bearer` для проверки без MAX |
| Yandex AI Studio | `POST /api/requests/classify`, синхронно, 3 с, текст проходит `mask_pii` | `YANDEX_API_KEY`, `YANDEX_FOLDER_ID`, `YANDEX_MODEL` | категория кнопками, опасные фразы ловят правила `core/danger` |
| Yandex Vision OCR | `POST /api/meters/readings/recognize` синхронно, 3 с; фото счетчика в боте - задача `recognize_meter_photo` | `YANDEX_API_KEY`, `YANDEX_FOLDER_ID` | житель вводит число сам |
| Yandex SpeechKit | задача `transcribe_voice`, только если MAX не прислал свою расшифровку, 10 с | `YANDEX_API_KEY`, `YANDEX_FOLDER_ID` | бот просит написать текстом |
| Квота Yandex | 60 вызовов в час на пользователя на все три сервиса, в памяти процесса | - | ответ как без ключей |
| OpenFreeMap, OSM | подложки MapLibre через кэширующий прокси nginx `/tiles/` | - | карта не грузится, дом выбирается списком |
| Nominatim | `GET /api/houses/at`: адрес здания по тапу, 1 rps на приложение, кэш в Redis 30 дней | - | тап вне справочника не дает адреса |
| Реформа ЖКХ, ГИС ЖКХ | не вызываются: паспорт дома и УК собраны в `seed/data/*.csv` заранее | - | - |
| Эквайринг | не делаем | - | `POST /api/charges/{id}/pay` только ставит `paid_at` |
| Биллинг УК | не делаем, точка интеграции - таблица `charges` | - | модельные начисления за полгода в демо-УК |
| ГЖИ | API нет: `POST /api/requests/{id}/gji-pdf` ставит задачу, бот присылает PDF жалобы | - | житель подает сам |
| GitHub Actions | `deploy.yml` по SSH, `uptime.yml` проверяет стенд и пишет капитану в MAX | секреты репозитория | ручной `deploy.sh` на VPS |
| Фронт без бэкенда | `pnpm mock` поднимает `mock-config-server` на `:31299` с базой `/api` | `DEV_API_TARGET=http://localhost:31299` | состояние в памяти мок-сервера |

На стенде ключей Yandex нет, поэтому там все три сервиса Yandex работают в
режиме фолбэка.

## 7. Режимы окружения

Одни и те же точки подмены в трех режимах. Переключается окружением, код не
меняется.

```mermaid
flowchart TB
    subgraph prod["Прод: VPS"]
        p_fe["Мини-приложение в клиенте MAX"] --> p_tls["nginx хоста :443"]
        p_max["MAX Bot API"] -- "POST /webhook" --> p_tls
        p_tls --> p_ng["nginx compose :80"]
        p_ng --> p_api["api: MAX_BOT_MODE=webhook,<br/>воркер на CPU"]
        p_api -.-> p_yc["ключей Yandex нет:<br/>фолбэки"]
        p_chk["DATA-API"] -- "Bearer API_TEST_TOKEN" --> p_tls
    end

    subgraph local["Локально: docker compose"]
        l_br["Браузер или DATA-API"] --> l_ng["nginx :80"]
        l_ng --> l_api["api: MAX_BOT_MODE=polling,<br/>один воркер"]
        l_api -- "GET /updates" --> l_max["MAX Bot API"]
        l_api -.-> l_yc["YANDEX_* пусто или заданы"]
    end

    subgraph dev["Фронт отдельно: Vite dev"]
        d_vite["Vite :5173"] -- "прокси /api" --> d_target{"DEV_API_TARGET"}
        d_target -- "http://localhost" --> d_ng["бэкенд за nginx"]
        d_target -- "http://localhost:31299" --> d_mock["mock-config-server"]
        d_vite -- "прокси /tiles/ofm, /tiles/osm" --> d_tiles["OpenFreeMap, OSM"]
        d_vite -. "pnpm tunnel: reverse SSH" .-> d_remote["удаленный хост<br/>с доменом для клиента MAX"]
    end

    classDef mock fill:#ffedd5,stroke:#c2410c,color:#431407
    class p_yc,l_yc,d_mock mock
```

## 8. Ключевые сценарии

### 8.1. Запуск мини-приложения и авторизация

Логина нет: каждый запрос несет подписанные данные запуска MAX. Для проверки
без MAX есть тестовый токен одной служебной учетной записи.

```mermaid
sequenceDiagram
    autonumber
    actor U as Житель или сотрудник
    participant C as Клиент MAX
    participant B as MAX Bridge
    participant F as Мини-приложение
    participant N as nginx
    participant A as api
    participant D as PostgreSQL

    U->>C: Кнопка «Открыть приложение», QR или диплинк
    C->>F: Открывает мини-приложение
    F->>B: window.WebApp.initData, start_param
    alt Внутри MAX
        B-->>F: initData, подписанный MAX
    else Вне MAX
        B-->>F: пусто
        Note over F: dev-сборка шлет WebAppData = dev,<br/>прод-сборка показывает outside-max
    end
    F->>N: GET /api/me, WebAppData, X-Org-Id при нескольких УК
    N->>A: proxy_pass api:7001
    alt Bearer совпал с API_TEST_TOKEN
        A->>A: учетка «Проверяющий API»
    else WebAppData
        A->>A: HMAC initData на токене бота
    end
    alt Нет данных или подпись неверна
        A-->>F: 401
    else Подпись верна
        A->>D: аккаунт, согласие, жительства, роли в УК
        A-->>F: 200 профиль
        Note over F: session-loader: нет согласия или дома -> онбординг,<br/>deeplink-loader разбирает start_param
    end
```

### 8.2. Апдейты бота: вебхук и опрос

```mermaid
sequenceDiagram
    autonumber
    participant M as MAX Bot API
    participant N as nginx
    participant A as api: FastAPI + maxo
    participant R as Redis
    participant D as PostgreSQL
    participant W as worker

    Note over A: lifespan выбирает режим по MAX_BOT_MODE
    alt webhook, прод
        A->>M: POST /subscriptions, url = MAX_WEBHOOK_URL
        M->>N: POST /webhook, X-Max-Bot-Api-Secret
        N->>A: proxy, read timeout 35 с
        A->>A: проверка секрета
        A-->>M: 200 сразу, обработка в фоне
    else polling, локально
        loop пока жив воркер api
            A->>M: GET /updates
            M-->>A: апдейты
        end
    end
    A->>A: ThrottlingMiddleware: пока идет апдейт пользователя, следующие пропускаются
    A->>R: FSM и стек диалогов maxo.dialogs
    A->>D: UserMiddleware, TransactionMiddleware
    A->>M: ответ через фасад апдейта
    opt Файлы, голосовое, фото счетчика
        A->>R: задача после коммита
        R->>W: bot_requests, meters
    end
    loop каждые 10 минут, только webhook
        W->>M: GET /subscriptions
        opt Вебхука нет в подписках
            W->>M: POST /subscriptions заново
        end
    end
```

### 8.3. Транзакция, задачи и уведомления

Задача уходит в очередь только после коммита. Рассылка - цикл через очередь с
ограничителями платформы.

```mermaid
sequenceDiagram
    autonumber
    participant F as Мини-приложение
    participant A as api: transaction_middleware
    participant S as Сервис
    participant P as TaskPublisher
    participant D as PostgreSQL
    participant R as Redis
    participant W as worker
    participant X as MaxSender
    participant M as MAX Bot API

    F->>A: POST /api/requests, Idempotency-Key
    A->>S: создать заявку
    S->>D: запись в транзакции
    S->>P: publish(send_to_user, broadcast_to_chats, ...)
    alt Ответ ниже 400
        A->>D: commit
        A->>P: flush
        P->>R: kiq задач
    else Ошибка
        A->>D: rollback
        Note over P: задачи не уходят
    end
    A-->>F: карточка заявки
    R->>W: задача
    W->>D: получатели, уровень из notification_settings
    loop по каждому получателю
        W->>X: send_message, notify по настройке
        X->>X: 30 rps на бот, 2 rps на чат
        X->>M: POST /messages
        alt 429
            X->>M: один повтор через секунду
        else Бот остановлен или не запускался
            M-->>X: 403 или 404
            X-->>W: пропуск
        end
    end
    W->>D: CommitMiddleware
```

### 8.4. Подсказка категории заявки (LLM)

```mermaid
sequenceDiagram
    autonumber
    actor U as Житель
    participant F as Мини-приложение
    participant A as api
    participant Q as YandexQuota
    participant L as YandexClassifier
    participant Y as Yandex AI Studio

    U->>F: Описывает проблему своими словами
    F->>A: POST /api/requests/classify
    A->>Q: take(user_id), 60 в час
    alt Текст короткий или квота исчерпана
        A-->>F: без подсказки
    else Можно звать модель
        A->>L: classify(text)
        alt Нет ключа или ключ уже отвергнут
            L-->>A: пусто
        else Ключ задан
            L->>L: mask_pii: телефоны, e-mail, счета, «кв. 45»
            L->>Y: completion, temperature 0, таймаут 3 с
            alt Ответ JSON
                Y-->>L: category, emergency_probability
            else 401 или 403
                L->>L: выключить до перезапуска процесса
            else Таймаут или мусор
                Y-->>L: ошибка
            end
            L-->>A: категория или пусто
        end
        A->>A: danger(text): правила аварии поверх модели
        A-->>F: категория и признак аварии
    end
    Note over F: кнопки категорий видны всегда, житель выбирает сам
```

### 8.5. Показание счетчика по фото (OCR)

Два входа: форма мини-приложения (синхронно) и фото в диалог с ботом
(фоновая задача). Любой сбой сводится к пустому полю.

```mermaid
sequenceDiagram
    autonumber
    actor U as Житель
    participant F as Мини-приложение
    participant BOT as Бот
    participant A as api
    participant W as worker
    participant V as VisionClient
    participant Y as Yandex Vision OCR
    participant M as MAX Bot API

    alt Мини-приложение
        U->>F: Фото в форме показаний
        F->>A: POST /api/files, затем /api/meters/readings/recognize
        A->>V: recognize(photo_path), если квота есть
    else Бот
        U->>BOT: Фото счетчика в диалог
        BOT->>W: задача recognize_meter_photo
        W->>M: скачать фото из сообщения
        W->>V: recognize(photo_name), если квота есть
    end
    alt Ключ задан
        V->>Y: POST recognizeText, таймаут 3 с
        Y-->>V: текст или ошибка
        V-->>V: первое число или None
    else Ключа нет
        V-->>V: None без похода в сеть
    end
    alt Мини-приложение
        A-->>F: values или null
    else Бот
        W->>M: окно подтверждения с распознанным числом или пустым
    end
```

### 8.6. Голосовое в боте (SpeechKit)

```mermaid
sequenceDiagram
    autonumber
    actor U as Житель
    participant M as MAX Bot API
    participant BOT as api: бот
    participant R as Redis
    participant W as worker
    participant S as SpeechClient
    participant Y as Yandex SpeechKit

    U->>M: Голосовое с описанием заявки
    M->>BOT: апдейт
    BOT->>M: «Разбираю голосовое»
    BOT->>R: задача transcribe_voice после коммита
    R->>W: задача
    W->>W: пауза, чтобы MAX успел расшифровать
    W->>M: GET сообщения по mid
    alt MAX прислал расшифровку
        M-->>W: текст
    else Расшифровки нет, ключ задан и квота есть
        W->>M: скачать аудио oggopus
        W->>S: recognize(audio)
        S->>Y: POST stt:recognize, таймаут 10 с
        Y-->>S: текст или ошибка
    end
    alt Текст есть
        W->>M: черновик заявки с текстом
    else Пусто
        W->>M: «Не разобрал голосовое, напишите текстом»
    end
```

### 8.7. Загрузка и отдача файлов

Тег `<img>` не умеет слать `WebAppData`, поэтому право на файл проверяется
при выдаче ссылки, а ссылка подписана HMAC и живет час.

```mermaid
sequenceDiagram
    autonumber
    participant F as Мини-приложение
    participant N as nginx
    participant A as api: FilesService
    participant FS as /data/files

    F->>N: POST /api/files, до 60 МБ на nginx
    N->>A: proxy
    A->>A: согласие, квота 30 загрузок в час
    A->>FS: запись кусками, фото до 10 МБ, видео до 50 МБ
    A->>A: тип по первым байтам: JPEG, PNG, WEBP, HEIC, MP4, MOV
    alt Сигнатура не подошла
        A->>FS: удалить
        A-->>F: 400
    else Файл принят
        A-->>F: name, url = /files/name?exp=...&sig=...
    end
    F->>N: GET /files/name?exp&sig из тега img
    N->>A: proxy, nosniff
    A->>A: имя по шаблону, срок, HMAC
    alt Подпись верна и срок не истек
        A->>FS: чтение
        A-->>F: 200 файл
    else Подделка или истек срок
        A-->>F: 404 «Файл не найден»
    end
    Note over FS: 03:30 уборка: черновики без ссылок старше суток,<br/>фото закрытых заявок и показаний старше 12 месяцев
```

### 8.8. Карта: подложки и геокодер

```mermaid
sequenceDiagram
    autonumber
    actor U as Житель
    participant F as Мини-приложение: MapLibre
    participant N as nginx /tiles/
    participant T as OpenFreeMap, OSM
    participant A as api
    participant R as Redis
    participant G as Nominatim

    F->>N: GET /tiles/ofm/... или /tiles/osm/...
    alt Есть в кэше zheka-tiles
        N-->>F: тайл, X-Cache HIT
    else Промах
        N->>T: HTTPS, свой User-Agent
        T-->>N: тайл
        N-->>F: тайл, в кэш
    end
    Note over F: нет WebGL или карта упала - выбор дома списком
    F->>A: GET /api/map/houses в рамке карты
    A-->>F: дома справочника
    U->>F: Тап по зданию вне справочника
    F->>A: GET /api/houses/at?lat&lon, 60 в час
    A->>R: кэш по точке, 30 дней
    alt Есть в кэше
        R-->>A: адрес
    else Промах кэша
        A->>R: слот 1 rps на приложение
        alt Слот получен за 1,5 с
            A->>G: reverse, таймаут 3 с
            G-->>A: адрес или ничего
            A->>R: в кэш
        else Слот не дождались
            A-->>F: ошибка геокодера
        end
    end
    A-->>F: дом, адрес или пусто
```

### 8.9. Демо-оплата квитанции

Реальной оплаты нет: ручка имитирует успех эквайринга, чтобы сценарий
квитанции проходился до конца.

```mermaid
sequenceDiagram
    autonumber
    actor U as Житель
    participant F as Мини-приложение
    participant A as api: ChargesService
    participant D as PostgreSQL

    U->>F: Оплатить квитанцию
    F->>A: POST /api/charges/charge_id/pay
    A->>D: квитанция и подтвержденный житель квартиры
    alt Нет права видеть начисления, например арендатор
        A-->>F: 403
    else Уже оплачена
        A-->>F: 409
    else Можно платить
        A->>D: paid_at = now
        A-->>F: charge_id, paid_at
    end
    Note over A,D: в проде здесь был бы вызов эквайринга<br/>и прием его callback
```

### 8.10. Деплой и мониторинг стенда

```mermaid
sequenceDiagram
    autonumber
    participant Dev as Команда
    participant GH as GitHub Actions
    participant V as VPS
    participant C as docker compose
    participant S as Стенд, HTTPS
    participant M as MAX Bot API

    Dev->>GH: push в master
    GH->>GH: проверка заморозки сдачи
    GH->>V: SSH deploy.sh
    V->>V: git fetch, merge --ff-only, BUILD_COMMIT
    V->>C: compose up -d --build, restart nginx
    loop uptime.yml по расписанию
        GH->>S: GET /api/healthcheck, ждет ok и commit
        GH->>S: GET /
        GH->>S: POST /webhook без секрета, ждет 403
        opt Любая проверка не прошла
            GH->>M: POST /messages капитану
        end
    end
    Note over V: reseed.sh: бэкап, down -v, up, python -m zheka.seed,<br/>затем прогрев проверок DATA-API
```
