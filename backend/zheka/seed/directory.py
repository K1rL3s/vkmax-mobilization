import csv
import secrets
from decimal import Decimal
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from zheka.base import ZhekaType
from zheka.core.models import House, Organization

DATA_DIR = Path(__file__).resolve().parent / "data"


class DirectoryHouse(ZhekaType):
    house: House
    living_flats: int
    living_area: int
    overhaul_rate: int


async def load_directory(session: AsyncSession) -> list[DirectoryHouse]:
    orgs: dict[str, Organization] = {}
    with (DATA_DIR / "organizations.csv").open(encoding="utf-8") as file:
        for row in csv.DictReader(file):
            orgs[row["inn"]] = Organization(
                name=row["name"],
                inn=row["inn"],
                phone=row["phone"],
                address=row["address"],
                timezone=row["timezone"],
            )
    session.add_all(orgs.values())
    await session.flush()

    directory = []
    with (DATA_DIR / "houses.csv").open(encoding="utf-8") as file:
        for row in csv.DictReader(file):
            org = orgs.get(row["org_inn"])
            house = House(
                org_id=None if org is None else org.id,
                region=row["region"],
                city=row["city"],
                street=row["street"],
                building=row["building"],
                built_year=int(row["built_year"]) if row["built_year"] else None,
                floors=int(row["floors"]),
                area=int(row["area"]),
                entrances=int(row["entrances"]),
                lat=Decimal(row["lat"]) if row["lat"] else None,
                lon=Decimal(row["lon"]) if row["lon"] else None,
                chat_binding_code=secrets.token_hex(4),
                timezone=row["timezone"],
            )
            directory.append(
                DirectoryHouse(
                    house=house,
                    living_flats=int(row["living_flats"]),
                    living_area=int(row["living_area"]),
                    overhaul_rate=int(row["overhaul_rate"]),
                ),
            )
    session.add_all(item.house for item in directory)
    await session.flush()
    return directory
