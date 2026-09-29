import csv
from functools import cache
from importlib.resources import files

from zheka.base import ZhekaType
from zheka.core.enums import CityServiceKind


class CityService(ZhekaType):
    region: str
    city: str
    kind: CityServiceKind
    name: str
    phone: str
    hours: str | None
    site: str | None
    note: str | None
    source_url: str


@cache
def directory() -> tuple[CityService, ...]:
    with (
        files("zheka.core").joinpath("city_services.csv").open(encoding="utf-8") as file
    ):
        return tuple(
            CityService(
                region=row["region"],
                city=row["city"],
                kind=CityServiceKind(row["kind"]),
                name=row["name"],
                phone=row["phone"],
                hours=row["hours"] or None,
                site=row["site"] or None,
                note=row["note"] or None,
                source_url=row["source_url"],
            )
            for row in csv.DictReader(file)
        )


def city_services(region: str, city: str) -> list[CityService]:
    return [
        service
        for service in directory()
        if service.region == region and service.city in {"", city}
    ]
