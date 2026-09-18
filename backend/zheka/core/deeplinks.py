from enum import StrEnum

from zheka.base import ZhekaType
from zheka.core.ids import HouseId


class DeeplinkKind(StrEnum):
    ORG_REGISTER = "reg"
    ORG_INVITE = "inv"
    FLAT_INVITE = "flat"
    HOUSE = "house"
    ENTRANCE_QR = "qr"
    DEMO_STAFF = "demo_staff"
    DEMO_RESIDENT = "demo_resident"


class Deeplink(ZhekaType):
    kind: DeeplinkKind
    value: str = ""


# демо-нагрузки целиком состоят из имени вида, у остальных после префикса
# идет значение
_STANDALONE = (DeeplinkKind.DEMO_STAFF, DeeplinkKind.DEMO_RESIDENT)
_BY_PREFIX = {kind.value: kind for kind in DeeplinkKind if kind not in _STANDALONE}


def org_register_payload(code: str) -> str:
    return f"{DeeplinkKind.ORG_REGISTER}_{code}"


def org_invite_payload(code: str) -> str:
    return f"{DeeplinkKind.ORG_INVITE}_{code}"


def flat_invite_payload(code: str) -> str:
    return f"{DeeplinkKind.FLAT_INVITE}_{code}"


def house_payload(house_id: HouseId) -> str:
    return f"{DeeplinkKind.HOUSE}_{house_id}"


def entrance_qr_payload(house_id: HouseId, entrance: int) -> str:
    return f"{DeeplinkKind.ENTRANCE_QR}_{house_id}_{entrance}"


def parse_deeplink(payload: str) -> Deeplink | None:
    for kind in _STANDALONE:
        if payload == kind:
            return Deeplink(kind=kind)

    prefix, _, value = payload.partition("_")
    kind_with_value = _BY_PREFIX.get(prefix)
    if kind_with_value is None or not value:
        return None
    return Deeplink(kind=kind_with_value, value=value)
