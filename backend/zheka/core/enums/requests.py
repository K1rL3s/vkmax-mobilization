from collections.abc import Mapping
from enum import StrEnum

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
    emoji: str
    zone: ResponsibilityZone
    normative_hours: int

    @property
    def caption(self) -> str:
        return f"{self.emoji} {self.label}"


CATEGORY_RULES: Mapping[RequestCategory, CategoryRule] = {
    RequestCategory.LEAK: CategoryRule(
        label="Протечка",
        emoji="💧",
        zone=ResponsibilityZone.MANAGEMENT,
        normative_hours=4,
    ),
    RequestCategory.ELEVATOR: CategoryRule(
        label="Лифт",
        emoji="🛗",
        zone=ResponsibilityZone.MANAGEMENT,
        normative_hours=24,
    ),
    RequestCategory.GARBAGE: CategoryRule(
        label="Мусор",
        emoji="🗑",
        zone=ResponsibilityZone.MANAGEMENT,
        normative_hours=24,
    ),
    RequestCategory.HEATING: CategoryRule(
        label="Отопление",
        emoji="🔥",
        zone=ResponsibilityZone.UTILITY,
        normative_hours=24,
    ),
    RequestCategory.WATER_SUPPLY: CategoryRule(
        label="Водоснабжение",
        emoji="🚰",
        zone=ResponsibilityZone.UTILITY,
        normative_hours=8,
    ),
    RequestCategory.ELECTRICITY: CategoryRule(
        label="Электричество",
        emoji="💡",
        zone=ResponsibilityZone.UTILITY,
        normative_hours=24,
    ),
    RequestCategory.ENTRANCE: CategoryRule(
        label="Подъезд",
        emoji="🚪",
        zone=ResponsibilityZone.MANAGEMENT,
        normative_hours=72,
    ),
    RequestCategory.YARD: CategoryRule(
        label="Двор и территория",
        emoji="🌳",
        zone=ResponsibilityZone.MUNICIPALITY,
        normative_hours=72,
    ),
    RequestCategory.METER_ERROR: CategoryRule(
        label="Ошибка в показаниях",
        emoji="📟",
        zone=ResponsibilityZone.MANAGEMENT,
        normative_hours=72,
    ),
    RequestCategory.CHARGE_DISPUTE: CategoryRule(
        label="Спор по начислению",
        emoji="🧾",
        zone=ResponsibilityZone.MANAGEMENT,
        normative_hours=72,
    ),
    RequestCategory.OTHER: CategoryRule(
        label="Другое",
        emoji="📝",
        zone=ResponsibilityZone.MANAGEMENT,
        normative_hours=72,
    ),
}
