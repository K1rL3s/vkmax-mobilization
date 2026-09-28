from zheka.core.enums import EventType, OrgRole, RequestCategory
from zheka.core.errors import EntityNotFound, InvalidRequest
from zheka.core.ids import OrgId, UserId
from zheka.core.models import Request
from zheka.core.services.events import EventsService
from zheka.core.services.notifications import NotificationsService
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import RequestsRepo

EXECUTOR_NOT_FOUND = "Исполнитель не найден"
NOT_AN_EXECUTOR = "Заявку ведет исполнитель, а не сотрудник кабинета"


class CategoryExecutorsService:
    __slots__ = ("_events", "_notifications", "_orgs", "_requests")

    def __init__(
        self,
        requests_repo: RequestsRepo,
        orgs_repo: OrgsRepo,
        notifications_service: NotificationsService,
        events_service: EventsService,
    ) -> None:
        self._requests = requests_repo
        self._orgs = orgs_repo
        self._notifications = notifications_service
        self._events = events_service

    async def mapping(self, org_id: OrgId) -> dict[RequestCategory, UserId]:
        stored = await self._orgs.list_category_executors(org_id)
        members = await self._orgs.list_members(org_id)
        executors = {
            member.user_id for member in members if member.role is OrgRole.EXECUTOR
        }
        return {
            category: user_id
            for category, user_id in stored.items()
            if user_id in executors
        }

    async def set(
        self,
        org_id: OrgId,
        category: RequestCategory,
        user_id: UserId | None,
    ) -> dict[RequestCategory, UserId]:
        if user_id is None:
            await self._orgs.unset_category_executor(org_id, category)
        else:
            await self.check(org_id, user_id)
            await self._orgs.set_category_executor(org_id, category, user_id)
        return await self.mapping(org_id)

    async def check(self, org_id: OrgId, user_id: UserId) -> None:
        member = await self._orgs.get_member(org_id, user_id)
        if member is None:
            raise EntityNotFound(EXECUTOR_NOT_FOUND)
        if member.role is not OrgRole.EXECUTOR:
            raise InvalidRequest(NOT_AN_EXECUTOR)

    async def assign_default(self, request: Request, org_id: OrgId | None) -> None:
        if org_id is None:
            return
        user_id = (await self._orgs.list_category_executors(org_id)).get(
            request.category,
        )
        if user_id is None:
            return
        member = await self._orgs.get_member(org_id, user_id)
        if member is None or member.role is not OrgRole.EXECUTOR:
            return
        await self._requests.set_executor(request, user_id)
        await self._events.record(
            EventType.REQUEST_ASSIGNED,
            request_id=request.id,
            executor_user_id=user_id,
        )
        self._notifications.open_executor_card(request.id)
