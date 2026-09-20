import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser

from zheka.api.schemas.polls import PollResults
from zheka.core.enums import OrgRole, PollStatus, ResidentRole, ResidentStatus
from zheka.core.errors import (
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    InvalidValue,
    NotEnoughRights,
)
from zheka.core.ids import (
    FlatId,
    HouseId,
    MaxUserId,
    OrgId,
    PollId,
    PollOptionId,
    UserId,
)
from zheka.core.services.events import EventsService
from zheka.core.services.polls import PollDraft, PollsService
from zheka.infra.database.models import Flat, OrgMember, Resident, User
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.polls import PollsRepo
from zheka.infra.database.repos.residents import ResidentsRepo

Fixture = Callable[..., Awaitable[OrgHouseFlatUser]]


def _make_service(session: AsyncSession) -> PollsService:
    return PollsService(
        PollsRepo(session),
        HousesRepo(session),
        ResidentsRepo(session),
        OrgsRepo(session),
        EventsService(EventsRepo(session)),
    )


def _future(days: int = 3) -> datetime:
    return datetime.now(UTC) + timedelta(days=days)


def _draft(
    *,
    title: str = "Ремонт подъезда",
    options: list[str] | None = None,
    ends_at: datetime | None = None,
    is_multiple: bool = False,
) -> PollDraft:
    return PollDraft(
        title=title,
        description=None,
        options=options or ["За", "Против"],
        ends_at=ends_at or _future(),
        is_multiple=is_multiple,
    )


async def _add_user(session: AsyncSession, name: str = "Сосед") -> UserId:
    user = User(max_user_id=MaxUserId(secrets.randbits(48)), name=name)
    session.add(user)
    await session.flush()
    return UserId(user.id)


async def _add_flat(
    session: AsyncSession,
    house_id: HouseId,
    number: str,
    *,
    entrance: int | None = None,
    area: int | None = None,
) -> FlatId:
    flat = Flat(house_id=house_id, number=number, entrance=entrance, area=area)
    session.add(flat)
    await session.flush()
    return FlatId(flat.id)


async def _add_resident(
    session: AsyncSession,
    user_id: UserId,
    house_id: HouseId,
    flat_id: FlatId | None,
    *,
    role: ResidentRole = ResidentRole.OWNER,
    verified: bool = True,
    status: ResidentStatus = ResidentStatus.ACTIVE,
    block_reason: str | None = None,
    is_chairman: bool = False,
) -> Resident:
    is_owner = role is ResidentRole.OWNER
    resident = Resident(
        user_id=user_id,
        house_id=house_id,
        flat_id=flat_id,
        role=role,
        can_see_charges=is_owner,
        can_vote=is_owner,
        verified_at=datetime.now(UTC) if verified else None,
        status=status,
        block_reason=block_reason,
        is_chairman=is_chairman,
    )
    session.add(resident)
    await session.flush()
    return resident


async def _add_org_member(
    session: AsyncSession,
    org_id: OrgId,
    user_id: UserId,
    role: OrgRole,
) -> OrgMember:
    member = OrgMember(org_id=org_id, user_id=user_id, role=role)
    session.add(member)
    await session.flush()
    return member


async def _chairman_setup(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> tuple[OrgHouseFlatUser, UserId]:
    base = await make_org_house_flat_user()
    chairman_id = await _add_user(session, "Председатель")
    await _add_resident(
        session,
        chairman_id,
        base.house_id,
        base.flat_id,
        is_chairman=True,
    )
    return base, chairman_id


# ---- создание опроса ----


async def test_create_org_poll_allows_org_staff(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    service = _make_service(session)

    card = await service.create(
        base.user_id,
        base.house_id,
        _draft(),
        org_id=base.org_id,
    )

    assert card.poll.created_by_role == "staff"
    assert card.poll.org_id == base.org_id
    assert card.poll.status is PollStatus.ACTIVE


async def test_create_poll_allows_the_house_chairman(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)

    card = await service.create(
        chairman_id,
        base.house_id,
        _draft(),
        org_id=None,
    )

    assert card.poll.created_by_role == "chairman"
    assert card.poll.org_id is None


async def test_create_poll_refuses_a_plain_resident(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base = await make_org_house_flat_user()
    resident_id = await _add_user(session, "Просто житель")
    await _add_resident(session, resident_id, base.house_id, base.flat_id)
    service = _make_service(session)

    with pytest.raises(NotEnoughRights):
        await service.create(resident_id, base.house_id, _draft(), org_id=None)


async def test_create_poll_refuses_an_end_date_in_the_past(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    past = datetime.now(UTC) - timedelta(days=1)

    with pytest.raises(InvalidValue):
        await service.create(
            chairman_id,
            base.house_id,
            _draft(ends_at=past),
            org_id=None,
        )


async def test_create_poll_requires_two_distinct_non_empty_options(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)

    with pytest.raises(InvalidRequest):
        await service.create(
            chairman_id,
            base.house_id,
            _draft(options=["Один вариант"]),
            org_id=None,
        )

    with pytest.raises(InvalidRequest):
        await service.create(
            chairman_id,
            base.house_id,
            _draft(options=["Да", "Да", ""]),
            org_id=None,
        )


async def test_create_org_poll_refuses_a_foreign_house(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    other = await make_org_house_flat_user()
    service = _make_service(session)

    with pytest.raises(EntityNotFound):
        await service.create(
            base.user_id,
            other.house_id,
            _draft(),
            org_id=base.org_id,
        )


# ---- голосование ----


async def test_vote_refuses_a_tenant(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    tenant_id = await _add_user(session, "Арендатор")
    await _add_resident(
        session,
        tenant_id,
        base.house_id,
        base.flat_id,
        role=ResidentRole.TENANT,
    )

    with pytest.raises(NotEnoughRights):
        await service.vote(
            PollId(card.poll.id),
            tenant_id,
            [PollOptionId(card.options[0].id)],
        )


async def test_vote_refuses_a_blocked_resident(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    blocked_id = await _add_user(session, "Заблокирован")
    await _add_resident(
        session,
        blocked_id,
        base.house_id,
        base.flat_id,
        status=ResidentStatus.BLOCKED,
        block_reason="долг",
    )

    with pytest.raises(NotEnoughRights):
        await service.vote(
            PollId(card.poll.id),
            blocked_id,
            [PollOptionId(card.options[0].id)],
        )


async def test_vote_refuses_after_the_poll_has_ended(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    # опрос заведен напрямую через репозиторий, минуя проверку "в будущем"
    # сервиса - тест бьет именно по границе окончания голосования
    polls_repo = PollsRepo(session)
    past = datetime.now(UTC) - timedelta(hours=1)
    poll = await polls_repo.create(
        base.house_id,
        None,
        chairman_id,
        "chairman",
        "Опрос",
        None,
        False,
        past - timedelta(days=1),
        past,
        ["За", "Против"],
    )
    options = await polls_repo.list_options(PollId(poll.id))

    with pytest.raises(InvalidState):
        await service.vote(
            PollId(poll.id),
            chairman_id,
            [PollOptionId(options[0].id)],
        )


async def test_vote_twice_raises_invalid_state(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    await service.vote(
        PollId(card.poll.id),
        chairman_id,
        [PollOptionId(card.options[0].id)],
    )

    with pytest.raises(InvalidState):
        await service.vote(
            PollId(card.poll.id),
            chairman_id,
            [PollOptionId(card.options[1].id)],
        )


async def test_multiple_choice_vote_stores_one_row_per_option(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(
        chairman_id,
        base.house_id,
        _draft(options=["Свет", "Вода", "Лифт"], is_multiple=True),
        org_id=None,
    )
    chosen = [PollOptionId(card.options[0].id), PollOptionId(card.options[2].id)]

    await service.vote(PollId(card.poll.id), chairman_id, chosen)

    polls_repo = PollsRepo(session)
    rows = await polls_repo.get_vote(PollId(card.poll.id), chairman_id)
    assert {row.option_id for row in rows} == set(chosen)
    assert len(rows) == 2

    with pytest.raises(InvalidState):
        await service.vote(PollId(card.poll.id), chairman_id, chosen)


async def test_single_choice_poll_refuses_more_than_one_option(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    with pytest.raises(InvalidRequest):
        await service.vote(
            PollId(card.poll.id),
            chairman_id,
            [PollOptionId(card.options[0].id), PollOptionId(card.options[1].id)],
        )


async def test_vote_with_an_empty_option_list_raises_invalid_request(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    with pytest.raises(InvalidRequest):
        await service.vote(PollId(card.poll.id), chairman_id, [])


async def test_vote_with_an_option_from_another_poll_raises_invalid_request(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)
    other_card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    with pytest.raises(InvalidRequest):
        await service.vote(
            PollId(card.poll.id),
            chairman_id,
            [PollOptionId(other_card.options[0].id)],
        )


async def test_vote_of_a_house_the_user_does_not_live_in_is_not_found(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    stranger_id = await _add_user(session, "Чужак")

    with pytest.raises(EntityNotFound):
        await service.vote(
            PollId(card.poll.id),
            stranger_id,
            [PollOptionId(card.options[0].id)],
        )


# ---- вес голоса по площади ----


async def test_counted_by_area_is_false_for_the_second_resident_of_one_flat(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    second_id = await _add_user(session, "Второй собственник")
    await _add_resident(session, second_id, base.house_id, base.flat_id)

    await service.vote(
        PollId(card.poll.id),
        chairman_id,
        [PollOptionId(card.options[0].id)],
    )
    await service.vote(
        PollId(card.poll.id),
        second_id,
        [PollOptionId(card.options[0].id)],
    )

    polls_repo = PollsRepo(session)
    first_vote = (await polls_repo.get_vote(PollId(card.poll.id), chairman_id))[0]
    second_vote = (await polls_repo.get_vote(PollId(card.poll.id), second_id))[0]
    assert first_vote.counted_by_area is True
    assert second_vote.counted_by_area is False

    results = await service.results(PollId(card.poll.id), chairman_id)
    # одна квартира - один голос в площади, несмотря на двух проголосовавших
    assert results.forecast.voted_flats == 1


async def test_unverified_resident_votes_but_lands_in_unverified_flats(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    unverified_id = await _add_user(session, "Не подтвержден")
    await _add_resident(
        session,
        unverified_id,
        base.house_id,
        base.flat_id,
        verified=False,
    )

    await service.vote(
        PollId(card.poll.id),
        unverified_id,
        [PollOptionId(card.options[0].id)],
    )

    results = await service.results(PollId(card.poll.id), chairman_id)
    assert results.forecast.unweighted_votes == 1


# ---- результаты и приватность ----


async def test_results_payload_carries_no_per_user_data(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)
    await service.vote(
        PollId(card.poll.id),
        chairman_id,
        [PollOptionId(card.options[0].id)],
    )

    results = await service.results(PollId(card.poll.id), chairman_id)
    payload = PollResults.of(results).model_dump()

    forbidden_keys = {
        "user_id",
        "resident_id",
        "created_by_user_id",
        "name",
        "voter",
        "voters",
    }

    def _collect_keys(value: object) -> set[str]:
        keys: set[str] = set()
        if isinstance(value, dict):
            for key, nested in value.items():
                keys.add(str(key))
                keys |= _collect_keys(nested)
        elif isinstance(value, list):
            for item in value:
                keys |= _collect_keys(item)
        return keys

    assert not (_collect_keys(payload) & forbidden_keys)


async def test_flats_without_area_are_reported_and_excluded_from_sums(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    # base.flat_id по умолчанию заведена без area (см. conftest)
    await _add_flat(session, base.house_id, "2", area=5000)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    results = await service.results(PollId(card.poll.id), chairman_id)

    assert results.flats_without_area == 1
    assert results.forecast.total_area == 5000


# ---- непроголосовавшие ----


async def test_non_voters_available_only_to_the_initiator(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    stranger_id = await _add_user(session, "Не организатор")
    await _add_resident(session, stranger_id, base.house_id, base.flat_id)

    with pytest.raises(NotEnoughRights):
        await service.non_voters(PollId(card.poll.id), stranger_id)

    non_voters = await service.non_voters(PollId(card.poll.id), chairman_id)
    assert any(flat.id == base.flat_id for flat in non_voters)


async def test_non_voters_available_to_org_staff_for_org_polls(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    service = _make_service(session)
    card = await service.create(
        base.user_id,
        base.house_id,
        _draft(),
        org_id=base.org_id,
    )

    other_staff_id = await _add_user(session, "Другой сотрудник")
    await _add_org_member(session, base.org_id, other_staff_id, OrgRole.EMPLOYEE)

    non_voters = await service.non_voters(PollId(card.poll.id), other_staff_id)
    assert any(flat.id == base.flat_id for flat in non_voters)


async def test_non_voters_excludes_a_flat_after_a_weighted_vote(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    await service.vote(
        PollId(card.poll.id),
        chairman_id,
        [PollOptionId(card.options[0].id)],
    )

    non_voters = await service.non_voters(PollId(card.poll.id), chairman_id)
    assert all(flat.id != base.flat_id for flat in non_voters)


# ---- закрытие опроса ----


async def test_close_poll_is_only_for_the_initiator_or_org_staff(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    stranger_id = await _add_user(session, "Не организатор")
    await _add_resident(session, stranger_id, base.house_id, base.flat_id)
    with pytest.raises(NotEnoughRights):
        await service.close(PollId(card.poll.id), stranger_id)

    closed = await service.close(PollId(card.poll.id), chairman_id)
    assert closed.status is PollStatus.CLOSED
    assert closed.poll.status is PollStatus.CLOSED


async def test_voting_is_refused_once_the_poll_is_closed(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)
    await service.close(PollId(card.poll.id), chairman_id)

    with pytest.raises(InvalidState):
        await service.vote(
            PollId(card.poll.id),
            chairman_id,
            [PollOptionId(card.options[0].id)],
        )


# ---- списки опросов ----


async def test_list_polls_puts_active_before_closed_and_newest_first(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    older_active = await service.create(
        chairman_id,
        base.house_id,
        _draft(title="Старый активный"),
        org_id=None,
    )
    closed = await service.create(
        chairman_id,
        base.house_id,
        _draft(title="Закрытый"),
        org_id=None,
    )
    await service.close(PollId(closed.poll.id), chairman_id)
    newer_active = await service.create(
        chairman_id,
        base.house_id,
        _draft(title="Новый активный"),
        org_id=None,
    )

    items = await service.list_polls(base.house_id, chairman_id, None)
    ids = [item.poll.id for item in items]

    assert ids.index(newer_active.poll.id) < ids.index(older_active.poll.id)
    assert ids.index(older_active.poll.id) < ids.index(closed.poll.id)


async def test_list_polls_filters_by_effective_status(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    active = await service.create(chairman_id, base.house_id, _draft(), org_id=None)
    closed = await service.create(chairman_id, base.house_id, _draft(), org_id=None)
    await service.close(PollId(closed.poll.id), chairman_id)

    active_items = await service.list_polls(
        base.house_id,
        chairman_id,
        PollStatus.ACTIVE,
    )
    closed_items = await service.list_polls(
        base.house_id,
        chairman_id,
        PollStatus.CLOSED,
    )

    assert {item.poll.id for item in active_items} == {active.poll.id}
    assert {item.poll.id for item in closed_items} == {closed.poll.id}


async def test_list_org_polls_scoped_by_org_with_a_foreign_house_404(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    own = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    foreign = await make_org_house_flat_user()
    service = _make_service(session)

    with pytest.raises(EntityNotFound):
        await service.list_org_polls(
            own.org_id,
            own.user_id,
            foreign.house_id,
            None,
            20,
            0,
        )


async def test_list_org_polls_only_shows_this_orgs_own_polls(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
) -> None:
    base = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    service = _make_service(session)
    org_card = await service.create(
        base.user_id,
        base.house_id,
        _draft(),
        org_id=base.org_id,
    )

    chairman_id = await _add_user(session, "Председатель")
    await _add_resident(
        session,
        chairman_id,
        base.house_id,
        base.flat_id,
        is_chairman=True,
    )
    chairman_card = await service.create(
        chairman_id,
        base.house_id,
        _draft(),
        org_id=None,
    )

    items, total = await service.list_org_polls(
        base.org_id,
        base.user_id,
        None,
        None,
        20,
        0,
    )

    ids = {item.item.poll.id for item in items}
    assert org_card.poll.id in ids
    assert chairman_card.poll.id not in ids
    assert total == len(items)
