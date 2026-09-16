from enum import StrEnum


class ResidentRole(StrEnum):
    OWNER = "owner"
    TENANT = "tenant"


class ResidentStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"


class VerificationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
