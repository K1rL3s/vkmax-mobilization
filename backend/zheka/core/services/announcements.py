from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence
from datetime import UTC, datetime

from zheka.base import ZhekaType
from zheka.core import texts
from zheka.core.deeplinks import ANNOUNCEMENTS_APP_PATH, poll_app_path
from zheka.core.enums import (
    AnnouncementChannel,
    EventType,
    NoticeStatus,
    NotificationCategory,
    RequestCategory,
)
from zheka.core.errors import (
    FLAT_NOT_FOUND,
    HOUSE_NOT_FOUND,
    NO_BOT_DIALOG,
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    NotEnoughRights,
)
from zheka.core.ids import (
    AnnouncementId,
    FlatId,
    HouseId,
    MaxChatId,
    OrgId,
    PollId,
    UserId,
)
from zheka.core.models import (
    Announcement,
    Flat,
    House,
    NoticeDelivery,
    Poll,
    Resident,
)
from zheka.core.services.demo import DEMO_LOCKED
from zheka.core.services.events import EventsService
from zheka.core.services.files import PDF_SUFFIX, FilesService
from zheka.core.services.notifications import NotificationsService
from zheka.infra.database.repos.announcements import AnnouncementsRepo
from zheka.infra.database.repos.chats import ChatsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo

ANNOUNCEMENT_TEXT_LIMIT = 2000
EMPTY_TEXT = "Напишите текст объявления"
TEXT_TOO_LONG = f"Сократите объявление до {ANNOUNCEMENT_TEXT_LIMIT} символов"
NO_HOUSES = "Выберите хотя бы один дом"
NO_CHANNELS = "Выберите хотя бы один канал"
UNKNOWN_ORG = "УК"
ENTRANCES_OR_FLATS = "Выберите подъезды или квартиры, но не то и другое сразу"
SCOPE_OF_ONE_HOUSE = "Подъезды и квартиры выбираются только для одного дома"
SCOPE_NEEDS_DIRECT = "Объявление для подъездов и квартир уходит в личные сообщения"
FLATS_NOT_IN_CHAT = "Объявление для квартир не отправляется в чат дома"
NO_SUCH_ENTRANCE = "В доме нет такого подъезда"
ANNOUNCEMENT_NOT_FOUND = "Объявление не найдено"
ALL_FLATS_LIMIT = 10_000
WORKS_END_BEFORE_START = "Работы должны закончиться позже, чем начнутся"
WORKS_ALREADY_OVER = "Срок работ уже прошел"
DOCUMENT_NOT_FOUND = "Документ не найден, загрузите его заново"
WORKS_NOT_GOING = "Работы сейчас не идут"


class AnnouncementData(ZhekaType):
    announcement: Announcement
    org_name: str | None
    houses_without_chat: Sequence[HouseId] = ()


class WorksDraft(ZhekaType):
    category: RequestCategory | None
    starts_at: datetime
    ends_at: datetime


class ActiveWorks(ZhekaType):
    announcement: Announcement
    ends_at: datetime


class RegisterFlat(ZhekaType):
    flat: Flat
    deliveries: Sequence[NoticeDelivery]

    @property
    def delivered(self) -> bool:
        return any(
            delivery.status is NoticeStatus.DELIVERED for delivery in self.deliveries
        )


class NoticeRegisterData(ZhekaType):
    announcement: AnnouncementData
    house: House
    flats: Sequence[RegisterFlat]
    without_flat: Sequence[NoticeDelivery]
    generated_at: datetime

    @property
    def flats_delivered(self) -> int:
        return sum(flat.delivered for flat in self.flats)


class AnnouncementsService:
    __slots__ = (
        "_announcements",
        "_chats",
        "_events",
        "_files",
        "_houses",
        "_notifications",
        "_orgs",
        "_residents",
        "_users",
    )

    def __init__(
        self,
        announcements_repo: AnnouncementsRepo,
        houses_repo: HousesRepo,
        residents_repo: ResidentsRepo,
        chats_repo: ChatsRepo,
        orgs_repo: OrgsRepo,
        notifications_service: NotificationsService,
        events_service: EventsService,
        files_service: FilesService,
        users_repo: UsersRepo,
    ) -> None:
        self._announcements = announcements_repo
        self._houses = houses_repo
        self._residents = residents_repo
        self._chats = chats_repo
        self._orgs = orgs_repo
        self._notifications = notifications_service
        self._events = events_service
        self._files = files_service
        self._users = users_repo

    async def create(
        self,
        org_id: OrgId,
        user_id: UserId,
        house_ids: Sequence[HouseId],
        text: str,
        channels: Sequence[AnnouncementChannel],
        *,
        urgent: bool = False,
        entrances: Sequence[int] | None = None,
        flat_ids: Sequence[FlatId] | None = None,
        poll_id: PollId | None = None,
        works: WorksDraft | None = None,
        documents: Sequence[Mapping[str, str]] = (),
    ) -> AnnouncementData:
        stated = text.strip()
        if not stated:
            raise InvalidRequest(EMPTY_TEXT)
        if len(stated) > ANNOUNCEMENT_TEXT_LIMIT:
            raise InvalidRequest(TEXT_TOO_LONG)
        if not house_ids:
            raise InvalidRequest(NO_HOUSES)
        if not channels:
            raise InvalidRequest(NO_CHANNELS)

        targets = list(dict.fromkeys(house_ids))
        picked = list(dict.fromkeys(channels))
        known = await self._houses.ids_for_org(targets, org_id)
        if any(house_id not in known for house_id in targets):
            raise EntityNotFound(HOUSE_NOT_FOUND)
        if any(
            not document["name"].endswith(PDF_SUFFIX)
            or not self._files.path_of(document["name"]).is_file()
            for document in documents
        ):
            raise EntityNotFound(DOCUMENT_NOT_FOUND)
        works_line = None
        starts_at = ends_at = None
        if works is not None:
            [house] = await self._houses.list_by_ids(targets[:1])
            starts_at = house.to_utc(works.starts_at)
            ends_at = house.to_utc(works.ends_at)
            if starts_at >= ends_at:
                raise InvalidRequest(WORKS_END_BEFORE_START)
            if ends_at <= datetime.now(UTC):
                raise InvalidRequest(WORKS_ALREADY_OVER)
            works_line = texts.planned_works(
                works.category,
                house.local(starts_at),
                house.local(ends_at),
            )
        whole_house = entrances is None and flat_ids is None
        if not whole_house:
            entrances, flat_ids = await self._scope(
                org_id,
                targets,
                picked,
                entrances,
                flat_ids,
            )

        residents: Sequence[Resident] = ()
        chat_ids: Sequence[MaxChatId] = ()
        houses_without_chat: Sequence[HouseId] = ()
        if AnnouncementChannel.DIRECT in picked:
            residents = (
                await self._residents.active_residents(targets)
                if whole_house
                else await self._residents.active_residents_in(
                    targets[0],
                    entrances or (),
                    flat_ids or (),
                )
            )
        if AnnouncementChannel.CHAT in picked:
            chats = await self._chats.list_for_houses(targets)
            chat_ids = [chat.chat_id for chat in chats]
            bound = {chat.house_id for chat in chats}
            houses_without_chat = [
                house_id for house_id in targets if house_id not in bound
            ]

        org = await self._orgs.get(org_id)
        org_name = UNKNOWN_ORG if org is None else org.name
        user_ids = [resident.user_id for resident in residents]
        if org is not None and org.is_demo and user_ids:
            residents = [
                resident for resident in residents if resident.user_id == user_id
            ]
            user_ids = [user_id]
        announcement = await self._announcements.create(
            org_id,
            user_id,
            targets,
            stated,
            picked,
            len(user_ids) + len(chat_ids),
            urgent=urgent,
            delivered_direct=None if user_ids else 0,
            delivered_chat=None if chat_ids else 0,
            entrances=entrances,
            flat_ids=flat_ids,
            poll_id=poll_id,
            works_category=None if works is None else works.category,
            works_from=starts_at,
            works_until=ends_at,
            documents=documents,
        )
        await self._announcements.add_deliveries(
            [NoticeDelivery.of(announcement.id, resident) for resident in residents]
            or [
                NoticeDelivery(
                    announcement_id=announcement.id,
                    user_id=recipient,
                    house_id=targets[0],
                )
                for recipient in user_ids
            ],
        )

        for channel in picked:
            await self._events.record(
                EventType.ANNOUNCEMENT_SENT,
                user_id=user_id,
                announcement_id=announcement.id,
                channel=channel.value,
                houses_count=len(targets),
            )

        message = texts.announcement(
            org_name,
            stated,
            urgent=urgent,
            entrances=entrances,
            for_flats=flat_ids is not None,
            works=works_line,
            documents=bool(documents),
        )
        app_button = app_path = None
        if poll_id is not None:
            app_button, app_path = texts.VOTE, poll_app_path(poll_id)
        elif documents:
            app_button, app_path = texts.OPEN_DOCUMENTS, ANNOUNCEMENTS_APP_PATH
        self._notifications.notify_users(
            user_ids,
            message,
            category=NotificationCategory.ANNOUNCEMENTS,
            mandatory=False,
            app_button=app_button,
            app_path=app_path,
            announcement_id=announcement.id,
        )
        self._notifications.notify_chats(
            chat_ids,
            f"{message}\n\n{texts.ANNOUNCEMENT_HASHTAG}",
            app_button=app_button,
            app_path=app_path,
            announcement_id=announcement.id,
        )

        return AnnouncementData(
            announcement=announcement,
            org_name=org_name,
            houses_without_chat=houses_without_chat,
        )

    async def list_for_resident(
        self,
        house_id: HouseId,
        flat_id: FlatId | None,
        verified: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[AnnouncementData], int]:
        entrance, own_flat_id = await self._audience(flat_id, verified)
        announcements, total = await self._announcements.list_for_house(
            house_id,
            entrance,
            own_flat_id,
            limit,
            offset,
        )
        return await self._with_org_names(announcements), total

    async def list_for_org(
        self,
        org_id: OrgId,
        house_id: HouseId | None,
        poll_id: PollId | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AnnouncementData], int]:
        if (
            house_id is not None
            and await self._houses.get_for_org(house_id, org_id) is None
        ):
            raise EntityNotFound(HOUSE_NOT_FOUND)
        announcements, total = await self._announcements.list_for_org(
            org_id,
            house_id,
            poll_id,
            limit,
            offset,
        )
        return await self._with_org_names(announcements), total

    async def _with_org_names(
        self,
        announcements: Sequence[Announcement],
    ) -> list[AnnouncementData]:
        orgs = {
            org.id: org.name
            for org in await self._orgs.list_by_ids(
                {announcement.org_id for announcement in announcements},
            )
        }
        return [
            AnnouncementData(
                announcement=announcement,
                org_name=orgs.get(announcement.org_id),
            )
            for announcement in announcements
        ]

    async def _scope(
        self,
        org_id: OrgId,
        house_ids: Sequence[HouseId],
        channels: Collection[AnnouncementChannel],
        entrances: Sequence[int] | None,
        flat_ids: Sequence[FlatId] | None,
    ) -> tuple[list[int] | None, list[FlatId] | None]:
        if entrances is not None and flat_ids is not None:
            raise InvalidRequest(ENTRANCES_OR_FLATS)
        if len(house_ids) != 1:
            raise InvalidRequest(SCOPE_OF_ONE_HOUSE)
        if AnnouncementChannel.DIRECT not in channels:
            raise InvalidRequest(SCOPE_NEEDS_DIRECT)
        [house_id] = house_ids
        if entrances is not None:
            house = await self._houses.get_for_org(house_id, org_id)
            if house is None or not all(
                1 <= entrance <= house.entrances for entrance in entrances
            ):
                raise InvalidRequest(NO_SUCH_ENTRANCE)
            return sorted(set(entrances)), None
        if AnnouncementChannel.CHAT in channels:
            raise InvalidRequest(FLATS_NOT_IN_CHAT)
        picked = list(dict.fromkeys(flat_ids or ()))
        flats = await self._houses.list_flats_by_ids(picked)
        if len(flats) != len(picked) or any(
            flat.house_id != house_id for flat in flats
        ):
            raise EntityNotFound(FLAT_NOT_FOUND)
        return None, picked

    async def announce_poll(
        self,
        org_id: OrgId,
        user_id: UserId,
        poll: Poll,
    ) -> AnnouncementData:
        house = await self._houses.get_for_org(poll.house_id, org_id)
        if house is None:
            raise EntityNotFound(HOUSE_NOT_FOUND)
        return await self.create(
            org_id,
            user_id,
            [house.id],
            texts.poll_notice(poll.title, house.local(poll.ends_at)),
            [AnnouncementChannel.DIRECT],
            poll_id=poll.id,
        )

    async def register(
        self,
        org_id: OrgId,
        announcement_id: AnnouncementId,
        house_id: HouseId | None,
    ) -> NoticeRegisterData:
        announcement, house = await self._register_house(
            org_id,
            announcement_id,
            house_id,
        )
        flats, _total = await self._houses.list_flats(
            house.id,
            None,
            None,
            limit=ALL_FLATS_LIMIT,
            offset=0,
        )
        if announcement.entrances is not None:
            flats = [flat for flat in flats if flat.entrance in announcement.entrances]
        if announcement.flat_ids is not None:
            flats = [flat for flat in flats if flat.id in announcement.flat_ids]
        by_flat: defaultdict[FlatId | None, list[NoticeDelivery]] = defaultdict(list)
        for delivery in await self._announcements.deliveries(announcement.id, house.id):
            by_flat[delivery.flat_id].append(delivery)
        [data] = await self._with_org_names([announcement])
        return NoticeRegisterData(
            announcement=data,
            house=house,
            flats=[
                RegisterFlat(flat=flat, deliveries=by_flat[flat.id]) for flat in flats
            ],
            without_flat=by_flat[None],
            generated_at=datetime.now(UTC),
        )

    async def active_works(
        self,
        user_id: UserId,
        house_id: HouseId,
        category: RequestCategory,
    ) -> ActiveWorks | None:
        resident = await self._residents.get_for_house(user_id, house_id)
        house = await self._houses.get(house_id)
        if resident is None or house is None:
            return None
        entrance, flat_id = await self._audience(
            resident.flat_id,
            resident.verified_at is not None,
        )
        announcement = await self._announcements.active_works(
            house_id,
            entrance,
            flat_id,
            category,
            datetime.now(UTC),
        )
        if announcement is None or announcement.works_until is None:
            return None
        return ActiveWorks(
            announcement=announcement,
            ends_at=house.local(announcement.works_until),
        )

    async def finish_works(
        self,
        org_id: OrgId,
        announcement_id: AnnouncementId,
        actor_id: UserId,
    ) -> AnnouncementData:
        announcement = await self._announcements.get_for_org(announcement_id, org_id)
        if announcement is None:
            raise EntityNotFound(ANNOUNCEMENT_NOT_FOUND)
        if (
            announcement.created_by != actor_id
            and (await self._orgs.get_existing(org_id)).is_demo
        ):
            raise NotEnoughRights(DEMO_LOCKED)
        if not await self._announcements.finish_works(announcement, datetime.now(UTC)):
            raise InvalidState(WORKS_NOT_GOING)
        message = texts.works_finished(announcement.works_category)
        self._notifications.notify_users(
            await self._announcements.addressees(announcement.id),
            message,
            category=NotificationCategory.ANNOUNCEMENTS,
            mandatory=False,
            silent=True,
        )
        if AnnouncementChannel.CHAT in announcement.channels:
            chats = await self._chats.list_for_houses(announcement.house_ids)
            self._notifications.notify_chats(
                [chat.chat_id for chat in chats],
                f"{message}\n\n{texts.ANNOUNCEMENT_HASHTAG}",
            )
        [data] = await self._with_org_names([announcement])
        return data

    async def _audience(
        self,
        flat_id: FlatId | None,
        verified: bool,
    ) -> tuple[int | None, FlatId | None]:
        flat = None if flat_id is None else await self._houses.get_flat(flat_id)
        return None if flat is None else flat.entrance, flat_id if verified else None

    async def send_register_pdf(
        self,
        org_id: OrgId,
        user_id: UserId,
        announcement_id: AnnouncementId,
        house_id: HouseId | None,
        *,
        unmarked_only: bool,
    ) -> None:
        _announcement, house = await self._register_house(
            org_id,
            announcement_id,
            house_id,
        )
        user = await self._users.get_by_id(user_id)
        if user is None or not user.in_dialog:
            raise InvalidState(NO_BOT_DIALOG)
        self._notifications.send_register_pdf(
            user_id,
            org_id,
            announcement_id,
            house.id,
            unmarked_only=unmarked_only,
        )

    async def _register_house(
        self,
        org_id: OrgId,
        announcement_id: AnnouncementId,
        house_id: HouseId | None,
    ) -> tuple[Announcement, House]:
        announcement = await self._announcements.get_for_org(announcement_id, org_id)
        if announcement is None:
            raise EntityNotFound(ANNOUNCEMENT_NOT_FOUND)
        picked = announcement.house_ids[0] if house_id is None else house_id
        house = await self._houses.get_for_org(picked, org_id)
        if house is None or picked not in announcement.house_ids:
            raise EntityNotFound(HOUSE_NOT_FOUND)
        return announcement, house
