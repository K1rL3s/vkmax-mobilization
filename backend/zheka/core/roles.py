from zheka.core.enums import OrgRole


def is_staff(role: OrgRole) -> bool:
    return role in (OrgRole.CREATOR, OrgRole.ADMIN, OrgRole.EMPLOYEE)


def can_manage_houses(role: OrgRole) -> bool:
    return role in (OrgRole.CREATOR, OrgRole.ADMIN)


def can_invite(role: OrgRole, target_role: OrgRole) -> bool:
    return target_role is not OrgRole.CREATOR and (
        role is OrgRole.CREATOR
        or (
            role is OrgRole.ADMIN
            and target_role in (OrgRole.EMPLOYEE, OrgRole.EXECUTOR)
        )
    )


def can_remove_member(actor_role: OrgRole, target_role: OrgRole) -> bool:
    return target_role is not OrgRole.CREATOR and (
        actor_role is OrgRole.CREATOR
        or (actor_role is OrgRole.ADMIN and target_role is not OrgRole.ADMIN)
    )


def higher_role(first: OrgRole, second: OrgRole) -> OrgRole:
    return min(first, second, key=list(OrgRole).index)
