import type { components } from "../schema/generated";

import {
  badRequest,
  demoLocked,
  endpoint,
  forbidden,
  notFound,
  ok,
} from "./reply";
import { hours, user, ZHILSERVIS } from "./state";

type Schemas = components["schemas"];

type OrgRole = Schemas["OrgRole"];

type MockMember = Omit<Schemas["OrgMemberItem"], "can_remove">;

type MockInvite = Omit<Schemas["OrgInviteItem"], "deeplink">;

const canRemove = (role: OrgRole) => role !== "creator" && role !== "admin";

const isRole = (value: unknown): value is OrgRole =>
  ["creator", "admin", "employee", "executor"].includes(value as OrgRole);

const inviteCode = () =>
  btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(8))))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replace(/=+$/, "");

const member = (
  user_id: number,
  name: string,
  username: string | null,
  role: OrgRole,
  created_at: string,
): MockMember => ({ user_id, name, username, role, created_at });

const invite = (
  code: string,
  role: OrgRole,
  created_at: string,
  expires_at: string,
  max_activations: number,
  activations_used = 0,
  revoked_at: string | null = null,
): MockInvite => ({
  code,
  role,
  created_at,
  expires_at,
  max_activations,
  activations_used,
  revoked_at,
});

const state = {
  settings: {
    meter_window_day_from: 15,
    meter_window_day_to: 25,
    meter_window_always_open: false,
    group_threshold: 3,
    group_window_hours: 24,
    phone: "+7 843 200-10-10",
    reception_note: "Пн-чт 9:00-18:00, пт до 17:00",
    emergency_phone: "+7 843 200-10-11",
    email: "priem@zhilservis-kzn.ru",
    site: "https://zhilservis-kzn.ru",
  } as Schemas["OrgSettingsResponse"],
  members: [
    member(
      41,
      "Марина Ковалёва",
      "kovaleva",
      "creator",
      "2026-06-01T09:00:00Z",
    ),
    member(user.user_id, user.name, null, "admin", "2026-06-03T10:30:00Z"),
    member(42, "Олег Петров", "opetrov", "admin", "2026-06-10T08:15:00Z"),
    member(
      43,
      "Светлана Иванова",
      "ivanova_s",
      "employee",
      "2026-07-02T12:00:00Z",
    ),
    member(
      44,
      "Константин Александрович Верещагин-Нестеров",
      null,
      "employee",
      "2026-08-19T07:45:00Z",
    ),
    member(
      45,
      "Рустам Галиев",
      "galiev_master",
      "executor",
      "2026-07-15T06:20:00Z",
    ),
    member(46, "Игорь Никитин", null, "executor", "2026-09-01T06:00:00Z"),
  ],
  invites: [
    invite("q3Zr8sKd1Aw", "employee", hours(-2), hours(70), 1),
    invite("Xk2-Pm9_vTe", "executor", hours(-30), hours(138), 5, 2),
    invite("Lb7nQw0rYc4", "employee", hours(-50), hours(22), 1, 1),
    invite(
      "Hs5_uJ1oEe8",
      "executor",
      hours(-120),
      hours(48),
      3,
      0,
      hours(-100),
    ),
    invite("Rt4mZa9-Ngk", "employee", hours(-400), hours(-328), 1),
  ],
  categoryExecutors: [] as Schemas["CategoryExecutorItem"][],
};

const memberItem = (item: MockMember): Schemas["OrgMemberItem"] => ({
  ...item,
  can_remove: !ZHILSERVIS.is_demo && canRemove(item.role),
});

const inviteItem = (item: MockInvite): Schemas["OrgInviteItem"] => ({
  ...item,
  deeplink: `https://max.ru/zheka_bot?start=inv_${item.code}`,
});

const isInteger = (value: unknown): value is number =>
  typeof value === "number" && Number.isInteger(value);

const withScheme = (site: string | undefined): string | null => {
  const value = site?.trim();

  if (!value) {
    return null;
  }

  return /^https?:\/\//i.test(value) ? value : `https://${value}`;
};

const host = (site: string) =>
  site.replace(/^https?:\/\//i, "").split(/[/?#]/)[0];

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
    !(body.reception_note == null || typeof body.reception_note === "string") ||
    !(
      body.emergency_phone == null || typeof body.emergency_phone === "string"
    ) ||
    !(body.email == null || typeof body.email === "string") ||
    !(body.site == null || typeof body.site === "string")
  ) {
    return "Некорректные поля настроек";
  }

  const email = (body.email as string | null)?.trim();

  if (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    return "Почта УК указана неверно";
  }

  const site = withScheme((body.site as string | null) ?? undefined);

  if (
    site &&
    !/^[\p{L}\p{N}\p{M}_-]+(\.[\p{L}\p{N}\p{M}_-]+)+\.?$/u.test(host(site))
  ) {
    return "Сайт УК указан неверно: нужен адрес вида uk-primer.ru";
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
  endpoint("get", "/admin/org", () =>
    ok({
      id: 1,
      name: "ООО «Жилсервис»",
      inn: "1655123450",
      license_no: "016-000123",
      phone: state.settings.phone,
      address: "Казань, ул. Баумана, 10",
      reception_note: state.settings.reception_note,
      registered_at: "2026-06-01T09:00:00Z",
      is_demo: ZHILSERVIS.is_demo,
      houses_count: 3,
      members_count: state.members.length,
    } satisfies Schemas["OrgCard"]),
  ),
  endpoint("get", "/admin/org/settings", () => ok(state.settings)),
  endpoint("put", "/admin/org/settings", (request) => {
    if (ZHILSERVIS.is_demo) {
      return demoLocked;
    }

    const error = settingsError(request.body);

    if (error) {
      return badRequest(error);
    }

    state.settings = {
      ...(request.body as Schemas["UpdateOrgSettingsRequest"]),
      reception_note:
        (request.body.reception_note as string | undefined) ?? null,
      emergency_phone:
        (request.body.emergency_phone as string | undefined)?.trim() || null,
      email:
        (request.body.email as string | undefined)?.trim().toLowerCase() ||
        null,
      site: withScheme(request.body.site as string | undefined),
    };

    return ok(state.settings);
  }),
  endpoint("get", "/admin/org/members", () =>
    ok(state.members.map(memberItem)),
  ),
  endpoint("delete", "/admin/org/members/:user_id", (request) => {
    if (ZHILSERVIS.is_demo) {
      return demoLocked;
    }

    const userId = Number(request.params.user_id);
    const found = state.members.find((item) => item.user_id === userId);

    if (!found) {
      return notFound("Сотрудник не найден");
    }

    if (!canRemove(found.role)) {
      return forbidden("Этого сотрудника исключить нельзя");
    }

    state.members = state.members.filter((item) => item !== found);

    return ok({ ok: true });
  }),
  endpoint("get", "/admin/org/invites", () =>
    ok(
      [...state.invites]
        .sort((a, b) => b.created_at.localeCompare(a.created_at))
        .map(inviteItem),
    ),
  ),
  endpoint("post", "/admin/org/invites", (request) => {
    const { role } = request.body;
    const expiresIn = request.body.expires_in_hours ?? 72;
    const maxActivations = request.body.max_activations ?? 1;

    if (!isRole(role) || !isInteger(expiresIn) || !isInteger(maxActivations)) {
      return badRequest("Некорректные поля приглашения");
    }

    if (role !== "employee" && role !== "executor") {
      return forbidden("Эту роль выдать нельзя");
    }

    if (expiresIn <= 0) {
      return badRequest("Срок жизни кода - больше нуля часов");
    }

    if (maxActivations <= 0) {
      return badRequest("Число активаций - больше нуля");
    }

    const created = invite(
      inviteCode(),
      role,
      new Date().toISOString(),
      hours(expiresIn),
      maxActivations,
    );
    state.invites.push(created);

    return ok(inviteItem(created));
  }),
  endpoint("delete", "/admin/org/invites/:code", (request) => {
    const found = state.invites.find(
      (item) => item.code === request.params.code,
    );

    if (!found) {
      return notFound("Приглашение не найдено");
    }

    found.revoked_at = new Date().toISOString();

    return ok({ ok: true });
  }),
  endpoint("get", "/admin/org/category-executors", () =>
    ok(state.categoryExecutors),
  ),
  endpoint("put", "/admin/org/category-executors", (request) => {
    if (ZHILSERVIS.is_demo) {
      return demoLocked;
    }

    const body = request.body as Schemas["SetCategoryExecutorRequest"];
    const others = state.categoryExecutors.filter(
      (item) => item.category !== body.category,
    );

    state.categoryExecutors =
      body.executor_user_id == null
        ? others
        : [
            ...others,
            {
              category: body.category,
              executor_user_id: body.executor_user_id,
            },
          ];

    return ok(state.categoryExecutors);
  }),
];
