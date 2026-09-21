from collections.abc import Sequence

from zheka.base import ZhekaType
from zheka.core import texts
from zheka.core.enums import AnnouncementChannel, EventType, NotificationCategory
from zheka.core.errors import EntityNotFound, InvalidRequest
from zheka.core.ids import AnnouncementId, HouseId, MaxChatId, OrgId, UserId
from zheka.core.models import Announcement
from zheka.core.services.events import EventsService
from zheka.core.services.notifications import NotificationsService
from zheka.infra.database.repos.announcements import AnnouncementsRepo
from zheka.infra.database.repos.chats import ChatsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo

HOUSE_NOT_FOUND = "Дом не найден"
EMPTY_TEXT = "Напишите текст объявления"
NO_HOUSES = "Выберите хотя бы один дом"
NO_CHANNELS = "Выберите хотя бы один канал"
UNKNOWN_ORG = "УК"


class AnnouncementData(ZhekaType):
    announcement: Announcement
    org_name: str | None
    # только у только что созданного объявления
    houses_without_chat: Sequence[HouseId] = ()


class AnnouncementsService:
    __slots__ = (
        "_announcements",
        "_chats",
        "_events",
        "_houses",
        "_notifications",
        "_orgs",
        "_residents",
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
    ) -> None:
        self._announcements = announcements_repo
        self._houses = houses_repo
        self._residents = residents_repo
        self._chats = chats_repo
        self._orgs = orgs_repo
        self._notifications = notifications_service
        self._events = events_service

    async def create(
        self,
        org_id: OrgId,
        user_id: UserId,
        house_ids: Sequence[HouseId],
        text: str,
        channels: Sequence[AnnouncementChannel],
    ) -> AnnouncementData:
        stated = text.strip()
        if not stated:
            raise InvalidRequest(EMPTY_TEXT)
        if not house_ids:
            raise InvalidRequest(NO_HOUSES)
        if not channels:
            raise InvalidRequest(NO_CHANNELS)

        targets = list(dict.fromkeys(house_ids))
        picked = list(dict.fromkeys(channels))
        # дом чужой организации отвечает 404: 403 подтвердил бы, что он есть
        known = await self._houses.ids_for_org(targets, org_id)
        if any(house_id not in known for house_id in targets):
            raise EntityNotFound(HOUSE_NOT_FOUND)

        user_ids: Sequence[UserId] = ()
        chat_ids: Sequence[MaxChatId] = ()
        houses_without_chat: Sequence[HouseId] = ()
        if AnnouncementChannel.DIRECT in picked:
            user_ids = await self._residents.active_user_ids(targets)
        if AnnouncementChannel.CHAT in picked:
            chats = await self._chats.list_for_houses(targets)
            chat_ids = [MaxChatId(chat.chat_id) for chat in chats]
            bound = {chat.house_id for chat in chats}
            houses_without_chat = [
                house_id for house_id in targets if house_id not in bound
            ]

        org = await self._orgs.get(org_id)
        org_name = UNKNOWN_ORG if org is None else org.name
        announcement = await self._announcements.create(
            org_id,
            user_id,
            targets,
            stated,
            picked,
            len(user_ids) + len(chat_ids),
        )

        for channel in picked:
            await self._events.record(
                EventType.ANNOUNCEMENT_SENT,
                user_id=user_id,
                announcement_id=AnnouncementId(announcement.id),
                channel=channel.value,
                houses_count=len(targets),
            )

        message = texts.announcement(org_name, stated)
        self._notifications.notify_users(
            user_ids,
            message,
            category=NotificationCategory.ANNOUNCEMENTS,
            mandatory=False,
        )
        self._notifications.notify_chats(chat_ids, message)

        return AnnouncementData(
            announcement=announcement,
            org_name=org_name,
            houses_without_chat=houses_without_chat,
        )

    async def list_for_resident(
        self,
        house_id: HouseId,
        limit: int,
        offset: int,
    ) -> tuple[list[AnnouncementData], int]:
        # дом уже проверил CurrentResidency
        announcements, total = await self._announcements.list_for_house(
            house_id,
            limit,
            offset,
        )
        return await self._with_org_names(announcements), total

    async def list_for_org(
        self,
        org_id: OrgId,
        house_id: HouseId | None,
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
            limit,
            offset,
        )
        return await self._with_org_names(announcements), total

    async def _with_org_names(
        self,
        announcements: Sequence[Announcement],
    ) -> list[AnnouncementData]:
        orgs = {
            OrgId(org.id): org.name
            for org in await self._orgs.list_by_ids(
                {OrgId(announcement.org_id) for announcement in announcements},
            )
        }
        return [
            AnnouncementData(
                announcement=announcement,
                org_name=orgs.get(OrgId(announcement.org_id)),
            )
            for announcement in announcements
        ]
