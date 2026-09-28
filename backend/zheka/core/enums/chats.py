from enum import StrEnum


class ChatStatus(StrEnum):
    ACTIVE = "active"
    REMOVED = "removed"


class ChatBinder(StrEnum):
    STAFF = "staff"
    CHAIRMAN = "chairman"
    CODE = "code"


class ChatCardKind(StrEnum):
    REQUEST = "request"
    GROUP = "group"
    POLL = "poll"


class UnpinMethod(StrEnum):
    REPLY = "reply"
    NUMBER = "number"
    LIST_DELETED = "list_deleted"
    MESSAGE_DELETED = "message_deleted"
