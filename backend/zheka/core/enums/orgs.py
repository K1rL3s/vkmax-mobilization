from enum import StrEnum


class OrgRole(StrEnum):
    CREATOR = "creator"
    ADMIN = "admin"
    EMPLOYEE = "employee"
    EXECUTOR = "executor"
