from zheka.base import ZhekaType
from zheka.core.consent import CONSENT_VERSION
from zheka.core.errors import EntityNotFound, InvalidRequest
from zheka.core.ids import FlatId, HouseId, OrgId, UserId
from zheka.core.models import OrgMember, Organization, User
from zheka.core.services.houses import ResidencyView, is_connected
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


class ProfileService:
    __slots__ = ("_houses", "_orgs", "_residents", "_users")

    def __init__(
        self,
        users_repo: UsersRepo,
        residents_repo: ResidentsRepo,
        houses_repo: HousesRepo,
        orgs_repo: OrgsRepo,
    ) -> None:
        self._users = users_repo
        self._residents = residents_repo
        self._houses = houses_repo
        self._orgs = orgs_repo

    async def me(self, user_id: UserId) -> MeView:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise EntityNotFound("Пользователь не найден")

        residents = await self._residents.list_for_user(user_id)
        houses = {
            house.id: house
            for house in await self._houses.list_by_ids(
                [HouseId(resident.house_id) for resident in residents],
            )
        }
        flats = {
            flat.id: flat
            for flat in await self._houses.list_flats_by_ids(
                [
                    FlatId(resident.flat_id)
                    for resident in residents
                    if resident.flat_id is not None
                ],
            )
        }

        members = await self._orgs.list_for_user(user_id)
        org_ids = {OrgId(house.org_id) for house in houses.values() if house.org_id}
        org_ids |= {OrgId(member.org_id) for member in members}
        orgs = {org.id: org for org in await self._orgs.list_by_ids(org_ids)}

        residencies = []
        for resident in residents:
            house = houses[resident.house_id]
            org = None if house.org_id is None else orgs.get(OrgId(house.org_id))
            residencies.append(
                ResidencyView(
                    resident=resident,
                    house=house,
                    flat=None if resident.flat_id is None else flats[resident.flat_id],
                    is_connected=is_connected(house, org),
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
            # демо-режим красит весь кабинет, поэтому достаточно одной демо-УК
            is_demo=any(org.is_demo for org in orgs.values()),
        )

    async def accept_consent(self, user_id: UserId, version: str) -> MeView:
        if version != CONSENT_VERSION:
            raise InvalidRequest(f"Актуальная версия согласия - {CONSENT_VERSION}")
        await self._users.set_consent(user_id, version)
        return await self.me(user_id)
