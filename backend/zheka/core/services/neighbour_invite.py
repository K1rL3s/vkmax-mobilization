from zheka.base import ZhekaType
from zheka.core import texts
from zheka.core.errors import (
    HOUSE_NOT_FOUND,
    NO_BOT_DIALOG,
    EntityNotFound,
    InvalidState,
)
from zheka.core.ids import HouseId, UserId
from zheka.core.models import House
from zheka.core.services.houses import is_connected
from zheka.core.services.notifications import NotificationsService
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.users import UsersRepo


class NeighbourInvite(ZhekaType):
    house: House
    is_connected: bool
    is_demo: bool

    @property
    def text(self) -> str:
        return texts.neighbour_invite_text(
            self.house.address,
            connected=self.is_connected,
        )


class NeighbourInviteService:
    __slots__ = ("_houses", "_notifications", "_orgs", "_users")

    def __init__(
        self,
        houses_repo: HousesRepo,
        orgs_repo: OrgsRepo,
        users_repo: UsersRepo,
        notifications_service: NotificationsService,
    ) -> None:
        self._houses = houses_repo
        self._orgs = orgs_repo
        self._users = users_repo
        self._notifications = notifications_service

    async def invite(self, house_id: HouseId) -> NeighbourInvite:
        house = await self._houses.get(house_id)
        if house is None:
            raise EntityNotFound(HOUSE_NOT_FOUND)
        org = None if house.org_id is None else await self._orgs.get(house.org_id)
        return NeighbourInvite(
            house=house,
            is_connected=is_connected(house, org),
            is_demo=org is not None and org.is_demo,
        )

    async def send_leaflet(self, user_id: UserId, house_id: HouseId) -> None:
        await self.invite(house_id)
        user = await self._users.get_by_id(user_id)
        if user is None or not user.in_dialog:
            raise InvalidState(NO_BOT_DIALOG)
        self._notifications.send_neighbour_leaflet(user_id, house_id)
