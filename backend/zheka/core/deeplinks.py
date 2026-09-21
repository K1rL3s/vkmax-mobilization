from enum import StrEnum

from zheka.base import ZhekaType
from zheka.core.ids import HouseId
from zheka.core.services.demo import DEMO_INNS


class DeeplinkKind(StrEnum):
    ORG_REGISTER = "reg"
    ORG_INVITE = "inv"
    FLAT_INVITE = "flat"
    HOUSE = "house"
    ENTRANCE_QR = "qr"
    DEMO_ADMIN = "demo_admin"
    DEMO_STAFF = "demo_staff"
    DEMO_RESIDENT = "demo_resident"


class Deeplink(ZhekaType):
    kind: DeeplinkKind
    value: str = ""


_DEMO = (DeeplinkKind.DEMO_ADMIN, DeeplinkKind.DEMO_STAFF, DeeplinkKind.DEMO_RESIDENT)
_DEMO_NUMBERS = frozenset(str(number) for number in range(1, len(DEMO_INNS) + 1))
_BY_PREFIX = {kind.value: kind for kind in DeeplinkKind if kind not in _DEMO}


def org_invite_payload(code: str) -> str:
    return f"{DeeplinkKind.ORG_INVITE}_{code}"


def flat_invite_payload(code: str) -> str:
    return f"{DeeplinkKind.FLAT_INVITE}_{code}"


def house_payload(house_id: HouseId) -> str:
    return f"{DeeplinkKind.HOUSE}_{house_id}"


def entrance_qr_payload(house_id: HouseId, entrance: int) -> str:
    return f"{DeeplinkKind.ENTRANCE_QR}_{house_id}_{entrance}"


def parse_deeplink(payload: str) -> Deeplink | None:
    demo_kind, _, number = payload.rpartition("_")
    if demo_kind in _DEMO:
        if number not in _DEMO_NUMBERS:
            return None
        return Deeplink(kind=DeeplinkKind(demo_kind), value=number)

    prefix, _, value = payload.partition("_")
    kind_with_value = _BY_PREFIX.get(prefix)
    if kind_with_value is None or not value:
        return None
    return Deeplink(kind=kind_with_value, value=value)
