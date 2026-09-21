from enum import StrEnum


class ChatStatus(StrEnum):
    ACTIVE = "active"
    REMOVED = "removed"


class ChatBinder(StrEnum):
    STAFF = "staff"
    CHAIRMAN = "chairman"
    CODE = "code"
