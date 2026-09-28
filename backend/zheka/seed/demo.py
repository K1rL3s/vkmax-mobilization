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
from zheka.core.enums import (
    CATEGORY_RULES,
    AnnouncementChannel,
    AppointmentStatus,
    EventType,
    OrgRole,
    PollStatus,
    RequestActorRole,
    RequestCategory,
    RequestChannel,
    RequestCompletionReason,
    RequestGroupStatus,
    RequestPhotoKind,
    RequestStatus,
    ResidentRole,
    ServiceType,
)
from zheka.core.ids import FlatId, HouseId, MaxUserId, UserId
from zheka.core.models import (
    Announcement,
    Appointment,
    DemandSignal,
    Event,
    Flat,
    House,
    OrgMember,
    OrgSettings,
    Organization,
    Poll,
    PollOption,
    PollVote,
    ReceptionWindow,
    Request,
    RequestGroup,
    RequestPhoto,
    RequestStatusLog,
    Resident,
    Tariff,
    User,
)
from zheka.core.services.demo import DEMO_INN, DEMO_INNS, DemoService, demo_account_no
from zheka.core.services.readings import current_period
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
RESIDENTS_PER_HOUSE = 8
REVIEWERS_GROUP_THRESHOLD = 10
DEMO_AUTHORS = 15
POLL_TURNOUT = 4_870
DEMAND = (7, 5, 4, 2, 1)
RATED_PERCENT = 85
MIN_FLATS = 40
MAX_FLATS = 250
SEED_LOCK = 1


class OrgProfile(ZhekaType):
    name: str
    inn: str
    cities: tuple[str, ...]
    accept_minutes: int
    phone_percent: int
    repeat_percent: int
    recent_repeats: int
    auto_close_percent: int
    ratings: tuple[int, ...]
    overdue: int


PROFILES = (
    OrgProfile(
        name="Демо-УК «Жэка Коммуналкин»",
        inn=DEMO_INNS[0],
        cities=("Москва",),
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
        cities=("Москва", "Санкт-Петербург"),
        accept_minutes=20,
        phone_percent=25,
        repeat_percent=3,
        recent_repeats=0,
        auto_close_percent=3,
        ratings=(5, 5, 5, 4),
        overdue=0,
    ),
    OrgProfile(
        name="Демо-УК «Надежный дом»",
        inn=DEMO_INNS[2],
        cities=("Москва", "Казань"),
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
        cities=("Москва", "Казань"),
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
        cities=("Москва", "Казань"),
        accept_minutes=300,
        phone_percent=35,
        repeat_percent=18,
        recent_repeats=5,
        auto_close_percent=40,
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
        40,
        "Плановое отключение горячей воды с 10:00 до 18:00, работы на теплотрассе",
        True,
    ),
    (
        20,
        "Во дворе начнется ремонт асфальта, машины просим переставить к торцу дома",
        False,
    ),
    (5, "Итоги опроса о шлагбауме опубликованы в разделе собраний", False),
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
    today: date,
) -> bool:
    stmt = select(func.pg_advisory_xact_lock(SEED_LOCK))
    await session.execute(stmt)
    if await OrgsRepo(session).get_by_inn(DEMO_INN) is not None:
        logger.info("Демо-организация уже есть, сид пропущен")
        return False
    _copy_files(files_dir)
    directory = await load_directory(session)
    await Seeder(session, demo, today).run(directory)
    logger.info("Сид готов: домов в справочнике %s", len(directory))
    return True


def _copy_files(files_dir: Path) -> None:
    files_dir.mkdir(parents=True, exist_ok=True)
    for name in (*DOCUMENTS, *RESULT_PHOTOS):
        target = files_dir / name
        if not target.exists():
            shutil.copyfile(FILES_DIR / name, target)


def _history_houses(
    directory: Sequence[DirectoryHouse],
) -> dict[str, list[DirectoryHouse]]:
    by_city: dict[str, list[DirectoryHouse]] = {}
    for item in sorted(directory, key=lambda item: item.house.org_id is not None):
        house = item.house
        if house.lat is not None and MIN_FLATS <= item.living_flats <= MAX_FLATS:
            by_city.setdefault(house.city, []).append(item)
    return by_city


class Seeder:
    __slots__ = ("_demo", "_max_ids", "_names", "_now", "_session", "_today")

    def __init__(self, session: AsyncSession, demo: DemoService, today: date) -> None:
        self._session = session
        self._demo = demo
        self._today = today
        self._now = datetime.combine(today, time(), UTC)
        self._max_ids: Iterator[int] = itertools.count(-1, -1)
        self._names = Random("names")

    async def run(self, directory: Sequence[DirectoryHouse]) -> None:
        free = _history_houses(directory)
        voters: list[User] = []
        taken: set[HouseId] = set()
        for profile in PROFILES:
            org = await self._org(profile, free[profile.cities[0]][0].house.timezone)
            staff = await self._staff(org, profile)
            for city in profile.cities:
                item = free[city].pop(0)
                item.house.org_id = org.id
                taken.add(item.house.id)
                await self._session.flush()
                flats = await self._flats(item)
                await self._tariffs(item.house, item.overhaul_rate)
                if profile.inn == DEMO_INN:
                    authors, voters = await self._demo_house(item, org, staff, flats)
                else:
                    authors = await self._owners(item.house, flats, staff)
                await self._requests(item.house, profile, staff, authors)
        await self._demand(
            [
                item.house
                for item in directory
                if item.house.city == "Москва" and item.house.id not in taken
            ],
            voters,
        )

    async def _user(self) -> User:
        name = f"{self._names.choice(FIRST_NAMES)} {self._names.choice(INITIALS)}."
        user = User(max_user_id=MaxUserId(next(self._max_ids)), name=name)
        self._session.add(user)
        await self._session.flush()
        return user

    async def _org(self, profile: OrgProfile, timezone: str) -> Organization:
        org = Organization(
            name=profile.name,
            inn=profile.inn,
            phone=f"+7 (000) 000-00-{PROFILES.index(profile) + 1:02d}",
            address="Адрес вымышлен, организация создана для демо",
            reception_note="Прием по вторникам и четвергам, запись в приложении",
            registered_at=self._now - HISTORY - timedelta(days=30),
            is_demo=True,
            timezone=timezone,
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

    async def _resident(
        self,
        user: User,
        flat: Flat,
        role: ResidentRole,
        staff: Staff,
    ) -> Resident:
        is_owner = role is ResidentRole.OWNER
        resident = Resident(
            user_id=user.id,
            house_id=flat.house_id,
            flat_id=flat.id,
            role=role,
            can_see_charges=is_owner,
            can_vote=is_owner,
            verified_at=self._now - HISTORY,
            verified_by=staff.admin,
        )
        self._session.add(resident)
        await self._session.flush()
        return resident

    async def _owners(
        self,
        house: House,
        flats: Sequence[Flat],
        staff: Staff,
    ) -> list[Author]:
        rng = Random(f"owners:{house.city}:{house.street}:{house.building}")
        authors = []
        for flat in rng.sample(list(flats), RESIDENTS_PER_HOUSE):
            user = await self._user()
            await self._resident(user, flat, ResidentRole.OWNER, staff)
            authors.append(Author(user_id=user.id, flat_id=flat.id))
        return authors

    async def _demo_house(
        self,
        item: DirectoryHouse,
        org: Organization,
        staff: Staff,
        flats: Sequence[Flat],
    ) -> tuple[list[Author], list[User]]:
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
            resident = await self._resident(user, flat, ResidentRole.OWNER, staff)
            owners.append((user, resident))
            await self._demo.furnish(
                flat,
                user.id,
                self._today,
                spike=scenario == "spike",
                below=scenario == "below",
                verification_soon=scenario == "verification",
            )
        await self._resident(await self._user(), main[0], ResidentRole.TENANT, staff)

        total = sum(flat.area or 0 for flat in flats)
        voted = sum(flat.area or 0 for flat in main)
        for flat in others:
            area = flat.area or 0
            if (voted + area) * 10_000 // total >= POLL_TURNOUT:
                continue
            voted += area
            user = await self._user()
            resident = await self._resident(user, flat, ResidentRole.OWNER, staff)
            owners.append((user, resident))
        await self._poll(house, org, staff, owners)
        await self._reception(house, org, owners)
        await self._announcements(house, org, staff, len(owners) + 1)
        authors = [
            Author(user_id=user.id, flat_id=resident.flat_id)
            for user, resident in owners[:DEMO_AUTHORS]
            if resident.flat_id is not None
        ]
        return authors, [user for user, _resident in owners]

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
    ) -> None:
        ends_at = self._now - timedelta(days=10)
        poll = Poll(
            house_id=house.id,
            org_id=org.id,
            created_by_user_id=staff.admin,
            created_by_role="staff",
            title="Установка шлагбаума во дворе",
            description="Шлагбаум на въезде во двор за счет собственников",
            starts_at=ends_at - timedelta(days=14),
            ends_at=ends_at,
            status=PollStatus.CLOSED,
        )
        self._session.add(poll)
        await self._session.flush()
        options = [
            PollOption(poll_id=poll.id, text=text, position=position)
            for position, text in enumerate(POLL_OPTIONS)
        ]
        self._session.add_all(options)
        await self._session.flush()
        rng = Random(f"poll:{house.city}:{house.street}:{house.building}")
        self._session.add_all(
            PollVote(
                poll_id=poll.id,
                option_id=rng.choices(options, weights=(7, 2, 1))[0].id,
                user_id=user.id,
                resident_id=resident.id,
                flat_id=resident.flat_id,
                counted_by_area=True,
                created_at=poll.starts_at + timedelta(hours=rng.randint(1, 13 * 24)),
            )
            for user, resident in owners
        )
        await self._session.flush()

    async def _reception(
        self,
        house: House,
        org: Organization,
        owners: Sequence[tuple[User, Resident]],
    ) -> None:
        self._session.add_all(
            ReceptionWindow(
                org_id=org.id,
                weekday=weekday,
                time_from=time(start),
                time_to=time(end),
                slot_minutes=30,
                capacity=2,
            )
            for weekday, start, end in ((1, 9, 12), (3, 15, 19))
        )
        past = self._today - timedelta(days=(self._today.weekday() - 1) % 7 or 7)
        upcoming = self._today + timedelta(days=(3 - self._today.weekday()) % 7 or 7)
        self._session.add_all(
            Appointment(
                org_id=org.id,
                house_id=house.id,
                user_id=user.id,
                starts_at=datetime.combine(day, at, org.zone),
                status=status,
            )
            for (user, _resident), day, at, status in (
                (owners[0], past, time(9, 30), AppointmentStatus.DONE),
                (owners[1], upcoming, time(16), AppointmentStatus.BOOKED),
            )
        )
        await self._session.flush()

    async def _announcements(
        self,
        house: House,
        org: Organization,
        staff: Staff,
        recipients: int,
    ) -> None:
        self._session.add_all(
            Announcement(
                org_id=org.id,
                house_ids=[house.id],
                text=text,
                channels=[AnnouncementChannel.DIRECT.value],
                created_by=staff.admin,
                recipients_count=recipients,
                created_at=self._now - timedelta(days=days_ago),
                urgent=urgent,
            )
            for days_ago, text, urgent in ANNOUNCEMENTS
        )
        await self._session.flush()

    async def _demand(self, houses: Sequence[House], users: Sequence[User]) -> None:
        rng = Random("demand")
        signals: list[DemandSignal] = []
        for house, count in zip(houses, DEMAND, strict=False):
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
    ) -> None:
        rng = Random(f"requests:{house.city}:{house.street}:{house.building}")
        moments = []
        moment = self._now - HISTORY
        step = timedelta(days=7) / REQUESTS_PER_WEEK
        while True:
            moment += step * rng.randint(20, 180) // 100
            if moment >= self._now - timedelta(hours=2):
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
                min(profile.overdue, len(overdue_candidates)),
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
        if profile.inn == DEMO_INN:
            plans.extend(await self._group(rng, house, profile, staff, authors))
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
            repeat = self._plan(
                rng,
                house,
                profile,
                staff,
                done_at + timedelta(days=rng.randint(1, 5)),
                request.category,
                author,
                keep_open=False,
            )
            repeat.request.parent_request_id = request.id
            repeat.request.description = f"Повторно: {request.description}"
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
        if profile.inn == DEMO_INN:
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
                    RequestPhoto(
                        request_id=request_id,
                        path=photo,
                        kind=RequestPhotoKind.RESULT,
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
        request = Request(
            created_at=created,
            deadline_at=deadline_at,
            react_deadline_at=react_deadline_at,
            house_id=house.id,
            flat_id=None if author is None else author.flat_id,
            author_user_id=None if author is None else author.user_id,
            category=category,
            description=rng.choice(DESCRIPTIONS[category]),
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
        if request.warn_at <= self._now:
            request.deadline_warned_at = self._now
        if deadline_at <= self._now:
            request.overdue_notified_at = self._now
        return Plan(
            request=request,
            author=author,
            steps=steps,
            assigned_at=assigned if is_assigned else None,
        )
