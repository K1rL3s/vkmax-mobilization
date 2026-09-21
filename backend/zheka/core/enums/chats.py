from enum import StrEnum


class ChatStatus(StrEnum):
    ACTIVE = "active"
    REMOVED = "removed"


class ChatBinder(StrEnum):
    # по какому праву привязан чат: пишется в CHAT_BOUND как by_role
    STAFF = "staff"
    CHAIRMAN = "chairman"
    CODE = "code"
