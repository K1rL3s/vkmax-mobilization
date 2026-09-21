from collections.abc import Sequence

from zheka.base import ZhekaType

# порог кворума по площади - 50% дома, сотые доли процента: 50% = 5000
QUORUM_PERCENT = 5000


class QuorumForecast(ZhekaType):
    voted_flats: int
    total_flats: int
    voted_area: int  # 1/100 square metre
    total_area: int  # 1/100 square metre
    area_percent: int  # 1/100 of a percent
    quorum_reached: bool
    unweighted_votes: int


def area_percent_of(area: int, total_area: int) -> int:
    # без площади дома доля не считается - опрос без ни одной квартиры
    # с известной площадью не может дать кворум, а не деление на ноль
    return area * 10_000 // total_area if total_area else 0


def forecast(
    voted_areas: Sequence[int | None],
    all_areas: Sequence[int | None],
    unverified_votes: int,
) -> QuorumForecast:
    # одна площадь на квартиру, None - площадь неизвестна
    total_area = sum(area for area in all_areas if area is not None)
    voted_area = sum(area for area in voted_areas if area is not None)
    area_percent = area_percent_of(voted_area, total_area)
    return QuorumForecast(
        voted_flats=len(voted_areas),
        total_flats=len(all_areas),
        voted_area=voted_area,
        total_area=total_area,
        area_percent=area_percent,
        quorum_reached=area_percent >= QUORUM_PERCENT,
        unweighted_votes=unverified_votes,
    )
