import secrets
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy.exc import IntegrityError

from zheka.base import ZhekaType
from zheka.config import DeeplinksConfig
from zheka.core.enums import EventType, OrgRole
from zheka.core.errors import (
    INVITE_NOT_FOUND,
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    NotEnoughRights,
)
from zheka.core.ids import OrgId, UserId
from zheka.core.models import OrgInvite, OrgMember, OrgSettings, Organization, User
from zheka.core.services.events import EventsService
from zheka.core.services.houses import HouseFound, is_connected
from zheka.core.services.invites import issue_invite
from zheka.core.services.profile import OrgMembershipView
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.invites import InvitesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.users import UsersRepo

MIN_METER_WINDOW_DAY = 1
MAX_METER_WINDOW_DAY = 28
MIN_GROUP_THRESHOLD = 2
MIN_GROUP_WINDOW_HOURS = 1
MAX_GROUP_WINDOW_HOURS = 168
INVITE_USED_UP = "Код приглашения истек, отозван или исчерпан"


class OrgLookupView(ZhekaType):
    org: Organization | None
    houses: list[HouseFound]


class OrgCardView(ZhekaType):
    org: Organization
    houses_count: int
    members_count: int


class OrgSettingsView(ZhekaType):
    org: Organization
    settings: OrgSettings


class OrgMemberView(ZhekaType):
    member: OrgMember
    user: User


class OrgsService:
    __slots__ = ("_deeplinks", "_events", "_houses", "_invites", "_orgs", "_users")

    def __init__(
        self,
        orgs_repo: OrgsRepo,
        invites_repo: InvitesRepo,
        houses_repo: HousesRepo,
        users_repo: UsersRepo,
        events_service: EventsService,
        deeplinks: DeeplinksConfig,
    ) -> None:
        self._orgs = orgs_repo
        self._invites = invites_repo
        self._houses = houses_repo
        self._users = users_repo
        self._events = events_service
        self._deeplinks = deeplinks

    async def lookup(self, inn: str | None, license_no: str | None) -> OrgLookupView:
        if (inn is None) == (license_no is None):
            raise InvalidRequest("Укажите или ИНН, или номер лицензии")

        org = (
            await self._orgs.get_by_inn(inn)
            if inn is not None
            else await self._orgs.get_by_license(cast("str", license_no))
        )
        if org is None:
            return OrgLookupView(org=None, houses=[])

        houses = await self._houses.list_for_org(org.id)
        return OrgLookupView(
            org=org,
            houses=[
                HouseFound(house=house, org=org, is_connected=is_connected(house, org))
                for house in houses
            ],
        )

    async def register(
        self,
        user_id: UserId,
        deeplink_code: str,
        inn: str,
        license_no: str | None,
        name: str,
        phone: str,
        address: str,
    ) -> OrgCardView:
        if not deeplink_code.isascii() or not secrets.compare_digest(
            deeplink_code,
            self._deeplinks.org_register,
        ):
            raise NotEnoughRights("Неверный код регистрации организации")

        org = await self._orgs.get_by_inn(inn)
        if org is None and license_no is not None:
            org = await self._orgs.get_by_license(license_no)
        if org is None:
            raise EntityNotFound("Организация не найдена в реестре")
        if org.registered_at is not None:
            raise InvalidState("Организация уже зарегистрирована")

        org.registered_at = datetime.now(UTC)
        org.name = name
        org.phone = phone
        org.address = address

        org_id = org.id
        await self._orgs.add_member(org_id, user_id, OrgRole.CREATOR)
        try:
            await self._orgs.add_settings(org_id)
        except IntegrityError as error:
            raise InvalidState("Организация уже зарегистрирована") from error
        await self._events.record(
            EventType.ORG_REGISTERED,
            user_id=user_id,
            org_id=org_id,
            inn=org.inn,
        )
        return await self.card(org_id)

    async def card(self, org_id: OrgId) -> OrgCardView:
        org = await self._orgs.get_existing(org_id)
        houses = await self._houses.list_for_org(org_id)
        return OrgCardView(
            org=org,
            houses_count=len(houses),
            members_count=await self._orgs.count_members(org_id),
        )

    async def settings(self, org_id: OrgId) -> OrgSettingsView:
        org = await self._orgs.get_existing(org_id)
        settings = await self._orgs.get_settings(org_id)
        return OrgSettingsView(org=org, settings=settings or OrgSettings(org_id=org_id))

    async def update_settings(
        self,
        org_id: OrgId,
        meter_window_day_from: int,
        meter_window_day_to: int,
        meter_window_always_open: bool,
        group_threshold: int,
        group_window_hours: int,
        phone: str,
        reception_note: str | None,
        emergency_phone: str | None,
    ) -> OrgSettingsView:
        for day in (meter_window_day_from, meter_window_day_to):
            if not MIN_METER_WINDOW_DAY <= day <= MAX_METER_WINDOW_DAY:
                raise InvalidRequest(
                    f"День окна показаний - число от {MIN_METER_WINDOW_DAY} "
                    f"до {MAX_METER_WINDOW_DAY}",
                )
        if group_threshold < MIN_GROUP_THRESHOLD:
            raise InvalidRequest(
                f"Порог склейки заявок - не меньше {MIN_GROUP_THRESHOLD}",
            )
        if not MIN_GROUP_WINDOW_HOURS <= group_window_hours <= MAX_GROUP_WINDOW_HOURS:
            raise InvalidRequest(
                f"Окно склейки заявок - от {MIN_GROUP_WINDOW_HOURS} "
                f"до {MAX_GROUP_WINDOW_HOURS} часов",
            )

        org = await self._orgs.get_existing(org_id)
        settings = await self._orgs.get_settings(org_id)
        if settings is None:
            settings = await self._orgs.add_settings(org_id)

        settings.meter_window_day_from = meter_window_day_from
        settings.meter_window_day_to = meter_window_day_to
        settings.meter_window_always_open = meter_window_always_open
        settings.group_threshold = group_threshold
        settings.group_window_hours = group_window_hours
        org.phone = phone
        org.reception_note = reception_note
        org.emergency_phone = (emergency_phone or "").strip() or None
        return OrgSettingsView(org=org, settings=settings)

    async def members(self, org_id: OrgId) -> list[OrgMemberView]:
        members = await self._orgs.list_members(org_id)
        users = {
            user.id: user
            for user in await self._users.list_by_ids(
                [member.user_id for member in members],
            )
        }
        return [
            OrgMemberView(member=member, user=users[member.user_id])
            for member in members
        ]

    async def remove_member(
        self,
        org_id: OrgId,
        actor_role: OrgRole,
        user_id: UserId,
    ) -> None:
        member = await self._orgs.get_member(org_id, user_id)
        if member is None:
            raise EntityNotFound("Сотрудник не найден")
        if not actor_role.can_remove_member(member.role):
            raise NotEnoughRights("Этого сотрудника исключить нельзя")
        await self._orgs.remove_member(member)

    async def invites(self, org_id: OrgId) -> list[OrgInvite]:
        return list(await self._invites.list_for_org(org_id))

    async def create_invite(
        self,
        org_id: OrgId,
        user_id: UserId,
        actor_role: OrgRole,
        role: OrgRole,
        expires_in_hours: int,
        max_activations: int,
    ) -> OrgInvite:
        if not actor_role.can_invite(role):
            raise NotEnoughRights("Эту роль выдать нельзя")
        if expires_in_hours <= 0:
            raise InvalidRequest("Срок жизни кода - больше нуля часов")
        if max_activations <= 0:
            raise InvalidRequest("Число активаций - больше нуля")

        expires_at = datetime.now(UTC) + timedelta(hours=expires_in_hours)
        invite = await issue_invite(
            lambda code: self._invites.create(
                code=code,
                org_id=org_id,
                role=role,
                expires_at=expires_at,
                max_activations=max_activations,
                created_by=user_id,
            ),
        )
        await self._events.record(
            EventType.STAFF_INVITED,
            user_id=user_id,
            org_id=org_id,
            role=role.value,
        )
        return invite

    async def revoke_invite(self, org_id: OrgId, code: str) -> None:
        invite = await self._invites.get(code)
        if invite is None or invite.org_id != org_id:
            raise EntityNotFound(INVITE_NOT_FOUND)
        await self._invites.revoke(invite, datetime.now(UTC))

    async def activate_invite(self, user_id: UserId, code: str) -> OrgMembershipView:
        invite = await self._invites.get(code)
        if invite is None:
            raise EntityNotFound(INVITE_NOT_FOUND)

        org_id = invite.org_id
        org = await self._orgs.get_existing(org_id)

        member = await self._orgs.get_member(org_id, user_id)
        if member is not None:
            if invite.revoked_at is not None or invite.expires_at <= datetime.now(UTC):
                raise InvalidState("Код приглашения истек или отозван")
            role = member.role.higher_role(invite.role)
            if role is not member.role and await self._invites.consume(code) is None:
                raise InvalidState(INVITE_USED_UP)
            await self._orgs.set_member_role(member, role)
            return OrgMembershipView(member=member, org=org)

        consumed = await self._invites.consume(code)
        if consumed is None:
            raise InvalidState(INVITE_USED_UP)
        return OrgMembershipView(
            member=await self._orgs.add_member(org_id, user_id, consumed.role),
            org=org,
        )
