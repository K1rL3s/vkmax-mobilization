import csv
import secrets
from collections.abc import Iterable
from decimal import Decimal
from math import cos, inf, radians
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zheka.base import ZhekaType
from zheka.core.models import House, Organization
from zheka.infra.database.tables.houses import houses_table
from zheka.infra.database.tables.organizations import organizations_table

DATA_DIR = Path(__file__).resolve().parent / "data"


class DirectoryHouse(ZhekaType):
    house: House
    living_flats: int
    living_area: int
    overhaul_rate: int

    def distance(self, other: "DirectoryHouse") -> float:
        here, there = self.house, other.house
        if (
            here.lat is None
            or here.lon is None
            or there.lat is None
            or there.lon is None
        ):
            return inf
        scale = cos(radians(float(here.lat)))
        return (
            float(there.lat - here.lat) ** 2
            + (float(there.lon - here.lon) * scale) ** 2
        )


async def load_directory(session: AsyncSession) -> list[DirectoryHouse]:
    orgs = _read_orgs()
    session.add_all(orgs.values())
    await session.flush()

    directory = [_directory_house(row, _house(row, orgs)) for row in _read_houses()]
    session.add_all(item.house for item in directory)
    await session.flush()
    return directory


def passport(row: dict[str, str]) -> dict[str, object]:
    return {
        "reforma_on": row["reforma_on"],
        "entrances_estimated": row["entrances_estimated"] == "1",
        "energy_class": row["energy_class"] or None,
        "wear": int(row["wear"]) if row["wear"] else None,
        "wear_on": row["wear_on"] or None,
        "condition": row["condition"] or None,
        "gis_on": row["gis_on"] or None,
    }


async def extend_directory(session: AsyncSession) -> list[DirectoryHouse]:
    orgs = _read_orgs()
    known = await _known_orgs(session, orgs.keys())
    session.add_all(org for inn, org in orgs.items() if inn not in known)
    orgs |= known
    await session.flush()

    existing = await _houses_by_address(session)
    directory = []
    for row in _read_houses():
        house = existing.get((row["city"], row["street"], row["building"]))
        if house is None:
            house = _house(row, orgs)
            session.add(house)
        directory.append(_directory_house(row, house))
    await session.flush()
    return directory


def _read_orgs() -> dict[str, Organization]:
    with (DATA_DIR / "organizations.csv").open(encoding="utf-8") as file:
        return {
            row["inn"]: Organization(
                name=row["name"],
                inn=row["inn"],
                phone=row["phone"],
                address=row["address"],
                email=row["email"] or None,
                site=row["site"] or None,
                timezone=row["timezone"],
            )
            for row in csv.DictReader(file)
        }


def _read_houses() -> list[dict[str, str]]:
    with (DATA_DIR / "houses.csv").open(encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _house(row: dict[str, str], orgs: dict[str, Organization]) -> House:
    org = orgs.get(row["org_inn"])
    return House(
        org_id=None if org is None else org.id,
        region=row["region"],
        city=row["city"],
        street=row["street"],
        building=row["building"],
        cadastral_no=row["cadastral_no"] or None,
        built_year=int(row["built_year"]) if row["built_year"] else None,
        floors=int(row["floors"]),
        area=int(row["area"]),
        entrances=int(row["entrances"]),
        lat=Decimal(row["lat"]) if row["lat"] else None,
        lon=Decimal(row["lon"]) if row["lon"] else None,
        chat_binding_code=secrets.token_hex(4),
        timezone=row["timezone"],
        passport=passport(row),
    )


def _directory_house(row: dict[str, str], house: House) -> DirectoryHouse:
    return DirectoryHouse(
        house=house,
        living_flats=int(row["living_flats"]),
        living_area=int(row["living_area"]),
        overhaul_rate=int(row["overhaul_rate"]),
    )


async def _known_orgs(
    session: AsyncSession,
    inns: Iterable[str],
) -> dict[str, Organization]:
    stmt = select(Organization).where(organizations_table.c.inn.in_(list(inns)))
    return {org.inn: org for org in (await session.execute(stmt)).scalars()}


async def _houses_by_address(
    session: AsyncSession,
) -> dict[tuple[str, str, str], House]:
    stmt = select(House).order_by(houses_table.c.id.desc())
    return {
        (house.city, house.street, house.building): house
        for house in (await session.execute(stmt)).scalars()
    }
