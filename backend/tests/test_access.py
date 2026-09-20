import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser

from zheka.core.enums import EventType, ResidentRole, ResidentStatus
from zheka.core.errors import (
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    NotEnoughRights,
)
from zheka.core.ids import (
    AccessRequestId,
    AccessSlotId,
    FlatId,
    HouseId,
    MaxUserId,
    UserId,
)
from zheka.core.services.access import (
    AccessRequestDraft,
    AccessService,
    AccessSlotDraft,
)
from zheka.core.services.events import EventsService
from zheka.infra.database.models import Event, Flat, Resident, User
from zheka.infra.database.repos.access import AccessRepo
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.tables.events import events_table

Fixture = Callable[..., Awaitable[OrgHouseFlatUser]]


def _make_service(session: AsyncSession) -> AccessService:
    return AccessService(
        AccessRepo(session),
        HousesRepo(session),
        ResidentsRepo(session),
        EventsService(EventsRepo(session)),
    )


def _tomorrow() -> date:
    return datetime.now(UTC).date() + timedelta(days=1)


def _draft(
    house_id: HouseId,
    flat_ids: list[FlatId],
    *,
    reason: str = "Поверка газового оборудования",
    capacity: int = 1,
    slots: int = 2,
) -> AccessRequestDraft:
    day = _tomorrow()
    return AccessRequestDraft(
        house_id=house_id,
        reason=reason,
        date=day,
        flat_ids=flat_ids,
        slots=[
            AccessSlotDraft(
                starts_at=datetime.combine(day, datetime.min.time(), tzinfo=UTC)
                + timedelta(hours=10 + number),
                capacity=capacity,
            )
            for number in range(slots)
        ],
    )


async def _events(session: AsyncSession, type_: EventType) -> list[Event]:
    stmt = select(Event).where(events_table.c.type == type_)
    return list((await session.execute(stmt)).scalars().all())


async def _add_user(session: AsyncSession, name: str = "Сосед") -> UserId:
    user = User(max_user_id=MaxUserId(secrets.randbits(48)), name=name)
    session.add(user)
    await session.flush()
    return UserId(user.id)


async def _add_flat(
    session: AsyncSession,
    house_id: HouseId,
    number: str,
) -> FlatId:
    flat = Flat(house_id=house_id, number=number)
    session.add(flat)
    await session.flush()
    return FlatId(flat.id)


async def _add_resident(
    session: AsyncSession,
    user_id: UserId,
    house_id: HouseId,
    flat_id: FlatId,
    *,
    verified: bool = True,
    status: ResidentStatus = ResidentStatus.ACTIVE,
    block_reason: str | None = None,
) -> None:
    session.add(
        Resident(
            user_id=user_id,
            house_id=house_id,
            flat_id=flat_id,
            role=ResidentRole.OWNER,
            verified_at=datetime.now(UTC) if verified else None,
            status=status,
            block_reason=block_reason,
        ),
    )
    await session.flush()


async def _with_resident(
    session: AsyncSession,
    house_id: HouseId,
    number: str,
    *,
    verified: bool = True,
) -> tuple[FlatId, UserId]:
    flat_id = await _add_flat(session, house_id, number)
    user_id = await _add_user(session, f"Житель {number}")
    await _add_resident(session, user_id, house_id, flat_id, verified=verified)
    return flat_id, user_id


async def test_a_house_of_another_org_is_not_found(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    other = await make_org_house_flat_user()
    service = _make_service(session)

    with pytest.raises(EntityNotFound, match="Дом"):
        await service.create(
            fixture.org_id,
            fixture.user_id,
            _draft(other.house_id, [other.flat_id]),
        )

    with pytest.raises(EntityNotFound, match="Дом"):
        await service.list_for_org(fixture.org_id, other.house_id)

    # чужой дом не оставляет после себя ни запроса, ни ячеек
    assert await service.list_for_org(fixture.org_id, None) == []
    assert await service.list_for_org(other.org_id, None) == []


async def test_a_request_of_another_org_is_not_found(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    other = await make_org_house_flat_user()
    service = _make_service(session)
    flat_id, _ = await _with_resident(session, fixture.house_id, "12")
    grid = await service.create(
        fixture.org_id,
        fixture.user_id,
        _draft(fixture.house_id, [flat_id]),
    )

    with pytest.raises(EntityNotFound, match="Запрос доступа"):
        await service.grid(
            other.org_id,
            AccessRequestId(grid.request.request.id),
        )


async def test_a_flat_of_another_house_is_not_found(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    other = await make_org_house_flat_user()
    service = _make_service(session)

    with pytest.raises(EntityNotFound, match="Квартира"):
        await service.create(
            fixture.org_id,
            fixture.user_id,
            _draft(fixture.house_id, [other.flat_id]),
        )


async def test_a_flat_without_a_verified_resident_gets_no_target(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    with_resident, _ = await _with_resident(session, fixture.house_id, "12")
    unverified, _ = await _with_resident(
        session,
        fixture.house_id,
        "13",
        verified=False,
    )
    empty = await _add_flat(session, fixture.house_id, "14")

    grid = await service.create(
        fixture.org_id,
        fixture.user_id,
        _draft(fixture.house_id, [with_resident, unverified, empty]),
    )

    assert [cell.target.flat_id for cell in grid.targets] == [with_resident]
    assert list(grid.flats_without_residents) == [unverified, empty]
    assert grid.request.targets_count == 1
    assert grid.request.responded_count == 0

    events = await _events(session, EventType.ACCESS_REQUEST_SENT)

    assert len(events) == 1
    # в событии те квартиры, до которых дошли, а не те, что назвала УК
    assert events[0].payload["flats_count"] == 1


async def test_a_request_where_every_flat_is_skipped_is_not_an_error(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    empty = await _add_flat(session, fixture.house_id, "14")

    grid = await service.create(
        fixture.org_id,
        fixture.user_id,
        _draft(fixture.house_id, [empty]),
    )

    assert grid.targets == []
    assert list(grid.flats_without_residents) == [empty]
    assert len(grid.request.slots) == 2


@pytest.mark.parametrize(
    ("reason", "flats", "slots", "capacity"),
    [
        ("   ", 1, 2, 1),
        ("Поверка", 1, 0, 1),
        ("Поверка", 0, 2, 1),
        ("Поверка", 1, 2, 0),
    ],
)
async def test_a_broken_draft_is_rejected(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    reason: str,
    flats: int,
    slots: int,
    capacity: int,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    flat_ids = [fixture.flat_id] * flats

    with pytest.raises(InvalidRequest):
        await service.create(
            fixture.org_id,
            fixture.user_id,
            _draft(
                fixture.house_id,
                flat_ids,
                reason=reason,
                slots=slots,
                capacity=capacity,
            ),
        )


async def test_two_windows_at_the_same_moment_are_rejected(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    draft = _draft(fixture.house_id, [fixture.flat_id])
    at = draft.slots[0].starts_at

    with pytest.raises(InvalidRequest, match="одно и то же время"):
        await service.create(
            fixture.org_id,
            fixture.user_id,
            AccessRequestDraft(
                house_id=draft.house_id,
                reason=draft.reason,
                date=draft.date,
                flat_ids=draft.flat_ids,
                slots=[
                    AccessSlotDraft(starts_at=at, capacity=1),
                    AccessSlotDraft(starts_at=at, capacity=2),
                ],
            ),
        )


async def test_a_full_slot_rejects_the_next_pick(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    first_flat, first_user = await _with_resident(session, fixture.house_id, "12")
    second_flat, second_user = await _with_resident(session, fixture.house_id, "13")
    grid = await service.create(
        fixture.org_id,
        fixture.user_id,
        _draft(fixture.house_id, [first_flat, second_flat], capacity=1),
    )
    request_id = AccessRequestId(grid.request.request.id)
    slot_id = AccessSlotId(grid.request.slots[0].slot.id)

    await service.pick(first_user, request_id, slot_id)

    with pytest.raises(InvalidState, match="больше нет мест"):
        await service.pick(second_user, request_id, slot_id)

    # второе окно свободно, и туда житель проходит
    free = AccessSlotId(grid.request.slots[1].slot.id)
    picked = await service.pick(second_user, request_id, free)

    assert picked.my_slot_id == free


async def test_a_repeated_pick_does_not_double_the_counter(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    flat_id, user_id = await _with_resident(session, fixture.house_id, "12")
    grid = await service.create(
        fixture.org_id,
        fixture.user_id,
        _draft(fixture.house_id, [flat_id], capacity=2),
    )
    request_id = AccessRequestId(grid.request.request.id)
    first_slot = AccessSlotId(grid.request.slots[0].slot.id)
    second_slot = AccessSlotId(grid.request.slots[1].slot.id)

    await service.pick(user_id, request_id, first_slot)
    before = await service.grid(fixture.org_id, request_id)
    first_answer = before.targets[0].target.responded_at

    await service.pick(user_id, request_id, first_slot)
    moved = await service.pick(user_id, request_id, second_slot)
    after = await service.grid(fixture.org_id, request_id)

    assert after.request.responded_count == 1
    assert after.request.targets_count == 1
    assert moved.my_slot_id == second_slot
    # ответ остается первым: смена решения не новый ответ
    assert first_answer is not None
    assert after.targets[0].target.responded_at == first_answer
    assert [data.taken for data in after.request.slots] == [0, 1]


async def test_a_pick_of_a_stranger_or_of_another_request_is_not_found(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    flat_id, user_id = await _with_resident(session, fixture.house_id, "12")
    outsider_flat, outsider = await _with_resident(session, fixture.house_id, "13")
    grid = await service.create(
        fixture.org_id,
        fixture.user_id,
        _draft(fixture.house_id, [flat_id]),
    )
    request_id = AccessRequestId(grid.request.request.id)
    slot_id = AccessSlotId(grid.request.slots[0].slot.id)

    with pytest.raises(EntityNotFound, match="Запрос доступа"):
        await service.pick(outsider, request_id, slot_id)

    other_grid = await service.create(
        fixture.org_id,
        fixture.user_id,
        _draft(fixture.house_id, [outsider_flat]),
    )
    foreign_slot = AccessSlotId(other_grid.request.slots[0].slot.id)

    with pytest.raises(EntityNotFound, match="Слот"):
        await service.pick(user_id, request_id, foreign_slot)

    # в сетке первого запроса стоит только его собственная ячейка
    grid_again = await service.grid(fixture.org_id, request_id)

    assert [cell.target.flat_id for cell in grid_again.targets] == [flat_id]


async def test_an_unverified_resident_cannot_pick(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    flat_id, _ = await _with_resident(session, fixture.house_id, "12")
    guest = await _add_user(session, "Гость")
    await _add_resident(session, guest, fixture.house_id, flat_id, verified=False)
    grid = await service.create(
        fixture.org_id,
        fixture.user_id,
        _draft(fixture.house_id, [flat_id]),
    )

    with pytest.raises(EntityNotFound, match="Запрос доступа"):
        await service.pick(
            guest,
            AccessRequestId(grid.request.request.id),
            AccessSlotId(grid.request.slots[0].slot.id),
        )


async def test_the_resident_list_carries_the_flat_and_the_choice(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    flat_id, user_id = await _with_resident(session, fixture.house_id, "12")
    neighbour_flat, _ = await _with_resident(session, fixture.house_id, "13")
    grid = await service.create(
        fixture.org_id,
        fixture.user_id,
        _draft(fixture.house_id, [flat_id, neighbour_flat], capacity=2),
    )
    request_id = AccessRequestId(grid.request.request.id)
    slot_id = AccessSlotId(grid.request.slots[0].slot.id)
    await service.pick(user_id, request_id, slot_id)

    rows = await service.list_for_resident(flat_id)

    assert len(rows) == 1
    assert rows[0].my_flat_id == flat_id
    assert rows[0].my_slot_id == slot_id
    assert rows[0].responded_count == 1
    assert rows[0].targets_count == 2
    assert rows[0].address.endswith("Тестовая, 1")

    # соседу тот же запрос показывается без чужого выбора
    neighbour_rows = await service.list_for_resident(neighbour_flat)

    assert neighbour_rows[0].my_slot_id is None


async def test_a_request_of_another_house_stays_out_of_the_list(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    flat_id, _ = await _with_resident(session, fixture.house_id, "12")
    await service.create(
        fixture.org_id,
        fixture.user_id,
        _draft(fixture.house_id, [flat_id]),
    )

    other = await make_org_house_flat_user()

    assert await service.list_for_org(other.org_id, None) == []
    assert len(await service.list_for_org(fixture.org_id, None)) == 1


async def test_a_repeat_of_the_same_choice_is_a_no_op(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    # окно на одну квартиру: если повторный выбор пойдет мимо проверки
    # «то же самое окно», житель упрется в собственную занятую ячейку
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    flat_id, user_id = await _with_resident(session, fixture.house_id, "12")
    grid = await service.create(
        fixture.org_id,
        fixture.user_id,
        _draft(fixture.house_id, [flat_id], capacity=1),
    )
    request_id = AccessRequestId(grid.request.request.id)
    slot_id = AccessSlotId(grid.request.slots[0].slot.id)

    await service.pick(user_id, request_id, slot_id)
    again = await service.pick(user_id, request_id, slot_id)

    assert again.my_slot_id == slot_id
    assert again.responded_count == 1
    assert [data.taken for data in again.slots] == [1, 0]

    # повторный выбор не пишет ни ячейку, ни событие
    events = await _events(session, EventType.ACCESS_SLOT_PICKED)

    assert len(events) == 1
    assert events[0].payload["slot_id"] == slot_id


async def test_a_resident_blocked_after_the_request_is_refused_with_the_reason(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    # УК закрыла жителю дом уже после рассылки: чужой получает 404 и ничего
    # не узнает, а этот - 403 с причиной, которую ему уже назвали
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    flat_id, user_id = await _with_resident(session, fixture.house_id, "12")
    grid = await service.create(
        fixture.org_id,
        fixture.user_id,
        _draft(fixture.house_id, [flat_id]),
    )
    request_id = AccessRequestId(grid.request.request.id)

    resident = (await ResidentsRepo(session).list_for_flat(flat_id))[0]
    resident.status = ResidentStatus.BLOCKED
    resident.block_reason = "долг за отопление"
    await session.flush()

    with pytest.raises(NotEnoughRights, match="долг за отопление"):
        await service.pick(
            user_id,
            request_id,
            AccessSlotId(grid.request.slots[0].slot.id),
        )

    after = await service.grid(fixture.org_id, request_id)

    assert after.request.responded_count == 0
    assert after.targets[0].target.slot_id is None


async def test_a_flat_whose_only_resident_is_blocked_gets_no_target(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    # заблокированному жителю некому написать, и ответить он уже не сможет:
    # его квартира попадает в тот же список, что и квартира без жителей
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    good_flat, _ = await _with_resident(session, fixture.house_id, "12")
    blocked_flat = await _add_flat(session, fixture.house_id, "13")
    blocked_user = await _add_user(session, "Житель 13")
    await _add_resident(
        session,
        blocked_user,
        fixture.house_id,
        blocked_flat,
        status=ResidentStatus.BLOCKED,
        block_reason="долг",
    )

    grid = await service.create(
        fixture.org_id,
        fixture.user_id,
        _draft(fixture.house_id, [good_flat, blocked_flat]),
    )

    assert [cell.target.flat_id for cell in grid.targets] == [good_flat]
    assert list(grid.flats_without_residents) == [blocked_flat]
    assert grid.request.targets_count == 1


async def test_a_block_in_another_house_does_not_reach_this_request(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    # блокировка читается у той квартиры, по которой пришел запрос: житель,
    # закрытый в другом доме, отвечает здесь как ни в чем не бывало
    fixture = await make_org_house_flat_user()
    elsewhere = await make_org_house_flat_user()
    service = _make_service(session)
    flat_id, user_id = await _with_resident(session, fixture.house_id, "12")
    other_flat = await _add_flat(session, elsewhere.house_id, "99")
    await _add_resident(
        session,
        user_id,
        elsewhere.house_id,
        other_flat,
        status=ResidentStatus.BLOCKED,
        block_reason="долг",
    )
    grid = await service.create(
        fixture.org_id,
        fixture.user_id,
        _draft(fixture.house_id, [flat_id]),
    )
    request_id = AccessRequestId(grid.request.request.id)

    picked = await service.pick(
        user_id,
        request_id,
        AccessSlotId(grid.request.slots[0].slot.id),
    )

    assert picked.my_flat_id == flat_id

    # и тот же житель, не адресат чужого запроса, получает 404, а не отказ
    stranger_grid = await service.create(
        elsewhere.org_id,
        elsewhere.user_id,
        _draft(elsewhere.house_id, [other_flat]),
    )

    with pytest.raises(EntityNotFound, match="Запрос доступа"):
        await service.pick(
            user_id,
            AccessRequestId(stranger_grid.request.request.id),
            AccessSlotId(stranger_grid.request.slots[0].slot.id),
        )


async def test_a_request_for_today_is_accepted(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    # «приедем сегодня в 16:00» - обычный случай, а не прошедший день
    fixture = await make_org_house_flat_user()
    service = _make_service(session)
    flat_id, _ = await _with_resident(session, fixture.house_id, "12")
    today = datetime.now(UTC).date()

    grid = await service.create(
        fixture.org_id,
        fixture.user_id,
        AccessRequestDraft(
            house_id=fixture.house_id,
            reason="Поверка",
            date=today,
            flat_ids=[flat_id],
            slots=[
                AccessSlotDraft(
                    starts_at=datetime.combine(today, datetime.min.time(), tzinfo=UTC)
                    + timedelta(hours=16),
                    capacity=1,
                ),
            ],
        ),
    )

    assert grid.request.request.date == today
