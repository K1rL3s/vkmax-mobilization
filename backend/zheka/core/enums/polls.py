from enum import StrEnum


class PollStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"


class PollAuthor(StrEnum):
    STAFF = "staff"
    CHAIRMAN = "chairman"
    RESIDENT = "resident"
