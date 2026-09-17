import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError

from zheka.base import ZhekaType
from zheka.config import DeeplinksConfig
from zheka.core.enums import EventType, OrgRole
from zheka.core.errors import (
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    NotEnoughRights,
)
from zheka.core.ids import OrgId, UserId
from zheka.core.models import OrgInvite, OrgMember, OrgSettings, Organization, User
from zheka.core.services.access import can_invite, can_remove_member, higher_role
from zheka.core.services.events import EventsService
from zheka.core.services.houses import HouseFound, is_connected
from zheka.core.services.invites import issue_invite
from zheka.core.services.profile import OrgMembershipView
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.invites import InvitesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.users import UsersRepo

MIN_METER_WINDOW_DAY = 1
# 28-е число есть в любом месяце, включая февраль невисокосного года
MAX_METER_WINDOW_DAY = 28
MIN_GROUP_THRESHOLD = 2
MIN_GROUP_WINDOW_HOURS = 1
MAX_GROUP_WINDOW_HOURS = 168


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

        # ветки исчерпывают проверку выше, но mypy этого не знает
        org: Organization | None = None
        if inn is not None:
            org = await self._orgs.get_by_inn(inn)
        elif license_no is not None:
            org = await self._orgs.get_by_license(license_no)
        # это проба реестра, а не карточка: ненайденная УК отвечает флагом,
        # а не 404
        if org is None:
            return OrgLookupView(org=None, houses=[])

        houses = await self._houses.list_for_org(OrgId(org.id))
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
        # скрытый код проверяется до любого обращения к базе
        if not deeplink_code.isascii() or not secrets.compare_digest(
            deeplink_code,
            self._deeplinks.org_register,
        ):
            raise NotEnoughRights("Неверный код регистрации организации")

        org = await self._orgs.get_by_inn(inn)
        if org is None and license_no is not None:
            org = await self._orgs.get_by_license(license_no)
        # привязки дома к УК руками нет: организация берется из реестра
        if org is None:
            raise EntityNotFound("Организация не найдена в реестре")
        if org.registered_at is not None:
            raise InvalidState("Организация уже зарегистрирована")

        org.registered_at = datetime.now(UTC)
        # УК правит свои контакты в момент регистрации: в реестре они старые
        org.name = name
        org.phone = phone
        org.address = address

        org_id = OrgId(org.id)
        await self._orgs.add_member(org_id, user_id, OrgRole.CREATOR)
        try:
            await self._orgs.add_settings(org_id)
        except IntegrityError as error:
            # гонку двух регистраций одного ИНН разводит первичный ключ
            # org_settings: проигравший получает тот же ответ, что и опоздавший
            raise InvalidState("Организация уже зарегистрирована") from error
        await self._events.record(
            EventType.ORG_REGISTERED,
            user_id=user_id,
            org_id=org_id,
            inn=org.inn,
        )
        return await self.card(org_id)

    async def card(self, org_id: OrgId) -> OrgCardView:
        org = await self._get_org(org_id)
        houses = await self._houses.list_for_org(org_id)
        return OrgCardView(
            org=org,
            houses_count=len(houses),
            members_count=await self._orgs.count_members(org_id),
        )

    async def settings(self, org_id: OrgId) -> OrgSettingsView:
        org = await self._get_org(org_id)
        settings = await self._orgs.get_settings(org_id)
        return OrgSettingsView(
            org=org,
            # у организации из реестра строки настроек еще нет: экран
            # показывает значения по умолчанию, а не падает
            settings=settings or OrgSettings(org_id=org_id),
        )

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

        org = await self._get_org(org_id)
        settings = await self._orgs.get_settings(org_id)
        if settings is None:
            settings = await self._orgs.add_settings(org_id)

        # окно показаний хранит дни и при поднятом флаге: флаг снимут, и дни
        # снова заработают
        settings.meter_window_day_from = meter_window_day_from
        settings.meter_window_day_to = meter_window_day_to
        settings.meter_window_always_open = meter_window_always_open
        settings.group_threshold = group_threshold
        settings.group_window_hours = group_window_hours
        # телефон и заметка о приеме живут в organizations, а не в настройках
        org.phone = phone
        org.reception_note = reception_note
        return OrgSettingsView(org=org, settings=settings)

    async def members(self, org_id: OrgId) -> list[OrgMemberView]:
        members = await self._orgs.list_members(org_id)
        users = {
            user.id: user
            for user in await self._users.list_by_ids(
                [UserId(member.user_id) for member in members],
            )
        }
        return [
            OrgMemberView(member=member, user=users[member.user_id])
            for member in members
            if member.user_id in users
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
        if not can_remove_member(actor_role, member.role):
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
        if not can_invite(actor_role, role):
            raise NotEnoughRights("Эту роль выдать нельзя")
        # нулевой срок жизни выдал бы код, мертвый в момент создания
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
            raise EntityNotFound("Приглашение не найдено")
        await self._invites.revoke(invite, datetime.now(UTC))

    async def activate_invite(self, user_id: UserId, code: str) -> OrgMembershipView:
        invite = await self._invites.get(code)
        if invite is None:
            raise EntityNotFound("Приглашение не найдено")

        org_id = OrgId(invite.org_id)
        org = await self._get_org(org_id)

        # членство проверяется до списания: повышение роли уже нанятого
        # сотрудника не должно съедать активацию
        member = await self._orgs.get_member(org_id, user_id)
        if member is not None:
            self._ensure_alive(invite)
            await self._orgs.set_member_role(
                member,
                higher_role(member.role, invite.role),
            )
            return OrgMembershipView(member=member, org=org)

        consumed = await self._invites.consume(code)
        if consumed is None:
            raise InvalidState("Код приглашения истек, отозван или исчерпан")
        return OrgMembershipView(
            member=await self._orgs.add_member(org_id, user_id, consumed.role),
            org=org,
        )

    def _ensure_alive(self, invite: OrgInvite) -> None:
        if invite.revoked_at is not None or invite.expires_at <= datetime.now(UTC):
            raise InvalidState("Код приглашения истек или отозван")

    async def _get_org(self, org_id: OrgId) -> Organization:
        org = await self._orgs.get(org_id)
        if org is None:
            raise EntityNotFound("Организация не найдена")
        return org
