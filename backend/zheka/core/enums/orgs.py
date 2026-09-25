from enum import StrEnum


class OrgRole(StrEnum):
    CREATOR = "creator"
    ADMIN = "admin"
    EMPLOYEE = "employee"
    EXECUTOR = "executor"

    @property
    def is_staff(self) -> bool:
        return self in (OrgRole.CREATOR, OrgRole.ADMIN, OrgRole.EMPLOYEE)

    @property
    def can_manage_houses(self) -> bool:
        return self in (OrgRole.CREATOR, OrgRole.ADMIN)

    def can_invite(self, target_role: "OrgRole") -> bool:
        return target_role is not OrgRole.CREATOR and (
            self is OrgRole.CREATOR
            or (
                self is OrgRole.ADMIN
                and target_role in (OrgRole.EMPLOYEE, OrgRole.EXECUTOR)
            )
        )

    def can_remove_member(self, target_role: "OrgRole") -> bool:
        return target_role is not OrgRole.CREATOR and (
            self is OrgRole.CREATOR
            or (self is OrgRole.ADMIN and target_role is not OrgRole.ADMIN)
        )

    def higher_role(self, other: "OrgRole") -> "OrgRole":
        return min(self, other, key=list(OrgRole).index)
