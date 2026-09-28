from zheka.base import ZhekaType
from zheka.core.consent import CONSENT_VERSION
from zheka.core.enums import EventSource, EventType, VerificationStatus
from zheka.core.errors import EntityNotFound, InvalidRequest
from zheka.core.ids import UserId
from zheka.core.models import OrgMember, Organization, User
from zheka.core.services.events import EventsService
from zheka.core.services.houses import ResidencyView
from zheka.infra.database.repos.flats import FlatsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo


class OrgMembershipView(ZhekaType):
    member: OrgMember
    org: Organization


class MeView(ZhekaType):
    user: User
    residencies: list[ResidencyView]
    orgs: list[OrgMembershipView]
    is_demo: bool

    @property
    def latest_residency(self) -> ResidencyView | None:
        return max(
            self.residencies,
            key=lambda item: item.resident.created_at,
            default=None,
        )

    @property
    def is_staff(self) -> bool:
        return any(membership.member.role.is_staff for membership in self.orgs)


class ProfileService:
    __slots__ = ("_events", "_flats", "_houses", "_orgs", "_residents", "_users")

    def __init__(
        self,
        users_repo: UsersRepo,
        residents_repo: ResidentsRepo,
        houses_repo: HousesRepo,
        orgs_repo: OrgsRepo,
        flats_repo: FlatsRepo,
        events_service: EventsService,
    ) -> None:
        self._users = users_repo
        self._residents = residents_repo
        self._houses = houses_repo
        self._orgs = orgs_repo
        self._flats = flats_repo
        self._events = events_service

    async def me(self, user_id: UserId) -> MeView:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise EntityNotFound("Пользователь не найден")

        residents = await self._residents.list_for_user(user_id)
        houses = {
            house.id: house
            for house in await self._houses.list_by_ids(
                [resident.house_id for resident in residents],
            )
        }
        flats = {
            flat.id: flat
            for flat in await self._houses.list_flats_by_ids(
                [
                    resident.flat_id
                    for resident in residents
                    if resident.flat_id is not None
                ],
            )
        }

        latest_by_flat = {
            request.flat_id: request
            for request in await self._flats.list_latest_requests(user_id, flats.keys())
        }

        members = await self._orgs.list_for_user(user_id)
        org_ids = {house.org_id for house in houses.values() if house.org_id}
        org_ids |= {member.org_id for member in members}
        orgs = {org.id: org for org in await self._orgs.list_by_ids(org_ids)}

        residencies = []
        for resident in residents:
            house = houses[resident.house_id]
            org = None if house.org_id is None else orgs.get(house.org_id)
            latest = (
                None
                if resident.flat_id is None
                else latest_by_flat.get(resident.flat_id)
            )
            residencies.append(
                ResidencyView(
                    resident=resident,
                    house=house,
                    flat=None if resident.flat_id is None else flats[resident.flat_id],
                    org=org,
                    verification_status=None if latest is None else latest.status,
                    verification_reject_reason=(
                        latest.reason
                        if latest is not None
                        and latest.status is VerificationStatus.REJECTED
                        else None
                    ),
                ),
            )
        memberships = [
            OrgMembershipView(member=member, org=orgs[member.org_id])
            for member in members
        ]
        return MeView(
            user=user,
            residencies=residencies,
            orgs=memberships,
            is_demo=any(org.is_demo for org in orgs.values()),
        )

    async def accept_consent(
        self,
        user_id: UserId,
        version: str,
        source: EventSource,
    ) -> MeView:
        if version != CONSENT_VERSION:
            raise InvalidRequest(f"Актуальная версия согласия - {CONSENT_VERSION}")
        await self._users.set_consent(user_id, version)
        await self._events.record(
            EventType.CONSENT_GIVEN,
            user_id=user_id,
            source=source.value,
            version=version,
        )
        return await self.me(user_id)
