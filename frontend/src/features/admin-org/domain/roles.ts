import type { components } from "@/shared/api/schema/generated";
import type { StatusPillTone } from "@/shared/ui/status-pill";

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

export type InvitableRole = Exclude<OrgRole, "creator">;

export const INVITABLE_ROLES: InvitableRole[] = [
  "admin",
  "employee",
  "executor",
];

export const inviteBlock = (actor: OrgRole, target: OrgRole): string | null => {
  if (actor !== "creator" && actor !== "admin")
    return "Приглашают создатель и администраторы";
  if (actor === "admin" && target === "admin")
    return "Администратора приглашает только создатель";
  return null;
};

export const removeBlock = (member: OrgMember): string | null => {
  if (member.can_remove) return null;
  if (member.role === "creator")
    return "Создателя организации исключить нельзя";

  return member.role === "admin"
    ? "Администратора исключает только создатель"
    : "Этого сотрудника исключить нельзя";
};

export const ROLE_TONE: Record<OrgRole, StatusPillTone> = {
  creator: "promo",
  admin: "themed",
  employee: "neutral",
  executor: "positive",
};
