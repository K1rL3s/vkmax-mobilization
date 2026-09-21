from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from zheka.base import ZhekaType


class RequestStatus(StrEnum):
    NEW = "new"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    ON_REVIEW = "on_review"
    DONE = "done"


class RequestCompletionReason(StrEnum):
    RESIDENT_ACCEPTED = "resident_accepted"
    RESIDENT_REJECTED = "resident_rejected"
    AUTO_CLOSED = "auto_closed"


class RequestActorRole(StrEnum):
    RESIDENT = "resident"
    STAFF = "staff"
    EXECUTOR = "executor"
    SYSTEM = "system"


class RequestChannel(StrEnum):
    MINIAPP = "miniapp"
    BOT = "bot"
    CHAT = "chat"
    PHONE = "phone"


class RequestPhotoKind(StrEnum):
    ISSUE = "issue"
    RESULT = "result"


class RequestGroupStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class ResponsibilityZone(StrEnum):
    MANAGEMENT = "management"
    UTILITY = "utility"
    MUNICIPALITY = "municipality"


class RequestCategory(StrEnum):
    LEAK = "leak"
    ELEVATOR = "elevator"
    GARBAGE = "garbage"
    HEATING = "heating"
    WATER_SUPPLY = "water_supply"
    ELECTRICITY = "electricity"
    ENTRANCE = "entrance"
    YARD = "yard"
    METER_ERROR = "meter_error"
    CHARGE_DISPUTE = "charge_dispute"
    OTHER = "other"


class CategoryRule(ZhekaType):
    label: str
    zone: ResponsibilityZone
    normative_hours: int


CATEGORY_RULES: Mapping[RequestCategory, CategoryRule] = MappingProxyType(
    {
        RequestCategory.LEAK: CategoryRule(
            label="Протечка", zone=ResponsibilityZone.MANAGEMENT, normative_hours=4
        ),
        RequestCategory.ELEVATOR: CategoryRule(
            label="Лифт", zone=ResponsibilityZone.MANAGEMENT, normative_hours=24
        ),
        RequestCategory.GARBAGE: CategoryRule(
            label="Мусор", zone=ResponsibilityZone.MANAGEMENT, normative_hours=24
        ),
        RequestCategory.HEATING: CategoryRule(
            label="Отопление", zone=ResponsibilityZone.UTILITY, normative_hours=24
        ),
        RequestCategory.WATER_SUPPLY: CategoryRule(
            label="Водоснабжение", zone=ResponsibilityZone.UTILITY, normative_hours=8
        ),
        RequestCategory.ELECTRICITY: CategoryRule(
            label="Электричество", zone=ResponsibilityZone.UTILITY, normative_hours=24
        ),
        RequestCategory.ENTRANCE: CategoryRule(
            label="Подъезд", zone=ResponsibilityZone.MANAGEMENT, normative_hours=72
        ),
        RequestCategory.YARD: CategoryRule(
            label="Двор и территория",
            zone=ResponsibilityZone.MUNICIPALITY,
            normative_hours=72,
        ),
        RequestCategory.METER_ERROR: CategoryRule(
            label="Ошибка в показаниях",
            zone=ResponsibilityZone.MANAGEMENT,
            normative_hours=72,
        ),
        RequestCategory.CHARGE_DISPUTE: CategoryRule(
            label="Спор по начислению",
            zone=ResponsibilityZone.MANAGEMENT,
            normative_hours=72,
        ),
        RequestCategory.OTHER: CategoryRule(
            label="Другое", zone=ResponsibilityZone.MANAGEMENT, normative_hours=72
        ),
    }
)
