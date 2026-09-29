from enum import StrEnum


class ProposalStatus(StrEnum):
    NEW = "new"
    ACCEPTED = "accepted"
    DECLINED = "declined"
