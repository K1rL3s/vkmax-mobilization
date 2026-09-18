from zheka.core.enums import OrgRole

_STAFF_ROLES = (OrgRole.CREATOR, OrgRole.ADMIN, OrgRole.EMPLOYEE)
_INVITABLE_BY_ADMIN = (OrgRole.EMPLOYEE, OrgRole.EXECUTOR)
_MANAGERS = (OrgRole.CREATOR, OrgRole.ADMIN)
_REQUEST_WORKERS = (OrgRole.CREATOR, OrgRole.ADMIN, OrgRole.EMPLOYEE)


def is_staff(role: OrgRole) -> bool:
    return role in _STAFF_ROLES


def can_manage_houses(role: OrgRole) -> bool:
    return role in _MANAGERS


def can_invite(role: OrgRole, target_role: OrgRole) -> bool:
    # второго создателя не выдает никто: создатель один и неисключаем
    if target_role is OrgRole.CREATOR:
        return False
    if role is OrgRole.CREATOR:
        return True
    if role is OrgRole.ADMIN:
        return target_role in _INVITABLE_BY_ADMIN
    return False


def can_remove_member(actor_role: OrgRole, target_role: OrgRole) -> bool:
    if target_role is OrgRole.CREATOR:
        return False
    if actor_role is OrgRole.CREATOR:
        return True
    if actor_role is OrgRole.ADMIN:
        return target_role is not OrgRole.ADMIN
    return False


def can_work_requests(role: OrgRole) -> bool:
    return role in _REQUEST_WORKERS


def can_edit_org_settings(role: OrgRole) -> bool:
    return role in _MANAGERS


def higher_role(first: OrgRole, second: OrgRole) -> OrgRole:
    # старшинство ролей - это порядок объявления OrgRole, от создателя
    # к исполнителю: отдельная таблица рангов молча разошлась бы с ним
    order = list(OrgRole)
    return min(first, second, key=order.index)
