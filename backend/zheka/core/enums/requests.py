from collections.abc import Mapping
from datetime import datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from zheka.base import ZhekaType
from zheka.core.workdays import working_days_end

HOURS_IN_DAY = 24


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
    RESIDENT_CANCELED = "resident_canceled"


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


class RequestAttachmentKind(StrEnum):
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
    fix_hours: int = 0
    fix_working_days: int | None = None
    react_minutes: int | None = None
    basis: str | None = None
    rejection_needs_photo: bool = True

    @property
    def caption(self) -> str:
        return f"{self.emoji} {self.label}"

    @property
    def deadline_text(self) -> str:
        if self.fix_working_days is not None:
            return _amount(
                self.fix_working_days,
                ("рабочий день", "рабочих дня", "рабочих дней"),
            )
        if self.fix_hours > HOURS_IN_DAY and self.fix_hours % HOURS_IN_DAY == 0:
            return f"{self.fix_hours // HOURS_IN_DAY} суток"
        return _amount(self.fix_hours, ("час", "часа", "часов"))

    @property
    def react_text(self) -> str | None:
        if self.react_minutes is None:
            return None
        return _amount(self.react_minutes, ("минута", "минуты", "минут"))

    def deadlines(
        self,
        created_at: datetime,
        zone: ZoneInfo,
    ) -> tuple[datetime | None, datetime]:
        react = (
            None
            if self.react_minutes is None
            else created_at + timedelta(minutes=self.react_minutes)
        )
        if self.fix_working_days is not None:
            return react, working_days_end(created_at, zone, self.fix_working_days)
        return react, created_at + timedelta(hours=self.fix_hours)


CATEGORY_RULES: Mapping[RequestCategory, CategoryRule] = {
    RequestCategory.LEAK: CategoryRule(
        label="Протечка",
        emoji="💧",
        zone=ResponsibilityZone.MANAGEMENT,
        fix_hours=72,
        react_minutes=30,
        basis="ПП РФ № 416, п. 13",
    ),
    RequestCategory.ELEVATOR: CategoryRule(
        label="Лифт",
        emoji="🛗",
        zone=ResponsibilityZone.MANAGEMENT,
        fix_hours=24,
    ),
    RequestCategory.GARBAGE: CategoryRule(
        label="Мусор",
        emoji="🗑",
        zone=ResponsibilityZone.MANAGEMENT,
        fix_hours=24,
    ),
    RequestCategory.HEATING: CategoryRule(
        label="Отопление",
        emoji="🔥",
        zone=ResponsibilityZone.MANAGEMENT,
        fix_hours=16,
        basis="ПП РФ № 354, прил. 1, п. 14",
    ),
    RequestCategory.WATER_SUPPLY: CategoryRule(
        label="Водоснабжение",
        emoji="🚰",
        zone=ResponsibilityZone.UTILITY,
        fix_hours=4,
        basis="ПП РФ № 354, прил. 1, п. 1, 4",
    ),
    RequestCategory.ELECTRICITY: CategoryRule(
        label="Электричество",
        emoji="💡",
        zone=ResponsibilityZone.MANAGEMENT,
        fix_hours=24,
        basis="ПП РФ № 354, прил. 1, п. 9",
    ),
    RequestCategory.ENTRANCE: CategoryRule(
        label="Подъезд",
        emoji="🚪",
        zone=ResponsibilityZone.MANAGEMENT,
        fix_hours=72,
    ),
    RequestCategory.YARD: CategoryRule(
        label="Двор и территория",
        emoji="🌳",
        zone=ResponsibilityZone.MANAGEMENT,
        fix_hours=72,
    ),
    RequestCategory.METER_ERROR: CategoryRule(
        label="Ошибка в показаниях",
        emoji="📟",
        zone=ResponsibilityZone.MANAGEMENT,
        fix_working_days=10,
        basis="ПП РФ № 354, п. 31 «е(2)»",
        rejection_needs_photo=False,
    ),
    RequestCategory.CHARGE_DISPUTE: CategoryRule(
        label="Спор по начислению",
        emoji="🧾",
        zone=ResponsibilityZone.MANAGEMENT,
        fix_working_days=10,
        basis=(
            "ПП РФ № 416, п. 36; проверка начисления - при обращении "
            "или по договоренности до 1 месяца, ПП РФ № 354, п. 31 «д»"
        ),
        rejection_needs_photo=False,
    ),
    RequestCategory.OTHER: CategoryRule(
        label="Другое",
        emoji="📝",
        zone=ResponsibilityZone.MANAGEMENT,
        fix_working_days=10,
        basis="ПП РФ № 416, п. 36",
    ),
}


def _amount(count: int, forms: tuple[str, str, str]) -> str:
    if count % 10 == 1 and count % 100 != 11:  # noqa: PLR2004
        form = forms[0]
    elif 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:  # noqa: PLR2004
        form = forms[1]
    else:
        form = forms[2]
    return f"{count} {form}"


class DangerKind(StrEnum):
    GAS = "gas"
    FIRE = "fire"
    ELECTRIC = "electric"
    TRAPPED = "trapped"
    FLOOD_ELECTRIC = "flood_electric"
    LLM = "llm"
