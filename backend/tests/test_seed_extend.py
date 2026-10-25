import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_seed import FILES, NOW, _counts, _demo, _positive_user

from zheka.core.enums import ResidentRole
from zheka.infra.database.models import Resident
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.tables.houses import houses_table
from zheka.infra.database.tables.organizations import org_members_table
from zheka.infra.database.tables.users import users_table
from zheka.seed import demo as demo_module
from zheka.seed.demo import ADDED_PROFILES, EXPO_PROFILE, Seeder, extend, seed


async def test_extending_without_a_seed_is_refused(session: AsyncSession) -> None:
    assert not await extend(session, _demo(session), FILES, NOW)
    assert (await _counts(session))["houses"] == 0


async def test_extending_an_older_seed_adds_orgs_around_real_residents(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(demo_module, "ADDED_PROFILES", ())
    assert await seed(session, _demo(session), FILES, NOW)
    stmt = select(houses_table.c.id, houses_table.c.org_id)
    houses = dict((await session.execute(stmt)).tuples().all())
    stmt = select(func.min(users_table.c.max_user_id))
    lowest = (await session.execute(stmt)).scalar_one()
    [profile, *_rest] = ADDED_PROFILES
    monkeypatch.setattr(demo_module, "ADDED_PROFILES", (profile,))

    trial = await session.begin_nested()
    assert await extend(session, _demo(session), FILES, NOW)
    org = await OrgsRepo(session).get_by_inn(profile.inn)
    assert org is not None
    [first, *_others] = await HousesRepo(session).list_for_org(org.id)
    claimed = first.id
    await trial.rollback()
    session.expire_all()
    session.add(
        Resident(
            user_id=await _positive_user(session),
            house_id=claimed,
            role=ResidentRole.OWNER,
        ),
    )
    await session.flush()

    assert await extend(session, _demo(session), FILES, NOW)

    org = await OrgsRepo(session).get_by_inn(profile.inn)
    assert org is not None
    taken = await HousesRepo(session).list_for_org(org.id)
    assert len(taken) == profile.houses
    assert claimed not in {house.id for house in taken}
    assert {house.city for house in taken} == {profile.city}
    stmt = select(houses_table.c.id, houses_table.c.org_id)
    after = dict((await session.execute(stmt)).tuples().all())
    assert after.keys() == houses.keys()
    assert {house_id: after[house_id] for house_id in houses} == houses | {
        house.id: org.id for house in taken
    }
    stmt = (
        select(func.count())
        .select_from(org_members_table)
        .join(users_table, users_table.c.id == org_members_table.c.user_id)
        .where(
            org_members_table.c.org_id == org.id,
            users_table.c.max_user_id >= lowest,
        )
    )
    assert (await session.execute(stmt)).scalar_one() == 0


async def test_extending_an_older_seed_adds_the_expo_org_once(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with monkeypatch.context() as patch:
        patch.setattr(Seeder, "expo", _skip)
        assert await seed(session, _demo(session), FILES, NOW)
    stmt = select(houses_table.c.id, houses_table.c.org_id)
    houses = dict((await session.execute(stmt)).tuples().all())
    assert await OrgsRepo(session).get_by_inn(EXPO_PROFILE.inn) is None

    assert await extend(session, _demo(session), FILES, NOW)

    org = await OrgsRepo(session).get_by_inn(EXPO_PROFILE.inn)
    assert org is not None
    taken = await HousesRepo(session).list_for_org(org.id)
    assert len(taken) == EXPO_PROFILE.houses
    after = dict((await session.execute(stmt)).tuples().all())
    assert {house_id: after[house_id] for house_id in houses} == houses
    assert after.keys() - houses.keys() == {house.id for house in taken}
    before = await _counts(session)
    assert await extend(session, _demo(session), FILES, NOW)
    assert await _counts(session) == before


async def _skip(_seeder: Seeder) -> None:
    return None
