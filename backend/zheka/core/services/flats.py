from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from zheka.base import ZhekaType
from zheka.core import texts
from zheka.core.enums import (
    EventType,
    NotificationCategory,
    ResidentRole,
    VerificationStatus,
)
from zheka.core.errors import (
    FLAT_NOT_FOUND,
    INVITE_NOT_FOUND,
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    NotEnoughRights,
)
from zheka.core.ids import FlatId, HouseId, OrgId, UserId, VerificationRequestId
from zheka.core.models import (
    Flat,
    FlatInvite,
    House,
    Resident,
    User,
    VerificationRequest,
)
from zheka.core.services.events import EventsService
from zheka.core.services.houses import NOT_CONNECTED, ResidencyView, is_connected
from zheka.core.services.invites import issue_invite
from zheka.core.services.notifications import NotificationsService
from zheka.infra.database.repos.flats import FlatsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.invites import InvitesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo

ACCOUNT_TAIL = 4

ALREADY_VERIFIED_DETAIL = "Квартира уже подтверждена"
MISMATCH_DETAIL = (
    "Лицевой счет не совпал. Отправьте запрос на подтверждение в управляющую компанию"
)
NO_ACCOUNT_DETAIL = (
    "По этой квартире нет лицевого счета. "
    "Отправьте запрос на подтверждение в управляющую компанию"
)
MOVED_OUT = "Житель привязан к другой квартире, переезд оформляет УК"
NOT_A_RESIDENT = "Вы не житель этой квартиры"


def normalize_account(account_no: str) -> str:
    return "".join(account_no.split()).casefold()


class FlatCardData(ZhekaType):
    flat: Flat
    house: House
    resident: Resident
    meters_count: int
    residents_count: int
    verification_status: VerificationStatus | None


class VerifyResult(ZhekaType):
    verified: bool
    detail: str
    verification_status: VerificationStatus | None


class VerificationRequestView(ZhekaType):
    request: VerificationRequest
    flat: Flat
    house: House
    user: User


class FlatResidentView(ZhekaType):
    resident: Resident
    user: User


class FlatsService:
    __slots__ = (
        "_events",
        "_flats",
        "_houses",
        "_invites",
        "_notifications",
        "_orgs",
        "_residents",
        "_users",
    )

    def __init__(
        self,
        flats_repo: FlatsRepo,
        houses_repo: HousesRepo,
        residents_repo: ResidentsRepo,
        invites_repo: InvitesRepo,
        users_repo: UsersRepo,
        orgs_repo: OrgsRepo,
        notifications_service: NotificationsService,
        events_service: EventsService,
    ) -> None:
        self._flats = flats_repo
        self._houses = houses_repo
        self._residents = residents_repo
        self._invites = invites_repo
        self._users = users_repo
        self._orgs = orgs_repo
        self._notifications = notifications_service
        self._events = events_service

    async def flat_card(self, user_id: UserId, flat_id: FlatId) -> FlatCardData:
        flat, house = await self._flat_and_house(flat_id)
        resident = await self._resident_of_flat(user_id, flat)
        latest = await self._flats.get_latest_request(user_id, flat_id)
        return FlatCardData(
            flat=flat,
            house=house,
            resident=resident,
            meters_count=await self._flats.count_meters(flat_id),
            residents_count=len(await self._residents.list_for_flat(flat_id)),
            verification_status=None if latest is None else latest.status,
        )

    async def verify(
        self, user_id: UserId, flat_id: FlatId, account_no: str
    ) -> VerifyResult:
        flat, _ = await self._flat_and_house(flat_id)
        resident = await self._resident_of_house(user_id, flat.house_id)
        if resident.role is ResidentRole.TENANT:
            raise NotEnoughRights("Квартиру подтверждает собственник, а не арендатор")
        self._ensure_not_moving(resident, flat_id)

        if resident.verified_at is not None:
            return VerifyResult(
                verified=True, detail=ALREADY_VERIFIED_DETAIL, verification_status=None
            )

        matched = flat.account_no is not None and normalize_account(
            flat.account_no
        ) == normalize_account(account_no)
        if matched:
            await self._residents.set_verified(
                resident, flat_id, datetime.now(UTC), None
            )
        await self._events.record(
            EventType.FLAT_VERIFICATION_REQUESTED,
            user_id=user_id,
            flat_id=flat_id,
            method="account",
            matched=matched,
        )
        if not matched:
            latest = await self._flats.get_latest_request(user_id, flat_id)
            return VerifyResult(
                verified=False,
                detail=(
                    NO_ACCOUNT_DETAIL if flat.account_no is None else MISMATCH_DETAIL
                ),
                verification_status=None if latest is None else latest.status,
            )

        await self._events.record(
            EventType.FLAT_VERIFIED, user_id=user_id, flat_id=flat_id, by="account"
        )
        return VerifyResult(
            verified=True, detail="Квартира подтверждена", verification_status=None
        )

    async def request_verification(
        self, user_id: UserId, flat_id: FlatId, account_no: str, comment: str | None
    ) -> VerificationRequestView:
        stated = account_no.strip()
        if not stated:
            raise InvalidRequest("Укажите лицевой счет")

        flat, house = await self._flat_and_house(flat_id)
        resident = await self._resident_of_house(user_id, flat.house_id)
        self._ensure_not_moving(resident, flat_id)
        if resident.verified_at is not None:
            raise InvalidState(ALREADY_VERIFIED_DETAIL)
        org = None if house.org_id is None else await self._orgs.get(house.org_id)
        if not is_connected(house, org):
            raise InvalidState(NOT_CONNECTED)

        request = await self._flats.add_verification_request(
            flat_id,
            user_id,
            stated,
            None if comment is None or not comment.strip() else comment.strip(),
        )
        if request is None:
            raise InvalidState("Заявка на подтверждение уже отправлена")
        await self._events.record(
            EventType.FLAT_VERIFICATION_REQUESTED,
            user_id=user_id,
            flat_id=flat_id,
            method="admin",
        )
        return await self._view(request, flat, house)

    async def verification_requests(
        self,
        org_id: OrgId,
        status: VerificationStatus | None,
        house_id: HouseId | None,
        limit: int,
        offset: int,
    ) -> tuple[list[VerificationRequestView], int]:
        requests, total = await self._flats.list_verification_requests(
            org_id, status, house_id, limit, offset
        )
        return await self._request_views(requests), total

    async def approve_verification(
        self, org_id: OrgId, verification_id: VerificationRequestId, by: UserId
    ) -> VerificationRequestView:
        request, flat, house = await self._pending_request(org_id, verification_id)
        resident = await self._residents.get_for_house(request.user_id, flat.house_id)
        if resident is None:
            raise EntityNotFound("Житель не найден")
        flat_id = flat.id
        self._ensure_not_moving(resident, flat_id)

        now = datetime.now(UTC)
        await self._residents.set_verified(resident, flat_id, now, by)
        await self._flats.decide_verification_request(
            request, VerificationStatus.APPROVED, by, now, None
        )
        await self._events.record(
            EventType.FLAT_VERIFIED,
            user_id=request.user_id,
            flat_id=flat_id,
            by="admin",
            decided_by=by,
        )
        self._notify(request.user_id, texts.flat_verified(flat.number, house.address))
        return await self._view(request, flat, house)

    async def reject_verification(
        self,
        org_id: OrgId,
        verification_id: VerificationRequestId,
        by: UserId,
        reason: str,
    ) -> VerificationRequestView:
        stated = reason.strip()
        if not stated:
            raise InvalidRequest("Укажите причину отказа")

        request, flat, house = await self._pending_request(org_id, verification_id)
        await self._flats.decide_verification_request(
            request, VerificationStatus.REJECTED, by, datetime.now(UTC), stated
        )
        self._notify(
            request.user_id,
            texts.flat_verification_rejected(flat.number, house.address, stated),
        )
        return await self._view(request, flat, house)

    async def list_residents(
        self, user_id: UserId, flat_id: FlatId
    ) -> list[FlatResidentView]:
        flat, _ = await self._flat_and_house(flat_id)
        await self._resident_of_flat(user_id, flat)
        residents = await self._residents.list_for_flat(flat_id)
        users = {
            user.id: user
            for user in await self._users.list_by_ids(
                [resident.user_id for resident in residents]
            )
        }
        return [
            FlatResidentView(resident=resident, user=users[resident.user_id])
            for resident in residents
        ]

    async def list_invites(self, user_id: UserId, flat_id: FlatId) -> list[FlatInvite]:
        flat, _ = await self._flat_and_house(flat_id)
        await self._resident_of_flat(user_id, flat)
        return list(await self._invites.list_for_flat(flat_id))

    async def create_invite(
        self,
        user_id: UserId,
        flat_id: FlatId,
        expires_in_hours: int,
        max_activations: int,
    ) -> FlatInvite:
        if expires_in_hours <= 0:
            raise InvalidRequest("Срок жизни кода - больше нуля часов")
        if max_activations <= 0:
            raise InvalidRequest("Число активаций - больше нуля")

        await self._verified_owner(user_id, flat_id)
        expires_at = datetime.now(UTC) + timedelta(hours=expires_in_hours)
        invite = await issue_invite(
            lambda code: self._invites.create_flat(
                code=code,
                flat_id=flat_id,
                expires_at=expires_at,
                max_activations=max_activations,
                created_by=user_id,
            )
        )
        await self._events.record(
            EventType.FLAT_INVITE_CREATED,
            user_id=user_id,
            flat_id=flat_id,
            max_activations=max_activations,
        )
        return invite

    async def revoke_invite(self, user_id: UserId, code: str) -> None:
        invite = await self._invites.get_flat(code)
        if invite is None:
            raise EntityNotFound(INVITE_NOT_FOUND)
        try:
            await self._verified_owner(user_id, invite.flat_id)
        except NotEnoughRights as error:
            raise EntityNotFound(INVITE_NOT_FOUND) from error
        await self._invites.revoke_flat(invite, datetime.now(UTC))

    async def activate_invite(self, user_id: UserId, code: str) -> ResidencyView:
        invite = await self._invites.get_flat(code)
        if invite is None:
            raise EntityNotFound(INVITE_NOT_FOUND)

        flat_id = invite.flat_id
        flat, house = await self._flat_and_house(flat_id)
        house_id = flat.house_id
        existing = await self._residents.get_for_house(user_id, house_id)
        if existing is not None and existing.flat_id == flat_id:
            if invite.revoked_at is not None or invite.expires_at <= datetime.now(UTC):
                raise InvalidState("Код приглашения истек или отозван")
            return await self._residency_view(existing, house, flat)
        if existing is not None and existing.flat_id is not None:
            raise InvalidState(MOVED_OUT)

        consumed = await self._invites.consume_flat(code)
        if consumed is None:
            raise InvalidState("Код приглашения истек, отозван или исчерпан")

        resident, _ = await self._residents.add_or_get(
            user_id, house_id, flat_id, None, ResidentRole.TENANT
        )
        await self._residents.set_verified(
            resident, flat_id, datetime.now(UTC), invite.created_by
        )
        await self._events.record(
            EventType.FLAT_INVITE_ACTIVATED,
            user_id=user_id,
            flat_id=flat_id,
            invited_by=invite.created_by,
        )
        return await self._residency_view(resident, house, flat)

    def _ensure_not_moving(self, resident: Resident, flat_id: FlatId) -> None:
        if (
            resident.verified_at is not None
            and resident.flat_id is not None
            and resident.flat_id != flat_id
        ):
            raise InvalidState(MOVED_OUT)

    async def _flat_and_house(self, flat_id: FlatId) -> tuple[Flat, House]:
        flat = await self._houses.get_flat(flat_id)
        if flat is None:
            raise EntityNotFound(FLAT_NOT_FOUND)
        house = await self._houses.get(flat.house_id)
        if house is None:
            raise EntityNotFound("Дом не найден")
        return flat, house

    async def _resident_of_house(self, user_id: UserId, house_id: HouseId) -> Resident:
        resident = await self._residents.get_for_house(user_id, house_id)
        if resident is None:
            raise EntityNotFound(FLAT_NOT_FOUND)
        return resident

    async def _resident_of_flat(self, user_id: UserId, flat: Flat) -> Resident:
        resident = await self._resident_of_house(user_id, flat.house_id)
        if resident.flat_id != flat.id:
            raise NotEnoughRights(NOT_A_RESIDENT)
        return resident

    async def _verified_owner(self, user_id: UserId, flat_id: FlatId) -> Resident:
        flat, _ = await self._flat_and_house(flat_id)
        resident = await self._resident_of_flat(user_id, flat)
        if resident.role is not ResidentRole.OWNER:
            raise NotEnoughRights("Код приглашения выдает собственник, а не арендатор")
        if resident.verified_at is None:
            raise NotEnoughRights("Сначала подтвердите квартиру")
        return resident

    async def _pending_request(
        self, org_id: OrgId, verification_id: VerificationRequestId
    ) -> tuple[VerificationRequest, Flat, House]:
        request = await self._flats.get_verification_request(verification_id, org_id)
        if request is None:
            raise EntityNotFound("Запрос подтверждения не найден")
        if request.status is not VerificationStatus.PENDING:
            raise InvalidState("Запрос подтверждения уже рассмотрен")
        flat, house = await self._flat_and_house(request.flat_id)
        return request, flat, house

    async def _view(
        self, request: VerificationRequest, flat: Flat, house: House
    ) -> VerificationRequestView:
        user = await self._users.get_by_id(request.user_id)
        if user is None:
            raise EntityNotFound("Пользователь не найден")
        return VerificationRequestView(
            request=request, flat=flat, house=house, user=user
        )

    async def _residency_view(
        self, resident: Resident, house: House, flat: Flat
    ) -> ResidencyView:
        org = None if house.org_id is None else await self._orgs.get(house.org_id)
        return ResidencyView(
            resident=resident,
            house=house,
            flat=flat,
            is_connected=is_connected(house, org),
        )

    async def _request_views(
        self, requests: Sequence[VerificationRequest]
    ) -> list[VerificationRequestView]:
        flats = {
            flat.id: flat
            for flat in await self._houses.list_flats_by_ids(
                [request.flat_id for request in requests]
            )
        }
        houses = {
            house.id: house
            for house in await self._houses.list_by_ids(
                [flat.house_id for flat in flats.values()]
            )
        }
        users = {
            user.id: user
            for user in await self._users.list_by_ids(
                [request.user_id for request in requests]
            )
        }
        return [
            VerificationRequestView(
                request=request,
                flat=flats[request.flat_id],
                house=houses[flats[request.flat_id].house_id],
                user=users[request.user_id],
            )
            for request in requests
        ]

    def _notify(self, user_id: UserId, text: str) -> None:
        self._notifications.notify_user(
            user_id, text, category=NotificationCategory.REQUESTS, mandatory=True
        )
