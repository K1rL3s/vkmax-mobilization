# Сравнение архитектуры: `prod_hacaton_2025` против `zheka`

Разбор референса https://github.com/IvanKirpichnikov/prod_hacaton_2025 (клон от 2026-09-16,
shallow, единственный видимый коммит `de2707b docs(): add diagrams to rfc`) и построчное
сравнение с нашим бэкендом. Главный вопрос - переходить ли на классический (императивный)
маппинг SQLAlchemy.

Все утверждения про обе стороны проверены чтением файлов, механика императивного маппинга -
исполнением проб на нашем же `.venv` (SQLAlchemy 2.0.53). Где написано «проверено» - значит
скрипт был запущен, а не вычитан из документации.

---

## 1. Что такое референс

Пакет внутри называется `template_project` - это не проект с нуля, а чей-то шаблон чистой
архитектуры, на который натянули хакатонский кейс «сколько ты зарабатываешь»: пользователь
загружает резюме, ML-сервис считает эмбеддинг, ищет похожие вакансии по pgvector и предсказывает
зарплату.

**Размер.** 135 файлов `.py`, 7664 строки, из них:

| Слой | LOC |
|------|-----|
| `application/` | 2291 |
| `web_api/` | 1919 |
| `adapters/` | 1000 |
| `ml/` | 400 |
| `tests/` | 1428 |

8 файлов `entity.py`, 16 интеракторов, 7 файлов с протоколами гейтвеев, 13 таблиц.

**Стек.** FastAPI 0.119 + dishka 1.7 + SQLAlchemy 2.0.44 + psycopg3 + pgvector + adaptix + pydantic,
отдельный ML-сервис на torch/sentence-transformers, alembic, uv, hatchling. Линтеры совпадают с
нашими почти один в один: mypy strict, ruff, codespell, bandit.

**Насколько зрелым выглядит.** Инфраструктурно - серьёзно: `RFC.md` с диаграммами, ansible-роли,
`.gitlab-ci.yml` на 10 КБ, Coolify, Grafana, Prometheus, cAdvisor, отдельные конфиги для каждого
сервиса. Внутри кода - нет:

- три миграции подряд названы `"empty message"`, файлы `2c99db38e99b_.py` без слага;
- `# TODO: N+1` прямо в `adapters/data_gateways/resume.py:69`, и это не единственное место -
  `GetResumeListInteractor.execute` делает 4 запроса на каждое резюме в цикле;
- `application/resume/interactors/get.py` - 250 строк, где один и тот же блок сборки ответа
  скопирован три раза подряд для get / list / history;
- `application/user/interactors/get_me.py` - мёртвый код: `GetMeInteractor` не зарегистрирован
  ни в одном провайдере, не подключён ни к одному роуту, а его `get_converter(User, GetMeResponse)`
  упал бы на импорте, потому что у сущности `User` нет поля `email`;
- пароли от Coolify и Grafana лежат в `README.md` открытым текстом.

**Вывод для доверия.** Слоям, направлению зависимостей и механике императивного маппинга верить
можно - они сделаны аккуратно и последовательно. Конкретным реализациям (интеракторы резюме,
запросы, миграции) - нет, там видно, как за два дня до дедлайна перестали следить за собой.
Это ровно наш сценарий, и это полезно: видно, что именно ломается первым под давлением.

---

## 2. Архитектура референса

### Дерево

```
src/template_project/
├── application/              <- ядро: ничего не знает про SQLAlchemy, FastAPI и pydantic
│   ├── common/
│   │   ├── entity.py             Entity[EntityId], to_entity
│   │   ├── data_structure.py     to_data_structure (DTO)
│   │   ├── interactor.py         to_interactor
│   │   ├── errors.py             ApplicationError, to_error
│   │   ├── unit_of_work.py       Protocol UnitOfWork
│   │   ├── identity_provider.py  Protocol IdentityProvider
│   │   ├── containers.py         SecretString
│   │   ├── enums.py              EducationGrade, ExperienceType
│   │   ├── file_storage.py, embedding.py, notifications/, oauth/
│   ├── user/
│   │   ├── entity.py, errors.py, data_gateway.py, password_utils.py
│   │   ├── interactors/get_me.py
│   │   └── profile/{entity,data_gateway,interactors/}
│   ├── auth_identity/{entity,errors,data_gateway,interactors/{sign_in,sign_up}}
│   ├── access_token/{entity,entity_factory,cryptographer,data_gateway,errors}
│   ├── resume/{entity,errors,data_gateway,interactors/{add,edit,get,predict_model,prediction_pipeline}}
│   ├── vacancy/{entity,data_gateway,data_structure,vector_generator}
│   └── notification_device/{entity,errors,data_gateway,interactors/}
├── adapters/                 <- реализации портов
│   ├── data_gateways/
│   │   ├── tables.py             <<< ВСЕ Table + registry.map_imperatively, 280 строк
│   │   ├── user.py, resume.py, vacancy.py, profile.py, auth_identity.py,
│   │   ├── access_token.py, key_skills.py, notification_device.py
│   │   └── unit_of_work.py (уровнем выше, в adapters/)
│   ├── access_token/{cryptographer,factory}
│   ├── oauth/yandex.py, notifications/fcm.py, s3_storage.py
│   ├── embedding/minilm_embedder.py, generators/, ml_api_gateway.py
│   └── password_utils.py
├── web_api/                  <- presentation
│   ├── entry_point.py            make_ioc -> make_asgi_application -> uvicorn
│   ├── configuration.py          TOML через adaptix Retort
│   ├── identity_provider.py      реализация IdentityProvider поверх Request
│   ├── ioc/                      11 провайдеров dishka + make.py
│   └── routes/                   auth, profile, resume, key_skills, notification, storage, healthcheck
├── ml/                       <- второй сервис, свой FastAPI, свой ioc
└── migrations/               env.py + versions/
```

### Направление зависимостей

Проверено grep-ом:

- `application/` не импортирует **ничего** из `adapters/`, `web_api/`, `sqlalchemy`, `fastapi`,
  `pydantic`. Ноль совпадений. Ядро действительно чистое.
- `adapters/` импортирует `application/` (протоколы и сущности) - и один раз протекает наверх:
  `adapters/access_token/factory.py:6` тянет `from template_project.web_api.configuration import AccessTokenConfiguration`.
  Единственное нарушение во всём проекте.
- `web_api/` импортирует всё.

Это классическая чистая архитектура (Clean Architecture дядюшки Боба, что прямо заявлено в
`RFC.md`), а не гексагон и не вертикальные слайсы. Внутри `application/` есть слабая нарезка по
доменам (`user/`, `resume/`, `vacancy/`), но это папки, а не слайсы: общие вещи живут в `common/`,
и интерактор резюме свободно тянет `user.entity`.

Одна деталь, которая стоит отдельного упоминания: **`application/` зависит от `adaptix`** через
`application/user/interactors/get_me.py:1`. То есть «ядро без внешних зависимостей» - декларация,
которая уже надтреснута, и надтреснута она в мёртвом файле.

---

## 3. Императивный маппинг в деталях

Весь маппинг живёт в одном файле - `src/template_project/adapters/data_gateways/tables.py`.
Дальше - полная механика, её хватит, чтобы воспроизвести подход не открывая референс.

### 3.1. Реестр и метаданные

```python
meta_data: Final = MetaData()
mapper_registry: Final = registry()
```

Обратите внимание: `registry()` создан **без** `metadata=meta_data`, то есть у реестра свои
метаданные, а таблицы регистрируются в `meta_data` напрямую. Работает потому, что
`map_imperatively` получает уже готовый объект `Table` и метаданные реестра не использует.
Naming convention не задан вообще - имена констрейнтов раздаёт Postgres по умолчанию.

### 3.2. Таблицы

```python
user_table: Final = Table(
    "users",
    meta_data,
    Column("id", UUID, primary_key=True),
    Column("deleted_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

auth_identity_table: Final = Table(
    "auth_identities",
    meta_data,
    Column("id", UUID, primary_key=True),
    Column("user_id", UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("method", Enum(AuthMethod, name="auth_method"), nullable=False),
    Column("identifier", String, nullable=False),
    Column("secret_key", String, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("method", "identifier", name="uq_auth_method_identifier"),
)
```

Никаких миксинов: `id`, `created_at`, `deleted_at` выписаны руками в каждой из 13 таблиц.
Порядок колонок - буквально порядок строк, и он не выдержан: у `users` это `id, deleted_at,
created_at`, у `resume` - `id, deleted_at, created_at, user_id, ...`, у `auth_identities` -
`created_at` в конце. Аналога нашего `sort_order` тут нет и не нужно.

Индексы объявлены отдельными модульными константами после таблиц:

```python
vacancy_embedding_vector_cosine_index: Final = Index(
    "ix_vacancy_embedding_vector_cosine",
    vacancy_embedding_table.c.vector,
    postgresql_using="hnsw",
    postgresql_ops={"vector": "vector_cosine_ops"},
    postgresql_with={"m": 32, "ef_construction": 256},
)
```

### 3.3. Вызов маппера

В самом низу того же файла, на уровне модуля:

```python
mapper_registry.map_imperatively(User, user_table)
mapper_registry.map_imperatively(AccessToken, access_token_table)
mapper_registry.map_imperatively(AuthIdentity, auth_identity_table)
mapper_registry.map_imperatively(Profile, profile_table)
mapper_registry.map_imperatively(NotificationDevice, notification_device_table)
mapper_registry.map_imperatively(
    Resume,
    resume_table,
    properties={
        "key_skills": resume_table.c.key_skills,
        "experience_type": resume_table.c.experience_type,
    },
)
```

**Когда это выполняется:** в момент первого импорта модуля `tables.py`. Никакой явной функции
`setup_mappers()` нет, конфигурация - побочный эффект импорта. Импортируют его восемь гейтвеев
(`from template_project.adapters.data_gateways.tables import user_table`) и `migrations/env.py`.
Это и есть главный подводный камень схемы: **импорт доменной сущности сам по себе её не мапит**.
Пока `tables.py` не импортирован, `select(User)` упадёт с `UnmappedClassError`.

Блоки `properties={...}` в `Resume`, `ResumePrediction`, `Vacancy` не делают ничего: они повторяют
то, что маппер и так вывел бы по совпадению имён. Это карго-культ, скопированный из документации.

### 3.4. Доменная сущность

```python
# application/common/entity.py
@dataclass_transform(kw_only_default=True)
def to_entity[EntityCLsT](entity_cls: type[EntityCLsT]) -> type[EntityCLsT]:
    return dataclass(kw_only=True)(entity_cls)


@to_entity
class Entity[EntityId: UUID](Hashable):
    id: EntityId
    created_at: datetime
    deleted_at: datetime | None = None

    def ensure_not_deleted(self) -> None:
        if self.deleted_at is not None:
            raise EntityAlreadyDeletedError(entity_name=self.__class__.__name__)

    @override
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Entity):
            return cast(bool, self.id == other.id)
        return NotImplemented
```

```python
# application/user/entity.py
UserId = NewType("UserId", UUID)

@to_entity
class User(Entity[UserId]):
    @classmethod
    def factory(cls) -> Self:
        return cls(id=UserId(uuid7()), created_at=datetime.now(tz=UTC))
```

Три вещи тут выбраны намеренно и все три критичны:

1. **`dataclass(kw_only=True)` - и всё.** Ни `frozen`, ни `slots`. Это не небрежность, это
   требование SQLAlchemy (см. 3.8).
2. **Идентификаторы - `NewType` поверх `UUID`**, и они используются в самой сущности
   (`user_id: UserId`), а не только на границах.
3. **`__init__` не переопределяется.** Конструирование идёт через `@classmethod factory`,
   который генерирует `uuid7()` и `created_at` на стороне приложения, а не базы. Поэтому в
   таблицах нет ни `server_default`, ни `autoincrement` для id.

Поведение объекта после маппинга (проверено): `dataclasses.is_dataclass(C) is True`, `__repr__`
и `__eq__` от датакласса живы, в `__dict__` появляется `_sa_instance_state` рядом с полями.

### 3.5. Как выражены связи

**Никак.** `grep -rn "relationship\|backref\|composite\|column_property"` по всему референсу даёт
ноль совпадений. Все связи - голые колонки `user_id`, `resume_id` плюс `ForeignKey`, а сборка
агрегата делается руками в интеракторе пятью последовательными запросами:

```python
# application/resume/interactors/get.py
resume = await self.resume_data_gateway.load_by_resume_id(resume_id)
resume_prediction = await self.resume_prediction_data_gateway.load_by_resume_id(resume.id)
experiences = await self.resume_experience_data_gateway.load_by_resume_id(resume.id)
educations = await self.resume_education_data_gateway.load_by_resume_id(resume.id)
projects = await self.resume_project_data_gateway.load_by_resume_id(resume.id)
```

Это **находка, а не упущение**: у нас в `zheka/infra/database/models/` тоже ровно ноль
`relationship` (проверено по всем 18 файлам). То есть самая тяжёлая часть императивного
маппинга - переезд отношений и `lazy=`-стратегий - нас просто не касается. Ленивая загрузка
не может сломаться там, где её нет.

### 3.6. Энумы и value objects

Энумы - стандартный `sqlalchemy.Enum` прямо в колонке: `Column("method", Enum(AuthMethod,
name="auth_method"), nullable=False)`. Наш хелпер `pg_enum` с `values_callable` там отсутствует,
из-за чего в БД лежат **имена** членов (`BACHELOR`), а не значения (`bachelor`). Плагина
`alembic-postgresql-enum` тоже нет, поэтому добавление члена в энум для их autogenerate невидимо
и чинится руками.

Value objects есть ровно один - `SecretString` в `application/common/containers.py`, и он не
мапится в БД, а только прячет пароль в логах. Ни `composite()`, ни кастомных типов для доменных
значений нет. Зато есть два `TypeDecorator` для откровенно инфраструктурных задач - `StringArrayType`
(list[str] в JSONB) и `ExperienceTypeType`, причём второй - это ручная замена `Enum`, написанная
на 30 строк защитного кода с `isinstance`-лесенкой:

```python
class ExperienceTypeType(TypeDecorator[ExperienceType]):
    impl: Any = String
    cache_ok: bool | None = True

    @override
    def process_result_value(self, value: Any, dialect: Any) -> ExperienceType:
        if value is None:
            raise ValueError("experience_type cannot be None")
        if isinstance(value, ExperienceType):
            return value
        if isinstance(value, str):
            try:
                return ExperienceType(value)
            except ValueError as err:
                raise ValueError(f"Invalid experience_type value: {value}") from err
        raise ValueError(f"Cannot convert {type(value)} to ExperienceType")
```

Это написано потому, что в `vacancy_table` то же поле объявлено как `Column("experience_type",
String, ...)`, а в `resume_table` - как `ExperienceTypeType()`. Одно понятие, два разных типа в
одной схеме. Брать не надо.

### 3.7. Что видит alembic

```python
# migrations/env.py
from template_project.adapters.data_gateways.tables import meta_data
target_metadata = meta_data
```

Ровно так же, как у нас, только источник метаданных - модуль с таблицами, а не декларативная
база. Autogenerate видит **абсолютно то же самое**: `MetaData` не знает, декларативно она
наполнена или императивно. Побочный эффект: импорт `meta_data` заодно выполняет все
`map_imperatively`, хотя alembic-у они не нужны.

Один настоящий минус их варианта виден в сгенерированной миграции:

```python
# migrations/versions/9a32674539dd_.py
import template_project.adapters.data_gateways.tables
from template_project.adapters.data_gateways.tables import StringArrayType
...
sa.Column('key_skills', template_project.adapters.data_gateways.tables.StringArrayType(astext_type=Text()), ...)
```

Кастомный `TypeDecorator` вмораживает путь к модулю приложения в файл миграции навсегда. Переименуете
модуль - сломается история. Это цена `TypeDecorator`, а не императивного маппинга, но видно её именно здесь.

Их `env.py` при этом заметно слабее нашего: синхронный `engine_from_config`, нет `compare_type=True`,
нет плагина энумов, комментарии из шаблона alembic не вычищены.

### 3.8. Что я проверил исполнением (это важнее всего остального в разделе)

Запустил пробы на нашем `.venv` с SQLAlchemy 2.0.53 и нашим же `zheka/base.py`:

| Вариант класса | Результат |
|---|---|
| `ZhekaType` (frozen=True, slots=True) | `map_imperatively` проходит, но **инстанс не создать**: `TypeError: cannot create weak reference to 'A' object` |
| `ZhekaMutableType` (frozen=False, slots=True) | то же самое - падает на `weakref` |
| `class C(ZhekaMutableType, slots=False)` | **работает полностью** |
| `@dataclass(frozen=True)` без slots | `FrozenInstanceError: cannot assign to field '_sa_instance_state'` |
| `@dataclass(kw_only=True)` (как в референсе) | работает |

Отсюда железное следствие для нас: **доменная сущность, участвующая в императивном маппинге, не
может быть ни frozen, ни slots**. Наш `ZhekaType` по умолчанию и то и другое, `ZhekaMutableType` -
slots. Любой маппинг на них потребует явного `slots=False`, то есть третьего варианта базового
класса.

Что при этом работает штатно (тоже проверено round-trip-ом на sqlite):

- запись, чтение, `session.get`, identity map (`got is s.get(C, got.id)` -> `True`);
- грязное отслеживание: `got.name = "y"; s.commit()` записывает изменение;
- загрузка из БД **минует `__init__`** - поэтому сущность может иметь обязательные поля без
  дефолтов, и SQLAlchemy их не потребует;
- ловушка: поле датакласса, которого нет в `Table`, после загрузки из БД **отсутствует на
  объекте вообще** (`getattr(got, "extra")` -> `AttributeError`), хотя при ручном конструировании
  оно есть. Разное поведение одного класса в зависимости от происхождения объекта.

И самая ценная проба - **запросы в репозиториях после перехода не меняются**:

```
class attr is instrumented: InstrumentedAttribute
select(U).where(U.max_user_id == 5) -> SELECT u.id, u.max_user_id, u.name FROM u WHERE u.max_user_id = :max_user_id_1
session.get(U, 1): U(id=1, max_user_id=7, name='a')
pg_insert(U) (class, not table) also works
```

То есть `select(User).where(User.max_user_id == ...)`, `session.get(User, id)`,
`pg_insert(User).returning(User)` и наш `scoped_to_org(select(Request), Request.house_id, org_id)`
после `map_imperatively` продолжают работать **без единой правки**. Референс пишет
`user_table.c.id` по своей воле, а не по необходимости.

---

## 4. Сравнение с zheka

| Аспект | Референс | zheka сейчас | В чём реальная разница |
|---|---|---|---|
| **Маппинг** | `Table` + `registry.map_imperatively` в `adapters/data_gateways/tables.py`, 13 таблиц | Declarative: `Mapped[...] = mapped_column(...)`, 32 класса в 18 файлах, 221 колонка | Стилистическая. Схема на выходе одинаковая, запросы одинаковые. Разница только в том, знает ли класс сущности про SQLAlchemy |
| **Доменный слой** | Есть: `application/` с нулём инфраструктурных импортов | Нет. `zheka/core/` - это enums, ids, errors и два сервиса; данные живут в ORM-моделях | Настоящая разница. У нас ORM-модель **и есть** доменная модель |
| **Связи** | Ноль `relationship`, агрегаты собираются руками | Ноль `relationship`, то же самое | **Разницы нет.** Совпадение, которое снимает 80% риска перехода |
| **Репозитории** | `Protocol` в `application/*/data_gateway.py` + `Default*DataGateway` в `adapters/`. Возвращают сущности | `BaseAlchemyRepo` с `__slots__ = ("_session",)`, конкретные классы без интерфейсов. Возвращают ORM-модели | Разница в церемонии: 7 файлов протоколов на 8 реализаций. Возвращаемое значение фактически то же - маппленный объект |
| **Транзакции** | Явный `UnitOfWork.add()/commit()`, интерактор вызывает `commit()` руками. `add()` делает `flush()` | Коммит на выходе из scope: `di/database/session.py` коммитит в `else` генератора, `broker/middlewares.py:CommitMiddleware` - в `post_execute` | Наш вариант **строже**: забыть коммит нельзя, откат при исключении гарантирован кодом, а не дисциплиной. У них `sign_up_yandex` при раннем `raise` тихо теряет добавленное |
| **DI** | dishka + `STRICT_VALIDATION`, 11 провайдеров, `provide_all` и `WithParents[...]` | dishka без `validation_settings`, 7 провайдеров, каждый репозиторий - отдельный метод `@provide` с ручным `return UsersRepo(session)` | У них компактнее и строже. `di/database/repos.py` у нас - 4 идентичных метода, которые вырастут до 20 |
| **Ошибки** | `ApplicationError` + `@to_error`-датаклассы с `__str__`. Маппинг в HTTP - **вручную в каждом роуте** через `try/except` -> `HTTPException`. Глобальный обработчик один: `AuthError` -> 401 | `ZhekaError` с 6 осями, `__init_subclass__` заполняет `title`, `api/errors.py` строит `exception_handlers` comprehension-ом, плюс trace_id в теле | Наш вариант **заметно лучше**. У них 11 мест с `raise HTTPException` и дублирование статусов в `responses={}` каждого роута |
| **DTO** | Трёхэтажно: сущность -> `@to_data_structure` DTO в application -> pydantic-модель в роуте, перекладывание поле за полем руками | Двухэтажно: ORM-модель -> pydantic-схема в `api/schemas/`. `ZhekaType` для внутренних структур вроде `CurrentResidency` | У них лишний этаж. `routes/profile.py:57-65` - семь строк ручного копирования полей между двумя одинаковыми структурами |
| **Энумы** | `Enum(AuthMethod, name="auth_method")`, в БД лежат имена. Плюс самописный `ExperienceTypeType` на 30 строк | `pg_enum(enum_cls, name)` с `values_callable`, в БД лежат значения. `alembic-postgresql-enum` следит за изменениями | Наш вариант лучше и уже оплачен |
| **Идентификаторы** | `NewType("UserId", UUID)`, используются в сущностях и гейтвеях. `uuid7()` на стороне приложения | `NewType("UserId", int)` в `core/ids.py` - но **в моделях не используются**: там `Mapped[int]`. Есть только на границах (`CurrentAccount`, сигнатуры репозиториев) | Реальная разница. У нас `Resident.user_id` имеет тип `int`, и `UserId(resident.user_id)` в `current_residency.py:35` - ручная перепаковка, которую mypy не проверяет |
| **Тесты** | 1428 LOC: unit по сущностям (фабрики, инварианты) + e2e через поднятый uvicorn, `DatabaseClearer` с `TRUNCATE ... CASCADE`, `dirty-equals` для ассертов | 2 файла: `conftest.py` с testcontainers + alembic upgrade + фикстура сессии на savepoint-откате, `test_tenancy.py` (83 строки) | Наша изоляция **чище**: вложенная транзакция с откатом вместо TRUNCATE, тесты не зависят друг от друга по порядку. У них шире покрытие, но e2e гоняют реальный сервер в фоне |
| **Миграции** | Синхронный `engine_from_config`, без `compare_type`, без плагина энумов, имена файлов - хэши, сообщения - "empty message" | Асинхронный `async_engine_from_config`, `compare_type=True`, `alembic_postgresql_enum`, дата в имени файла, английские сообщения | Наш вариант лучше по всем пунктам |
| **Бот / брокер** | Нет бота. Фоновая работа - `BackgroundTasks` FastAPI с ручным открытием request-scope контейнера внутри | maxo-диспетчер в том же процессе, taskiq + Redis, отдельный scheduler, `CommitMiddleware` | Несравнимо: у нас реальная очередь, у них `BackgroundTasks` в том же воркере |

Итог сравнения: **единственное, что у референса действительно лучше устроено, чем у нас - это
отделение доменных данных от SQLAlchemy.** По ошибкам, транзакциям, миграциям, энумам и изоляции
тестов наш бэкенд впереди. Это надо учитывать, решая, что заимствовать: соблазн взять «всю
архитектуру целиком» приведёт к замене работающих и лучших решений на худшие.

---

## 5. Решения на выбор

Пункты независимы, если явно не сказано иначе. Оценка часов - для агента с ревью, при
последовательном выполнении блоков.

### Решение 1. Императивный маппинг как стиль объявления, без доменного слоя

**Что меняется.** `zheka/infra/database/models/*.py` (18 файлов, 32 класса) переписываются из
`class X(IdMixin, CreatedAtMixin, BaseAlchemyModel)` в `x_table = Table("x", metadata, ...)` плюс
`mapper_registry.map_imperatively(X, x_table)`. Классы `X` остаются датаклассами в том же пакете
`infra/database/models/` - в `core/` ничего не переезжает. `models/base.py` теряет
`DeclarativeBase` и `__repr__` (датакласс даёт repr сам). `_mixins.py` превращается из классов в
функции-фабрики колонок. `migrations/env.py` меняет одну строку.

**Что даёт.** Один шаг к домену без домена: сущности перестают наследовать SQLAlchemy-базу, их
можно создавать и тестировать без БД. Дальше можно переехать в `core/` уже одним `git mv`.

**Что стоит.** 5-7 часов. Затрагивает **0 из 22 блоков будущей работы** и 1 блок текущей:
репозитории, зависимости, тесты и `di/` не меняются вообще (проверено, см. 3.8 - класс-атрибуты
остаются `InstrumentedAttribute`). Ломаются: `BaseAlchemyModel.__repr__`, любые обращения к
`__table__` (у нас их нет), `Mapped[...]`-аннотации теряют роль подсказки nullable, поэтому
каждой из 221 колонки нужен явный `nullable=`.

**Обратимо?** Да, полностью, в обе стороны, не трогая БД.

**Рекомендация: брать, но не сейчас.** Ценность целиком в том, чтобы открыть дорогу решению 2.
Само по себе оно даёт только «красивее». Если решение 2 не берётся - это чистый расход 6 часов
на переписывание 823 строк, которые сегодня работают.

### Решение 2. Доменные сущности отдельно от таблиц (полный вариант)

**Что меняется.** Появляется `zheka/core/models/` с 32 датаклассами (без SQLAlchemy-импортов),
`zheka/infra/database/tables.py` с 32 `Table` и вызовами `map_imperatively`. `models/` в `infra/`
исчезает. `zheka/base.py` получает третий вариант - немутабельный, неslotted базовый класс для
сущностей (проверено: frozen и slots несовместимы с маппингом, см. 3.8). AGENTS.md - инвариант
про `ZhekaType` переписывается.

**Что даёт.** `core/` становится самодостаточным: доменные сервисы (`core/services/access.py`)
и будущая бизнес-логика смогут принимать сущности, не втягивая инфраструктуру. Тесты бизнес-правил
- без БД.

**Что стоит.** 10-14 часов сверх решения 1. Затрагивает **все 22 блока** в одном смысле: каждый
новый блок будет обязан решать, куда класть новую сущность и как её мапить, то есть каждая новая
таблица - это правка в двух файлах вместо одного. Плюс постоянный риск `UnmappedClassError`, если
блок импортирует сущность, не импортируя `tables.py`.

**Обратимо?** Формально да, но с каждым блоком дороже. После 5-6 блоков - фактически односторонняя
дверь.

**Рекомендация: не брать.** У нас ноль `relationship` и ноль бизнес-логики на моделях - модели уже
и так анемичные датаклассы с колонками. Отделение даёт чистоту импортов и почти ничего сверх: за
две недели мы не успеем написать домен, ради которого это отделение существует. Единственное, что
я бы сделал в этом направлении - решение 5.

### Решение 3. Репозитории возвращают доменные сущности, а не ORM-модели

**Что меняется.** Ничего, если взято решение 2 (маппленный класс и есть сущность). Если решения 2
нет - это означает ручной `_to_entity()` в каждом методе каждого репозитория.

**Что даёт.** Без решения 2 - ничего, кроме лишнего слоя перекладывания.

**Что стоит.** 15+ часов и по строке-другой в каждом методе всех 20 будущих репозиториев.

**Рекомендация: не брать никогда в этом проекте.** Это тот самый третий этаж DTO, из-за которого
`routes/profile.py` в референсе руками копирует семь полей между двумя идентичными структурами.

### Решение 4. Протоколы (`Protocol`) для репозиториев

**Что меняется.** На каждый репозиторий - файл с `Protocol` в `core/`, `WithParents[...]` в
`di/database/repos.py`.

**Что даёт.** Возможность подменить реализацию. У нас одна реализация на репозиторий и она будет
одна всегда.

**Что стоит.** ~20 новых файлов, по одному на блок из 22.

**Рекомендация: не брать.** Интерфейс с единственной реализацией - это чистая церемония. Наши
тесты ходят в настоящий Postgres через testcontainers, моки репозиториев нам не нужны.

### Решение 5. Типизированные идентификаторы в моделях

**Что меняется.** `Mapped[int]` -> `Mapped[UserId]` в `models/*.py` там, где колонка - это ссылка
или ключ. Требует `type_annotation_map` в `BaseAlchemyModel` либо явного `BigInteger` в
`mapped_column` (у нас он и так везде явный, так что достаточно поправить аннотацию).
Исчезают ручные перепаковки вида `UserId(resident.user_id)` в
`api/dependencies/current_residency.py:33-40` и `current_org.py:47`.

**Что даёт.** mypy начинает ловить перепутанные id - `HouseId` вместо `FlatId` в аргументе
репозитория. Для схемы с 23 типами id и сквозным multi-tenancy это не косметика: подстановка
чужого id и есть наш главный класс багов, ровно тот, что проверяет `test_tenancy.py`.

**Что стоит.** 2-3 часа. Затрагивает 18 файлов моделей и ~10 строк в зависимостях. На будущие
блоки влияет положительно: новые репозитории сразу пишутся типизированно.

**Обратимо?** Да, тривиально.

**Рекомендация: брать, и брать первым.** Это единственный пункт из всего списка, который даёт
измеримую защиту от багов за один вечер, и он **не требует императивного маппинга вообще**. Это
лучшая идея референса, отвязанная от его архитектуры.

### Решение 6. Явный `UnitOfWork` вместо коммита на выходе из scope

**Что меняется.** `di/database/session.py` перестаёт коммитить, появляется `UnitOfWork` с
`add()/commit()`, каждый хендлер вызывает `commit()` руками.

**Что даёт.** Явность границы транзакции; возможность нескольких коммитов в одном запросе.

**Что стоит.** 4 часа + **по одной строке в каждом пишущем эндпоинте всех 22 блоков**, и каждая
такая строка может быть забыта.

**Рекомендация: не брать.** Наш вариант строго безопаснее: забыть коммит физически нельзя. В самом
референсе цена видна - `sign_up_yandex` в ветке с существующим пользователем добавляет сущности и
может выйти по исключению до `commit()`.

### Решение 7. Слой интеракторов между роутами и репозиториями

**Что меняется.** Появляется `zheka/core/interactors/` (или `application/`), роуты худеют до
парсинга и вызова, бизнес-логика уезжает из роутов.

**Что даёт.** Логика становится переиспользуемой между API, ботом и taskiq-задачами. У нас
**три** точки входа против одной у референса, так что аргумент здесь сильнее, чем у них.

**Что стоит.** 6-8 часов на каркас + примерно час на блок, итого затрагивает все 22 блока.

**Рекомендация: брать в урезанном виде - без класса-интерактора.** Нам нужна переиспользуемость
между api/bot/broker, а не церемония `@to_interactor`-датакласса с `provide_all` на каждый
сценарий. У нас уже есть правильная заготовка: `zheka/core/services/` с `EventsService` и
свободными функциями в `access.py`. Правило «логика, нужная больше чем одной точке входа, живёт в
`core/services/`» даёт 90% пользы за 0 часов каркаса. Класс-на-сценарий заводить только если
функция перестанет справляться.

### Решение 8. Фабричные `classmethod`-ы на сущностях

**Что меняется.** `User.factory(...)` вместо `User(...)` в местах создания.

**Что даёт.** Одно место, где проставляются `created_at` и инварианты.

**Что стоит.** ~1 час, по мере появления сущностей.

**Рекомендация: не брать.** У нас `created_at` ставит база через `server_default=fresh_timestamp()`,
а `id` - `autoincrement`. Фабрика референса существует потому, что они генерируют `uuid7()` в
приложении. Нам нечего класть в фабрику.

### Решение 9. `STRICT_VALIDATION` в dishka

**Что меняется.** Одна строка в `zheka/di/__init__.py`.

**Что даёт.** Контейнер падает при старте на несогласованных scope-ах вместо загадочной ошибки в
рантайме на 15-м блоке.

**Что стоит.** 15 минут плюс возможная починка того, что вскроется.

**Рекомендация: брать.** Дешевле не бывает, а цена пропущенной ошибки растёт с каждым блоком.

### Решение 10. `provide_all` / `WithParents` в провайдерах репозиториев

**Что меняется.** `zheka/di/database/repos.py` - 26 строк с четырьмя одинаковыми методами
`@provide` превращаются в один `repos = provide_all(UsersRepo, ResidentsRepo, OrgsRepo, EventsRepo)`.
Работает потому, что все наши репозитории имеют единственный параметр `AsyncSession`, который
dishka резолвит сама.

**Что даёт.** К 22-му блоку это разница между 20 строками и 130.

**Что стоит.** 30 минут. Затрагивает 1 файл, зато во всех будущих блоках правка сводится к
добавлению имени в список.

**Рекомендация: брать.**

### Решение 11. `dirty-equals` в тестах

**Что меняется.** Добавляется зависимость, ассерты вида
`assert response.json() == IsDict(resume_id=IsUUID())`.

**Что даёт.** Компактные проверки JSON-ответов без переписывания при добавлении полей.

**Что стоит.** 20 минут.

**Рекомендация: брать, когда появятся первые API-тесты** (сейчас у нас тесты на уровне сессии, им
это не нужно).

---

## 6. Что я бы не брал

1. **Разделение `application/` и `adapters/` как физическую границу пакетов.** Даёт чистоту
   импортов, стоит правки в двух-трёх местах на каждую новую сущность во всех 22 блоках. Наше
   `core/` vs `infra/` уже проводит ту же границу там, где она реально нужна.

2. **Протоколы на всё** (`UnitOfWork`, `IdentityProvider`, семь `*DataGateway`). У каждого ровно
   одна реализация. `IdentityProvider` у них существует, чтобы ядро не зависело от FastAPI - у нас
   ту же роль играют `api/dependencies/current_*.py`, которые честно живут в `api/` и не
   притворяются доменом.

3. **Трёхэтажные DTO** (сущность -> application DTO -> pydantic-модель). Референс платит за это
   сотнями строк ручного перекладывания, а `get.py` из-за этого распух до 250 строк с
   троекратным копипастом.

4. **Ручной `raise HTTPException` в роутах.** 11 таких мест против нашего единого
   `exception_handlers`. Наш способ строго лучше, менять его на их - регресс.

5. **Явный `UnitOfWork.commit()`.** См. решение 6: их собственный код показывает, как это теряет
   данные.

6. **`TypeDecorator` вместо `pg_enum`.** 30 строк `isinstance`-лесенки на одно поле, вмороженный
   путь к модулю приложения в файл миграции и рассогласование типов между двумя таблицами одной
   схемы.

7. **`BackgroundTasks` с ручным открытием request-scope контейнера внутри хендлера**
   (`routes/resume.py:410-415`). У нас для этого есть taskiq, и `AGENTS.md` прямо запрещает
   тяжёлую работу в вебхуке.

8. **Их `migrations/env.py`.** Синхронный движок, нет `compare_type`, нет плагина энумов,
   сообщения "empty message". Наш лучше по каждому пункту.

9. **Их e2e-схема** (uvicorn в фоновой корутине + `TRUNCATE ... CASCADE` перед каждым тестом).
   Наш savepoint-откат в `tests/conftest.py` даёт ту же изоляцию, работает быстрее и не зависит
   от порядка тестов.

---

## 7. Если брать императивный маппинг: план миграции

План для решения 1 (стиль объявления, сущности остаются в `infra/database/models/`). Для решения 2
добавляется шаг 8.

Опорный факт, снимающий большую часть страха: **схема на выходе не меняется ни на байт**.
Проверено - я собрал `Table("houses", md, ...)` с нашим naming convention и получил ровно те же
имена, что стоят в `2026.09.16_20.22_initial_schema.py`:

```
pk: pk_houses
fk: ['fk_houses_org_id_organizations']
uq: ['uq_houses_code']
indexes: ['ix_houses_city', 'ix_houses_org_id']
```

Значит корректность перехода проверяется одной командой: `just migration "check"` после переписывания
должен сгенерировать **пустую** миграцию. Если он что-то нашёл - перенос колонки сделан неверно.
Это и есть приёмочный тест всего шага.

### Шаг 1. `models/base.py`: убрать `DeclarativeBase`

`BaseAlchemyModel` исчезает. Остаётся модульный уровень:

```python
metadata = MetaData(naming_convention={...})   # convention переносится дословно
mapper_registry = registry(metadata=metadata)
```

Naming convention **обязан** переехать дословно, иначе `uq_houses_chat_binding_code` превратится
в что-то другое и autogenerate потребует пересоздания констрейнтов. `__repr__` и `_repr` с
обработкой `DetachedInstanceError` удаляются - датакласс даёт repr сам, а с
`expire_on_commit=False` в `di/database/session.py` detached-доступа у нас и так не бывает.

### Шаг 2. `_mixins.py`: `sort_order` умирает, миксины становятся функциями

Это самый неочевидный пункт. `sort_order` - параметр **`mapped_column`**, у `Column` его нет.
В императивном объявлении порядок колонок - это буквально порядок аргументов `Table(...)`, так
что механизм не нужен: `id`, `created_at`, `updated_at` просто пишутся первыми.

Делить один объект `Column` между таблицами нельзя (проверено:
`ArgumentError: Column object 'id' already assigned to Table 't1'`), поэтому миксины-классы
превращаются в фабрики:

```python
def id_column() -> Column[int]:
    return Column("id", BigInteger, primary_key=True, autoincrement=True)

def created_at_column() -> Column[datetime]:
    return Column(
        "created_at", DateTime(timezone=True),
        default=fresh_timestamp(), server_default=fresh_timestamp(), nullable=False,
    )

def updated_at_column() -> Column[datetime]:
    return Column(
        "updated_at", DateTime(timezone=True),
        default=fresh_timestamp(), onupdate=fresh_timestamp(),
        server_default=fresh_timestamp(), server_onupdate=fresh_timestamp(), nullable=False,
    )
```

`fresh_timestamp()` не трогается вообще. Инвариант из `AGENTS.md` («`id`, `created_at` и
`updated_at` ведут каждую таблицу, миксины несут отрицательный `sort_order`») переформулируется в
«каждая таблица начинается с `id_column(), created_at_column()[, updated_at_column()]`» - правило
становится проще, потому что глазами проверяется по первым строкам `Table`.

Осторожно с исключениями: `OrgSettings` использует только `UpdatedAtMixin` и имеет свой
`primary_key` на `org_id`, `NotificationSetting` - только `IdMixin`. Каждый класс переносить
индивидуально, не по шаблону.

### Шаг 3. Переписать 32 таблицы

18 файлов, 221 колонка. Главная механическая опасность: **`Mapped[int | None]` больше не означает
`nullable=True`**. У `Column` дефолт - `nullable=True` для обычных колонок, то есть все
непустые колонки (221 - 55 = 166 штук) получат `NULL` молча, если забыть `nullable=False`.
Пустая миграция на шаге 7 это поймает, но лучше писать `nullable` явно везде, включая nullable-случаи.

`pg_enum` **не меняется вообще** - проверено, `Column("role", pg_enum(OrgRole, "org_role"),
nullable=False)` даёт тот же `VARCHAR`-обёрнутый `Enum` с `values_callable` и тем же именем типа.
Это единственный наш хелпер, который переживает переход нетронутым.

`__table_args__` (13 штук) переезжают в позиционные аргументы `Table` - `UniqueConstraint` и
`Index` принимаются там напрямую. `Index(None, "city", "street")` внутри `Table(...)` даёт
`ix_houses_city` ровно как сейчас (проверено). `desc("valid_from")` в индексах `charges.py` и
`meters.py` работает так же.

Классы сущностей пишутся рядом, в том же файле:

```python
class Organization:
    id: int
    created_at: datetime
    name: str
    ...
```

с одним из трёх оформлений: `@dataclass(kw_only=True)` как в референсе, либо новый вариант
`ZhekaType` с `frozen=False, slots=False`. **Ни frozen, ни slots использовать нельзя** - проверено,
падает на `_sa_instance_state` и на `weakref` соответственно.

### Шаг 4. Место вызова `map_imperatively`

Референс делает это побочным эффектом импорта `tables.py`, и это их главная ловушка. Наш
`models/__init__.py` уже собирает все 32 модели и все репозитории импортируют именно из него -
значит, если положить вызовы в конец `models/__init__.py`, ловушка закрыта структурно и ничего
не меняется в 22 будущих блоках. Явную `setup_mappers()` заводить не надо: она добавит вызов,
который кто-нибудь забудет.

### Шаг 5. `migrations/env.py` - одна строка

```python
from zheka.infra.database.models import metadata   # вместо BaseAlchemyModel
target_metadata = metadata
```

Остальное (`async_engine_from_config`, `compare_type=True`, `import alembic_postgresql_enum`)
не трогается.

### Шаг 6. Что **не** меняется - перечислить, чтобы не трогали лишнего

- **`alembic-postgresql-enum`**: работает, не замечая перехода. Проверено по исходникам плагина -
  его `get_declared_enums` принимает `metadata: Union[MetaData, List[MetaData]]` и ничего не знает
  про declarative. Существующая миграция с `sa.Enum(...).create(op.get_bind())` и
  `create_type=False` в колонках остаётся валидной.
- **`alembic autogenerate`**: видит `MetaData`, а не способ её наполнения. После корректного
  переноса генерирует пустую миграцию.
- **Все 5 репозиториев** (`users.py`, `residents.py`, `orgs.py`, `events.py`, `scopes.py`):
  ноль правок. `select(User).where(User.max_user_id == ...)`, `session.get(Resident, id)`,
  `pg_insert(User).returning(User)`, `scoped_to_org(select(Request), Request.house_id, org_id)` -
  всё проверено на маппленном императивно классе и работает.
- **`di/`**, **`api/dependencies/`**, **`api/errors.py`**, **`core/`**, **`bot/`**, **`broker/`**:
  ноль правок.
- **`tests/conftest.py` и `test_tenancy.py`**: ноль правок. Конструирование
  `Organization(name=..., inn=...)` в фикстурах продолжает работать - датакласс принимает те же
  kwargs, а `session.add` + `flush` заполняет `id` на самом объекте (проверено).
- **Существующая миграция `2026.09.16_20.22_initial_schema.py`**: не трогается. Она уже слита,
  она описывает ту же схему, база о смене стиля не узнает.

### Шаг 7. Приёмка

```
just migration "verify imperative mapping"   # должно выйти пустое upgrade()/downgrade()
just check                                    # ruff, slotscheck, bandit, mypy strict
just test                                     # testcontainers поднимает базу и катит миграции
```

Пустая сгенерированная миграция - обязательное условие. Файл после проверки удалить, в историю
он не идёт.

Отдельно проверить `slotscheck`: сущности теперь не имеют `__slots__`, а `strict-imports = true`
в `[tool.slotscheck]`. Требования «все классы слоттед» там не включено, так что должно пройти,
но это первое, что стоит запустить после шага 3.

### Шаг 8 (только для решения 2). Переезд в `core/`

`git mv` классов сущностей в `zheka/core/models/`, `Table`-ов - в
`zheka/infra/database/tables.py`. После этого:

- импорт сущности перестаёт мапить её - обязателен импорт `tables.py` на старте всех трёх точек
  входа (`api/app.py`, `broker/broker.py`, `bot/`), иначе `UnmappedClassError` в рантайме;
- `AGENTS.md` переписывается в части инварианта `ZhekaType`;
- каждая новая таблица в каждом из 22 блоков трогает два файла вместо одного.

Отдельные +3 часа и постоянный налог. См. рекомендацию в решении 2 - я бы этот шаг не делал.

### Сводная оценка

| Шаг | Часы | Риск |
|---|---|---|
| 1-2 (база и миксины) | 1 | низкий |
| 3 (32 таблицы, 221 колонка) | 4-5 | средний: забытый `nullable=False` |
| 4-5 (маппер, env.py) | 0.5 | низкий |
| 6-7 (приёмка) | 1 | низкий, пустая миграция всё ловит |
| **Итого решение 1** | **6-7** | **0 из 22 будущих блоков** |
| Шаг 8 (решение 2) | +3 | все 22 блока, односторонняя дверь |

---

## Итоговая рекомендация

Три пункта брать: **типизированные id в моделях** (решение 5), **`STRICT_VALIDATION`** (9),
**`provide_all` для репозиториев** (10). Вместе - около четырёх часов, ни один не затрагивает
будущие блоки, и первый из них реально ловит класс багов, критичный для multi-tenancy.

Императивный маппинг сам по себе (решение 1) дешевле, чем кажется - 6-7 часов, ноль влияния на
22 блока, полностью обратим, репозитории и тесты не трогаются. Но и пользы сам по себе он не даёт
никакой: его единственный смысл - открыть дверь к решению 2, которое за две недели не окупится.
Брать его стоит только если владелец хочет отделённый домен принципиально, а не ради выгоды в
этом хакатоне.

Три пункта отказать: **доменный слой целиком** (2), **протоколы на репозитории** (4), **явный
UnitOfWork** (6).
