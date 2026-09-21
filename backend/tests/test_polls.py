from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import OrgHouseFlatUser
from tests.test_requests import _add_user

from zheka.api.schemas.polls import PollResults
from zheka.core.enums import OrgRole, PollStatus, ResidentRole, ResidentStatus
from zheka.core.errors import (
    EntityNotFound,
    InvalidRequest,
    InvalidState,
    InvalidValue,
    NotEnoughRights,
)
from zheka.core.ids import FlatId, HouseId, UserId
from zheka.core.services.events import EventsService
from zheka.core.services.polls import PollDraft, PollsService
from zheka.infra.database.models import Flat, OrgMember, Resident
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


async def _chairman_setup(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    org_role: OrgRole | None = None,
) -> tuple[OrgHouseFlatUser, UserId]:
    base = await make_org_house_flat_user(org_role=org_role)
    chairman_id = await _add_user(session, "Председатель")
    await _add_resident(
        session, chairman_id, base.house_id, base.flat_id, is_chairman=True
    )
    return base, chairman_id


# ---- создание опроса ----


async def test_create_org_poll_allows_org_staff(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    base = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    service = _make_service(session)

    card = await service.create(
        base.user_id, base.house_id, _draft(), org_id=base.org_id
    )

    assert card.poll.created_by_role == "staff"
    assert card.poll.org_id == base.org_id
    assert card.poll.status is PollStatus.ACTIVE


async def test_create_poll_allows_the_house_chairman(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)

    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    assert card.poll.created_by_role == "chairman"
    assert card.poll.org_id is None


async def test_create_poll_refuses_a_plain_resident(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    base = await make_org_house_flat_user()
    resident_id = await _add_user(session, "Просто житель")
    await _add_resident(session, resident_id, base.house_id, base.flat_id)
    service = _make_service(session)

    with pytest.raises(NotEnoughRights):
        await service.create(resident_id, base.house_id, _draft(), org_id=None)


@pytest.mark.parametrize(
    ("draft", "error"),
    [
        (_draft(ends_at=datetime.now(UTC) - timedelta(days=1)), InvalidValue),
        (_draft(options=["Один вариант"]), InvalidRequest),
        (_draft(options=["Да", "Да", ""]), InvalidRequest),
    ],
)
async def test_create_poll_refuses_a_bad_draft(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    draft: PollDraft,
    error: type[Exception],
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)

    with pytest.raises(error):
        await _make_service(session).create(
            chairman_id, base.house_id, draft, org_id=None
        )


async def test_create_org_poll_refuses_a_foreign_house(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    base = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    other = await make_org_house_flat_user()
    service = _make_service(session)

    with pytest.raises(EntityNotFound):
        await service.create(base.user_id, other.house_id, _draft(), org_id=base.org_id)


# ---- голосование ----


@pytest.mark.parametrize(
    "resident",
    [
        {"role": ResidentRole.TENANT},
        {"status": ResidentStatus.BLOCKED, "block_reason": "долг"},
    ],
    ids=["tenant", "blocked"],
)
async def test_vote_refuses_a_tenant_and_a_blocked_resident(
    session: AsyncSession, make_org_house_flat_user: Fixture, resident: dict[str, Any]
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)
    voter_id = await _add_user(session)
    await _add_resident(session, voter_id, base.house_id, base.flat_id, **resident)

    with pytest.raises(NotEnoughRights):
        await service.vote(card.poll.id, voter_id, [card.options[0].id])


async def test_vote_refuses_after_the_poll_has_ended(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)
    # статус еще ACTIVE: срок истек, а close_expired_polls не успел
    card.poll.ends_at = datetime.now(UTC) - timedelta(hours=1)

    with pytest.raises(InvalidState):
        await service.vote(card.poll.id, chairman_id, [card.options[0].id])


async def test_vote_twice_raises_invalid_state(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    await service.vote(card.poll.id, chairman_id, [card.options[0].id])

    with pytest.raises(InvalidState):
        await service.vote(card.poll.id, chairman_id, [card.options[1].id])


async def test_multiple_choice_vote_stores_one_row_per_option(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(
        chairman_id,
        base.house_id,
        _draft(options=["Свет", "Вода", "Лифт"], is_multiple=True),
        org_id=None,
    )
    chosen = [card.options[0].id, card.options[2].id]

    results = await service.vote(card.poll.id, chairman_id, chosen)

    rows = await PollsRepo(session).get_vote(card.poll.id, chairman_id)
    assert {row.option_id for row in rows} == set(chosen)
    assert len(rows) == 2
    # две строки голоса - одна квартира в кворуме
    assert results.forecast.voted_flats == 1


async def test_vote_refuses_a_bad_option_choice(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)
    other_card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)
    own = [option.id for option in card.options]

    for choice in ([], own, [other_card.options[0].id]):
        with pytest.raises(InvalidRequest):
            await service.vote(card.poll.id, chairman_id, choice)


async def test_vote_of_a_house_the_user_does_not_live_in_is_not_found(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    stranger_id = await _add_user(session, "Чужак")

    with pytest.raises(EntityNotFound):
        await service.vote(card.poll.id, stranger_id, [card.options[0].id])


# ---- вес голоса по площади ----


async def test_counted_by_area_is_false_for_the_second_resident_of_one_flat(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    second_id = await _add_user(session, "Второй собственник")
    await _add_resident(session, second_id, base.house_id, base.flat_id)

    await service.vote(card.poll.id, chairman_id, [card.options[0].id])
    await service.vote(card.poll.id, second_id, [card.options[0].id])

    polls_repo = PollsRepo(session)
    first_vote = (await polls_repo.get_vote(card.poll.id, chairman_id))[0]
    second_vote = (await polls_repo.get_vote(card.poll.id, second_id))[0]
    assert first_vote.counted_by_area is True
    assert second_vote.counted_by_area is False

    results = await service.results(card.poll.id, chairman_id)
    # одна квартира - один голос в площади, несмотря на двух проголосовавших
    assert results.forecast.voted_flats == 1


async def test_unverified_resident_votes_but_lands_in_unverified_flats(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    unverified_id = await _add_user(session, "Не подтвержден")
    await _add_resident(
        session, unverified_id, base.house_id, base.flat_id, verified=False
    )

    await service.vote(card.poll.id, unverified_id, [card.options[0].id])

    results = await service.results(card.poll.id, chairman_id)
    assert results.forecast.unweighted_votes == 1


# ---- результаты и приватность ----


async def test_results_payload_carries_no_per_user_data(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)
    await service.vote(card.poll.id, chairman_id, [card.options[0].id])

    results = await service.results(card.poll.id, chairman_id)
    payload = PollResults.of(results).model_dump_json()

    forbidden_keys = (
        "user_id",
        "resident_id",
        "created_by_user_id",
        "name",
        "voter",
        "voters",
    )
    assert not [key for key in forbidden_keys if f'"{key}":' in payload]


async def test_flats_without_area_are_reported_and_excluded_from_sums(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    # base.flat_id заведена без area
    session.add(Flat(house_id=base.house_id, number="2", area=5000))
    await session.flush()
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    results = await service.results(card.poll.id, chairman_id)

    assert results.flats_without_area == 1
    assert results.forecast.total_area == 5000


# ---- непроголосовавшие ----


async def test_non_voters_available_only_to_the_initiator(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    stranger_id = await _add_user(session, "Не организатор")
    await _add_resident(session, stranger_id, base.house_id, base.flat_id)

    with pytest.raises(NotEnoughRights):
        await service.non_voters(card.poll.id, stranger_id)

    non_voters = await service.non_voters(card.poll.id, chairman_id)
    assert any(flat.id == base.flat_id for flat in non_voters)


async def test_non_voters_available_to_org_staff_for_org_polls(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    base = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    service = _make_service(session)
    card = await service.create(
        base.user_id, base.house_id, _draft(), org_id=base.org_id
    )

    other_staff_id = await _add_user(session, "Другой сотрудник")
    session.add(
        OrgMember(org_id=base.org_id, user_id=other_staff_id, role=OrgRole.EMPLOYEE)
    )
    await session.flush()

    non_voters = await service.non_voters(card.poll.id, other_staff_id)
    assert any(flat.id == base.flat_id for flat in non_voters)


async def test_non_voters_excludes_a_flat_after_a_weighted_vote(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    await service.vote(card.poll.id, chairman_id, [card.options[0].id])

    non_voters = await service.non_voters(card.poll.id, chairman_id)
    assert all(flat.id != base.flat_id for flat in non_voters)


# ---- закрытие опроса ----


async def test_close_poll_is_only_for_the_initiator_or_org_staff(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)

    stranger_id = await _add_user(session, "Не организатор")
    await _add_resident(session, stranger_id, base.house_id, base.flat_id)
    with pytest.raises(NotEnoughRights):
        await service.close(card.poll.id, stranger_id)

    closed = await service.close(card.poll.id, chairman_id)
    assert closed.status is PollStatus.CLOSED
    assert closed.poll.status is PollStatus.CLOSED


async def test_voting_is_refused_once_the_poll_is_closed(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    card = await service.create(chairman_id, base.house_id, _draft(), org_id=None)
    await service.close(card.poll.id, chairman_id)

    with pytest.raises(InvalidState):
        await service.vote(card.poll.id, chairman_id, [card.options[0].id])


# ---- списки опросов ----


async def test_list_polls_puts_active_before_closed_and_newest_first(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    older_active = await service.create(
        chairman_id, base.house_id, _draft(title="Старый активный"), org_id=None
    )
    closed = await service.create(
        chairman_id, base.house_id, _draft(title="Закрытый"), org_id=None
    )
    await service.close(closed.poll.id, chairman_id)
    newer_active = await service.create(
        chairman_id, base.house_id, _draft(title="Новый активный"), org_id=None
    )

    items = await service.list_polls(base.house_id, chairman_id, None)
    ids = [item.poll.id for item in items]

    assert ids.index(newer_active.poll.id) < ids.index(older_active.poll.id)
    assert ids.index(older_active.poll.id) < ids.index(closed.poll.id)


async def test_list_polls_filters_by_effective_status(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    base, chairman_id = await _chairman_setup(session, make_org_house_flat_user)
    service = _make_service(session)
    active = await service.create(chairman_id, base.house_id, _draft(), org_id=None)
    closed = await service.create(chairman_id, base.house_id, _draft(), org_id=None)
    await service.close(closed.poll.id, chairman_id)

    active_items = await service.list_polls(
        base.house_id, chairman_id, PollStatus.ACTIVE
    )
    closed_items = await service.list_polls(
        base.house_id, chairman_id, PollStatus.CLOSED
    )

    assert {item.poll.id for item in active_items} == {active.poll.id}
    assert {item.poll.id for item in closed_items} == {closed.poll.id}


async def test_list_org_polls_scoped_by_org_with_a_foreign_house_404(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    own = await make_org_house_flat_user(org_role=OrgRole.ADMIN)
    foreign = await make_org_house_flat_user()
    service = _make_service(session)

    with pytest.raises(EntityNotFound):
        await service.list_org_polls(
            own.org_id, own.user_id, foreign.house_id, None, 20, 0
        )


async def test_list_org_polls_only_shows_this_orgs_own_polls(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    base, chairman_id = await _chairman_setup(
        session, make_org_house_flat_user, OrgRole.ADMIN
    )
    service = _make_service(session)
    org_card = await service.create(
        base.user_id, base.house_id, _draft(), org_id=base.org_id
    )
    chairman_card = await service.create(
        chairman_id, base.house_id, _draft(), org_id=None
    )

    items, total = await service.list_org_polls(
        base.org_id, base.user_id, None, None, 20, 0
    )

    ids = {item.item.poll.id for item in items}
    assert org_card.poll.id in ids
    assert chairman_card.poll.id not in ids
    assert total == len(items)
