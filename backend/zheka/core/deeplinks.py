from enum import StrEnum
from urllib.parse import quote

from zheka.base import ZhekaType
from zheka.core.enums import EventSource, RequestCategory
from zheka.core.ids import HouseId, PollId, RequestId
from zheka.core.services.demo import DEMO_INNS


class DeeplinkKind(StrEnum):
    ORG_REGISTER = "reg"
    ORG_INVITE = "inv"
    FLAT_INVITE = "flat"
    CHAIRMAN = "chair"
    HOUSE = "house"
    ENTRANCE_QR = "qr"
    DEMO_ADMIN = "demo_admin"
    DEMO_STAFF = "demo_staff"
    DEMO_RESIDENT = "demo_resident"
    DEMO_EXECUTOR = "demo_executor"


class Deeplink(ZhekaType):
    kind: DeeplinkKind
    value: str = ""

    @property
    def source(self) -> EventSource:
        return _SOURCES.get(self.kind, EventSource.DEEPLINK)


_SOURCES = {
    DeeplinkKind.HOUSE: EventSource.CHAT,
    DeeplinkKind.ENTRANCE_QR: EventSource.QR,
}
_DEMO = (
    DeeplinkKind.DEMO_ADMIN,
    DeeplinkKind.DEMO_STAFF,
    DeeplinkKind.DEMO_RESIDENT,
    DeeplinkKind.DEMO_EXECUTOR,
)
_DEMO_NUMBERS = frozenset(str(number) for number in range(1, len(DEMO_INNS) + 1))
_BY_PREFIX = {kind.value: kind for kind in DeeplinkKind if kind not in _DEMO}
ADMIN_APP_PATH = "/admin/requests"
METERS_APP_PATH = "/meters"
APPOINTMENTS_APP_PATH = "/appointments"
MEETINGS_APP_PATH = "/meetings"


def org_invite_payload(code: str) -> str:
    return f"{DeeplinkKind.ORG_INVITE}_{code}"


def flat_invite_payload(code: str) -> str:
    return f"{DeeplinkKind.FLAT_INVITE}_{code}"


def chairman_payload(code: str) -> str:
    return f"{DeeplinkKind.CHAIRMAN}_{code}"


def house_payload(house_id: HouseId) -> str:
    return f"{DeeplinkKind.HOUSE}_{house_id}"


def house_category_payload(house_id: HouseId, category: RequestCategory) -> str:
    return f"{DeeplinkKind.HOUSE}_{house_id}_{category}"


def entrance_qr_payload(house_id: HouseId, entrance: int) -> str:
    return f"{DeeplinkKind.ENTRANCE_QR}_{house_id}_{entrance}"


OBJECT_QR_CATEGORIES = (
    RequestCategory.ELEVATOR,
    RequestCategory.ELECTRICITY,
    RequestCategory.ENTRANCE,
)


def object_qr_payload(
    house_id: HouseId,
    entrance: int,
    category: RequestCategory,
) -> str:
    return f"obj_{house_id}_{entrance}_{category}"


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


def request_app_path(request_id: RequestId) -> str:
    return f"/requests/{request_id}"


def admin_request_app_path(request_id: RequestId) -> str:
    return f"{ADMIN_APP_PATH}/{request_id}"


def org_register_app_path(code: str) -> str:
    return f"/register/{quote(code, safe='')}"


def poll_app_path(poll_id: PollId) -> str:
    return f"/meetings/{poll_id}"
