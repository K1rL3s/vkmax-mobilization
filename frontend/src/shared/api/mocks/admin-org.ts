import type { components } from "../schema/generated";

import { badRequest, forbidden, notFound, ok, route } from "./reply";
import { me } from "./state";

type Schemas = components["schemas"];

type OrgRole = Schemas["OrgRole"];

type MockMember = Omit<Schemas["OrgMemberItem"], "can_remove">;

type MockInvite = Omit<Schemas["OrgInviteItem"], "deeplink">;

// X-Org-Id мок не сверяет, как и дома: мок-пользователь в state.ts сотрудник
// чужой организации, и бэк отказал бы ему во всём этом файле. Здесь он
// администратор «Жилсервиса» - так видны оба запрета: создателя не исключить,
// другого администратора тоже, а приглашать администраторов нельзя
const ACTOR_ROLE: OrgRole = "admin";

const HOUR = 60 * 60 * 1000;

const hours = (count: number) =>
  new Date(Date.now() + count * HOUR).toISOString();

// правила - копия core/roles.py бэка
const canInvite = (actor: OrgRole, target: OrgRole) =>
  target !== "creator" &&
  (actor === "creator" ||
    (actor === "admin" && (target === "employee" || target === "executor")));

const canRemove = (actor: OrgRole, target: OrgRole) =>
  target !== "creator" &&
  (actor === "creator" || (actor === "admin" && target !== "admin"));

const ROLES: OrgRole[] = ["creator", "admin", "employee", "executor"];

const isRole = (value: unknown): value is OrgRole =>
  ROLES.includes(value as OrgRole);

// token_urlsafe(8) бэка: 11 символов base64url
const inviteCode = () =>
  btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(8))))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replace(/=+$/, "");

const seedMembers = (): MockMember[] => [
  {
    user_id: 41,
    name: "Марина Ковалёва",
    username: "kovaleva",
    role: "creator",
    created_at: "2026-06-01T09:00:00Z",
  },
  {
    user_id: me().user_id,
    name: me().name,
    username: null,
    role: ACTOR_ROLE,
    created_at: "2026-06-03T10:30:00Z",
  },
  {
    user_id: 42,
    name: "Олег Петров",
    username: "opetrov",
    role: "admin",
    created_at: "2026-06-10T08:15:00Z",
  },
  {
    user_id: 43,
    name: "Светлана Иванова",
    username: "ivanova_s",
    role: "employee",
    created_at: "2026-07-02T12:00:00Z",
  },
  {
    user_id: 44,
    name: "Константин Александрович Верещагин-Нестеров",
    username: null,
    role: "employee",
    created_at: "2026-08-19T07:45:00Z",
  },
  {
    user_id: 45,
    name: "Рустам Галиев",
    username: "galiev_master",
    role: "executor",
    created_at: "2026-07-15T06:20:00Z",
  },
  {
    user_id: 46,
    name: "Игорь Никитин",
    username: null,
    role: "executor",
    created_at: "2026-09-01T06:00:00Z",
  },
];

const seedInvites = (): MockInvite[] => [
  {
    code: "q3Zr8sKd1Aw",
    role: "employee",
    created_at: hours(-2),
    expires_at: hours(70),
    max_activations: 1,
    activations_used: 0,
    revoked_at: null,
  },
  {
    code: "Xk2-Pm9_vTe",
    role: "executor",
    created_at: hours(-30),
    expires_at: hours(138),
    max_activations: 5,
    activations_used: 2,
    revoked_at: null,
  },
  {
    code: "Lb7nQw0rYc4",
    role: "employee",
    created_at: hours(-50),
    expires_at: hours(22),
    max_activations: 1,
    activations_used: 1,
    revoked_at: null,
  },
  {
    code: "Hs5_uJ1oEe8",
    role: "executor",
    created_at: hours(-120),
    expires_at: hours(48),
    max_activations: 3,
    activations_used: 0,
    revoked_at: hours(-100),
  },
  {
    code: "Rt4mZa9-Ngk",
    role: "employee",
    created_at: hours(-400),
    expires_at: hours(-328),
    max_activations: 1,
    activations_used: 0,
    revoked_at: null,
  },
];

const state = {
  settings: {
    meter_window_day_from: 15,
    meter_window_day_to: 25,
    meter_window_always_open: false,
    group_threshold: 3,
    group_window_hours: 24,
    phone: "+7 843 200-10-10",
    reception_note: "Пн-чт 9:00-18:00, пт до 17:00",
  } as Schemas["OrgSettingsResponse"],
  members: seedMembers(),
  invites: seedInvites(),
};

const memberItem = (member: MockMember): Schemas["OrgMemberItem"] => ({
  ...member,
  can_remove: canRemove(ACTOR_ROLE, member.role),
});

const inviteItem = (invite: MockInvite): Schemas["OrgInviteItem"] => ({
  ...invite,
  deeplink: `https://max.ru/zheka_bot?start=inv_${invite.code}`,
});

const isInteger = (value: unknown): value is number =>
  typeof value === "number" && Number.isInteger(value);

// проверки и тексты - из OrgsService.update_settings; не то число бэк
// отвергает pydantic'ом с 422, мок отвечает 400 тем же конвертом
const settingsError = (body: Record<string, unknown>): string | null => {
  const numbers = [
    body.meter_window_day_from,
    body.meter_window_day_to,
    body.group_threshold,
    body.group_window_hours,
  ];

  if (
    !numbers.every(isInteger) ||
    typeof body.meter_window_always_open !== "boolean" ||
    typeof body.phone !== "string" ||
    !(body.reception_note == null || typeof body.reception_note === "string")
  ) {
    return "Некорректные поля настроек";
  }

  const [dayFrom, dayTo, threshold, windowHours] = numbers;

  if ([dayFrom, dayTo].some((day) => day < 1 || day > 28)) {
    return "День окна показаний - число от 1 до 28";
  }

  if (threshold < 2) {
    return "Порог склейки заявок - не меньше 2";
  }

  if (windowHours < 1 || windowHours > 168) {
    return "Окно склейки заявок - от 1 до 168 часов";
  }

  return null;
};

export const adminOrgConfigs = [
  {
    path: "/admin/org" as const,
    method: "get" as const,
    routes: [
      route(() =>
        ok({
          id: 1,
          name: "ООО «Жилсервис»",
          inn: "1655123450",
          license_no: "016-000123",
          phone: state.settings.phone,
          address: "Казань, ул. Баумана, 10",
          reception_note: state.settings.reception_note,
          registered_at: "2026-06-01T09:00:00Z",
          is_demo: true,
          houses_count: 3,
          members_count: state.members.length,
        } satisfies Schemas["OrgCard"]),
      ),
    ],
  },
  {
    path: "/admin/org/settings" as const,
    method: "get" as const,
    routes: [route(() => ok(state.settings))],
  },
  {
    path: "/admin/org/settings" as const,
    method: "put" as const,
    routes: [
      route((request) => {
        const error = settingsError(request.body);

        if (error) {
          return badRequest(error);
        }

        state.settings = {
          ...(request.body as Schemas["UpdateOrgSettingsRequest"]),
          reception_note:
            (request.body.reception_note as string | undefined) ?? null,
        };

        return ok(state.settings);
      }),
    ],
  },
  {
    path: "/admin/org/members" as const,
    method: "get" as const,
    routes: [route(() => ok(state.members.map(memberItem)))],
  },
  {
    path: "/admin/org/members/:user_id" as const,
    method: "delete" as const,
    routes: [
      route((request) => {
        const userId = Number(request.params.user_id);
        const member = state.members.find((item) => item.user_id === userId);

        if (!member) {
          return notFound("Сотрудник не найден");
        }

        if (!canRemove(ACTOR_ROLE, member.role)) {
          return forbidden("Этого сотрудника исключить нельзя");
        }

        state.members = state.members.filter((item) => item !== member);

        return ok({ ok: true });
      }),
    ],
  },
  {
    path: "/admin/org/invites" as const,
    method: "get" as const,
    routes: [
      route(() =>
        ok(
          [...state.invites]
            .sort((a, b) => b.created_at.localeCompare(a.created_at))
            .map(inviteItem),
        ),
      ),
    ],
  },
  {
    path: "/admin/org/invites" as const,
    method: "post" as const,
    routes: [
      route((request) => {
        const { role } = request.body;
        const expiresIn = request.body.expires_in_hours ?? 72;
        const maxActivations = request.body.max_activations ?? 1;

        if (
          !isRole(role) ||
          !isInteger(expiresIn) ||
          !isInteger(maxActivations)
        ) {
          return badRequest("Некорректные поля приглашения");
        }

        if (!canInvite(ACTOR_ROLE, role)) {
          return forbidden("Эту роль выдать нельзя");
        }

        if (expiresIn <= 0) {
          return badRequest("Срок жизни кода - больше нуля часов");
        }

        if (maxActivations <= 0) {
          return badRequest("Число активаций - больше нуля");
        }

        const invite: MockInvite = {
          code: inviteCode(),
          role,
          created_at: new Date().toISOString(),
          expires_at: hours(expiresIn),
          max_activations: maxActivations,
          activations_used: 0,
          revoked_at: null,
        };
        state.invites = [...state.invites, invite];

        return ok(inviteItem(invite));
      }),
    ],
  },
  {
    path: "/admin/org/invites/:code" as const,
    method: "delete" as const,
    routes: [
      route((request) => {
        const invite = state.invites.find(
          (item) => item.code === request.params.code,
        );

        if (!invite) {
          return notFound("Приглашение не найдено");
        }

        invite.revoked_at = new Date().toISOString();

        return ok({ ok: true });
      }),
    ],
  },
];
