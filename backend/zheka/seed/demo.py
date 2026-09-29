import itertools
import logging
import shutil
from collections.abc import Iterator, Sequence
from datetime import UTC, date, datetime, time, timedelta
from math import ceil
from pathlib import Path
from random import Random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from zheka.base import ZhekaType
from zheka.core.charges import previous_period
from zheka.core.danger import detect_danger
from zheka.core.enums import (
    CATEGORY_RULES,
    AnnouncementChannel,
    AppointmentStatus,
    EventType,
    NoticeStatus,
    OrgRole,
    PollStatus,
    RequestActorRole,
    RequestAttachmentKind,
    RequestCategory,
    RequestChannel,
    RequestCompletionReason,
    RequestGroupStatus,
    RequestStatus,
    ResidentRole,
    ServiceType,
    VerificationStatus,
)
from zheka.core.ids import FlatId, HouseId, MaxUserId, UserId
from zheka.core.models import (
    Announcement,
    Appointment,
    DemandSignal,
    Event,
    Flat,
    House,
    Meter,
    NoticeDelivery,
    OrgMember,
    OrgSettings,
    Organization,
    Poll,
    PollOption,
    PollVote,
    Reading,
    ReceptionWindow,
    Request,
    RequestAttachment,
    RequestGroup,
    RequestStatusLog,
    Resident,
    Tariff,
    User,
    VerificationRequest,
)
from zheka.core.services.demo import (
    DEMO_INN,
    DEMO_INNS,
    MONTHLY_USAGE,
    SERIAL_CODES,
    DemoService,
    demo_account_no,
)
from zheka.core.services.readings import current_period
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.seed.directory import DATA_DIR, DirectoryHouse, load_directory

logger = logging.getLogger(__name__)

FILES_DIR = DATA_DIR / "files"
DOCUMENTS = (
    "5e4d464bd16d444f8024c2cfd616c0e2.png",
    "9f63808559da4ca9a4ace56a7ddf160a.png",
)
RESULT_PHOTOS = {
    "fa678cbaf3614e0a95540b46f24227db.png": frozenset(
        {RequestCategory.LEAK, RequestCategory.WATER_SUPPLY},
    ),
    "3c5c76b61ff14eb1a6cc5c56931d9dda.png": frozenset(
        {RequestCategory.ELECTRICITY, RequestCategory.ENTRANCE},
    ),
}

HISTORY = timedelta(days=182)
REQUESTS_PER_WEEK = 3
RECENT = timedelta(days=30)
AUTO_CLOSE_AFTER = timedelta(hours=48)
MIN_OWNERS = 4
MAX_OWNERS = 30
REVIEWERS_GROUP_THRESHOLD = 10
DEMO_AUTHORS = 15
POLL_TURNOUT = 4_870
DEMAND = {
    "Москва": (7, 5, 4, 2, 1),
    "Санкт-Петербург": (6, 4, 3, 2, 1),
    "Казань": (7, 3, 3, 2, 1),
}
RATED_PERCENT = 85
MIN_FLATS = 40
MAX_FLATS = 250
SEED_LOCK = 1
HOUSES_PER_DEMO_ORG = 12
CLOSED_BEFORE = timedelta(days=4)
URGENT_EVERY = 6
ACTIVE_POLL_EVERY = 5
RECEPTION_DAYS = 30
NOTICE_WEIGHTS = {
    NoticeStatus.DELIVERED: 86,
    NoticeStatus.FAILED: 3,
    NoticeStatus.MUTED: 6,
    NoticeStatus.BOT_STOPPED: 5,
}


class OrgProfile(ZhekaType):
    name: str
    inn: str
    city: str
    houses: int
    accept_minutes: int
    phone_percent: int
    repeat_percent: int
    recent_repeats: int
    auto_close_percent: int
    ratings: tuple[int, ...]
    overdue: int
    requests_per_week: int = REQUESTS_PER_WEEK


PROFILES = (
    OrgProfile(
        name="Демо-УК «Жэка Коммуналкин»",
        inn=DEMO_INNS[0],
        city="Москва",
        houses=HOUSES_PER_DEMO_ORG,
        accept_minutes=40,
        phone_percent=3,
        repeat_percent=5,
        recent_repeats=1,
        auto_close_percent=10,
        ratings=(5, 5, 5, 4, 4, 5, 3),
        overdue=1,
    ),
    OrgProfile(
        name="Демо-УК «Северный квартал»",
        inn=DEMO_INNS[1],
        city="Санкт-Петербург",
        houses=HOUSES_PER_DEMO_ORG,
        accept_minutes=20,
        phone_percent=25,
        repeat_percent=3,
        recent_repeats=0,
        auto_close_percent=3,
        ratings=(5, 5, 5, 4),
        overdue=1,
    ),
    OrgProfile(
        name="Демо-УК «Надежный дом»",
        inn=DEMO_INNS[2],
        city="Казань",
        houses=HOUSES_PER_DEMO_ORG,
        accept_minutes=75,
        phone_percent=15,
        repeat_percent=8,
        recent_repeats=2,
        auto_close_percent=18,
        ratings=(5, 4, 4, 3),
        overdue=2,
    ),
    OrgProfile(
        name="Демо-УК «Уютный двор»",
        inn=DEMO_INNS[3],
        city="Москва",
        houses=HOUSES_PER_DEMO_ORG,
        accept_minutes=150,
        phone_percent=40,
        repeat_percent=12,
        recent_repeats=3,
        auto_close_percent=28,
        ratings=(4, 4, 3, 3, 5),
        overdue=3,
    ),
    OrgProfile(
        name="Демо-УК «Городской сервис»",
        inn=DEMO_INNS[4],
        city="Санкт-Петербург",
        houses=HOUSES_PER_DEMO_ORG,
        accept_minutes=300,
        phone_percent=35,
        repeat_percent=18,
        recent_repeats=5,
        auto_close_percent=50,
        ratings=(4, 3, 3, 2, 5),
        overdue=4,
    ),
)

CATEGORY_WEIGHTS = {
    RequestCategory.LEAK: 3,
    RequestCategory.ELEVATOR: 2,
    RequestCategory.GARBAGE: 2,
    RequestCategory.HEATING: 2,
    RequestCategory.WATER_SUPPLY: 2,
    RequestCategory.ELECTRICITY: 2,
    RequestCategory.ENTRANCE: 3,
    RequestCategory.YARD: 2,
    RequestCategory.OTHER: 1,
}
DESCRIPTIONS = {
    RequestCategory.LEAK: (
        "Течет стояк в санузле",
        "Протечка с потолка на кухне после дождя",
    ),
    RequestCategory.ELEVATOR: (
        "Лифт застревает между этажами",
        "Не работает кнопка вызова лифта на первом этаже",
    ),
    RequestCategory.GARBAGE: (
        "Не вывезли мусор с площадки",
        "Переполнены контейнеры у подъезда",
    ),
    RequestCategory.HEATING: ("Холодные батареи в комнате", "Шумит стояк отопления"),
    RequestCategory.WATER_SUPPLY: ("Слабый напор холодной воды", "Ржавая горячая вода"),
    RequestCategory.ELECTRICITY: (
        "Не горит свет на лестничной площадке",
        "Искрит розетка в щитке на этаже",
    ),
    RequestCategory.ENTRANCE: (
        "Сломан доводчик входной двери",
        "Разбито окно между этажами",
    ),
    RequestCategory.YARD: (
        "Яма на проезде во дворе",
        "Сломана скамейка на детской площадке",
    ),
    RequestCategory.OTHER: ("Не работает домофон", "Нужна справка о составе семьи"),
}
FIRST_NAMES = (
    "Анна",
    "Мария",
    "Елена",
    "Ольга",
    "Ирина",
    "Наталья",
    "Татьяна",
    "Светлана",
    "Иван",
    "Алексей",
    "Сергей",
    "Дмитрий",
    "Андрей",
    "Михаил",
    "Николай",
    "Павел",
)
INITIALS = "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЭЮЯ"
POLL_OPTIONS = ("За", "Против", "Воздержался")
ANNOUNCEMENTS = (
    (
        timedelta(days=40),
        "Плановое отключение горячей воды с 10:00 до 18:00, работы на теплотрассе",
        True,
    ),
    (
        timedelta(days=20),
        "Во дворе начнется ремонт асфальта, машины просим переставить к торцу дома",
        False,
    ),
)
POLL_RESULTS = (
    timedelta(days=5),
    "Итоги опроса о шлагбауме опубликованы в разделе собраний",
    False,
)
URGENT_ANNOUNCEMENTS = (
    "Аварийное отключение холодной воды, бригада уже работает на месте",
    "Прорыв трубы отопления в подвале, возможны перебои с отоплением до вечера",
    "Не работает лифт во втором подъезде, специалисты приедут сегодня",
)
CLOSED_POLL = (
    "Установка шлагбаума во дворе",
    "Шлагбаум на въезде во двор за счет собственников",
)
ACTIVE_POLL = (
    "Покраска подъездов",
    "Покраска стен и перил во всех подъездах за счет текущего ремонта",
)
PLANNED_WORKS = (
    "Опрессовка системы водоснабжения\n"
    "Возможны перепады давления и кратковременные отключения холодной воды днем. "
    "Приказ о проведении работ приложен"
)
WORKS_ORDER = "99865224236a46b1870414615a7ed62f.pdf"
WORKS_ORDER_TITLE = "Приказ № 12 об опрессовке (модельный)"
WORKS_DAYS_LEFT = 7
RECEPTION_WINDOWS = ((0, 9, 12), (1, 9, 12), (2, 15, 19), (3, 15, 19), (4, 9, 12))
MAP_STATES = ("emergency", "escalated", "overdue", "open", "calm")
STATE_CATEGORIES = {
    "emergency": RequestCategory.LEAK,
    "escalated": RequestCategory.GARBAGE,
    "overdue": RequestCategory.ELECTRICITY,
    "open": RequestCategory.OTHER,
}
OVERDUE_AGE = timedelta(days=2)
BACKGROUND_PROFILES = (
    OrgProfile(
        name="Демо-УК «Столичный дом»",
        inn="9900000050",
        city="Москва",
        houses=10,
        accept_minutes=55,
        phone_percent=10,
        repeat_percent=6,
        recent_repeats=1,
        auto_close_percent=15,
        ratings=(5, 4, 4, 3, 5),
        overdue=2,
        requests_per_week=2,
    ),
    OrgProfile(
        name="Демо-УК «Зеленый квартал»",
        inn="9900000060",
        city="Москва",
        houses=8,
        accept_minutes=120,
        phone_percent=30,
        repeat_percent=10,
        recent_repeats=2,
        auto_close_percent=22,
        ratings=(4, 4, 3, 5),
        overdue=1,
        requests_per_week=1,
    ),
    OrgProfile(
        name="Демо-УК «Садовое кольцо»",
        inn="9900000080",
        city="Москва",
        houses=12,
        accept_minutes=35,
        phone_percent=8,
        repeat_percent=4,
        recent_repeats=0,
        auto_close_percent=6,
        ratings=(5, 5, 4, 4),
        overdue=0,
        requests_per_week=2,
    ),
    OrgProfile(
        name="Демо-УК «Рассвет»",
        inn="9900000090",
        city="Москва",
        houses=9,
        accept_minutes=240,
        phone_percent=45,
        repeat_percent=16,
        recent_repeats=3,
        auto_close_percent=40,
        ratings=(3, 4, 2, 4, 3),
        overdue=3,
        requests_per_week=1,
    ),
    OrgProfile(
        name="Демо-УК «Невская линия»",
        inn="9900000100",
        city="Санкт-Петербург",
        houses=14,
        accept_minutes=90,
        phone_percent=18,
        repeat_percent=7,
        recent_repeats=1,
        auto_close_percent=12,
        ratings=(5, 4, 4, 4),
        overdue=1,
        requests_per_week=2,
    ),
    OrgProfile(
        name="Демо-УК «Балтийский двор»",
        inn="9900000110",
        city="Санкт-Петербург",
        houses=11,
        accept_minutes=180,
        phone_percent=35,
        repeat_percent=14,
        recent_repeats=2,
        auto_close_percent=33,
        ratings=(4, 3, 3, 4, 2),
        overdue=2,
        requests_per_week=1,
    ),
    OrgProfile(
        name="Демо-УК «Белые ночи»",
        inn="9900000130",
        city="Санкт-Петербург",
        houses=9,
        accept_minutes=28,
        phone_percent=6,
        repeat_percent=3,
        recent_repeats=0,
        auto_close_percent=4,
        ratings=(5, 5, 5, 4, 5),
        overdue=0,
        requests_per_week=1,
    ),
    OrgProfile(
        name="Демо-УК «Петроградский дом»",
        inn="9900000140",
        city="Санкт-Петербург",
        houses=15,
        accept_minutes=65,
        phone_percent=22,
        repeat_percent=9,
        recent_repeats=2,
        auto_close_percent=20,
        ratings=(4, 5, 4, 3),
        overdue=1,
        requests_per_week=2,
    ),
    OrgProfile(
        name="Демо-УК «Волжская набережная»",
        inn="9900000150",
        city="Казань",
        houses=15,
        accept_minutes=45,
        phone_percent=12,
        repeat_percent=5,
        recent_repeats=1,
        auto_close_percent=9,
        ratings=(5, 4, 5, 4),
        overdue=1,
        requests_per_week=2,
    ),
    OrgProfile(
        name="Демо-УК «Казанский двор»",
        inn="9900000160",
        city="Казань",
        houses=13,
        accept_minutes=210,
        phone_percent=40,
        repeat_percent=15,
        recent_repeats=3,
        auto_close_percent=38,
        ratings=(3, 3, 4, 2, 4),
        overdue=3,
        requests_per_week=1,
    ),
    OrgProfile(
        name="Демо-УК «Кремлевский квартал»",
        inn="9900000170",
        city="Казань",
        houses=10,
        accept_minutes=100,
        phone_percent=20,
        repeat_percent=8,
        recent_repeats=1,
        auto_close_percent=17,
        ratings=(4, 4, 5, 3),
        overdue=1,
        requests_per_week=1,
    ),
    OrgProfile(
        name="Демо-УК «Идель»",
        inn="9900000180",
        city="Казань",
        houses=12,
        accept_minutes=150,
        phone_percent=28,
        repeat_percent=11,
        recent_repeats=2,
        auto_close_percent=26,
        ratings=(4, 3, 4, 4, 3),
        overdue=2,
        requests_per_week=2,
    ),
)


class Staff(ZhekaType):
    admin: UserId
    executors: tuple[UserId, ...]


class Author(ZhekaType):
    user_id: UserId
    flat_id: FlatId


class Step(ZhekaType):
    status: RequestStatus
    at: datetime
    by: UserId | None
    role: RequestActorRole


class Plan(ZhekaType):
    request: Request
    author: Author | None
    steps: list[Step]
    assigned_at: datetime | None


async def seed(
    session: AsyncSession,
    demo: DemoService,
    files_dir: Path,
    now: datetime,
) -> bool:
    stmt = select(func.pg_advisory_xact_lock(SEED_LOCK))
    await session.execute(stmt)
    if await OrgsRepo(session).get_by_inn(DEMO_INN) is not None:
        logger.info("Демо-организация уже есть, сид пропущен")
        return False
    _copy_files(files_dir)
    directory = await load_directory(session)
    await Seeder(session, demo, now).run(directory)
    logger.info("Сид готов: домов в справочнике %s", len(directory))
    return True


def _copy_files(files_dir: Path) -> None:
    files_dir.mkdir(parents=True, exist_ok=True)
    for name in (*DOCUMENTS, *RESULT_PHOTOS, WORKS_ORDER):
        target = files_dir / name
        if not target.exists():
            shutil.copyfile(FILES_DIR / name, target)


def _history_houses(
    directory: Sequence[DirectoryHouse],
) -> dict[str, list[DirectoryHouse]]:
    by_city: dict[str, list[DirectoryHouse]] = {}
    for item in directory:
        house = item.house
        if (
            house.org_id is None
            and house.lat is not None
            and house.lon is not None
            and MIN_FLATS <= item.living_flats <= MAX_FLATS
        ):
            by_city.setdefault(house.city, []).append(item)
    for items in by_city.values():
        items.sort(key=lambda item: (item.house.lat, item.house.lon))
    return by_city


class Seeder:
    __slots__ = (
        "_demo",
        "_max_ids",
        "_names",
        "_now",
        "_seeded_at",
        "_session",
        "_today",
    )

    def __init__(self, session: AsyncSession, demo: DemoService, now: datetime) -> None:
        self._session = session
        self._demo = demo
        self._today = now.date()
        self._now = datetime.combine(self._today, time(), UTC)
        self._seeded_at = now
        self._max_ids: Iterator[int] = itertools.count(-1, -1)
        self._names = Random("names")

    async def run(self, directory: Sequence[DirectoryHouse]) -> None:
        free = _history_houses(directory)
        profiles = (*PROFILES, *BACKGROUND_PROFILES)
        voters: list[User] = []
        taken: set[HouseId] = set()
        for number, profile in enumerate(profiles, start=1):
            neighbours = [other for other in profiles if other.city == profile.city]
            items = self._territory(
                free[profile.city],
                neighbours.index(profile),
                len(neighbours),
                profile.houses,
            )
            org = await self._org(profile, number, items[0].house.timezone)
            staff = await self._staff(org, profile)
            for item in items:
                item.house.org_id = org.id
                taken.add(item.house.id)
            await self._session.flush()
            by_id = {item.house.id: item for item in items}
            ordered = [
                by_id[house.id]
                for house in await HousesRepo(self._session).list_for_org(org.id)
            ]
            voters.extend(await self._houses(profile, org, staff, ordered))
        await self._demand(directory, taken, voters)

    async def _user(self) -> User:
        return (await self._users(1))[0]

    async def _org(
        self,
        profile: OrgProfile,
        number: int,
        timezone: str,
    ) -> Organization:
        org = Organization(
            name=profile.name,
            inn=profile.inn,
            phone=f"+7 (000) 000-00-{number:02d}",
            address="Адрес вымышлен, организация создана для демо",
            reception_note="Прием по будням, запись в приложении",
            registered_at=self._now - HISTORY - timedelta(days=30),
            is_demo=True,
            timezone=timezone,
            emergency_phone=f"+7 (000) 000-01-{number:02d}",
            email=f"priem-{number}@demo-uk.example.com",
            site=f"https://demo-uk-{number}.example.com",
        )
        self._session.add(org)
        await self._session.flush()
        self._session.add(
            OrgSettings(
                org_id=org.id,
                meter_window_always_open=True,
                group_threshold=REVIEWERS_GROUP_THRESHOLD,
            ),
        )
        self._session.add_all(
            ReceptionWindow(
                org_id=org.id,
                weekday=weekday,
                time_from=time(start),
                time_to=time(end),
                slot_minutes=30,
                capacity=2,
            )
            for weekday, start, end in RECEPTION_WINDOWS
        )
        await self._session.flush()
        return org

    async def _staff(self, org: Organization, profile: OrgProfile) -> Staff:
        admin = await self._user()
        roles = [(admin, OrgRole.CREATOR)]
        if profile.inn == DEMO_INN:
            roles.append((await self._user(), OrgRole.EMPLOYEE))
        executors = [await self._user(), await self._user()]
        roles.extend((executor, OrgRole.EXECUTOR) for executor in executors)
        self._session.add_all(
            OrgMember(org_id=org.id, user_id=user.id, role=role) for user, role in roles
        )
        await self._session.flush()
        return Staff(
            admin=UserId(admin.id),
            executors=tuple(UserId(executor.id) for executor in executors),
        )

    async def _flats(self, item: DirectoryHouse) -> list[Flat]:
        house = item.house
        rng = Random(f"flats:{house.city}:{house.street}:{house.building}")
        count = item.living_flats
        per_entrance = ceil(count / house.entrances)
        average = item.living_area // count
        flats = [
            Flat(
                house_id=house.id,
                number=str(number),
                entrance=(number - 1) // per_entrance + 1,
                area=average * rng.randint(75, 125) // 100,
                account_no=demo_account_no(str(number)),
            )
            for number in range(1, count + 1)
        ]
        self._session.add_all(flats)
        await self._session.flush()
        return flats

    def _resident(
        self,
        user: User,
        flat: Flat,
        role: ResidentRole,
        staff: Staff | None,
    ) -> Resident:
        is_owner = role is ResidentRole.OWNER
        resident = Resident(
            user_id=user.id,
            house_id=flat.house_id,
            flat_id=flat.id,
            role=role,
            can_see_charges=is_owner,
            can_vote=is_owner,
            verified_at=None if staff is None else self._now - HISTORY,
            verified_by=None if staff is None else staff.admin,
        )
        self._session.add(resident)
        return resident

    async def _owners(
        self,
        house: House,
        flats: Sequence[Flat],
        staff: Staff,
    ) -> list[tuple[User, Resident]]:
        rng = Random(f"owners:{house.city}:{house.street}:{house.building}")
        chosen = rng.sample(
            list(flats),
            min(len(flats), rng.randint(MIN_OWNERS, MAX_OWNERS)),
        )
        verified = rng.randint(30, 100)
        users = await self._users(len(chosen))
        owners = [
            (
                user,
                self._resident(
                    user,
                    flat,
                    ResidentRole.OWNER,
                    staff if index == 0 or rng.randint(1, 100) <= verified else None,
                ),
            )
            for index, (user, flat) in enumerate(zip(users, chosen, strict=True))
        ]
        await self._session.flush()
        return owners

    async def _demo_house(
        self,
        item: DirectoryHouse,
        org: Organization,
        staff: Staff,
        flats: Sequence[Flat],
    ) -> list[tuple[User, Resident]]:
        house = item.house
        house.overhaul = {
            "program": f"Региональная программа капитального ремонта, {house.region}",
            "works": [
                {
                    "title": "Ремонт системы холодного водоснабжения",
                    "year": 2023,
                    "is_done": True,
                },
                {
                    "title": "Замена лифтового оборудования",
                    "year": self._today.year,
                    "is_done": False,
                },
                {
                    "title": "Ремонт крыши",
                    "year": self._today.year + 3,
                    "is_done": False,
                },
            ],
        }
        house.documents = list(DOCUMENTS)

        rng = Random(f"demo:{house.city}:{house.street}:{house.building}")
        shuffled = rng.sample(list(flats), len(flats))
        main, others = shuffled[:3], shuffled[3:]
        owners: list[tuple[User, Resident]] = []
        for flat, scenario in zip(
            main,
            ("spike", "below", "verification"),
            strict=True,
        ):
            user = await self._user()
            resident = self._resident(user, flat, ResidentRole.OWNER, staff)
            owners.append((user, resident))
            await self._demo.furnish(
                flat,
                user.id,
                self._today,
                spike=scenario == "spike",
                below=scenario == "below",
                verification_soon=scenario == "verification",
            )
        tenant = self._resident(await self._user(), main[0], ResidentRole.TENANT, staff)

        total = sum(flat.area or 0 for flat in flats)
        voted = sum(flat.area or 0 for flat in main)
        for flat in others:
            area = flat.area or 0
            if (voted + area) * 10_000 // total >= POLL_TURNOUT:
                continue
            voted += area
            user = await self._user()
            resident = self._resident(user, flat, ResidentRole.OWNER, staff)
            owners.append((user, resident))
        await self._session.flush()
        await self._poll(house, org, staff, owners, self._now - timedelta(days=10))
        await self._announcements(
            org,
            staff,
            [house.id],
            [*(resident for _user, resident in owners), tenant],
            [POLL_RESULTS],
        )
        await self._meters(house, owners[len(main) :])
        return owners

    async def _tariffs(self, house: House, overhaul_rate: int) -> None:
        current = current_period(self._today)
        raised = previous_period(current)
        since = date(current.year - 1, current.month, 1)
        rows = [
            (ServiceType.COLD_WATER, "м³", 590_000, since),
            (ServiceType.COLD_WATER, "м³", 660_500, raised),
            (ServiceType.HOT_WATER, "м³", 2_850_000, since),
            (ServiceType.HOT_WATER, "м³", 3_190_000, raised),
            (ServiceType.ELECTRICITY, "кВт·ч", 79_900, since),
            (ServiceType.ELECTRICITY, "кВт·ч", 89_300, raised),
            (ServiceType.MAINTENANCE, "м²", 350_000, since),
            (ServiceType.OVERHAUL, "м²", overhaul_rate, since),
        ]
        self._session.add_all(
            Tariff(
                house_id=house.id,
                service=service,
                value=value,
                unit=unit,
                valid_from=valid_from,
            )
            for service, unit, value, valid_from in rows
        )
        await self._session.flush()

    async def _poll(
        self,
        house: House,
        org: Organization,
        staff: Staff,
        owners: Sequence[tuple[User, Resident]],
        ends_at: datetime,
    ) -> None:
        rng = Random(f"poll:{house.city}:{house.street}:{house.building}")
        voters = [pair for pair in owners if pair[1].verified_at is not None]
        is_active = ends_at > self._now
        if is_active:
            starts_at = self._now - timedelta(days=rng.randint(2, 6))
            voters = rng.sample(voters, len(voters) * rng.randint(20, 70) // 100)
        else:
            starts_at = ends_at - timedelta(days=14)
        title, description = ACTIVE_POLL if is_active else CLOSED_POLL
        poll = Poll(
            house_id=house.id,
            org_id=org.id,
            created_by_user_id=staff.admin,
            created_by_role="staff",
            title=title,
            description=description,
            starts_at=starts_at,
            ends_at=ends_at,
            status=PollStatus.ACTIVE if is_active else PollStatus.CLOSED,
        )
        self._session.add(poll)
        await self._session.flush()
        options = [
            PollOption(poll_id=poll.id, text=text, position=position)
            for position, text in enumerate(POLL_OPTIONS)
        ]
        self._session.add_all(options)
        await self._session.flush()
        hours = (min(ends_at, self._now) - starts_at) // timedelta(hours=1) - 1
        self._session.add_all(
            PollVote(
                poll_id=poll.id,
                option_id=rng.choices(options, weights=(7, 2, 1))[0].id,
                user_id=user.id,
                resident_id=resident.id,
                flat_id=resident.flat_id,
                counted_by_area=True,
                created_at=starts_at + timedelta(hours=rng.randint(1, hours)),
            )
            for user, resident in voters
        )
        await self._session.flush()

    async def _reception(
        self,
        org: Organization,
        houses: Sequence[tuple[House, Sequence[tuple[User, Resident]]]],
    ) -> None:
        rng = Random(f"reception:{org.inn}")
        chosen = rng.sample(list(houses), rng.randint(3, 4))
        appointments = []
        for offset in range(RECEPTION_DAYS):
            day = self._today + timedelta(days=offset)
            for weekday, start, end in RECEPTION_WINDOWS:
                if weekday != day.weekday():
                    continue
                slots = [
                    time(start + half // 2, half % 2 * 30)
                    for half in range((end - start) * 2)
                ]
                for at in rng.sample(slots, rng.randint(1, 2)):
                    house, owners = rng.choice(chosen)
                    user, _resident = rng.choice(owners)
                    appointments.append(
                        Appointment(
                            org_id=org.id,
                            house_id=house.id,
                            user_id=user.id,
                            starts_at=datetime.combine(day, at, org.zone),
                            status=AppointmentStatus.BOOKED,
                        ),
                    )
        self._session.add_all(appointments)
        await self._session.flush()

    async def _announcements(
        self,
        org: Organization,
        staff: Staff,
        house_ids: Sequence[HouseId],
        residents: Sequence[Resident],
        rows: Sequence[tuple[timedelta, str, bool]],
    ) -> list[Announcement]:
        created = []
        for age, text, urgent in rows:
            rng = Random(f"notices:{org.inn}:{text}")
            statuses = rng.choices(
                list(NOTICE_WEIGHTS),
                weights=list(NOTICE_WEIGHTS.values()),
                k=len(residents),
            )
            announcement = Announcement(
                org_id=org.id,
                house_ids=list(house_ids),
                text=text,
                channels=[AnnouncementChannel.DIRECT.value],
                created_by=staff.admin,
                recipients_count=len(residents),
                created_at=self._now - age,
                urgent=urgent,
                delivered_direct=statuses.count(NoticeStatus.DELIVERED),
                delivered_chat=0,
            )
            self._session.add(announcement)
            await self._session.flush()
            created.append(announcement)
            for resident, status in zip(residents, statuses, strict=True):
                delivery = NoticeDelivery.of(announcement.id, resident)
                delivery.status = status
                delivery.at = announcement.created_at + timedelta(
                    seconds=rng.randint(1, 90),
                )
                self._session.add(delivery)
        await self._session.flush()
        return created

    async def _demand(
        self,
        directory: Sequence[DirectoryHouse],
        taken: set[HouseId],
        users: Sequence[User],
    ) -> None:
        rng = Random("demand")
        signals: list[DemandSignal] = []
        for city, counts in DEMAND.items():
            houses = [
                item.house
                for item in directory
                if item.house.city == city and item.house.id not in taken
            ]
            for house, count in zip(houses, counts, strict=False):
                signals.extend(
                    DemandSignal(
                        house_id=house.id,
                        user_id=user.id,
                        created_at=self._now - timedelta(days=rng.randint(1, 60)),
                    )
                    for user in rng.sample(list(users), count)
                )
        self._session.add_all(signals)
        await self._session.flush()

    async def _requests(
        self,
        house: House,
        profile: OrgProfile,
        staff: Staff,
        authors: Sequence[Author],
        *,
        demo: bool,
        overdue_count: int,
        pinned: str | None,
    ) -> None:
        rng = Random(f"requests:{house.city}:{house.street}:{house.building}")
        until = self._now - (CLOSED_BEFORE if pinned else timedelta(hours=2))
        moments = []
        moment = self._now - HISTORY
        step = timedelta(days=7) / profile.requests_per_week
        while True:
            moment += step * rng.randint(20, 180) // 100
            if moment >= until:
                break
            moments.append(moment)
        phone = set(
            rng.sample(
                range(len(moments)),
                len(moments) * profile.phone_percent // 100,
            ),
        )
        categories = [
            rng.choices(
                list(CATEGORY_WEIGHTS),
                weights=list(CATEGORY_WEIGHTS.values()),
            )[0]
            for _ in moments
        ]
        overdue_candidates = [
            index
            for index, created in enumerate(moments)
            if created >= self._now - RECENT
            and CATEGORY_RULES[categories[index]].deadlines(created, house.zone)[1]
            + timedelta(hours=1)
            < self._now
        ]
        overdue = set(
            rng.sample(
                overdue_candidates,
                min(overdue_count, len(overdue_candidates)),
            ),
        )

        plans = []
        for index, created in enumerate(moments):
            author = None if index in phone else rng.choice(authors)
            plans.append(
                self._plan(
                    rng,
                    house,
                    profile,
                    staff,
                    created,
                    categories[index],
                    author,
                    keep_open=index in overdue,
                ),
            )
        if demo:
            plans.extend(await self._group(rng, house, profile, staff, authors))
        if pinned in STATE_CATEGORIES:
            created = self._now - timedelta(minutes=rng.randint(30, 180))
            if pinned in {"escalated", "overdue"}:
                created -= OVERDUE_AGE
            fresh = self._plan(
                rng,
                house,
                profile,
                staff,
                created,
                STATE_CATEGORIES[pinned],
                rng.choice(authors),
                keep_open=True,
            )
            if pinned == "escalated":
                deadline = fresh.request.deadline_at
                fresh.request.escalated_at = deadline + (self._now - deadline) / 2
            plans.append(fresh)
        self._session.add_all(plan.request for plan in plans)
        await self._session.flush()

        recent_since = self._now - RECENT
        old: list[tuple[Request, datetime, Author]] = []
        recent: list[tuple[Request, datetime, Author]] = []
        for plan in plans:
            done_at, author = plan.request.done_at, plan.author
            if done_at is None or author is None:
                continue
            if recent_since <= done_at < self._now - timedelta(days=6):
                recent.append((plan.request, done_at, author))
            elif done_at < recent_since - timedelta(days=6):
                old.append((plan.request, done_at, author))
        chosen = rng.sample(
            old,
            min(len(old), len(old) * profile.repeat_percent // 100),
        )
        chosen += rng.sample(recent, min(len(recent), profile.recent_repeats))
        repeats = []
        for request, done_at, author in chosen:
            created = done_at + timedelta(days=rng.randint(1, 5))
            if created >= until:
                continue
            repeat = self._plan(
                rng,
                house,
                profile,
                staff,
                created,
                request.category,
                author,
                keep_open=False,
            )
            repeat.request.parent_request_id = request.id
            repeat.request.description = f"Повторно: {request.description}"
            repeat.request.danger = request.danger
            repeats.append(repeat)
        self._session.add_all(plan.request for plan in repeats)
        await self._session.flush()
        plans.extend(repeats)

        for plan in plans:
            request = plan.request
            self._session.add_all(
                RequestStatusLog(
                    request_id=request.id,
                    from_status=None if index == 0 else plan.steps[index - 1].status,
                    to_status=step.status,
                    by_user_id=step.by,
                    by_role=step.role.value,
                    at=step.at,
                )
                for index, step in enumerate(plan.steps)
            )
            if plan.assigned_at is not None:
                self._session.add(
                    Event(
                        user_id=staff.admin,
                        type=EventType.REQUEST_ASSIGNED.value,
                        payload={
                            "request_id": request.id,
                            "executor_user_id": request.executor_user_id,
                        },
                        created_at=plan.assigned_at,
                    ),
                )
        if demo:
            accepted = sorted(
                (
                    plan.request.created_at,
                    plan.request.id,
                    plan.request.category,
                    executor,
                    reviewed_at,
                )
                for plan in plans
                if plan.request.completion_reason
                is RequestCompletionReason.RESIDENT_ACCEPTED
                and (executor := plan.request.executor_user_id) is not None
                and (reviewed_at := plan.request.reviewed_at) is not None
            )
            for photo, depicted in RESULT_PHOTOS.items():
                shown = [row for row in accepted if row[2] in depicted]
                if not shown:
                    continue
                _created, request_id, _category, executor, reviewed_at = shown[-1]
                self._session.add(
                    RequestAttachment(
                        request_id=request_id,
                        path=photo,
                        kind=RequestAttachmentKind.RESULT,
                        uploaded_by=executor,
                        created_at=reviewed_at,
                    ),
                )
        await self._session.flush()

    async def _group(
        self,
        rng: Random,
        house: House,
        profile: OrgProfile,
        staff: Staff,
        authors: Sequence[Author],
    ) -> list[Plan]:
        started = self._now - timedelta(days=41)
        group = RequestGroup(
            house_id=house.id,
            category=RequestCategory.ELEVATOR,
            window_started_at=started,
            status=RequestGroupStatus.CLOSED,
        )
        self._session.add(group)
        await self._session.flush()
        plans = []
        for index, author in enumerate(rng.sample(list(authors), 3)):
            plan = self._plan(
                rng,
                house,
                profile,
                staff,
                started + timedelta(minutes=50 * index),
                RequestCategory.ELEVATOR,
                author,
                keep_open=False,
            )
            plan.request.group_id = group.id
            plan.request.description = (
                "Лифт в первом подъезде стоит с открытыми дверями"
            )
            plans.append(plan)
        return plans

    def _plan(
        self,
        rng: Random,
        house: House,
        profile: OrgProfile,
        staff: Staff,
        created: datetime,
        category: RequestCategory,
        author: Author | None,
        *,
        keep_open: bool,
    ) -> Plan:
        executor = rng.choice(staff.executors)
        accepted = created + timedelta(
            minutes=profile.accept_minutes * rng.randint(40, 180) // 100,
        )
        assigned = accepted + timedelta(minutes=rng.randint(2, 15))
        started = assigned + timedelta(minutes=rng.randint(10, 180))
        reviewed = started + timedelta(hours=rng.randint(1, 30))
        reason: RequestCompletionReason | None
        if author is None:
            closer = Step(
                status=RequestStatus.DONE,
                at=reviewed + timedelta(hours=rng.randint(1, 6)),
                by=staff.admin,
                role=RequestActorRole.STAFF,
            )
            reason = None
        elif rng.randint(1, 100) <= profile.auto_close_percent:
            closer = Step(
                status=RequestStatus.DONE,
                at=reviewed + AUTO_CLOSE_AFTER,
                by=None,
                role=RequestActorRole.SYSTEM,
            )
            reason = RequestCompletionReason.AUTO_CLOSED
        else:
            closer = Step(
                status=RequestStatus.DONE,
                at=reviewed + timedelta(hours=rng.randint(1, 20)),
                by=author.user_id,
                role=RequestActorRole.RESIDENT,
            )
            reason = RequestCompletionReason.RESIDENT_ACCEPTED
        opened = Step(
            status=RequestStatus.NEW,
            at=created,
            by=staff.admin if author is None else author.user_id,
            role=(
                RequestActorRole.STAFF if author is None else RequestActorRole.RESIDENT
            ),
        )
        steps = [
            opened,
            Step(
                status=RequestStatus.ACCEPTED,
                at=accepted,
                by=staff.admin,
                role=RequestActorRole.STAFF,
            ),
            Step(
                status=RequestStatus.IN_PROGRESS,
                at=started,
                by=executor,
                role=RequestActorRole.EXECUTOR,
            ),
            Step(
                status=RequestStatus.ON_REVIEW,
                at=reviewed,
                by=executor,
                role=RequestActorRole.EXECUTOR,
            ),
            closer,
        ]
        steps = [step for step in steps if step.at < self._now]
        if keep_open:
            steps = steps[: rng.randint(1, 3)]
        if steps[-1].status is RequestStatus.ON_REVIEW:
            steps.pop()
        reached = {step.status: step.at for step in steps}
        is_assigned = RequestStatus.ACCEPTED in reached and assigned < self._now
        is_done = RequestStatus.DONE in reached
        rating = None
        if (
            is_done
            and reason is RequestCompletionReason.RESIDENT_ACCEPTED
            and rng.randint(1, 100) <= RATED_PERCENT
        ):
            rating = rng.choice(profile.ratings)
        react_deadline_at, deadline_at = CATEGORY_RULES[category].deadlines(
            created,
            house.zone,
        )
        description = rng.choice(DESCRIPTIONS[category])
        danger = detect_danger(description)
        request = Request(
            created_at=created,
            deadline_at=deadline_at,
            react_deadline_at=react_deadline_at,
            house_id=house.id,
            flat_id=None if author is None else author.flat_id,
            author_user_id=None if author is None else author.user_id,
            category=category,
            description=description,
            danger=None if danger is None else danger.kind,
            status=steps[-1].status,
            completion_reason=reason if is_done else None,
            channel=(
                RequestChannel.PHONE
                if author is None
                else rng.choice(
                    (
                        RequestChannel.MINIAPP,
                        RequestChannel.MINIAPP,
                        RequestChannel.BOT,
                    ),
                )
            ),
            caller_name=(
                f"{rng.choice(FIRST_NAMES)} {rng.choice(INITIALS)}."
                if author is None
                else None
            ),
            caller_phone="+7 (000) 000-00-00" if author is None else None,
            executor_user_id=executor if is_assigned else None,
            rating=rating,
            accepted_at=reached.get(RequestStatus.ACCEPTED),
            reviewed_at=reached.get(RequestStatus.ON_REVIEW),
            done_at=reached.get(RequestStatus.DONE),
            is_staff_author=author is None,
        )
        if request.warn_at <= self._seeded_at:
            request.deadline_warned_at = self._seeded_at
        if deadline_at <= self._seeded_at:
            request.overdue_notified_at = self._seeded_at
        return Plan(
            request=request,
            author=author,
            steps=steps,
            assigned_at=assigned if is_assigned else None,
        )

    async def _houses(
        self,
        profile: OrgProfile,
        org: Organization,
        staff: Staff,
        ordered: Sequence[DirectoryHouse],
    ) -> list[User]:
        is_enterable = profile in PROFILES
        rng = Random(f"pending:{profile.inn}")
        pending = (
            set(rng.sample(range(1, len(ordered)), rng.randint(1, 3)))
            if is_enterable
            else set()
        )
        voters: list[User] = []
        booked: list[tuple[House, Sequence[tuple[User, Resident]]]] = []
        for index, item in enumerate(ordered):
            house = item.house
            flats = await self._flats(item)
            await self._tariffs(house, item.overhaul_rate)
            demo = index == 0 and profile.inn == DEMO_INN
            if demo:
                owners = await self._demo_house(item, org, staff, flats)
                voters = [user for user, _resident in owners]
            else:
                owners = await self._owners(house, flats, staff)
                await self._meters(house, owners)
            if index in pending:
                await self._pending(house, flats, owners)
            shift = index - profile.overdue
            pinned = (
                MAP_STATES[shift]
                if is_enterable and 0 <= shift < len(MAP_STATES)
                else None
            )
            await self._requests(
                house,
                profile,
                staff,
                [
                    Author(user_id=user.id, flat_id=resident.flat_id)
                    for user, resident in owners[:DEMO_AUTHORS]
                    if resident.flat_id is not None
                ],
                demo=demo,
                overdue_count=int(index < profile.overdue),
                pinned=pinned,
            )
            await self._activity(house, org, staff, owners, pinned)
            if index == 0:
                await self._planned_works(house, org, staff, owners)
            booked.append((house, owners))
        await self._announcements(
            org,
            staff,
            [house.id for house, _owners in booked],
            [resident for _house, owners in booked for _user, resident in owners],
            ANNOUNCEMENTS,
        )
        if is_enterable:
            await self._reception(org, booked)
        return voters

    async def _users(self, count: int) -> list[User]:
        names = self._names
        users = [
            User(
                max_user_id=MaxUserId(next(self._max_ids)),
                name=f"{names.choice(FIRST_NAMES)} {names.choice(INITIALS)}.",
            )
            for _ in range(count)
        ]
        self._session.add_all(users)
        await self._session.flush()
        return users

    async def _meters(
        self,
        house: House,
        owners: Sequence[tuple[User, Resident]],
    ) -> None:
        rng = Random(f"meters:{house.city}:{house.street}:{house.building}")
        verified = [
            (user, resident.flat_id)
            for user, resident in owners
            if resident.verified_at is not None and resident.flat_id is not None
        ]
        readers = set(
            rng.sample(
                range(len(verified)),
                ceil(len(verified) * rng.randint(10, 95) / 100),
            ),
        )
        meters = [
            (
                index in readers,
                user,
                monthly,
                Meter(
                    flat_id=flat_id,
                    type=meter_type,
                    tariff_zones=len(monthly),
                    serial=f"ДЕМО-{SERIAL_CODES[meter_type]}-{flat_id:06d}",
                    next_verification_date=date(
                        self._today.year + rng.randint(2, 6),
                        self._today.month,
                        1,
                    ),
                ),
            )
            for index, (user, flat_id) in enumerate(verified)
            for meter_type, monthly in MONTHLY_USAGE.items()
        ]
        self._session.add_all(meter for *_rest, meter in meters)
        await self._session.flush()
        period = current_period(self._today)
        opened = datetime.combine(period, time(), UTC)
        self._session.add_all(
            Reading(
                meter_id=meter.id,
                period=period,
                values={
                    zone: base * rng.randint(20, 60) for zone, base in monthly.items()
                },
                ocr_used=False,
                ocr_accepted=False,
                is_below_previous=False,
                submitted_at=opened + (self._now - opened) * rng.randint(10, 90) // 100,
                submitted_by=user.id,
            )
            for reads, user, monthly, meter in meters
            if reads
        )
        await self._session.flush()

    async def _pending(
        self,
        house: House,
        flats: Sequence[Flat],
        owners: Sequence[tuple[User, Resident]],
    ) -> None:
        rng = Random(f"pending:{house.city}:{house.street}:{house.building}")
        owned = {resident.flat_id for _user, resident in owners}
        flat = rng.choice([flat for flat in flats if flat.id not in owned])
        user = await self._user()
        self._resident(user, flat, ResidentRole.OWNER, None)
        account = demo_account_no(flat.number)
        self._session.add(
            VerificationRequest(
                flat_id=flat.id,
                user_id=user.id,
                account_no=account[:-1] + str((int(account[-1]) + 1) % 10),
                status=VerificationStatus.PENDING,
                created_at=self._now - timedelta(hours=rng.randint(2, 72)),
            ),
        )
        await self._session.flush()

    async def _activity(
        self,
        house: House,
        org: Organization,
        staff: Staff,
        owners: Sequence[tuple[User, Resident]],
        pinned: str | None,
    ) -> None:
        rng = Random(f"activity:{house.city}:{house.street}:{house.building}")
        urgent = None
        if pinned == "emergency":
            posted = self._seeded_at - timedelta(minutes=rng.randint(10, 50))
            urgent = (self._now - posted, URGENT_ANNOUNCEMENTS[0], True)
        elif rng.randrange(URGENT_EVERY) == 0:
            urgent = (
                timedelta(days=rng.randint(1, 2)),
                rng.choice(URGENT_ANNOUNCEMENTS),
                True,
            )
        if urgent is not None:
            await self._announcements(
                org,
                staff,
                [house.id],
                [resident for _user, resident in owners],
                [urgent],
            )
        if pinned == "open" or rng.randrange(ACTIVE_POLL_EVERY) == 0:
            ends_at = self._now + timedelta(days=rng.randint(7, 20))
            await self._poll(house, org, staff, owners, ends_at)

    @staticmethod
    def _territory(
        free: list[DirectoryHouse],
        index: int,
        orgs: int,
        count: int,
    ) -> list[DirectoryHouse]:
        start, end = index * len(free) // orgs, (index + 1) * len(free) // orgs
        centre = min(
            free[start:end],
            key=lambda item: sorted(item.distance(other) for other in free)[count - 1],
        )
        nearest = sorted(free, key=centre.distance)[:count]
        taken = {item.house.id for item in nearest}
        free[:] = [item for item in free if item.house.id not in taken]
        return nearest

    async def _planned_works(
        self,
        house: House,
        org: Organization,
        staff: Staff,
        owners: Sequence[tuple[User, Resident]],
    ) -> None:
        [works] = await self._announcements(
            org,
            staff,
            [house.id],
            [resident for _user, resident in owners],
            [(timedelta(days=3), PLANNED_WORKS, False)],
        )
        works.works_category = RequestCategory.WATER_SUPPLY
        works.works_from = datetime.combine(
            self._today - timedelta(days=1),
            time(9),
            house.zone,
        )
        works.works_until = datetime.combine(
            self._today + timedelta(days=WORKS_DAYS_LEFT),
            time(18),
            house.zone,
        )
        works.documents = [{"name": WORKS_ORDER, "title": WORKS_ORDER_TITLE}]
        await self._session.flush()
