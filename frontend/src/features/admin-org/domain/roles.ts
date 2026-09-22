import type { components } from "@/shared/api/schema/generated";

export type OrgRole = components["schemas"]["OrgRole"];

export type OrgMember = components["schemas"]["OrgMemberItem"];

export const ROLE_LABEL: Record<OrgRole, string> = {
  creator: "Создатель",
  admin: "Администратор",
  employee: "Сотрудник",
  executor: "Исполнитель",
};

export const ROLE_ORDER: OrgRole[] = [
  "creator",
  "admin",
  "employee",
  "executor",
];

// создателя не приглашают: он один, тот, кто зарегистрировал организацию
export type InvitableRole = Exclude<OrgRole, "creator">;

export const INVITABLE_ROLES: InvitableRole[] = [
  "admin",
  "employee",
  "executor",
];

// причины повторяют can_invite из core/roles.py бэка: кнопка гаснет ровно
// там, где бэк ответил бы 403
export const inviteBlock = (actor: OrgRole, target: OrgRole): string | null => {
  if (actor !== "creator" && actor !== "admin") {
    return "Приглашают создатель и администраторы";
  }

  if (actor === "admin" && target === "admin") {
    return "Администратора приглашает только создатель";
  }

  return null;
};

// can_remove считает бэк, здесь только объяснение отказа
export const removeBlock = (member: OrgMember): string | null => {
  if (member.can_remove) {
    return null;
  }

  if (member.role === "creator") {
    return "Создателя организации исключить нельзя";
  }

  return member.role === "admin"
    ? "Администратора исключает только создатель"
    : "Этого сотрудника исключить нельзя";
};
