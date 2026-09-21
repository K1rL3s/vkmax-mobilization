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
    living_area: int  # 1/100 square metre
    overhaul_rate: int  # 1/10000 rouble per square metre


async def load_directory(session: AsyncSession) -> list[DirectoryHouse]:
    # организации из реестра остаются незарегистрированными и без
    # сотрудников: «УК не подключена» про них - правда
    orgs: dict[str, Organization] = {}
    with (DATA_DIR / "organizations.csv").open(encoding="utf-8") as file:
        for row in csv.DictReader(file):
            orgs[row["inn"]] = Organization(
                name=row["name"],
                inn=row["inn"],
                phone=row["phone"],
                address=row["address"],
            )
    session.add_all(orgs.values())
    await session.flush()

    directory = []
    with (DATA_DIR / "houses.csv").open(encoding="utf-8") as file:
        for row in csv.DictReader(file):
            # дом связан с организацией, только если так сказано в карточке
            # дома, а кадастрового номера в открытых данных нет вовсе
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
                # код привязки чата - секрет, а не функция от адреса
                chat_binding_code=secrets.token_hex(4),
            )
            directory.append(
                DirectoryHouse(
                    house=house,
                    living_flats=int(row["living_flats"]),
                    living_area=int(row["living_area"]),
                    overhaul_rate=int(row["overhaul_rate"]),
                )
            )
    session.add_all(item.house for item in directory)
    await session.flush()
    return directory
