from collections.abc import Sequence

from zheka.base import ZhekaType
from zheka.core.ids import FlatId

# порог кворума по площади - 50% дома, сотые доли процента: 50% = 5000
QUORUM_PERCENT = 5000


class FlatArea(ZhekaType):
    flat_id: FlatId
    area: int | None  # 1/100 square metre


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
    voted: Sequence[FlatArea],
    all_flats: Sequence[FlatArea],
    unverified_votes: int,
) -> QuorumForecast:
    # дедуп по квартире - защита на случай, если вызывающий передаст одну
    # квартиру дважды: кворум считает квартиру, а не голос
    voted_by_flat = {flat.flat_id: flat.area for flat in voted}
    total_area = sum(flat.area for flat in all_flats if flat.area is not None)
    voted_area = sum(area for area in voted_by_flat.values() if area is not None)
    area_percent = area_percent_of(voted_area, total_area)
    return QuorumForecast(
        voted_flats=len(voted_by_flat),
        total_flats=len(all_flats),
        voted_area=voted_area,
        total_area=total_area,
        area_percent=area_percent,
        quorum_reached=area_percent >= QUORUM_PERCENT,
        unweighted_votes=unverified_votes,
    )
